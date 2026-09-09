---
name: spec-guard
description: >-
  Specification-Driven Development (SDD) engine and transactional state governor for code agents.
  Use whenever the user asks to build, plan, implement, verify, or scaffold an application or
  feature; for multi-step coding tasks; to resume work after a lost, crashed, or compacted session;
  or in any project that contains a `.spec-guard/` (or legacy `.state-guard/`) directory. Drives the
  `sg` CLI so that a change follows the strict 3-phase DAG: PLAN -> EXECUTE -> VERIFY with out-of-band
  human approval gate, 1:1 CRIT-XX criteria test traceability, and low-token session cursor (SESSION.md).
---

# SpecGuard: Specification-Driven Development (SDD) Engine

`sg` (long form: `spec-guard`) is a transactional state manager and SDD governor. A change moves through fixed phases in a directed acyclic graph (DAG):

```text
PLAN --plan-approve + plan-confirm (human /dev/tty)--> EXECUTE --tasks done + TDD--> VERIFY --verify-crit--> ARCHIVE
```

## Mandatory Lifecycle & Gate Rules

1. **Constitución de Estado (SDD State Contract)**:
   - Obey `AGENTS.md` in the project root if present; otherwise follow `~/.agents/skills/spec-guard/_shared/memory-guard.md`.
   - Never hand-edit generated or state files (`state.ini`). Always use `sg` CLI commands.

2. **Phase DAG & Human Gate Approval**:
   - `PLAN`: Define delta specs in `.spec-guard/changes/{name}/specs/`. Define explicit `### Fuera del Alcance` (Out of Scope). Classify deliverables into sequential criteria: `CRIT-01`, `CRIT-02` (`[automated]` or `[manual]`).
   - **Gate Mode `chat` (DEFAULT)**:
     - Mandatory STOP in chat. The agent is strictly forbidden from executing `commit` or coding in the same turn.
     - The agent asks the human for explicit approval in the conversation.
     - Once the human approves, `sg commit --change <name> --next-phase execute` advances the DAG to `lock_phase = execute`.
   - **Gate Mode `strict` (Adversarial Security)**:
     - When `commit` returns exit code 5 (`EXIT_GATE_REQUIRED`), STOP immediately. Never attempt to run `sg plan-approve` or `sg plan-confirm`. Instruct the human to run:
       ```bash
       sg plan-approve --change <name>
       sg plan-confirm --change <name> --token <CODE>
       ```
       in their interactive physical terminal (`/dev/tty`).

3. **Low-Token Execution & Session Checkpoint (`SESSION.md`)**:
   - During `EXECUTE`, operate with the lightweight cursor `SESSION.md` (~250 tokens) at repository root. Do not reload massive specification files in every turn.
   - Always verify Git ancestry: `git merge-base --is-ancestor <base-commit> HEAD`.
   - Run `sg session-checkpoint --change <name> --action "..."` to record atomic progress.
   - Maintain TDD discipline: RED (failing test with `CRIT-XX`) -> GREEN (implementation) -> REFACTOR.

4. **Deterministic Criteria Verification Gate (`verify-crit`)**:
   - Before closing `VERIFY`, run:
     ```bash
     sg verify-crit --change <name>
     ```
   - If any automated criterion lacks a matching test in `tests/`, `test/`, `spec/`, or `src/`, `verify-crit` exits with code 2. The phase CANNOT be approved with orphaned criteria.
   - On approved verdict, the change is archived to `.spec-guard/changes/archive/YYYY-MM-DD-{name}/` and `SESSION.md` is removed from repository root.

## CLI Commands Quick Reference

| Command | Purpose | Allowed Caller |
|---------|---------|----------------|
| `sg init [--force]` | Initialize `.spec-guard/`, `AGENTS.md`, `CLAUDE.md`, `scripts/verify-crit.sh` | Agent or Human |
| `sg status [--change <c>]` | Inspect active phase, lock status, and pending tasks | Agent or Human |
| `sg begin --change <c> --phase <p>` | Start ACID transaction for phase (`plan`, `execute`, `verify`) | Agent |
| `sg commit --change <c> --next-phase <p>` | Commit phase and advance DAG (exits 5 if gate required) | Agent |
| `sg rollback --change <c>` | Roll back in-progress transaction to idle | Agent |
| `sg checkpoint --change <c> --summary "..."` | Save persistent session summary block | Agent |
| `sg session-checkpoint --change <c> [--action <a>]` | Atomically update low-token `SESSION.md` cursor | Agent |
| `sg verify-crit --change <c>` | Deterministic audit of 1:1 `CRIT-XX` test traceability | Agent or Human |
| `sg validate-spec --change <c>` | Check structural validity and out-of-scope in specs | Agent or Human |
| `sg plan-approve` / `plan-confirm` | Human approval gate out-of-band via `/dev/tty` | **HUMAN ONLY** |
| `sg hotfix-init` / `hotfix-confirm` | Emergency bypass gate out-of-band via `/dev/tty` | **HUMAN ONLY** |
