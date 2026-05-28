"""Tests for config loading."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import gir.config as config_mod

if TYPE_CHECKING:
    from pathlib import Path


class TestConfigLoad:
    def test_load_example(self, example_config: config_mod.Config) -> None:
        assert example_config.default == "abstain"
        assert len(example_config.block_bash) > 0
        assert len(example_config.block_write) > 0
        assert len(example_config.ask_bash) > 0

    def test_load_missing_file(self, tmp_path: Path) -> None:
        cfg = config_mod.Config.load(tmp_path / "nonexistent.json")
        assert cfg.default == "abstain"
        assert cfg.block_bash == []

    def test_load_malformed_json(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{invalid json")
        cfg = config_mod.Config.load(bad_file)
        assert cfg.default == "abstain"

    def test_load_empty_config(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty.json"
        empty.write_text("{}")
        cfg = config_mod.Config.load(empty)
        assert cfg.default == "abstain"
        assert cfg.block_bash == []

    def test_block_bash_patterns(self, example_config: config_mod.Config) -> None:
        patterns = [r.pattern.pattern for r in example_config.block_bash]
        assert any("rm" in p and "/" in p for p in patterns)
        assert any("rm" in p and "~" in p for p in patterns)

    def test_block_write_patterns(self, example_config: config_mod.Config) -> None:
        patterns = [r.pattern.pattern for r in example_config.block_write]
        assert any("env" in p for p in patterns)

    def test_ask_bash_patterns(self, example_config: config_mod.Config) -> None:
        assert len(example_config.ask_bash) > 0
        reasons = [r.reason for r in example_config.ask_bash]
        assert any("production" in r.lower() for r in reasons)

    def test_contexts_loaded(self, example_config: config_mod.Config) -> None:
        assert "production" in example_config.contexts
        assert "dev" in example_config.contexts
        assert example_config.contexts["production"].default == "ask"
        assert example_config.contexts["dev"].default == "allow"

    def test_custom_log_file(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(json.dumps({"log_file": "/tmp/custom.log"}))
        cfg = config_mod.Config.load(cfg_file)
        assert cfg.log_file == "/tmp/custom.log"


class TestRule:
    def test_from_dict_with_reason(self) -> None:
        rule = config_mod.Rule.from_dict({"pattern": "rm -rf", "reason": "dangerous"})
        assert rule.pattern.search("rm -rf /")
        assert rule.reason == "dangerous"

    def test_from_dict_without_reason(self) -> None:
        rule = config_mod.Rule.from_dict({"pattern": "rm -rf"})
        assert rule.reason == ""

    def test_case_insensitive(self) -> None:
        rule = config_mod.Rule.from_dict({"pattern": "DROP TABLE"})
        assert rule.pattern.search("drop table users")
