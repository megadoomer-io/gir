"""Decision logging for GIR permission firewall."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


def log_decision(
    *,
    log_file: str,
    tool: str,
    decision: str,
    rule: str,
    command: str | None = None,
    file_path: str | None = None,
    segments: list[str] | None = None,
    context: str | None = None,
    duration_ms: float | None = None,
) -> None:
    """Append a decision record to the JSON lines log file."""
    resolved = Path(log_file).expanduser()
    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return

    entry: dict[str, object] = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tool": tool,
        "decision": decision,
        "rule": rule,
        "cwd": os.getcwd(),
    }
    if command is not None:
        entry["command"] = command
    if file_path is not None:
        entry["file_path"] = file_path
    if segments is not None and len(segments) > 1:
        entry["segments"] = segments
    if context is not None:
        entry["context"] = context
    if duration_ms is not None:
        entry["duration_ms"] = round(duration_ms, 1)

    try:
        with open(resolved, "a") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")
    except OSError as e:
        print(f"[gir] log write error: {e}", file=sys.stderr)
