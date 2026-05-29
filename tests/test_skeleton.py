"""Tests for command skeleton extraction."""

from __future__ import annotations

import re

import gir.skeleton as skeleton_mod


class TestKnownCommands:
    def test_git_commit(self) -> None:
        assert skeleton_mod.extract_skeleton("git commit -m 'initial commit'") == r"^git\s+commit\b"

    def test_git_push(self) -> None:
        assert skeleton_mod.extract_skeleton("git push origin main") == r"^git\s+push\b"

    def test_git_add(self) -> None:
        assert skeleton_mod.extract_skeleton("git add src/main.py README.md") == r"^git\s+add\b"

    def test_git_log_with_flags(self) -> None:
        assert skeleton_mod.extract_skeleton("git log --oneline -3") == r"^git\s+log\b"

    def test_git_status(self) -> None:
        assert skeleton_mod.extract_skeleton("git status") == r"^git\s+status\b"

    def test_git_diff(self) -> None:
        assert skeleton_mod.extract_skeleton("git diff HEAD~1") == r"^git\s+diff\b"

    def test_kubectl_get_pods(self) -> None:
        assert skeleton_mod.extract_skeleton("kubectl get pods -n kube-system") == r"^kubectl\s+get\s+pods\b"

    def test_kubectl_get_deployments(self) -> None:
        assert skeleton_mod.extract_skeleton("kubectl get deployments -o wide") == r"^kubectl\s+get\s+deployments\b"

    def test_kubectl_describe_pod(self) -> None:
        assert skeleton_mod.extract_skeleton("kubectl describe pod my-pod-abc123") == r"^kubectl\s+describe\s+pod\b"

    def test_kubectl_apply(self) -> None:
        # -f is a flag, deploy.yaml is the first non-flag positional after apply
        assert skeleton_mod.extract_skeleton("kubectl apply -f deploy.yaml --context=prod") == (
            r"^kubectl\s+apply\s+deploy\.yaml\b"
        )

    def test_kubectl_delete_pod(self) -> None:
        assert skeleton_mod.extract_skeleton("kubectl delete pod my-pod -n staging") == (
            r"^kubectl\s+delete\s+pod\b"
        )

    def test_docker_build(self) -> None:
        assert skeleton_mod.extract_skeleton("docker build -t myapp:latest .") == r"^docker\s+build\b"

    def test_docker_run(self) -> None:
        assert skeleton_mod.extract_skeleton("docker run --rm -it ubuntu bash") == r"^docker\s+run\b"

    def test_helm_install(self) -> None:
        assert skeleton_mod.extract_skeleton("helm install myapp ./chart --set foo=bar") == r"^helm\s+install\b"

    def test_helm_upgrade(self) -> None:
        assert skeleton_mod.extract_skeleton("helm upgrade --install myapp ./chart") == r"^helm\s+upgrade\b"

    def test_make_validate(self) -> None:
        assert skeleton_mod.extract_skeleton("make validate") == r"^make\s+validate\b"

    def test_make_test(self) -> None:
        assert skeleton_mod.extract_skeleton("make test") == r"^make\s+test\b"

    def test_npm_test(self) -> None:
        assert skeleton_mod.extract_skeleton("npm test -- --watch") == r"^npm\s+test\b"

    def test_npm_install(self) -> None:
        assert skeleton_mod.extract_skeleton("npm install express") == r"^npm\s+install\b"

    def test_uv_sync(self) -> None:
        assert skeleton_mod.extract_skeleton("uv sync --all-groups") == r"^uv\s+sync\b"

    def test_uv_add(self) -> None:
        assert skeleton_mod.extract_skeleton("uv add pytest --group test") == r"^uv\s+add\b"

    def test_cargo_build(self) -> None:
        assert skeleton_mod.extract_skeleton("cargo build --release") == r"^cargo\s+build\b"

    def test_cargo_test(self) -> None:
        assert skeleton_mod.extract_skeleton("cargo test -- --nocapture") == r"^cargo\s+test\b"

    def test_go_test(self) -> None:
        assert skeleton_mod.extract_skeleton("go test ./...") == r"^go\s+test\b"

    def test_terraform_apply(self) -> None:
        assert skeleton_mod.extract_skeleton("terraform apply -auto-approve") == r"^terraform\s+apply\b"

    def test_terraform_plan(self) -> None:
        assert skeleton_mod.extract_skeleton("terraform plan -var-file=dev.tfvars") == r"^terraform\s+plan\b"

    def test_aws_s3_cp(self) -> None:
        assert skeleton_mod.extract_skeleton("aws s3 cp file.txt s3://bucket/") == r"^aws\s+s3\s+cp\b"

    def test_aws_ecs_update(self) -> None:
        assert skeleton_mod.extract_skeleton("aws ecs update-service --cluster foo") == (
            r"^aws\s+ecs\s+update\-service\b"
        )

    def test_gh_pr_create(self) -> None:
        assert skeleton_mod.extract_skeleton("gh pr create --title 'Fix bug'") == r"^gh\s+pr\s+create\b"

    def test_gh_issue_list(self) -> None:
        assert skeleton_mod.extract_skeleton("gh issue list --repo owner/repo") == r"^gh\s+issue\s+list\b"

    def test_brew_install(self) -> None:
        assert skeleton_mod.extract_skeleton("brew install ripgrep") == r"^brew\s+install\b"

    def test_systemctl_restart(self) -> None:
        assert skeleton_mod.extract_skeleton("systemctl restart nginx") == r"^systemctl\s+restart\b"


class TestPassThrough:
    def test_uv_run_pytest(self) -> None:
        assert skeleton_mod.extract_skeleton("uv run pytest -q --tb=short") == r"^uv\s+run\s+pytest\b"

    def test_uv_run_mypy(self) -> None:
        assert skeleton_mod.extract_skeleton("uv run mypy src/") == r"^uv\s+run\s+mypy\b"

    def test_uv_run_ruff(self) -> None:
        assert skeleton_mod.extract_skeleton("uv run ruff check .") == r"^uv\s+run\s+ruff\b"

    def test_uv_non_passthrough(self) -> None:
        assert skeleton_mod.extract_skeleton("uv sync --all-groups") == r"^uv\s+sync\b"

    def test_docker_compose_up(self) -> None:
        assert skeleton_mod.extract_skeleton("docker compose up -d") == r"^docker\s+compose\s+up\b"

    def test_docker_compose_down(self) -> None:
        assert skeleton_mod.extract_skeleton("docker compose down --volumes") == r"^docker\s+compose\s+down\b"

    def test_docker_buildx_build(self) -> None:
        assert skeleton_mod.extract_skeleton("docker buildx build --platform linux/amd64 .") == (
            r"^docker\s+buildx\s+build\b"
        )

    def test_docker_non_passthrough(self) -> None:
        assert skeleton_mod.extract_skeleton("docker build -t foo .") == r"^docker\s+build\b"

    def test_sudo_git(self) -> None:
        assert skeleton_mod.extract_skeleton("sudo git push origin main") == r"^sudo\s+git\s+push\b"

    def test_sudo_apt_get(self) -> None:
        assert skeleton_mod.extract_skeleton("sudo apt-get install vim") == r"^sudo\s+apt\-get\s+install\b"

    def test_sudo_unknown(self) -> None:
        assert skeleton_mod.extract_skeleton("sudo rm -rf /tmp/build") == r"^sudo\s+rm\b"


class TestUnknownCommands:
    def test_grep(self) -> None:
        assert skeleton_mod.extract_skeleton("grep -rn 'pattern' src/") == r"^grep\b"

    def test_cat(self) -> None:
        assert skeleton_mod.extract_skeleton("cat /etc/hosts") == r"^cat\b"

    def test_ls(self) -> None:
        assert skeleton_mod.extract_skeleton("ls -la /tmp") == r"^ls\b"

    def test_echo(self) -> None:
        assert skeleton_mod.extract_skeleton("echo 'hello world'") == r"^echo\b"

    def test_cd(self) -> None:
        assert skeleton_mod.extract_skeleton("cd /tmp/build") == r"^cd\b"

    def test_python3(self) -> None:
        assert skeleton_mod.extract_skeleton("python3 -c 'import json; print(1)'") == r"^python3\b"

    def test_find(self) -> None:
        assert skeleton_mod.extract_skeleton("find . -name '*.py' -type f") == r"^find\b"

    def test_wc(self) -> None:
        assert skeleton_mod.extract_skeleton("wc -l README.md") == r"^wc\b"


class TestEdgeCases:
    def test_env_vars_skipped(self) -> None:
        assert skeleton_mod.extract_skeleton("FOO=bar BAZ=qux git commit -m 'msg'") == r"^git\s+commit\b"

    def test_env_var_with_path(self) -> None:
        assert skeleton_mod.extract_skeleton("PATH=/usr/bin:$PATH python3 script.py") == r"^python3\b"

    def test_single_env_var(self) -> None:
        assert skeleton_mod.extract_skeleton("DOCKER_HOST=unix:///var/run/docker.sock docker ps") == (
            r"^docker\s+ps\b"
        )

    def test_shlex_failure_unclosed_quote(self) -> None:
        result = skeleton_mod.extract_skeleton("echo 'unclosed")
        assert result == re.escape("echo 'unclosed")

    def test_empty_string(self) -> None:
        result = skeleton_mod.extract_skeleton("")
        assert result == ""

    def test_whitespace_only(self) -> None:
        result = skeleton_mod.extract_skeleton("   ")
        assert result == re.escape("   ")

    def test_single_token(self) -> None:
        assert skeleton_mod.extract_skeleton("ls") == r"^ls\b"

    def test_command_with_path(self) -> None:
        assert skeleton_mod.extract_skeleton("/usr/bin/git commit -m 'msg'") == r"^git\s+commit\b"

    def test_command_with_relative_path(self) -> None:
        assert skeleton_mod.extract_skeleton("./script.py --flag") == r"^script\.py\b"

    def test_pipe_stops_skeleton(self) -> None:
        assert skeleton_mod.extract_skeleton("git log --oneline | head -5") == r"^git\s+log\b"

    def test_redirect_stdout(self) -> None:
        assert skeleton_mod.extract_skeleton("echo hello > output.txt") == r"^echo\b"

    def test_redirect_stderr(self) -> None:
        assert skeleton_mod.extract_skeleton("make validate 2>&1") == r"^make\s+validate\b"

    def test_redirect_append(self) -> None:
        assert skeleton_mod.extract_skeleton("echo msg >> log.txt") == r"^echo\b"

    def test_only_env_vars(self) -> None:
        result = skeleton_mod.extract_skeleton("FOO=bar BAZ=qux")
        assert result == re.escape("FOO=bar BAZ=qux")

    def test_flag_with_equals(self) -> None:
        # --context=prod is one token, treated as a flag
        assert skeleton_mod.extract_skeleton("kubectl get pods --context=prod") == r"^kubectl\s+get\s+pods\b"

    def test_double_dash_separator(self) -> None:
        # -- is treated as a flag (starts with -)
        assert skeleton_mod.extract_skeleton("npm test -- --watch") == r"^npm\s+test\b"


class TestSkeletonMatchesCommands:
    """Verify that produced skeletons match future invocations correctly."""

    def test_git_commit_matches_variants(self) -> None:
        skeleton = skeleton_mod.extract_skeleton("git commit -m 'initial commit'")
        assert re.search(skeleton, "git commit -m 'different message'")
        assert re.search(skeleton, "git commit --amend")
        assert re.search(skeleton, "git commit --amend -m 'rewritten'")
        assert re.search(skeleton, "git commit")

    def test_git_commit_rejects_wrong_commands(self) -> None:
        skeleton = skeleton_mod.extract_skeleton("git commit -m 'msg'")
        assert not re.search(skeleton, "git push origin main")
        assert not re.search(skeleton, "git add README.md")
        assert not re.search(skeleton, "kubectl get pods")

    def test_git_commit_word_boundary(self) -> None:
        skeleton = skeleton_mod.extract_skeleton("git commit -m 'msg'")
        assert not re.search(skeleton, "git committed")
        assert not re.search(skeleton, "git committing")

    def test_kubectl_get_pods_matches_variants(self) -> None:
        skeleton = skeleton_mod.extract_skeleton("kubectl get pods -n default")
        assert re.search(skeleton, "kubectl get pods -n kube-system")
        assert re.search(skeleton, "kubectl get pods --all-namespaces")
        assert re.search(skeleton, "kubectl get pods -o wide")

    def test_kubectl_get_pods_rejects_wrong_resource(self) -> None:
        skeleton = skeleton_mod.extract_skeleton("kubectl get pods -n default")
        assert not re.search(skeleton, "kubectl get deployments")
        assert not re.search(skeleton, "kubectl get services -n default")
        assert not re.search(skeleton, "kubectl delete pod foo")

    def test_uv_run_pytest_matches_variants(self) -> None:
        skeleton = skeleton_mod.extract_skeleton("uv run pytest -q --tb=short")
        assert re.search(skeleton, "uv run pytest")
        assert re.search(skeleton, "uv run pytest -v --cov=src")
        assert re.search(skeleton, "uv run pytest tests/test_specific.py")

    def test_uv_run_pytest_rejects_different_tool(self) -> None:
        skeleton = skeleton_mod.extract_skeleton("uv run pytest -q")
        assert not re.search(skeleton, "uv run mypy src/")
        assert not re.search(skeleton, "uv run ruff check .")
        assert not re.search(skeleton, "uv sync --all-groups")

    def test_unknown_command_matches_broadly(self) -> None:
        skeleton = skeleton_mod.extract_skeleton("grep -rn 'foo' src/")
        assert re.search(skeleton, "grep -rn 'bar' tests/")
        assert re.search(skeleton, "grep pattern file.txt")
        assert re.search(skeleton, "grep --color=auto 'search term' .")

    def test_unknown_command_word_boundary(self) -> None:
        skeleton = skeleton_mod.extract_skeleton("grep -rn 'foo' src/")
        assert not re.search(skeleton, "egrep 'pattern' file")
        assert not re.search(skeleton, "fgrep 'literal' file")

    def test_case_insensitive_matching(self) -> None:
        skeleton = skeleton_mod.extract_skeleton("git commit -m 'msg'")
        assert re.search(skeleton, "git commit -m 'msg'", re.IGNORECASE)

    def test_env_var_skeleton_matches_without_env(self) -> None:
        skeleton = skeleton_mod.extract_skeleton("FOO=bar git push origin main")
        assert re.search(skeleton, "git push origin develop")
        assert re.search(skeleton, "git push upstream feature")
