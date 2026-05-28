"""Shared fixtures for GIR tests."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

import gir.config as config_mod

EXAMPLE_CONFIG = Path(__file__).parent.parent / "example.json"


@pytest.fixture
def example_config() -> config_mod.Config:
    """Load the example.json config for testing."""
    return config_mod.Config.load(EXAMPLE_CONFIG)


@pytest.fixture
def empty_config() -> config_mod.Config:
    """A config with no rules -- pure allow-by-default."""
    return config_mod.Config()


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


@pytest.fixture
def hook_runner() -> type[HookResult]:
    """Run the hook entry point as a subprocess (integration-style)."""

    class Runner:
        @staticmethod
        def run(tool_name: str, tool_input: dict[str, object], config_path: str | None = None) -> HookResult:
            hook_path = Path(__file__).parent.parent / "gir-hook.py"
            env = dict(__import__("os").environ)
            if config_path:
                env["GIR_CONFIG"] = config_path

            payload = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
            result = subprocess.run(
                ["python3", str(hook_path)],
                input=payload,
                capture_output=True,
                text=True,
                timeout=10,
                env=env,
            )
            return HookResult(stdout=result.stdout, stderr=result.stderr, exit_code=result.returncode)

    return Runner  # type: ignore[return-value]
