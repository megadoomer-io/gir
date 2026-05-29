#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""GIR v2 PostToolUse observer: learns from nah's ask decisions.

GIR v2 is a learning companion for nah (https://github.com/manuelschipper/nah).
nah handles PreToolUse classification and guardrails. GIR watches PostToolUse
events, correlates with nah's decision log, and tracks approval patterns so it
can suggest nah config changes that reduce future prompts.

Flow:
    1. nah's PreToolUse hook classifies a command as "ask"
    2. User gets prompted by Claude Code, approves the command
    3. Command executes successfully
    4. This PostToolUse hook fires
    5. GIR reads nah's log to find the matching "ask" decision
    6. GIR extracts the action_type and generalizes via skeleton extraction
    7. GIR tallies the (action_type, skeleton) pair per-project
    8. After threshold approvals, GIR suggests a nah config change

Register in ~/.claude/settings.json:
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "",
      "hooks": [{"type": "command", "command": "/path/to/gir/gir-post-hook-v2.py", "timeout": 5000}]
    }]
  }
}
"""

from __future__ import annotations

import json
import os
import sys
import time

_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_REPO_ROOT, "src"))

import gir.log as log_mod  # noqa: E402
import gir.skeleton as skeleton_mod  # noqa: E402
import gir.tally as tally_mod  # noqa: E402

SUGGESTION_THRESHOLD = 3


def _nah_log_path() -> str:
    xdg = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return os.path.join(xdg, "nah", "nah.log")


def _gir_log_path() -> str:
    xdg = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return os.path.join(xdg, "gir", "decisions.jsonl")


def _find_nah_ask(tool_name: str, tool_input: dict[str, object], log_path: str) -> dict[str, object] | None:
    """Find a matching nah 'ask' decision in nah's JSONL log.

    Searches the last 100 lines for a PreToolUse ask decision matching
    this tool call. Returns the full log entry dict if found.

    nah's ``input`` field is the full command text (possibly truncated at ~200
    chars and possibly prefixed with comments). Matching checks whether either
    string contains a significant prefix of the other.
    """
    if not os.path.exists(log_path):
        return None

    command = str(tool_input.get("command", "")) if tool_name == "Bash" else None
    file_path = str(tool_input.get("file_path", "")) if tool_name in ("Edit", "Write") else None

    if not command and not file_path:
        return None

    try:
        with open(log_path) as f:
            lines = f.readlines()
    except OSError:
        return None

    for line in reversed(lines[-100:]):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        if entry.get("decision") != "ask":
            continue
        if entry.get("tool") != tool_name:
            continue

        entry_input = str(entry.get("input", ""))

        if command:
            input_lines = entry_input.split("\n")
            bare_input = "\n".join(
                ln for ln in input_lines if not ln.lstrip().startswith("#")
            ).strip()
            cmd_trimmed = command.strip()
            if bare_input.startswith(cmd_trimmed[:60]) or cmd_trimmed.startswith(bare_input[:60]):
                return dict(entry)

        if file_path and (entry_input.strip() == file_path or file_path in entry_input):
            return dict(entry)

    return None


def _format_suggestion(action_type: str, count: int, project: str) -> str:
    """Format a nah config suggestion for additionalContext."""
    if action_type and action_type != "unknown":
        return (
            f"GIR: You've approved {count} '{action_type}' commands in '{project}'. "
            f"Run `nah allow {action_type} --project` to stop being asked, "
            f"or `nah allow {action_type}` for all projects."
        )
    return ""


def main() -> None:
    start = time.monotonic()

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    tool_name = str(payload.get("tool_name", ""))
    tool_input: dict[str, object] = payload.get("tool_input", {})
    cwd = str(payload.get("cwd", os.getcwd()))

    nah_entry = _find_nah_ask(tool_name, tool_input, _nah_log_path())
    if nah_entry is None:
        return

    action_type = str(nah_entry.get("action_type", "unknown"))
    project = tally_mod.project_slug(cwd)

    command = str(tool_input.get("command", "")) if tool_name == "Bash" else None
    file_path = str(tool_input.get("file_path", "")) if tool_name in ("Edit", "Write") else None

    value = command or file_path or ""
    if not value:
        return

    skel = skeleton_mod.extract_skeleton(command) if command else value

    print(
        f"[gir] nah asked about {tool_name} (action_type={action_type}), "
        f"skeleton='{skel}', project='{project}'",
        file=sys.stderr,
    )

    store = tally_mod.TallyStore()
    entry = store.record(
        action_type=action_type,
        skeleton=skel,
        command=value,
        project=project,
    )

    elapsed_ms = (time.monotonic() - start) * 1000
    log_mod.log_decision(
        log_file=_gir_log_path(),
        tool=tool_name,
        decision="learned",
        rule=f"nah-ask:{action_type}:{skel}",
        command=command,
        file_path=file_path,
        duration_ms=elapsed_ms,
    )

    if entry.count >= SUGGESTION_THRESHOLD:
        suggestion = _format_suggestion(action_type, entry.count, project)
        if suggestion:
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": suggestion,
                }
            }
            print(json.dumps(output))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[gir] post-hook-v2 error: {e}", file=sys.stderr)
