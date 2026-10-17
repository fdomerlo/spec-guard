---
name: spec-guard
description: >-
  Specification-Driven Development (SDD) engine and transactional state governor for code agents.
  Use whenever the user asks to build, plan, implement, verify, or scaffold an application or
  feature; for multi-step coding tasks; to resume work after a lost, crashed, or compacted session;
  or in any project that contains a `.spec-guard/` (or legacy `.state-guard/`) directory. Drives the
  `sg` CLI so that a change follows the strict 3-phase DAG: PLAN -> EXECUTE -> VERIFY with out-of-band
  human approval gate, 1:1 CRIT-XX criteria test traceability, and transactional session cursor in state.ini.
---

# SpecGuard: Specification-Driven Development (SDD) Engine

`sg` (long form: `spec-guard`) is a transactional state manager and SDD governor. A change moves through fixed phases in a directed acyclic graph (DAG):

```text
PLAN --approval gate (chat or strict /dev/tty)--> EXECUTE --TDD + tasks done--> VERIFY --verify-crit--> ARCHIVE
```

## Mandatory Lifecycle & Gate Rules

1. **State Constitution & Read-First Ignition (SDD State Contract)**:
   - Obey `AGENTS.md` in the project root if present.
   - On session start, run `sg context` and `sg list-changes` (or `sg status --change <name>`) to assimilate the strict glossary (`requirements.md §2`), mandatory tech stack (`design.md §1`), roles, out-of-scope, RF progress, and transactional state in `state.ini` before generating any code.
   - Never hand-edit generated or state files (`state.ini`). Always use `sg` CLI commands.

2. **Doubt-Driven Spec Intake & Phase `PLAN`**:
   - **5-Step Spec Intake Protocol**:
     1. **INTAKE**: Run `sg context` and `sg rf-status` to inspect existing RFs, glossary, and stack.
     2. **CONFLICT SCAN**: Check for contradictions or overlaps with existing `RF-XXX` and `Out of Scope`.
     3. **ASK / DOUBT**: If requirements, edge cases, or business rules are ambiguous, ask concise questions in chat before assuming.
     4. **DRAFT**: Compute the next sequential ID with `sg next-rf-id` and draft the requirement (`### [ ] RF-XXX: ...`) with sequential criteria `CRIT-<rf>-<n>` (`[automated]` or `[manual]`) and explicit `Fuera del Alcance` in root `requirements.md`, plus technical contracts in root `design.md` (or `objective.md` + `design.md` in legacy mode).
     5. **REVIEW**: Open the change with `sg init-change --change <name> [--rf RF-XXX]`, run `sg begin --change <name> --phase plan`, and validate with `sg validate-spec --change <name>` and `sg glossary-check`.
   - **Gate Mode `chat` (DEFAULT)**:
     - Mandatory STOP in chat. The agent is strictly forbidden from executing `commit` or coding in the same turn.
     - Present the plan summary and ask the human for explicit approval.
     - Once the human approves, run `sg commit --change <name> --next-phase execute --approval-text "<exact human response>"` to advance the DAG to `lock_phase = execute`.
   - **Gate Mode `strict` (Adversarial Security)**:
     - When `commit` returns exit code 5 (`EXIT_GATE_REQUIRED`), STOP immediately. Never attempt to run `sg plan-approve` or `sg plan-confirm`. Instruct the human to run:
       ```bash
       sg plan-approve --change <name>
       sg plan-confirm --change <name> --token <CODE>
       ```
       in their interactive physical terminal (`/dev/tty`).

3. **Transactional Execution & Session Cursor (`state.ini[Session]`)**:
   - Start execution with `sg begin --change <name> --phase execute` (which records `base_commit` and seals `spec_hash` SHA-256 in `state.ini[Transaction]`).
   - Operate using `state.ini` via `sg status --change <name>`. Do not reload massive specification files in every turn.
   - Maintain TDD discipline: RED (failing test named after `CRIT-XX`) -> GREEN (minimal implementation) -> REFACTOR, and audit terms with `sg glossary-check`.
   - Run `sg session-checkpoint --change <name> --action "..."` (or `sg checkpoint --change <name> --summary "..."`) to record atomic progress and verify Git ancestry (`git merge-base --is-ancestor <base-commit> HEAD`) directly inside `state.ini[Session]`.

4. **Deterministic Criteria Verification Gate (`VERIFY` & Archive)**:
   - Before closing `VERIFY`, run:
     ```bash
     sg verify-crit --change <name> --run-tests
     sg glossary-check --change <name>
     ```
   - `verify-crit` validates 1:1 `CRIT-XX` test traceability, cryptographic specification integrity (`spec_hash`), git commit history for `--no-verify` bypasses since `base_commit`, and (with `--run-tests`) test suite execution. If any check fails, `verify-crit` exits with code 2.
   - **Definition of Done**:
     - All automated `CRIT-XX` criteria have passing tests and 0 glossary violations.
     - Code adheres strictly to the declared stack in `design.md §1` and scope boundaries.
     - Working tree is clean and committed with Conventional Commits referencing `<change>` or `RF-XXX`.
   - **Security Checklist**:
     - No hardcoded secrets, tokens, credentials, or private keys in code or tests.
     - External inputs validated and parameterized queries/ORM used for persistence.
     - Authentication, authorization, and error handling do not leak sensitive internals.
   - In 2-File Root Protocol projects, close each covered RF using `sg mark-rf --change <name> --rf RF-XXX`.
   - On approved verdict, archive the change to `.spec-guard/changes/archive/YYYY-MM-DD-{name}/`.

## CLI Commands Quick Reference

| Command | Purpose | Allowed Caller |
|---------|---------|----------------|
| `sg init [--force]` | Initialize `.spec-guard/` (incl. `bin/verify-crit.sh`), `AGENTS.md`, `CLAUDE.md` and root `requirements.md` / `design.md` (never overwritten) | Agent or Human |
| `sg context [--root <dir>]` | Project context JSON (Read-First Ignition: glossary, stack, roles, RFs) | Agent or Human |
| `sg next-rf-id [--module <rf>]` | Compute next sequential `RF-XXX` identifier | Agent or Human |
| `sg status --change <c>` | Inspect active phase, lock status, transaction state, and `[Session]` cursor in `state.ini` | Agent or Human |
| `sg list-changes` | List all active changes with `lock_phase` and `txn_status` | Agent or Human |
| `sg begin --change <c> --phase <p>` | Start ACID transaction for phase (`plan`, `execute`, `verify`, `hotfix`) and seal `spec_hash` in `execute` | Agent |
| `sg commit --change <c> --next-phase <p> [--approval-text <t>]` | Commit phase and advance DAG (exits 5 if gate required) | Agent |
| `sg rollback --change <c>` | Roll back in-progress transaction to idle | Agent |
| `sg checkpoint --change <c> --summary "..."` | Save persistent session summary block in `state.ini[Session]` | Agent |
| `sg session-checkpoint --change <c> [--action <a>]` | Atomically update structured session cursor and Git ancestry check in `state.ini[Session]` | Agent |
| `sg init-change --change <c> [--rf RF-101]` | Create a change scoped to root RFs (or legacy specs) | Agent |
| `sg rf-status [--change <c>]` | RF status from root `requirements.md` (totals, pending, scope) | Agent or Human |
| `sg mark-rf --change <c> --rf RF-101` | Close an RF: VERIFY only, in scope, all CRIT covered | Agent |
| `sg glossary-check [--change <c>] [--strict]` | Audit diff or paths against forbidden glossary synonyms | Agent or Human |
| `sg verify-crit --change <c> [--run-tests]` | Deterministic audit of 1:1 `CRIT-XX` test traceability, `spec_hash`, git bypasses, and test runner | Agent or Human |
| `sg validate-spec --change <c>` | Check structural validity and out-of-scope in specs | Agent or Human |
| `sg mark-task --change <c> --task-id <id>` | Mark a task as completed in `tasks.md` | Agent |
| `sg install-hooks [--force]` | Install blocking `pre-commit` and `commit-msg` Git hooks | Human or Agent |
| `sg plan-approve` / `plan-confirm` | Human approval gate out-of-band via `/dev/tty` (strict mode) | **HUMAN ONLY** |
| `sg hotfix-init` / `hotfix-confirm` | Emergency bypass gate out-of-band via `/dev/tty` | **HUMAN ONLY** |
