#!/usr/bin/env python3
"""GIR: Guard, Inspect, Route -- Claude Code PreToolUse hook entry point.

Register in ~/.claude/settings.json:
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "",
      "hooks": [{"type": "command", "command": "/path/to/gir/gir-hook.py", "timeout": 5000}]
    }]
  }
}
"""

from __future__ import annotations

import json
import os
import sys
import time

# Add src/ to path so we can import gir without installing
_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_REPO_ROOT, "src"))

import gir.config as config_mod  # noqa: E402
import gir.hook as hook_mod  # noqa: E402
import gir.learned as learned_mod  # noqa: E402
import gir.log as log_mod  # noqa: E402


def main() -> None:
    start = time.monotonic()

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError) as e:
        print(f"[gir] stdin parse error: {e}", file=sys.stderr)
        return  # abstain on error -- fail-safe, falls through to built-in prompt

    tool_name = str(payload.get("tool_name", "unknown"))
    tool_input: dict[str, object] = payload.get("tool_input", {})

    cfg = config_mod.Config.load()
    cwd = str(payload.get("cwd", os.getcwd()))
    project = learned_mod._project_slug(cwd)
    learned = learned_mod.LearnedStore.load(project_slug=project)
    decision = hook_mod.evaluate(tool_name, tool_input, cfg, learned=learned)
    output = hook_mod.format_output(decision)

    elapsed_ms = (time.monotonic() - start) * 1000

    log_mod.log_decision(
        log_file=cfg.log_file,
        tool=tool_name,
        decision=decision.action,
        rule=decision.rule,
        command=str(tool_input.get("command", "")) if tool_name == "Bash" else None,
        file_path=str(tool_input.get("file_path", "")) if tool_name in ("Edit", "Write", "Read") else None,
        segments=decision.segments,
        context=decision.context,
        duration_ms=elapsed_ms,
    )

    if output is not None:
        print(json.dumps(output))
    # else: exit 0 with no output = hook abstains, falls through to built-in prompt


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[gir] unexpected error: {e}", file=sys.stderr)
        # abstain on error -- fail-safe, falls through to built-in prompt
