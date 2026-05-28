# GIR

**Guard, Inspect, Route** -- a Claude Code hook that replaces the built-in permission system with one that learns from you.

## The problem

Claude Code's permission system prompts you before running commands. You can add allow rules, but:

- Every command variant needs its own rule (`kubectl get` vs `kubectl --context=foo get`)
- Compound commands always prompt (`cd dir && git status` is hardcoded to prompt)
- You end up with 100+ rules and still get prompted for new patterns

GIR fixes this by sitting between Claude and the permission system. It blocks dangerous commands, lets everything else fall through to the built-in prompt, and **learns from your approvals** so the same prompt never appears twice.

## How it works

```
Claude wants to run a command
        |
        v
   GIR PreToolUse hook
        |
   +---------+----------+-----------+
   |         |          |           |
 BLOCK    LEARNED     ASK       ABSTAIN
 (deny)   (allow)   (prompt)   (prompt)
   |         |          |           |
   v         v          v           v
 Stopped   Runs     Built-in    Built-in
                    prompt      prompt
                      |           |
                      v           v
                  User approves? ---> GIR PostToolUse records it
                                      Next time: LEARNED (no prompt)
```

On a fresh install, GIR only blocks dangerous patterns. Everything else prompts normally. As you approve commands through Claude's built-in prompts, GIR's PostToolUse observer records them. Over days, prompts fade to near-zero.

## Install

```bash
# Clone
git clone git@github.com:megadoomer-io/gir.git ~/src/github.com/megadoomer-io/gir

# Copy the example config
mkdir -p ~/.config/gir
cp ~/src/github.com/megadoomer-io/gir/example.json ~/.config/gir/config.json

# Register hooks in ~/.claude/settings.json
# Add to the "hooks" section:
```

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "~/src/github.com/megadoomer-io/gir/gir-hook.py",
            "timeout": 5000
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "~/src/github.com/megadoomer-io/gir/gir-post-hook.py",
            "timeout": 5000
          }
        ]
      }
    ]
  }
}
```

Optionally, clear your existing allow rules from `~/.claude/settings.json` and `~/.claude/settings.local.json`. GIR handles permissions now.

## Config

GIR reads `~/.config/gir/config.json` (or `$GIR_CONFIG`). See `example.json` for the full format.

```json
{
  "default": "abstain",
  "log_file": "~/.config/gir/decisions.jsonl",
  "block": {
    "bash": [
      {"pattern": "rm -rf /", "reason": "Filesystem root removal"},
      {"pattern": "git push.*--force.*(main|master)", "reason": "Force push to main/master"}
    ],
    "write": [
      {"pattern": "\\.(env|secret|key|pem)($|\\.(?!example))", "reason": "Secrets file"}
    ]
  },
  "ask": {
    "bash": [
      {"pattern": "kubectl.*(apply|patch).*--context=.*(prod|infra-prod)", "reason": "K8s write to production"}
    ]
  }
}
```

### Decision tiers

| Tier | What happens | When |
|------|-------------|------|
| **Block** | Command denied, Claude sees the reason | Matches a `block` pattern |
| **Learned** | Command runs silently | Previously approved by the user, recorded by PostToolUse |
| **Ask** | Built-in Claude prompt fires | Matches an `ask` pattern (GIR abstains) |
| **Abstain** | Built-in Claude prompt fires | No rule matches (default behavior) |

Block always wins. Learned approvals override ask and abstain. Over time, most commands move from abstain to learned.

### Context scoping

Rules can depend on context (e.g., kubectl cluster):

```json
{
  "contexts": {
    "production": {
      "patterns": ["--context=.*prod"],
      "default": "ask"
    }
  }
}
```

## Compound commands

GIR decomposes `cd dir && git status` into segments and evaluates each independently. This fixes Claude Code's hardcoded rule that `cd + git` compounds always prompt.

The blocklist runs on the original unsplit command first (catching `curl | bash`), then segments are checked against the ask list.

## Learning

Learned approvals are stored per-project in `~/.config/gir/learned/`:

```
~/.config/gir/learned/
  _global.json         # approvals that apply everywhere
  my-project.json      # project-scoped approvals
```

Project identity is derived from the git repo root name.

## Decision log

Every decision is logged to `~/.config/gir/decisions.jsonl`:

```json
{"ts":"2026-05-28T20:30:00Z","tool":"Bash","command":"git status","decision":"abstain","rule":"default","cwd":"/home/user/project","duration_ms":1.2}
```

## Developing

```bash
cd ~/src/github.com/megadoomer-io/gir
uv sync --all-groups
make validate   # lint + typecheck + test
```

163 tests, 86% coverage. Requires Python 3.13+.

## Architecture

- `src/gir/hook.py` -- decision engine (block > learned > ask > context > default)
- `src/gir/config.py` -- JSON config loading with compiled regex patterns
- `src/gir/decompose.py` -- compound command splitting on `&&`, `||`, `;`
- `src/gir/learned.py` -- per-project learned approval storage
- `src/gir/log.py` -- JSON lines decision logging
- `gir-hook.py` -- PreToolUse entry point
- `gir-post-hook.py` -- PostToolUse observer (records learned approvals)

## Named after

GIR from Invader Zim -- the "security" robot who is hilariously bad at his job. Unlike the original GIR, this one actually works.
