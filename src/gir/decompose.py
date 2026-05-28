"""Compound command decomposition for Bash commands."""

from __future__ import annotations

import re

_SEPARATOR_PATTERN = re.compile(r"\s*(?:&&|\|\||;)\s*")

_QUOTE_CHARS = {'"', "'"}


def decompose(command: str) -> list[str]:
    """Split a compound command into segments on &&, ||, ; boundaries.

    Respects quoted strings. Does NOT split on pipes (|) since pipelines
    are single logical operations. Falls back to returning the original
    command as a single-element list if parsing fails.

    Examples:
        >>> decompose("cd /tmp && git status")
        ['cd /tmp', 'git status']
        >>> decompose("echo 'hello && world'")
        ["echo 'hello && world'"]
        >>> decompose("git log | head -5")
        ['git log | head -5']
    """
    try:
        return _split_respecting_quotes(command)
    except Exception:
        return [command]


def _split_respecting_quotes(command: str) -> list[str]:
    segments: list[str] = []
    current: list[str] = []
    i = 0
    length = len(command)

    while i < length:
        char = command[i]

        if char in _QUOTE_CHARS:
            quote = char
            current.append(char)
            i += 1
            while i < length and command[i] != quote:
                if command[i] == "\\" and i + 1 < length:
                    current.append(command[i])
                    current.append(command[i + 1])
                    i += 2
                else:
                    current.append(command[i])
                    i += 1
            if i < length:
                current.append(command[i])
                i += 1
            continue

        if char == "\\" and i + 1 < length:
            current.append(command[i])
            current.append(command[i + 1])
            i += 2
            continue

        remaining = command[i:]
        m = _SEPARATOR_PATTERN.match(remaining)
        if m and m.start() == 0:
            seg = "".join(current).strip()
            if seg:
                segments.append(seg)
            current = []
            i += m.end()
            continue

        current.append(char)
        i += 1

    seg = "".join(current).strip()
    if seg:
        segments.append(seg)

    return segments if segments else [command]
