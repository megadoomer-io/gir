"""Config loading for GIR permission firewall."""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Rule:
    pattern: re.Pattern[str]
    reason: str

    @classmethod
    def from_dict(cls, d: dict[str, str]) -> Rule:
        return cls(pattern=re.compile(d["pattern"], re.IGNORECASE), reason=d.get("reason", ""))


@dataclass(frozen=True)
class ContextScope:
    patterns: list[re.Pattern[str]]
    default: str

    @classmethod
    def from_dict(cls, d: dict[str, object]) -> ContextScope:
        raw_patterns = d.get("patterns", [])
        assert isinstance(raw_patterns, list)
        return cls(
            patterns=[re.compile(str(p)) for p in raw_patterns],
            default=str(d.get("default", "allow")),
        )


@dataclass(frozen=True)
class Config:
    default: str = "allow"
    log_file: str = "~/.gir/decisions.jsonl"
    block_bash: list[Rule] = field(default_factory=list)
    block_write: list[Rule] = field(default_factory=list)
    ask_bash: list[Rule] = field(default_factory=list)
    contexts: dict[str, ContextScope] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path | None = None) -> Config:
        if path is None:
            path = os.environ.get("GIR_CONFIG", "~/.gir/config.json")
        resolved = Path(str(path)).expanduser()
        if not resolved.exists():
            print(f"[gir] config not found at {resolved}, using defaults", file=sys.stderr)
            return cls()
        try:
            with open(resolved) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[gir] config error: {e}, using defaults", file=sys.stderr)
            return cls()
        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict[str, object]) -> Config:
        block = data.get("block", {})
        ask = data.get("ask", {})
        contexts_raw = data.get("contexts", {})
        assert isinstance(block, dict)
        assert isinstance(ask, dict)
        assert isinstance(contexts_raw, dict)

        return cls(
            default=str(data.get("default", "allow")),
            log_file=str(data.get("log_file", "~/.gir/decisions.jsonl")),
            block_bash=[Rule.from_dict(r) for r in block.get("bash", [])],
            block_write=[Rule.from_dict(r) for r in block.get("write", [])],
            ask_bash=[Rule.from_dict(r) for r in ask.get("bash", [])],
            contexts={name: ContextScope.from_dict(scope) for name, scope in contexts_raw.items()},
        )
