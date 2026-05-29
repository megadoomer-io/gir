# GIR

**Guard, Inspect, Route** — a learning companion for [nah](https://github.com/manuelschipper/nah) that watches your approval patterns and suggests config changes to reduce future prompts.

## The problem

[nah](https://github.com/manuelschipper/nah) is an excellent action-aware permission guard for Claude Code. It classifies commands into intent types (`filesystem_delete`, `git_history_rewrite`, `network_outbound`, etc.) and applies policies deterministically. But nah's config is entirely manual — you have to run `nah allow <type>` or `nah classify <command> <type>` yourself to teach it.

GIR closes this gap by learning from your behavior. When nah asks and you approve, GIR records the pattern. After repeated approvals of the same type, GIR suggests the right `nah` command to stop being asked.

## How it works

```
Claude wants to run a command
        |
        v
   nah PreToolUse hook
   (classify → policy → allow/ask/block)
        |
        v
   If "ask": user gets prompted, approves ✓
        |
        v
   nah PostToolUse (audit log)
        |
        v
   GIR PostToolUse
    1. Read nah.log, find the "ask" entry
    2. Extract action_type (e.g., git_remote_write)
    3. Generalize command → skeleton (e.g., ^gh\s+pr\s+review\b)
    4. Tally approvals per (action_type, skeleton) per project
    5. At threshold: suggest "nah allow <type>"
```

## Install

### Prerequisites

Install nah first:

```bash
pip install "nah[config,keys]"  # or: uv tool install "nah[config,keys]"
nah install claude
```

### GIR setup

```bash
git clone git@github.com:megadoomer-io/gir.git ~/src/github.com/megadoomer-io/gir
```

Add GIR's PostToolUse hook to `~/.claude/settings.json` (nah handles PreToolUse):

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "~/src/github.com/megadoomer-io/gir/gir-post-hook-v2.py",
            "timeout": 5000
          }
        ]
      }
    ]
  }
}
```

## What GIR tracks

GIR tallies approvals per `(action_type, skeleton)` pair, scoped per project:

```
~/.config/gir/tallies/
  my-project.json      # per-project approval tallies
  other-repo.json
```

Each entry tracks the nah action type, the command skeleton (generalized pattern), the count, and the last concrete command that matched.

## Suggestions

When you've approved the same type of command 3+ times in a project, GIR suggests a nah config change via Claude's `additionalContext`:

> GIR: You've approved 5 'git_remote_write' commands in 'my-project'. Run `nah allow git_remote_write --project` to stop being asked, or `nah allow git_remote_write` for all projects.

## Skeleton extraction

GIR generalizes specific commands into reusable patterns:

| Command | Skeleton |
|---------|----------|
| `git commit -m "fix typo"` | `^git\s+commit\b` |
| `kubectl get pods -n staging` | `^kubectl\s+get\s+pods\b` |
| `gh pr review 123 --approve` | `^gh\s+pr\s+review\b` |

This groups similar commands so the tally accumulates meaningfully.

## Decision log

GIR logs learning events to `~/.config/gir/decisions.jsonl`:

```json
{"ts":"2026-05-29T21:00:00Z","tool":"Bash","decision":"learned","rule":"nah-ask:git_remote_write:^gh\\s+pr\\s+review\\b","command":"gh pr review 123 --approve","duration_ms":12.3}
```

## Developing

```bash
cd ~/src/github.com/megadoomer-io/gir
uv sync --all-groups
make validate   # lint + typecheck + test
```

282 tests, 89% coverage. Requires Python 3.13+.

## Architecture

GIR v2 has two layers — the learning engine (PostToolUse) and the supporting modules:

- `gir-post-hook-v2.py` — PostToolUse entry point (reads nah's log, tallies approvals, suggests config)
- `src/gir/tally.py` — per-project approval tally storage
- `src/gir/skeleton.py` — command skeleton extraction (shlex tokenization + subcommand depth)
- `src/gir/log.py` — JSON lines decision logging

Legacy modules from GIR v1 (retained for reference, not active):

- `gir-hook.py` — v1 PreToolUse entry point (replaced by nah)
- `gir-post-hook.py` — v1 PostToolUse observer
- `src/gir/hook.py` — v1 decision engine
- `src/gir/config.py` — v1 config loading
- `src/gir/decompose.py` — v1 compound command splitting
- `src/gir/learned.py` — v1 learned approval storage

## Named after

GIR from Invader Zim — the "security" robot who is hilariously bad at his job. Unlike the original GIR, this one actually works. Now he's learned to delegate the hard stuff.
