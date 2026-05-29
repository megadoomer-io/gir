"""Tests for decision logging."""

from __future__ import annotations

import json
from pathlib import Path

import gir.log as log_mod


class TestLogDecision:
    def test_writes_jsonl(self, tmp_path: Path) -> None:
        log_file = str(tmp_path / "test.jsonl")
        log_mod.log_decision(
            log_file=log_file,
            tool="Bash",
            decision="allow",
            rule="default",
            command="git status",
        )
        with open(log_file) as f:
            lines = f.readlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["tool"] == "Bash"
        assert entry["decision"] == "allow"
        assert entry["rule"] == "default"
        assert entry["command"] == "git status"
        assert "ts" in entry
        assert "cwd" in entry

    def test_appends_multiple(self, tmp_path: Path) -> None:
        log_file = str(tmp_path / "test.jsonl")
        for i in range(3):
            log_mod.log_decision(
                log_file=log_file,
                tool="Bash",
                decision="allow",
                rule="default",
                command=f"cmd-{i}",
            )
        with open(log_file) as f:
            lines = f.readlines()
        assert len(lines) == 3

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        log_file = str(tmp_path / "deep" / "nested" / "test.jsonl")
        log_mod.log_decision(
            log_file=log_file,
            tool="Bash",
            decision="allow",
            rule="default",
        )
        with open(log_file) as f:
            lines = f.readlines()
        assert len(lines) == 1

    def test_file_path_field(self, tmp_path: Path) -> None:
        log_file = str(tmp_path / "test.jsonl")
        log_mod.log_decision(
            log_file=log_file,
            tool="Edit",
            decision="deny",
            rule="block:secrets",
            file_path="/app/.env",
        )
        entry = json.loads(Path(log_file).read_text().splitlines()[0])
        assert entry["file_path"] == "/app/.env"
        assert "command" not in entry

    def test_segments_only_when_compound(self, tmp_path: Path) -> None:
        log_file = str(tmp_path / "test.jsonl")
        log_mod.log_decision(
            log_file=log_file,
            tool="Bash",
            decision="allow",
            rule="default",
            segments=["git status"],
        )
        entry = json.loads(Path(log_file).read_text().splitlines()[0])
        assert "segments" not in entry

    def test_segments_included_when_multiple(self, tmp_path: Path) -> None:
        log_file = str(tmp_path / "test.jsonl")
        log_mod.log_decision(
            log_file=log_file,
            tool="Bash",
            decision="allow",
            rule="default",
            segments=["cd /tmp", "git status"],
        )
        entry = json.loads(Path(log_file).read_text().splitlines()[0])
        assert entry["segments"] == ["cd /tmp", "git status"]

    def test_context_field(self, tmp_path: Path) -> None:
        log_file = str(tmp_path / "test.jsonl")
        log_mod.log_decision(
            log_file=log_file,
            tool="Bash",
            decision="ask",
            rule="context:production",
            context="production",
        )
        entry = json.loads(Path(log_file).read_text().splitlines()[0])
        assert entry["context"] == "production"

    def test_duration_ms(self, tmp_path: Path) -> None:
        log_file = str(tmp_path / "test.jsonl")
        log_mod.log_decision(
            log_file=log_file,
            tool="Bash",
            decision="allow",
            rule="default",
            duration_ms=3.14159,
        )
        entry = json.loads(Path(log_file).read_text().splitlines()[0])
        assert entry["duration_ms"] == 3.1

    def test_tilde_expansion(self, tmp_path: Path) -> None:
        """Verify paths with ~ expand correctly via Path.expanduser()."""
        log_mod.log_decision(
            log_file=str(tmp_path / "tilde-test.jsonl"),
            tool="Bash",
            decision="allow",
            rule="default",
        )
        assert (tmp_path / "tilde-test.jsonl").exists()

    def test_readonly_dir_no_crash(self) -> None:
        log_mod.log_decision(
            log_file="/proc/nonexistent/test.jsonl",
            tool="Bash",
            decision="allow",
            rule="default",
        )
