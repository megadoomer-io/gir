#!/usr/bin/env python3
"""GIR relearn: re-process learned patterns through improved skeleton extraction.

Applies current skeleton logic to all existing learned approvals, producing
broader patterns that match future command variants. Old patterns are preserved;
new patterns are tagged source="re-learned" for auditability.

Usage:
    python3 gir-relearn.py [--dry-run] [--verbose]
"""

from __future__ import annotations

import argparse
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_REPO_ROOT, "src"))

import gir.log as log_mod  # noqa: E402
import gir.relearn as relearn_mod  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-learn existing GIR patterns with improved skeleton extraction")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be learned without writing")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show each pattern transformation")
    args = parser.parse_args()

    if args.dry_run:
        print("[gir relearn] DRY RUN -- no changes will be written")
        print()

    # Run relearn in a temporary directory for dry-run, or real config for live
    if args.dry_run:
        import tempfile
        from pathlib import Path

        import gir.learned as learned_mod

        real_dir = learned_mod._config_dir()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            for f in real_dir.glob("*.json"):
                (tmp_dir / f.name).write_text(f.read_text())
            stats = relearn_mod.relearn(config_dir=tmp_dir)
    else:
        stats = relearn_mod.relearn()

    if args.verbose or args.dry_run:
        for detail in stats.details:
            print(f"[gir relearn] {detail}")
        print()

    print(f"[gir relearn] Processed {stats.processed} existing patterns")
    print(f"[gir relearn]   {stats.new_skeletons} new skeletons created")
    print(f"[gir relearn]   {stats.already_existed} already existed")
    print(f"[gir relearn]   {stats.skipped_already_skeleton} skipped (already skeleton)")
    print(f"[gir relearn]   {stats.skipped_non_bash} skipped (non-Bash tool)")
    print(f"[gir relearn]   {stats.skipped_file_paths} skipped (file path)")

    if not args.dry_run and stats.new_skeletons > 0:
        xdg = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
        log_file = os.path.join(xdg, "gir", "decisions.jsonl")
        log_mod.log_decision(
            log_file=log_file,
            tool="gir-relearn",
            decision="re-learned",
            rule=f"batch:{stats.new_skeletons}-new",
        )
        print(f"\n[gir relearn] Logged to {log_file}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[gir relearn] error: {e}", file=sys.stderr)
        sys.exit(1)
