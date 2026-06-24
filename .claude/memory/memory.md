# Memory

Durable project-level context. Not a task log or scratchpad.

## Input Contract

Read when a task depends on prior decisions, a component contract is changing, or the user asks for consistency with previous work.

Write only when the information is confirmed, stable, project-scoped, and useful later. Use the Memory Entry format in `AGENTS.md`.

## Durable Facts

## 2026-06-24 - Enforced Tasks→Skills→Agents promotion loop

Fact: The Tasks→Skills→Agents chain is enforced by two PostToolUse hooks plus a policy. `.claude/hooks/task_ledger.py` auto-records executed actions and skill-usage (a `SKILL.md` read) to `.context/task-log/`, and accepts `record-task` for semantic task signatures. `.claude/hooks/detect_promotions.py` evaluates the ledger against `.claude/policies/promotion.json` (skill: signature recurs ≥`min_recurrence` across ≥`min_distinct_sessions`; agent: skills package co-used ≥`min_cousage` across ≥`min_distinct_sessions`) and re-surfaces candidates via `additionalContext` until closed with `detect_promotions.py resolve`. Authoring stays a judgment step (`write-skill`/`write-subagent`); only the trigger is deterministic. Ledger output lives under git-ignored `.context/`.
Source: Implementation in this session (hooks, tests, policy, doc declaration in AGENTS.md *Enforced Promotion Loop*, propagation in `init_agent_clone.py`).
Use Later When: Tuning promotion thresholds, debugging why a candidate did or did not surface, or extending the clone generator.

## 2026-06-24 - Enforced Memory→preference/term derivation loop + 3x promotion frequency

Fact: Added a memory-derivation loop mirroring the promotion loop. `.claude/hooks/detect_derivations.py` (PostToolUse + SessionStart, also `record-signal`/`evaluate`/`resolve` subcommands) surfaces `preference` and `term` candidates from two deterministic sources: optional `Derive: preference` / `Derive: term: <word>` markers in `memory.md` entries (surface immediately) and `record-signal` observations in `.context/memory-log/signals.jsonl` (surface on recurrence). Thresholds live in `.claude/policies/derivation.json` (preference/term: `min_recurrence` 2, `min_distinct_sessions` 1); candidates already in `user_preferences.md`/`word.json` are skipped; authoring stays judgment (`user_preferences.md` write or `register-term`). Separately, `promotion.json` count gates were lowered ~3x for higher auto-update frequency: skill `min_recurrence` 3→1 and `min_distinct_sessions` 2→1; agent `min_cousage` 3→1 and `min_distinct_sessions` 2→1 (`min_package_size` stays 2). Diagnosis recorded: root `.mcp.json` is an empty (`{"mcpServers": {}}`) runtime no-op but kept as the documented project-neutral MCP seam referenced by `.claude/mcp/README.md`.
Source: Implementation in this session (detect_derivations.py + test_detect_derivations.py (21 tests), derivation.json, settings.json wiring, promotion.json + policies/README.md, AGENTS.md *Enforced Derivation Loop* + Memory Entry `Derive:` field, .claude/CLAUDE.md, init_agent_clone.py parity).
Use Later When: Tuning derivation/promotion thresholds, debugging why a preference/term candidate did or did not surface, or deciding whether to keep the empty `.mcp.json`.
