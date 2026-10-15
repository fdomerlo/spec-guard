

<!-- BEGIN SPECGUARD -->
# Contributor & Executor Contract (SpecGuard SDD)

## Core Principles

- Code, comments, error messages, and commit messages: **English**. Chat with the human: user's preferred language.
- Atomic commits, one concern each, conventional-commit messages: `feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert`.
- Always run automated test suite before your first change in a session and after every logical unit. Never leave the suite red at a commit boundary.
- Never hand-edit generated or state files — use `sg` CLI commands for state transitions (`begin`, `commit`, `rollback`, `checkpoint`, `status`, `next-task`, `verify-gate`, `mark-task`, `verify-crit`, `session-checkpoint`, `context`, `glossary-check`).
- **Token Anchoring:** Strictly adhere to the strict glossary (`requirements.md §2`). Forbidden synonyms are prohibited in code, tests, and comments (`sg glossary-check`).
- **Stack Compliance:** Strictly adhere to the mandatory tech stack (`design.md §1`). No new dependencies without explicit human approval.
- **Read-First Ignition:** On session start, assimilate project rules via `sg context` before generating any code.


## Specification-Driven Development (SDD) Lifecycle

Every change follows a strict phase DAG: `PLAN` -> `EXECUTE` -> `VERIFY`.

### 1. PLAN Phase
- **2-File Root Protocol (default):** the project's sources of truth are root `requirements.md` (PRD) and `design.md` (SAD). Each change covers RFs (`### [ ] RF-XXX: ...`) opened with `sg init-change --change {change-name} --rf RF-XXX`; acceptance criteria are `CRIT-<rf>-<n>` inside each RF. RF checkboxes are only flipped by `sg mark-rf` during VERIFY.
- **Legacy mode:** changes with `objective.md` keep delta specs in `.spec-guard/changes/{change-name}/specs/`.
- Explicitly define **Fuera del Alcance (Out of Scope)** to prevent scope creep.
- Break down deliverables into numbered acceptance criteria: `CRIT-01`, `CRIT-02`, etc., classified as `[automated]` or `[manual]`.
- Human review gate: Human must approve the plan out-of-band with `sg plan-approve` + `sg plan-confirm`. Never attempt to bypass this gate.

### 2. EXECUTE Phase & Session Checkpoint
- Work with a lightweight **SESSION.md** cursor (~250 tokens) at `.spec-guard/SESSION.md` to keep token consumption minimal during implementation.
- Maintain test-driven discipline (RED -> GREEN -> REFACTOR).
- Criteria traceability (`CRIT-XX`): Every automated criterion MUST map to a test named after that criterion (e.g., `def test_crit_01_...()` or `test("CRIT-01: ...")`).
- Run `sg session-checkpoint --change {change-name} --action "..."` to record execution progress atomically with git ancestry verification.

### 3. VERIFY Phase
- Mandatory deterministic gate: `sg verify-crit --change {change-name}` (or `.spec-guard/bin/verify-crit.sh {change-name}`).
- If any automated criterion lacks a matching test, the gate exits with code 2 and the verdict is REJECTED.
- On approval, the change is archived to `.spec-guard/changes/archive/YYYY-MM-DD-{change-name}/` and `.spec-guard/SESSION.md` is cleaned up.
<!-- END SPECGUARD -->
