"""Tests for learned approval storage and integration."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import gir.config as config_mod

if TYPE_CHECKING:
    from pathlib import Path
import gir.hook as hook_mod
import gir.learned as learned_mod
import gir.skeleton as skeleton_mod
from tests.conftest import EXAMPLE_CONFIG


class TestLearnedStore:
    def test_load_empty_dir(self, tmp_path: Path) -> None:
        store = learned_mod.LearnedStore.load(config_dir=tmp_path)
        assert store.approvals == []

    def test_record_and_load(self, tmp_path: Path) -> None:
        store = learned_mod.LearnedStore()
        store.record_approval(
            tool="Bash",
            pattern="git push origin main",
            scope="my-project",
            config_dir=tmp_path,
        )
        loaded = learned_mod.LearnedStore.load(project_slug="my-project", config_dir=tmp_path)
        assert len(loaded.approvals) == 1
        assert loaded.approvals[0].tool == "Bash"
        assert loaded.approvals[0].pattern == "git push origin main"
        assert loaded.approvals[0].scope == "my-project"
        assert loaded.approvals[0].count == 1

    def test_duplicate_increments_count(self, tmp_path: Path) -> None:
        store = learned_mod.LearnedStore()
        for _ in range(3):
            store.record_approval(
                tool="Bash",
                pattern="git push origin main",
                scope="global",
                config_dir=tmp_path,
            )
        loaded = learned_mod.LearnedStore.load(config_dir=tmp_path)
        assert len(loaded.approvals) == 1
        assert loaded.approvals[0].count == 3

    def test_global_and_project_merge(self, tmp_path: Path) -> None:
        store = learned_mod.LearnedStore()
        store.record_approval(tool="Bash", pattern="npm test", scope="global", config_dir=tmp_path)
        store.record_approval(tool="Bash", pattern="make deploy", scope="my-project", config_dir=tmp_path)

        loaded = learned_mod.LearnedStore.load(project_slug="my-project", config_dir=tmp_path)
        assert len(loaded.approvals) == 2

    def test_project_scoped_not_visible_to_other_projects(self, tmp_path: Path) -> None:
        store = learned_mod.LearnedStore()
        store.record_approval(tool="Bash", pattern="make deploy", scope="project-a", config_dir=tmp_path)

        loaded = learned_mod.LearnedStore.load(project_slug="project-b", config_dir=tmp_path)
        assert len(loaded.approvals) == 0

    def test_global_visible_to_all_projects(self, tmp_path: Path) -> None:
        store = learned_mod.LearnedStore()
        store.record_approval(tool="Bash", pattern="npm test", scope="global", config_dir=tmp_path)

        loaded_a = learned_mod.LearnedStore.load(project_slug="project-a", config_dir=tmp_path)
        loaded_b = learned_mod.LearnedStore.load(project_slug="project-b", config_dir=tmp_path)
        assert len(loaded_a.approvals) == 1
        assert len(loaded_b.approvals) == 1


class TestLearnedApprovalMatching:
    def test_exact_match(self) -> None:
        approval = learned_mod.LearnedApproval(
            tool="Bash", pattern="git push origin main", scope="global", source="user-approved"
        )
        assert approval.matches("Bash", "git push origin main")
        assert not approval.matches("Bash", "git push origin develop")

    def test_regex_match(self) -> None:
        approval = learned_mod.LearnedApproval(
            tool="Bash", pattern="kubectl apply.*--context=prod", scope="global", source="user-approved"
        )
        assert approval.matches("Bash", "kubectl apply -f deploy.yaml --context=prod-apps")
        assert not approval.matches("Bash", "kubectl apply -f deploy.yaml --context=dev-apps")

    def test_tool_mismatch(self) -> None:
        approval = learned_mod.LearnedApproval(
            tool="Bash", pattern="git status", scope="global", source="user-approved"
        )
        assert not approval.matches("Edit", "git status")

    def test_wildcard_tool(self) -> None:
        approval = learned_mod.LearnedApproval(
            tool="*", pattern=".*\\.py$", scope="global", source="manual"
        )
        assert approval.matches("Edit", "src/main.py")
        assert approval.matches("Write", "tests/test_app.py")

    def test_case_insensitive(self) -> None:
        approval = learned_mod.LearnedApproval(
            tool="Bash", pattern="npm test", scope="global", source="user-approved"
        )
        assert approval.matches("Bash", "NPM TEST")


class TestLearnedIntegration:
    """Test that learned approvals override ask-list decisions."""

    def test_ask_without_learned(self) -> None:
        cfg = config_mod.Config.load(EXAMPLE_CONFIG)
        d = hook_mod.evaluate("Bash", {"command": "git push origin main"}, cfg, learned=None)
        assert d.action == "ask"

    def test_learned_overrides_ask(self) -> None:
        cfg = config_mod.Config.load(EXAMPLE_CONFIG)
        store = learned_mod.LearnedStore(
            approvals=[
                learned_mod.LearnedApproval(
                    tool="Bash",
                    pattern="git push origin main",
                    scope="test",
                    source="user-approved",
                )
            ]
        )
        d = hook_mod.evaluate("Bash", {"command": "git push origin main"}, cfg, learned=store)
        assert d.action == "allow"
        assert "learned" in d.rule

    def test_learned_does_not_override_block(self) -> None:
        """Block always wins over learned approvals."""
        cfg = config_mod.Config.load(EXAMPLE_CONFIG)
        store = learned_mod.LearnedStore(
            approvals=[
                learned_mod.LearnedApproval(
                    tool="Bash",
                    pattern="rm -rf /",
                    scope="test",
                    source="user-approved",
                )
            ]
        )
        d = hook_mod.evaluate("Bash", {"command": "rm -rf /"}, cfg, learned=store)
        assert d.action == "deny"

    def test_context_override_by_learned(self) -> None:
        cfg = config_mod.Config.load(EXAMPLE_CONFIG)
        store = learned_mod.LearnedStore(
            approvals=[
                learned_mod.LearnedApproval(
                    tool="Bash",
                    pattern="kubectl get pods --context=prod-apps",
                    scope="test",
                    source="user-approved",
                )
            ]
        )
        d = hook_mod.evaluate("Bash", {"command": "kubectl get pods --context=prod-apps"}, cfg, learned=store)
        assert d.action == "allow"
        assert "learned" in d.rule


class TestSkeletonBasedLearning:
    """Test that skeleton patterns work with the learned approval system."""

    def test_skeleton_matches_future_invocations(self) -> None:
        skeleton = skeleton_mod.extract_skeleton("git commit -m 'initial'")
        approval = learned_mod.LearnedApproval(tool="Bash", pattern=skeleton, scope="test", source="user-approved")
        assert approval.matches("Bash", "git commit -m 'different message'")
        assert approval.matches("Bash", "git commit --amend")
        assert approval.matches("Bash", "git commit")

    def test_skeleton_rejects_wrong_command(self) -> None:
        skeleton = skeleton_mod.extract_skeleton("git commit -m 'msg'")
        approval = learned_mod.LearnedApproval(tool="Bash", pattern=skeleton, scope="test", source="user-approved")
        assert not approval.matches("Bash", "git push origin main")
        assert not approval.matches("Bash", "kubectl get pods")

    def test_skeleton_word_boundary(self) -> None:
        skeleton = skeleton_mod.extract_skeleton("git commit -m 'msg'")
        approval = learned_mod.LearnedApproval(tool="Bash", pattern=skeleton, scope="test", source="user-approved")
        assert not approval.matches("Bash", "git committed")

    def test_old_exact_patterns_still_work(self) -> None:
        old_pattern = re.escape("git push origin main")
        approval = learned_mod.LearnedApproval(tool="Bash", pattern=old_pattern, scope="test", source="user-approved")
        assert approval.matches("Bash", "git push origin main")
        assert not approval.matches("Bash", "git push origin develop")

    def test_skeleton_overrides_ask_in_hook(self) -> None:
        cfg = config_mod.Config.load(EXAMPLE_CONFIG)
        skeleton = skeleton_mod.extract_skeleton("git push origin main")
        store = learned_mod.LearnedStore(
            approvals=[learned_mod.LearnedApproval(tool="Bash", pattern=skeleton, scope="test", source="user-approved")]
        )
        d = hook_mod.evaluate("Bash", {"command": "git push origin develop"}, cfg, learned=store)
        assert d.action == "allow"
        assert "learned" in d.rule

    def test_skeleton_stored_and_retrieved(self, tmp_path: Path) -> None:
        skeleton = skeleton_mod.extract_skeleton("uv run pytest -q --tb=short")
        store = learned_mod.LearnedStore()
        store.record_approval(tool="Bash", pattern=skeleton, scope="test-project", config_dir=tmp_path)

        loaded = learned_mod.LearnedStore.load(project_slug="test-project", config_dir=tmp_path)
        assert len(loaded.approvals) == 1
        result = loaded.check("Bash", "uv run pytest -v --cov=src")
        assert result is not None

    def test_kubectl_skeleton_resource_specific(self) -> None:
        skeleton = skeleton_mod.extract_skeleton("kubectl get pods -n default")
        store = learned_mod.LearnedStore(
            approvals=[learned_mod.LearnedApproval(tool="Bash", pattern=skeleton, scope="test", source="user-approved")]
        )
        assert store.check("Bash", "kubectl get pods -n kube-system") is not None
        assert store.check("Bash", "kubectl get deployments") is None

    def test_compound_command_per_segment_matching(self) -> None:
        git_add_skel = skeleton_mod.extract_skeleton("git add")
        git_commit_skel = skeleton_mod.extract_skeleton("git commit -m 'msg'")
        store = learned_mod.LearnedStore(
            approvals=[
                learned_mod.LearnedApproval(tool="Bash", pattern=git_add_skel, scope="test", source="user-approved"),
                learned_mod.LearnedApproval(
                    tool="Bash", pattern=git_commit_skel, scope="test", source="user-approved"
                ),
            ]
        )
        assert store.check("Bash", "git add README.md CHANGELOG.md") is not None
        assert store.check("Bash", "git commit -m 'totally new message'") is not None
        assert store.check("Bash", "git push origin main") is None
