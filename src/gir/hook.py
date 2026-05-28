"""Core hook logic for GIR permission firewall."""

from __future__ import annotations

from dataclasses import dataclass

import gir.config as config_mod
import gir.decompose as decompose_mod
import gir.learned as learned_mod


@dataclass(frozen=True)
class Decision:
    action: str  # "allow", "deny", "ask"
    reason: str = ""
    rule: str = "default"
    segments: list[str] | None = None
    context: str | None = None


def evaluate(
    tool_name: str,
    tool_input: dict[str, object],
    cfg: config_mod.Config,
    learned: learned_mod.LearnedStore | None = None,
) -> Decision:
    """Evaluate a tool call against the config and return a decision."""
    if tool_name == "Bash":
        return _evaluate_bash(str(tool_input.get("command", "")), cfg, learned)
    elif tool_name in ("Edit", "Write"):
        return _evaluate_write(str(tool_input.get("file_path", "")), cfg, learned)
    else:
        return Decision(action=cfg.default, rule="default")


def _evaluate_bash(command: str, cfg: config_mod.Config, learned: learned_mod.LearnedStore | None = None) -> Decision:
    # Step 1: Check blocklist against the ORIGINAL unsplit command (always first)
    for rule in cfg.block_bash:
        if rule.pattern.search(command):
            return Decision(action="deny", reason=rule.reason, rule=f"block:{rule.pattern.pattern}")

    # Step 2: Check learned approvals (before ask-list -- learned overrides ask)
    if learned:
        approval = learned.check("Bash", command)
        if approval:
            return Decision(action="allow", rule=f"learned:{approval.pattern}")

    # Step 3: Decompose compound commands
    segments = decompose_mod.decompose(command)

    # Step 4: Check each segment against ask-list
    for segment in segments:
        # Check if this specific segment has a learned approval
        if learned:
            seg_approval = learned.check("Bash", segment)
            if seg_approval:
                continue  # This segment is learned-approved, check next
        for rule in cfg.ask_bash:
            if rule.pattern.search(segment):
                return Decision(
                    action="ask",
                    reason=rule.reason,
                    rule=f"ask:{rule.pattern.pattern}",
                    segments=segments if len(segments) > 1 else None,
                )

    # Step 5: Check context scoping
    detected_context = _detect_context(command, cfg)
    if detected_context is not None:
        ctx_name, ctx_scope = detected_context
        if ctx_scope.default == "ask":
            # Check if the context itself has a learned override
            if learned:
                ctx_approval = learned.check("Bash", command)
                if ctx_approval:
                    return Decision(action="allow", rule=f"learned:{ctx_approval.pattern}")
            return Decision(
                action="ask",
                reason=f"context:{ctx_name}",
                rule=f"context:{ctx_name}",
                context=ctx_name,
                segments=segments if len(segments) > 1 else None,
            )

    # Step 6: Default
    return Decision(
        action=cfg.default,
        rule="default",
        segments=segments if len(segments) > 1 else None,
    )


def _evaluate_write(
    file_path: str, cfg: config_mod.Config, learned: learned_mod.LearnedStore | None = None
) -> Decision:
    for rule in cfg.block_write:
        if rule.pattern.search(file_path):
            return Decision(action="deny", reason=rule.reason, rule=f"block:{rule.pattern.pattern}")
    if learned:
        approval = learned.check("Write", file_path)
        if approval:
            return Decision(action="allow", rule=f"learned:{approval.pattern}")
    return Decision(action=cfg.default, rule="default")


def _detect_context(command: str, cfg: config_mod.Config) -> tuple[str, config_mod.ContextScope] | None:
    """Check if the command matches any context scope patterns."""
    for name, scope in cfg.contexts.items():
        for pattern in scope.patterns:
            if pattern.search(command):
                return (name, scope)
    return None


def format_output(decision: Decision) -> dict[str, object] | None:
    """Format a decision into Claude Code hook output JSON.

    Returns None for "ask" decisions (hook abstains, falls through to built-in prompt).
    """
    if decision.action == "allow":
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
            }
        }
    elif decision.action == "deny":
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"GIR: {decision.reason}",
            }
        }
    else:
        # "ask" -- return None, hook exits 0 with no output
        return None
