"""Learned approval storage for GIR permission firewall.

Tracks commands/patterns that the user has approved through the built-in
Claude Code permission prompt. When GIR abstains (ask-list), the built-in
prompt fires. If the user approves, the PostToolUse observer records the
approval here. On future invocations, GIR checks learned approvals before
the ask-list, allowing the command without prompting.

Storage layout:
    ~/.config/gir/learned/
        _global.json       -- approvals that apply everywhere
        <project-slug>.json -- project-scoped approvals
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


def _config_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return Path(xdg) / "gir" / "learned"


def _project_slug(cwd: str | None = None) -> str:
    """Derive a project slug from the git remote or directory name."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=2,
            cwd=cwd,
        )
        if result.returncode == 0:
            repo_root = result.stdout.strip()
            return Path(repo_root).name
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return Path(cwd or os.getcwd()).name


@dataclass
class LearnedApproval:
    tool: str
    pattern: str
    scope: str  # "global" or project slug
    source: str  # "user-approved", "manual"
    count: int = 0

    def matches(self, tool_name: str, value: str) -> bool:
        if self.tool != tool_name and self.tool != "*":
            return False
        try:
            return bool(re.search(self.pattern, value, re.IGNORECASE))
        except re.error:
            return False


@dataclass
class LearnedStore:
    approvals: list[LearnedApproval] = field(default_factory=list)
    _path: Path | None = None

    @classmethod
    def load(cls, project_slug: str | None = None, config_dir: Path | None = None) -> LearnedStore:
        base = config_dir or _config_dir()
        stores: list[LearnedStore] = []

        # Load global approvals
        global_store = cls._load_file(base / "_global.json")
        stores.append(global_store)

        # Load project-scoped approvals
        if project_slug:
            project_store = cls._load_file(base / f"{project_slug}.json")
            stores.append(project_store)

        merged = cls()
        for store in stores:
            merged.approvals.extend(store.approvals)
        return merged

    @classmethod
    def _load_file(cls, path: Path) -> LearnedStore:
        if not path.exists():
            store = cls()
            store._path = path
            return store
        try:
            with open(path) as f:
                data = json.load(f)
            approvals = [
                LearnedApproval(
                    tool=a["tool"],
                    pattern=a["pattern"],
                    scope=a.get("scope", "global"),
                    source=a.get("source", "user-approved"),
                    count=a.get("count", 0),
                )
                for a in data.get("approvals", [])
            ]
            store = cls(approvals=approvals)
            store._path = path
            return store
        except (json.JSONDecodeError, KeyError, OSError) as e:
            print(f"[gir] learned store error at {path}: {e}", file=sys.stderr)
            store = cls()
            store._path = path
            return store

    def check(self, tool_name: str, value: str) -> LearnedApproval | None:
        for approval in self.approvals:
            if approval.matches(tool_name, value):
                return approval
        return None

    def record_approval(
        self,
        *,
        tool: str,
        pattern: str,
        scope: str = "global",
        source: str = "user-approved",
        config_dir: Path | None = None,
    ) -> None:
        base = config_dir or _config_dir()
        filename = "_global.json" if scope == "global" else f"{scope}.json"
        path = base / filename

        existing = self._load_file(path)

        # Check for duplicate pattern
        for a in existing.approvals:
            if a.tool == tool and a.pattern == pattern:
                a.count += 1
                existing._save(path)
                return

        existing.approvals.append(
            LearnedApproval(tool=tool, pattern=pattern, scope=scope, source=source, count=1)
        )
        existing._save(path)

    def _save(self, path: Path) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "approvals": [
                    {
                        "tool": a.tool,
                        "pattern": a.pattern,
                        "scope": a.scope,
                        "source": a.source,
                        "count": a.count,
                    }
                    for a in self.approvals
                ]
            }
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
                f.write("\n")
        except OSError as e:
            print(f"[gir] learned store save error: {e}", file=sys.stderr)
