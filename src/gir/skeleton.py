"""Command skeleton extraction for GIR learning loop.

Extracts reusable regex patterns ("skeletons") from specific command strings.
A skeleton captures the command type while generalizing variable arguments:

    "git commit -m 'initial commit'" → "^git\\s+commit\\b"

This allows GIR to learn "this type of command is safe" rather than
"this exact command with these exact arguments is safe."
"""

from __future__ import annotations

import os
import re
import shlex

SUBCOMMAND_DEPTH: dict[str, int] = {
    "git": 1,
    "kubectl": 2,
    "docker": 1,
    "helm": 1,
    "kustomize": 1,
    "make": 1,
    "cargo": 1,
    "go": 1,
    "npm": 1,
    "npx": 1,
    "yarn": 1,
    "pnpm": 1,
    "uv": 1,
    "pip": 1,
    "poetry": 1,
    "terraform": 1,
    "aws": 2,
    "gcloud": 2,
    "gh": 2,
    "brew": 1,
    "systemctl": 1,
    "apt": 1,
    "apt-get": 1,
}

PASS_THROUGH: dict[str, set[str]] = {
    "uv": {"run"},
    "docker": {"compose", "buildx"},
    "sudo": set(),
}

_ENV_VAR_RE = re.compile(r"^[A-Za-z_]\w*=")

_SHELL_OPERATORS = frozenset({"|", ">", ">>", "<", "2>", "2>&1", "2>>", "&>", "&>>"})


def extract_skeleton(command: str) -> str:
    """Extract a command skeleton regex from a specific command string.

    Args:
        command: A single command segment (not a compound command --
            decomposition should happen upstream).

    Returns:
        A regex pattern string like ``^git\\s+commit\\b`` that matches
        future invocations of the same command type.
    """
    if not command or not command.strip():
        return re.escape(command)

    tokens = _tokenize(command)
    if tokens is None:
        return re.escape(command)

    fixed = _extract_fixed_tokens(tokens)
    if not fixed:
        return re.escape(command)

    escaped = [re.escape(t) for t in fixed]
    return "^" + r"\s+".join(escaped) + r"\b"


def _tokenize(command: str) -> list[str] | None:
    """Tokenize a command string using shlex.

    Returns None if the command cannot be parsed (unclosed quotes, etc.).
    """
    try:
        return shlex.split(command)
    except ValueError:
        return None


def _is_flag(token: str) -> bool:
    return token.startswith("-")


def _is_env_assignment(token: str) -> bool:
    return bool(_ENV_VAR_RE.match(token))


def _is_shell_operator(token: str) -> bool:
    return token in _SHELL_OPERATORS


def _extract_fixed_tokens(tokens: list[str]) -> list[str]:
    """Identify the fixed tokens (command + subcommands) from a token list.

    Skips leading env var assignments, uses SUBCOMMAND_DEPTH and
    PASS_THROUGH to determine how many tokens to keep.
    """
    idx = 0
    while idx < len(tokens) and _is_env_assignment(tokens[idx]):
        idx += 1

    if idx >= len(tokens):
        return []

    return _collect_command_tokens(tokens, idx)


def _collect_command_tokens(tokens: list[str], start: int) -> list[str]:
    """Collect the command name and its subcommand tokens starting at the given index."""
    if start >= len(tokens):
        return []

    cmd_token = tokens[start]
    cmd_base = os.path.basename(cmd_token)
    fixed = [cmd_base]
    idx = start + 1

    if cmd_base in PASS_THROUGH:
        pass_through_subcmds = PASS_THROUGH[cmd_base]
        if not pass_through_subcmds:
            rest = _collect_command_tokens(tokens, idx)
            return fixed + rest

        if idx < len(tokens) and not _is_flag(tokens[idx]) and not _is_shell_operator(tokens[idx]):
            subcmd = tokens[idx]
            if subcmd in pass_through_subcmds:
                fixed.append(subcmd)
                rest = _collect_command_tokens(tokens, idx + 1)
                return fixed + rest

    depth = SUBCOMMAND_DEPTH.get(cmd_base, 0)
    collected = 0
    while idx < len(tokens) and collected < depth:
        token = tokens[idx]
        if _is_shell_operator(token):
            break
        if _is_flag(token):
            idx += 1
            continue
        fixed.append(token)
        collected += 1
        idx += 1

    return fixed
