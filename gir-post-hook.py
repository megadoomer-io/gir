#!/usr/bin/env python3
"""GIR PostToolUse observer: records user-approved commands as learned patterns.

When GIR abstains on a command (ask-list), the built-in Claude Code prompt
fires. If the user approves and the command succeeds, this PostToolUse hook
records the pattern so GIR auto-allows it next time.

The correlation logic: GIR's PreToolUse decision log records "ask" decisions.
If PostToolUse fires for the same tool+command, the user approved it.
We generalize the command into a reusable pattern before storing.

Register in ~/.claude/settings.json alongside the PreToolUse hook:
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "",
      "hooks": [{"type": "command", "command": "/path/to/gir/gir-post-hook.py", "timeout": 5000}]
    }]
  }
}
"""

from __future__ import annotations

import json
import os
import re
import sys

_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_REPO_ROOT, "src"))

import gir.learned as learned_mod  # noqa: E402
import gir.log as log_mod  # noqa: E402


def _generalize_command(command: str) -> str:
    """Turn a specific command into a reusable pattern.

    Examples:
        "git push origin main" -> "git push origin main"  (kept specific -- ask-list item)
        "kubectl apply -f deploy.yaml --context=prod" -> "kubectl apply .* --context=prod"
        "npm test -- --watch" -> "npm test .*"
    """
    # For now, keep the command as-is as the pattern.
    # The user approved THIS command, so match it exactly.
    # Future: smarter generalization (collapse file paths, version numbers, etc.)
    return re.escape(command)


def _was_ask_decision(tool_name: str, command: str | None, file_path: str | None, log_file: str) -> bool:
    """Check if GIR's PreToolUse logged an 'ask' for this tool call.

    Reads the last 50 lines of the decision log looking for a matching ask.
    """
    from pathlib import Path

    resolved = Path(log_file).expanduser()
    if not resolved.exists():
        return False
    try:
        with open(resolved) as f:
            lines = f.readlines()
        for line in reversed(lines[-50:]):
            entry = json.loads(line)
            if entry.get("decision") != "ask":
                continue
            if entry.get("tool") != tool_name:
                continue
            if command and entry.get("command") == command:
                return True
            if file_path and entry.get("file_path") == file_path:
                return True
    except (json.JSONDecodeError, OSError):
        pass
    return False


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    tool_name = str(payload.get("tool_name", ""))
    tool_input: dict[str, object] = payload.get("tool_input", {})
    cwd = str(payload.get("cwd", os.getcwd()))

    command = str(tool_input.get("command", "")) if tool_name == "Bash" else None
    file_path = str(tool_input.get("file_path", "")) if tool_name in ("Edit", "Write") else None

    value = command or file_path
    if not value:
        return

    # Check if this was an ask decision from GIR's PreToolUse
    xdg = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    log_file = os.path.join(xdg, "gir", "decisions.jsonl")

    if not _was_ask_decision(tool_name, command, file_path, log_file):
        return

    # The user approved an ask-list item -- record it
    project = learned_mod._project_slug(cwd)
    pattern = _generalize_command(value)
    store = learned_mod.LearnedStore()

    print(f"[gir] learning: {tool_name} pattern '{value}' for project '{project}'", file=sys.stderr)

    store.record_approval(
        tool=tool_name,
        pattern=pattern,
        scope=project,
        source="user-approved",
    )

    log_mod.log_decision(
        log_file=log_file,
        tool=tool_name,
        decision="learned",
        rule=f"user-approved:{pattern}",
        command=command,
        file_path=file_path,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[gir] post-hook error: {e}", file=sys.stderr)
