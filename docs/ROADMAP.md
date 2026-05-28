# GIR Roadmap

## v0.1.0 (shipped)

- [x] PreToolUse hook with block/ask/abstain decision tiers
- [x] Compound command decomposition (`cd dir && git status`)
- [x] JSON config with block/ask rules and context scoping
- [x] Structured JSON lines decision logging
- [x] Fail-safe error handling (abstain on error)
- [x] PostToolUse learning observer
- [x] Per-project learned approval storage
- [x] `GIR:` prefix on block messages
- [x] 163 tests, 86% coverage

## v0.2.0 (next)

### Smarter pattern generalization

The learning loop currently records the exact escaped command string. A `git add && git commit -m "specific message" && git push` approval will never match again because the commit message differs.

The PostToolUse observer should extract a **command skeleton** instead:
- `cd <path> && git add <files> && git commit -m <msg> && git push <remote> <branch>` → learn `git add .* && git commit .* && git push .*`
- `kubectl get pods -n <ns>` → learn `kubectl get pods .*`
- Collapse file paths, version numbers, commit messages into `.*`
- Keep the command name and subcommand fixed, generalize arguments

This is the difference between GIR learning "this exact command" vs "this kind of command."

### One-time block override

When GIR blocks a command, the user currently has no way to proceed within the session. Add a mechanism:
1. GIR blocks with `GIR: [reason]. Say "proceed" to override once.`
2. User says "proceed" or "gir allow"
3. Claude retries, GIR checks for a one-time override token
4. Command runs, token consumed

### Anchor blocklist word boundaries

`git push.*--force.*(main|master)` matches `fakemain`. Should use `\b(main|master)\b` for whole-word matching on branch names.

## v0.3.0

### Interactive CLI ([#3](https://github.com/megadoomer-io/gir/issues/3))

```bash
gir review              # Review learned approvals across projects
gir review --project X  # Review for a specific project
gir stats               # Decision log summary
gir suggest             # Propose new config rules from log patterns
gir audit               # Interactive: walk through recent decisions
gir promote             # Move project approval to global
```

### Onboarding SKILL.md ([#4](https://github.com/megadoomer-io/gir/issues/4))

A Claude Code skill (`/gir-setup`) that guides users through:
1. Auditing current permission rules
2. Installing and configuring GIR
3. Migrating from built-in rules
4. First-session testing and tuning

## Future

### Session-scoped file ownership ([#1](https://github.com/megadoomer-io/gir/issues/1))

Track what files/directories a session creates via PostToolUse. Allow the same session to modify/delete its own files without prompting.

### Content-aware write blocking ([#2](https://github.com/megadoomer-io/gir/issues/2))

Scan write content for secrets patterns (AWS keys, API tokens, PEM keys) regardless of filename. Opt-in via config.

### MCP tool-specific rules

Add `mcp` section to config for blocking/asking on specific MCP operations (e.g., `mcp__kubectl__kubectl_delete` for production namespaces).

### Log rotation

Decision log grows unbounded. Add rotation (keep last N days or N MB).

### Metrics dashboard

`gir dashboard` -- show prompts over time, most-learned patterns, block frequency. Visualize how GIR improves your workflow over days/weeks.
