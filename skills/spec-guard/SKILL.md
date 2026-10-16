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

1. **Constitución de Estado & Read-First Ignition (SDD State Contract)**:
   - Obey `AGENTS.md` in the project root if present; otherwise follow `~/.agents/skills/spec-guard/_shared/memory-guard.md`.
   - On session start, run `sg context` to assimilate the strict glossary (`requirements.md §2`), mandatory tech stack (`design.md §1`), roles, out-of-scope, and RF progress before generating any code.
   - Never hand-edit generated or state files (`state.ini`). Always use `sg` CLI commands.

2. **Phase DAG & Human Gate Approval**:
   - `PLAN`:
     - **2-File Root Protocol (default)**: Define functional requirements (`### [ ] RF-XXX: ...`) with sequential criteria `CRIT-<rf>-<n>` (`[automated]` or `[manual]`) and explicit `Fuera del Alcance` (Out of Scope) in root `requirements.md`, and technical contracts in root `design.md`. Use `sg next-rf-id` and `sg init-change --change <name> --rf RF-XXX`.
     - **Legacy mode**: When `objective.md` is used, define specs in `.spec-guard/changes/{name}/` (`objective.md`, `design.md`, `specs/`) with `### Fuera del Alcance` and criteria `CRIT-01`, `CRIT-02`.
     - Run `sg validate-spec --change <name>` and `sg glossary-check` before requesting gate approval.
   - **Gate Mode `chat` (DEFAULT)**:
     - Mandatory STOP in chat. The agent is strictly forbidden from executing `commit` or coding in the same turn.
     - The agent asks the human for explicit approval in the conversation.
     - Once the human approves, run `sg commit --change <name> --next-phase execute --approval-text "<exact human response>"` to advance the DAG to `lock_phase = execute`.
   - **Gate Mode `strict` (Adversarial Security)**:
     - When `commit` returns exit code 5 (`EXIT_GATE_REQUIRED`), STOP immediately. Never attempt to run `sg plan-approve` or `sg plan-confirm`. Instruct the human to run:
       ```bash
       sg plan-approve --change <name>
       sg plan-confirm --change <name> --token <CODE>
       ```
       in their interactive physical terminal (`/dev/tty`).

3. **Low-Token Execution & Session Checkpoint (`SESSION.md`)**:
   - During `EXECUTE`, operate with the lightweight cursor `.spec-guard/SESSION.md` (~250 tokens). Do not reload massive specification files in every turn.
   - Always verify Git ancestry: `git merge-base --is-ancestor <base-commit> HEAD`.
   - Run `sg session-checkpoint --change <name> --action "..."` to record atomic progress.
   - Maintain TDD discipline: RED (failing test with `CRIT-XX`) -> GREEN (implementation) -> REFACTOR, and audit terms with `sg glossary-check`.

4. **Deterministic Criteria Verification Gate (`verify-crit` & `mark-rf`)**:
   - Before closing `VERIFY`, run:
     ```bash
     sg verify-crit --change <name>
     sg glossary-check --change <name>
     ```
   - If any automated criterion lacks a matching test in `tests/`, `test/`, `spec/`, or `src/`, `verify-crit` exits with code 2. The phase CANNOT be approved with orphaned criteria.
   - In 2-File Root Protocol projects, close each covered RF using `sg mark-rf --change <name> --rf RF-XXX`.
   - On approved verdict, the change is archived to `.spec-guard/changes/archive/YYYY-MM-DD-{name}/` and `.spec-guard/SESSION.md` is removed.

## CLI Commands Quick Reference

| Command | Purpose | Allowed Caller |
|---------|---------|----------------|
| `sg init [--force]` | Initialize `.spec-guard/` (incl. `bin/verify-crit.sh`), `AGENTS.md`, `CLAUDE.md` and root `requirements.md` / `design.md` (never overwritten) | Agent or Human |
| `sg context [--root <dir>]` | Project context JSON (Read-First Ignition: glossary, stack, roles, RFs) | Agent or Human |
| `sg next-rf-id [--module <rf>]` | Compute next sequential `RF-XXX` identifier | Agent or Human |
| `sg status --change <c>` | Inspect active phase, lock status, and transaction state | Agent or Human |
| `sg list-changes` | List all active changes with `lock_phase` and `txn_status` | Agent or Human |
| `sg begin --change <c> --phase <p>` | Start ACID transaction for phase (`plan`, `execute`, `verify`, `hotfix`) | Agent |
| `sg commit --change <c> --next-phase <p> [--approval-text <t>]` | Commit phase and advance DAG (exits 5 if gate required) | Agent |
| `sg rollback --change <c>` | Roll back in-progress transaction to idle | Agent |
| `sg checkpoint --change <c> --summary "..."` | Save persistent session summary block in `state.ini[Session]` | Agent |
| `sg session-checkpoint --change <c> [--action <a>]` | Atomically update low-token `.spec-guard/SESSION.md` cursor | Agent |
| `sg init-change --change <c> [--rf RF-101]` | Create a change scoped to root RFs (or legacy specs) | Agent |
| `sg rf-status [--change <c>]` | RF status from root `requirements.md` (totals, pending, scope) | Agent or Human |
| `sg mark-rf --change <c> --rf RF-101` | Close an RF: VERIFY only, in scope, all CRIT covered | Agent |
| `sg glossary-check [--change <c>] [--strict]` | Audit diff or paths against forbidden glossary synonyms | Agent or Human |
| `sg verify-crit --change <c>` | Deterministic audit of 1:1 `CRIT-XX` test traceability | Agent or Human |
| `sg validate-spec --change <c>` | Check structural validity and out-of-scope in specs | Agent or Human |
| `sg mark-task --change <c> --task-id <id>` | Mark a task as completed in `tasks.md` | Agent |
| `sg plan-approve` / `plan-confirm` | Human approval gate out-of-band via `/dev/tty` (strict mode) | **HUMAN ONLY** |
| `sg hotfix-init` / `hotfix-confirm` | Emergency bypass gate out-of-band via `/dev/tty` | **HUMAN ONLY** |
