"""Tests for the relearn module."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

import gir.relearn as relearn_mod

if TYPE_CHECKING:
    from pathlib import Path


def _write_learned(tmp_path: Path, filename: str, approvals: list[dict[str, object]]) -> None:
    path = tmp_path / filename
    path.write_text(json.dumps({"approvals": approvals}))


class TestUnescapeRe:
    def test_simple_command(self) -> None:
        assert relearn_mod._unescape_re(re.escape("git push origin main")) == "git push origin main"

    def test_special_chars(self) -> None:
        assert relearn_mod._unescape_re(re.escape("kubectl apply -f deploy.yaml")) == "kubectl apply -f deploy.yaml"

    def test_dots_and_dashes(self) -> None:
        assert relearn_mod._unescape_re(re.escape("/path/to/file-name.py")) == "/path/to/file-name.py"

    def test_dollar_and_parens(self) -> None:
        assert relearn_mod._unescape_re(re.escape("echo $(date)")) == "echo $(date)"

    def test_compound_command(self) -> None:
        original = "cd ~/project && git status"
        assert relearn_mod._unescape_re(re.escape(original)) == original

    def test_roundtrip_various(self) -> None:
        commands = [
            "git log --oneline -10",
            "FOO=bar make test",
            "grep -rn 'pattern' src/",
            'echo "hello world"',
            "kubectl get pods -n kube-system --context=prod",
        ]
        for cmd in commands:
            assert relearn_mod._unescape_re(re.escape(cmd)) == cmd


class TestIsSkeleton:
    def test_skeleton_pattern(self) -> None:
        assert relearn_mod._is_skeleton(r"^git\s+commit\b")

    def test_skeleton_with_multiple_parts(self) -> None:
        assert relearn_mod._is_skeleton(r"^kubectl\s+get\s+pods\b")

    def test_exact_match_pattern(self) -> None:
        assert not relearn_mod._is_skeleton(re.escape("git push origin main"))

    def test_empty_string(self) -> None:
        assert not relearn_mod._is_skeleton("")

    def test_partial_skeleton_no_anchor(self) -> None:
        assert not relearn_mod._is_skeleton(r"git\s+commit\b")

    def test_partial_skeleton_no_boundary(self) -> None:
        assert not relearn_mod._is_skeleton(r"^git\s+commit")


class TestRelearn:
    def test_converts_exact_to_skeleton(self, tmp_path: Path) -> None:
        _write_learned(tmp_path, "test-project.json", [
            {"tool": "Bash", "pattern": re.escape("git push origin main"), "scope": "test-project",
             "source": "user-approved", "count": 1},
        ])
        stats = relearn_mod.relearn(config_dir=tmp_path)
        assert stats.new_skeletons >= 1

        data = json.loads((tmp_path / "test-project.json").read_text())
        patterns = [a["pattern"] for a in data["approvals"]]
        assert r"^git\s+push\b" in patterns

    def test_re_learned_source_tag(self, tmp_path: Path) -> None:
        _write_learned(tmp_path, "test-project.json", [
            {"tool": "Bash", "pattern": re.escape("git status"), "scope": "test-project",
             "source": "user-approved", "count": 1},
        ])
        relearn_mod.relearn(config_dir=tmp_path)

        data = json.loads((tmp_path / "test-project.json").read_text())
        re_learned = [a for a in data["approvals"] if a["source"] == "re-learned"]
        assert len(re_learned) == 1
        assert re_learned[0]["pattern"] == r"^git\s+status\b"

    def test_preserves_original_pattern(self, tmp_path: Path) -> None:
        original_pattern = re.escape("git push origin main")
        _write_learned(tmp_path, "test-project.json", [
            {"tool": "Bash", "pattern": original_pattern, "scope": "test-project",
             "source": "user-approved", "count": 3},
        ])
        relearn_mod.relearn(config_dir=tmp_path)

        data = json.loads((tmp_path / "test-project.json").read_text())
        original = [a for a in data["approvals"] if a["pattern"] == original_pattern]
        assert len(original) == 1
        assert original[0]["count"] == 3

    def test_skips_already_skeleton(self, tmp_path: Path) -> None:
        _write_learned(tmp_path, "test-project.json", [
            {"tool": "Bash", "pattern": r"^git\s+commit\b", "scope": "test-project",
             "source": "user-approved", "count": 5},
        ])
        stats = relearn_mod.relearn(config_dir=tmp_path)
        assert stats.skipped_already_skeleton == 1
        assert stats.new_skeletons == 0

    def test_skips_non_bash(self, tmp_path: Path) -> None:
        _write_learned(tmp_path, "test-project.json", [
            {"tool": "Edit", "pattern": re.escape("/path/to/file.py"), "scope": "test-project",
             "source": "user-approved", "count": 1},
        ])
        stats = relearn_mod.relearn(config_dir=tmp_path)
        assert stats.skipped_non_bash == 1
        assert stats.new_skeletons == 0

    def test_deduplicates_existing_skeleton(self, tmp_path: Path) -> None:
        _write_learned(tmp_path, "test-project.json", [
            {"tool": "Bash", "pattern": re.escape("git push origin main"), "scope": "test-project",
             "source": "user-approved", "count": 1},
            {"tool": "Bash", "pattern": r"^git\s+push\b", "scope": "test-project",
             "source": "user-approved", "count": 2},
        ])
        stats = relearn_mod.relearn(config_dir=tmp_path)
        assert stats.already_existed == 1
        assert stats.new_skeletons == 0

    def test_compound_command_produces_multiple_skeletons(self, tmp_path: Path) -> None:
        _write_learned(tmp_path, "test-project.json", [
            {"tool": "Bash", "pattern": re.escape("cd ~/project && git add . && git commit -m 'msg'"),
             "scope": "test-project", "source": "user-approved", "count": 1},
        ])
        stats = relearn_mod.relearn(config_dir=tmp_path)
        assert stats.new_skeletons == 3

        data = json.loads((tmp_path / "test-project.json").read_text())
        patterns = [a["pattern"] for a in data["approvals"]]
        assert r"^cd\b" in patterns
        assert r"^git\s+add\b" in patterns
        assert r"^git\s+commit\b" in patterns

    def test_processes_multiple_scopes(self, tmp_path: Path) -> None:
        _write_learned(tmp_path, "project-a.json", [
            {"tool": "Bash", "pattern": re.escape("npm test"), "scope": "project-a",
             "source": "user-approved", "count": 1},
        ])
        _write_learned(tmp_path, "project-b.json", [
            {"tool": "Bash", "pattern": re.escape("cargo build --release"), "scope": "project-b",
             "source": "user-approved", "count": 1},
        ])
        stats = relearn_mod.relearn(config_dir=tmp_path)
        assert stats.new_skeletons == 2

        data_a = json.loads((tmp_path / "project-a.json").read_text())
        assert any(a["pattern"] == r"^npm\s+test\b" for a in data_a["approvals"])

        data_b = json.loads((tmp_path / "project-b.json").read_text())
        assert any(a["pattern"] == r"^cargo\s+build\b" for a in data_b["approvals"])

    def test_idempotent(self, tmp_path: Path) -> None:
        _write_learned(tmp_path, "test-project.json", [
            {"tool": "Bash", "pattern": re.escape("git push origin main"), "scope": "test-project",
             "source": "user-approved", "count": 1},
        ])

        stats1 = relearn_mod.relearn(config_dir=tmp_path)
        assert stats1.new_skeletons == 1

        stats2 = relearn_mod.relearn(config_dir=tmp_path)
        assert stats2.new_skeletons == 0
        assert stats2.already_existed == 1

    def test_global_scope(self, tmp_path: Path) -> None:
        _write_learned(tmp_path, "_global.json", [
            {"tool": "Bash", "pattern": re.escape("docker ps"), "scope": "global",
             "source": "user-approved", "count": 1},
        ])
        stats = relearn_mod.relearn(config_dir=tmp_path)
        assert stats.new_skeletons == 1

        data = json.loads((tmp_path / "_global.json").read_text())
        re_learned = [a for a in data["approvals"] if a["source"] == "re-learned"]
        assert len(re_learned) == 1
        assert re_learned[0]["scope"] == "global"

    def test_empty_dir(self, tmp_path: Path) -> None:
        stats = relearn_mod.relearn(config_dir=tmp_path)
        assert stats.processed == 0
        assert stats.new_skeletons == 0

    def test_wildcard_tool_skipped(self, tmp_path: Path) -> None:
        _write_learned(tmp_path, "test-project.json", [
            {"tool": "Write", "pattern": re.escape("/some/file.txt"), "scope": "test-project",
             "source": "user-approved", "count": 1},
        ])
        stats = relearn_mod.relearn(config_dir=tmp_path)
        assert stats.skipped_non_bash == 1
