"""Tests for the approval tally tracker."""

from __future__ import annotations

from pathlib import Path

import gir.tally as tally_mod


class TestTallyStore:
    def test_record_new_entry(self, tmp_path: Path) -> None:
        store = tally_mod.TallyStore()
        entry = store.record(
            action_type="git_remote_write",
            skeleton="^gh\\s+pr\\s+review\\b",
            command="gh pr review 123 --approve",
            project="my-project",
            config_dir=tmp_path,
        )
        assert entry.count == 1
        assert entry.action_type == "git_remote_write"
        assert entry.skeleton == "^gh\\s+pr\\s+review\\b"
        assert entry.last_command == "gh pr review 123 --approve"

    def test_record_increments_count(self, tmp_path: Path) -> None:
        store = tally_mod.TallyStore()
        store.record(
            action_type="filesystem_delete",
            skeleton="^rm\\b",
            command="rm -rf __pycache__",
            project="test-proj",
            config_dir=tmp_path,
        )
        entry = store.record(
            action_type="filesystem_delete",
            skeleton="^rm\\b",
            command="rm -rf .mypy_cache",
            project="test-proj",
            config_dir=tmp_path,
        )
        assert entry.count == 2
        assert entry.last_command == "rm -rf .mypy_cache"

    def test_record_different_skeletons_separate(self, tmp_path: Path) -> None:
        store = tally_mod.TallyStore()
        store.record(
            action_type="filesystem_delete",
            skeleton="^rm\\b",
            project="proj",
            config_dir=tmp_path,
        )
        store.record(
            action_type="filesystem_write",
            skeleton="^touch\\b",
            project="proj",
            config_dir=tmp_path,
        )
        loaded = tally_mod.TallyStore.load("proj", config_dir=tmp_path)
        assert len(loaded.entries) == 2

    def test_load_nonexistent_returns_empty(self, tmp_path: Path) -> None:
        store = tally_mod.TallyStore.load("no-such-project", config_dir=tmp_path)
        assert store.entries == []

    def test_persistence_across_loads(self, tmp_path: Path) -> None:
        store = tally_mod.TallyStore()
        store.record(
            action_type="git_remote_write",
            skeleton="^git\\s+push\\b",
            project="persist-test",
            config_dir=tmp_path,
        )
        loaded = tally_mod.TallyStore.load("persist-test", config_dir=tmp_path)
        assert len(loaded.entries) == 1
        assert loaded.entries[0].action_type == "git_remote_write"
        assert loaded.entries[0].count == 1

    def test_get_count(self, tmp_path: Path) -> None:
        store = tally_mod.TallyStore()
        store.record(
            action_type="filesystem_delete",
            skeleton="^rm\\b",
            project="count-test",
            config_dir=tmp_path,
        )
        store.record(
            action_type="filesystem_delete",
            skeleton="^rm\\b",
            project="count-test",
            config_dir=tmp_path,
        )
        loaded = tally_mod.TallyStore.load("count-test", config_dir=tmp_path)
        assert loaded.get_count("filesystem_delete", "^rm\\b") == 2
        assert loaded.get_count("filesystem_delete", "^other\\b") == 0

    def test_projects_isolated(self, tmp_path: Path) -> None:
        store = tally_mod.TallyStore()
        store.record(
            action_type="filesystem_delete",
            skeleton="^rm\\b",
            project="project-a",
            config_dir=tmp_path,
        )
        store.record(
            action_type="filesystem_delete",
            skeleton="^rm\\b",
            project="project-b",
            config_dir=tmp_path,
        )
        a = tally_mod.TallyStore.load("project-a", config_dir=tmp_path)
        b = tally_mod.TallyStore.load("project-b", config_dir=tmp_path)
        assert a.get_count("filesystem_delete", "^rm\\b") == 1
        assert b.get_count("filesystem_delete", "^rm\\b") == 1


class TestProjectSlug:
    def test_returns_directory_name_outside_git(self, tmp_path: Path) -> None:
        slug = tally_mod.project_slug(str(tmp_path))
        assert slug == tmp_path.name

    def test_returns_repo_name_in_git(self) -> None:
        slug = tally_mod.project_slug("/Users/mike.dougherty/src/github.com/megadoomer-io/gir")
        assert slug == "gir"
