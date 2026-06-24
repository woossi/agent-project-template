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
