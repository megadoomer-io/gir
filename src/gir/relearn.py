"""Re-learn existing patterns through improved skeleton extraction.

Processes all learned approvals and applies current skeleton logic to
produce broader, more reusable patterns. Old exact-match patterns are
preserved (additive, not destructive). New patterns are tagged with
source "re-learned" for auditability.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import gir.decompose as decompose_mod

if TYPE_CHECKING:
    from pathlib import Path
import gir.learned as learned_mod
import gir.skeleton as skeleton_mod


@dataclass
class RelearnStats:
    processed: int = 0
    new_skeletons: int = 0
    already_existed: int = 0
    skipped_file_paths: int = 0
    skipped_already_skeleton: int = 0
    skipped_non_bash: int = 0
    details: list[str] = field(default_factory=list)


def _unescape_re(pattern: str) -> str:
    """Reverse ``re.escape()`` to recover the original command string."""
    return re.sub(r"\\(.)", r"\1", pattern)


def _is_skeleton(pattern: str) -> bool:
    """Check if a pattern is already a skeleton (starts with ^, ends with \\b)."""
    return pattern.startswith("^") and pattern.endswith(r"\b")


def relearn(config_dir: Path | None = None) -> RelearnStats:
    """Re-process all learned approvals through current skeleton logic.

    For each Bash approval that uses an old exact-match pattern:
    1. Un-escape the pattern to recover the original command
    2. Decompose compound commands into segments
    3. Extract a skeleton for each segment
    4. Record as a new approval with source "re-learned"

    Non-Bash approvals and patterns that are already skeletons are skipped.
    """
    base = config_dir or learned_mod._config_dir()
    stats = RelearnStats()

    for path in sorted(base.glob("*.json")):
        scope = path.stem
        if scope == "_global":
            scope = "global"

        store = learned_mod.LearnedStore._load_file(path)
        for approval in store.approvals:
            stats.processed += 1

            if approval.tool not in ("Bash", "*"):
                stats.skipped_non_bash += 1
                continue

            if _is_skeleton(approval.pattern):
                stats.skipped_already_skeleton += 1
                continue

            command = _unescape_re(approval.pattern)
            segments = decompose_mod.decompose(command)

            for segment in segments:
                skel = skeleton_mod.extract_skeleton(segment)
                if _is_skeleton(skel):
                    existing = _find_existing(base, approval.tool, skel, scope)
                    if existing:
                        stats.already_existed += 1
                        stats.details.append(f"  exists: {skel} (scope={scope})")
                    else:
                        recorder = learned_mod.LearnedStore()
                        recorder.record_approval(
                            tool=approval.tool,
                            pattern=skel,
                            scope=scope,
                            source="re-learned",
                            config_dir=base,
                        )
                        stats.new_skeletons += 1
                        short = segment[:60] + "..." if len(segment) > 60 else segment
                        stats.details.append(f"  new: {short} → {skel} (scope={scope})")

    return stats


def _find_existing(config_dir: Path, tool: str, pattern: str, scope: str) -> bool:
    """Check if a pattern already exists in the store for the given scope."""
    filename = "_global.json" if scope == "global" else f"{scope}.json"
    path = config_dir / filename
    store = learned_mod.LearnedStore._load_file(path)
    return any(a.tool == tool and a.pattern == pattern for a in store.approvals)
