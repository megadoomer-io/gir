"""Shared fixtures for GIR tests.

All tests run with HOME and XDG_CONFIG_HOME redirected to a temp directory.
This means production code paths (~ expansion, default config location) are
exercised exactly as they run in production, but nothing touches the real
home directory.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

import gir.config as config_mod

EXAMPLE_CONFIG = Path(__file__).parent.parent / "example.json"
HOOK_SCRIPT = Path(__file__).parent.parent / "gir-hook.py"


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect HOME and XDG_CONFIG_HOME to tmp_path for every test.

    Production code that resolves ~/.config/gir/ will land in
    tmp_path/.config/gir/ instead. No test touches the real home directory.
    """
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    fake_config = fake_home / ".config" / "gir"
    fake_config.mkdir(parents=True)

    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(fake_home / ".config"))

    return fake_home


@pytest.fixture
def example_config(isolated_home: Path) -> config_mod.Config:
    """Load the example.json config, installed to the isolated home."""
    config_dir = isolated_home / ".config" / "gir"
    installed = config_dir / "config.json"
    with open(EXAMPLE_CONFIG) as f:
        config_data = json.load(f)
    config_data["log_file"] = str(config_dir / "decisions.jsonl")
    installed.write_text(json.dumps(config_data))
    return config_mod.Config.load(installed)


@pytest.fixture
def empty_config() -> config_mod.Config:
    """A config with no rules -- pure abstain-by-default."""
    return config_mod.Config()


def run_hook(
    tool_name: str,
    tool_input: dict[str, object],
    *,
    config_path: str | None = None,
    home: str | None = None,
) -> HookResult:
    """Run the hook entry point as a subprocess with isolated env."""
    env = dict(os.environ)
    if config_path:
        env["GIR_CONFIG"] = config_path
    if home:
        env["HOME"] = home
        env["XDG_CONFIG_HOME"] = str(Path(home) / ".config")

    payload = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
    result = subprocess.run(
        ["python3", str(HOOK_SCRIPT)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )
    return HookResult(stdout=result.stdout, stderr=result.stderr, exit_code=result.returncode)


@dataclass
class HookResult:
    stdout: str
    stderr: str
    exit_code: int

    @property
    def output(self) -> dict[str, object] | None:
        if not self.stdout.strip():
            return None
        return json.loads(self.stdout)

    @property
    def decision(self) -> str | None:
        out = self.output
        if out is None:
            return None
        hook_output = out.get("hookSpecificOutput", {})
        assert isinstance(hook_output, dict)
        return str(hook_output.get("permissionDecision", ""))
