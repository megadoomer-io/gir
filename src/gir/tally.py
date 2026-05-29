"""Approval tally tracker for GIR v2.

Tracks how many times the user has approved commands of each
(action_type, skeleton) pair per project. When a tally crosses a
configurable threshold, GIR suggests a nah config change.

Storage layout:
    ~/.config/gir/tallies/
        <project-slug>.json  -- per-project approval tallies
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


def _config_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return Path(xdg) / "gir" / "tallies"


def project_slug(cwd: str | None = None) -> str:
    """Derive a project slug from the git repo root or directory name."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=2,
            cwd=cwd,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip()).name
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return Path(cwd or os.getcwd()).name


@dataclass
class TallyEntry:
    action_type: str
    skeleton: str
    count: int = 0
    last_command: str = ""


@dataclass
class TallyStore:
    entries: list[TallyEntry] = field(default_factory=list)

    @classmethod
    def load(cls, project: str, config_dir: Path | None = None) -> TallyStore:
        base = config_dir or _config_dir()
        path = base / f"{project}.json"
        if not path.exists():
            return cls()
        try:
            with open(path) as f:
                data = json.load(f)
            entries = [
                TallyEntry(
                    action_type=e["action_type"],
                    skeleton=e["skeleton"],
                    count=e.get("count", 0),
                    last_command=e.get("last_command", ""),
                )
                for e in data.get("entries", [])
            ]
            return cls(entries=entries)
        except (json.JSONDecodeError, KeyError, OSError) as err:
            print(f"[gir] tally load error: {err}", file=sys.stderr)
            return cls()

    def record(
        self,
        *,
        action_type: str,
        skeleton: str,
        command: str = "",
        project: str,
        config_dir: Path | None = None,
    ) -> TallyEntry:
        """Record an approval and return the updated entry."""
        base = config_dir or _config_dir()
        path = base / f"{project}.json"

        store = self.load(project, config_dir=config_dir)

        for entry in store.entries:
            if entry.action_type == action_type and entry.skeleton == skeleton:
                entry.count += 1
                entry.last_command = command
                store._save(path)
                return entry

        new_entry = TallyEntry(
            action_type=action_type,
            skeleton=skeleton,
            count=1,
            last_command=command,
        )
        store.entries.append(new_entry)
        store._save(path)
        return new_entry

    def get_count(self, action_type: str, skeleton: str) -> int:
        for entry in self.entries:
            if entry.action_type == action_type and entry.skeleton == skeleton:
                return entry.count
        return 0

    def _save(self, path: Path) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "entries": [
                    {
                        "action_type": e.action_type,
                        "skeleton": e.skeleton,
                        "count": e.count,
                        "last_command": e.last_command,
                    }
                    for e in self.entries
                ]
            }
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
                f.write("\n")
        except OSError as err:
            print(f"[gir] tally save error: {err}", file=sys.stderr)
