# Changelog

## [3.0.0] - 2026-09-09

### Rebrand & SDD Engine
- **Rebranding oficial a SpecGuard (`spec-guard`)**: Evolución completa desde persistencia de estado genérica hacia un motor formal de **Specification-Driven Development (SDD)** con memoria transaccional.
- **Soporte de Directorio Dual**: Detección nativa y soporte prioritario de `.spec-guard/` manteniendo 100% de retrocompatibilidad con repositorios que usen `.state-guard/`.
- **CLI unificado**: Preservación del comando `sg` para ergonomía y cero ruptura de hábitos, con alias `spec-guard`.

### Arquitectura Canónica Modular (`spec_guard/`)
- Creación del paquete canónico `spec_guard`:
  - `spec_guard.core.locking`: POSIX write-locks atómicos con detección de locks huérfanos/estériles por PID y antigüedad.
  - `spec_guard.core.state_manager`: Motor transaccional ACID (`BEGIN`, `COMMIT`, `ROLLBACK`, `CHECKPOINT`, `STATUS`).
  - `spec_guard.cli`: Punto de entrada CLI con soporte de entorno `SPECGUARD_GATE_DIR` y salidas formateadas en JSON.
  - `spec_guard.mcp.server`: Servidor FastMCP nativo exponiendo 4 herramientas (`get_next_task`, `verify_phase_gate`, `mark_task_completed`, `get_active_changes`) y recursos URI de solo lectura (`spec://{change}/objective`, `spec://{change}/design`).
  - `spec_guard.daemon.hook_daemon`: Observador de filesystem para tareas derivadas con prohibición hardcodeada de mutar especificaciones de arquitectura.
- **Shims de Compatibilidad**: Mantenimiento de ejecutables delgados en `scripts/` (`sg.py`, `state_manager.py`, `_lock_utils.py`, `mcp_server.py`, `hook_daemon.py`).

### Seguridad & Hardening
- **Gate Lockout**: Implementación de revocación automática del token de aprobación humana y bloqueo de sesión tras 3 intentos fallidos consecutivos en `plan-confirm` y `hotfix-confirm`.
- **Validación de Terminal Física**: Verificación reforzada de `/dev/tty` con aislamiento de PTY.

### Distribución & Documentación
- `pyproject.toml` actualizado para `spec-guard` v3.0.0 con entrypoints `sg`, `spec-guard`, `spec-guard-mcp` y alias de compatibilidad `state-guard-mcp`.
- `scripts/install.sh`: Instalación unificada en `~/.agents/skills/spec-guard`, symlinks en `~/.local/bin/sg`, y registro en orquestadores (`GEMINI.md`, `opencode.jsonc`).
- `README.md` reescrito por completo como la documentación oficial de SpecGuard; purga de `README.old.md`.
- `MANUAL.md` actualizado con la arquitectura v3.0.0 y recursos MCP.

## [2.6.0] - 2026-07-30

### Spec-Driven Coding (Fase 4A)
- División de `plan.md` en los artefactos `objective.md` y `design.md`.
- Nuevo comando `sg validate-spec --change <nombre>` para validación estructural previa al gate humano.
- Actualización de todas las referencias de especificación en `phases/` y `skills/`.

### Agent Hooks (Fase 4B)
- Daemon de observabilidad de filesystem (`scripts/hook_daemon.py`) basado en `watchdog`.
- Esquema declarativo de reglas en `.state-guard/hooks.yaml.example`.
- Subcomandos de gestión `sg hooks-start`, `sg hooks-stop` y `sg hooks-status`.
- Log de auditoría append-only en `.state-guard/hooks.log.jsonl`.
- Modelo de confianza estricto que prohíbe la modificación automática de artefactos de arquitectura (`objective.md`, `design.md`) o gates humanos.

## [2.5.0] - 2026-07-28

### Integración (Fase 1)
- Detección de write-lock huérfano (PID + antigüedad), portada desde `context-guard`.
- Suite de tests unitarios granular en `tests/unit/` (34 tests).
- Corrección de harness de `concurrency_test.py` usando `pty.fork()` para independizarlo del estado TTY del desarrollador.

### Servidor MCP (Fase 2)
- Servidor MCP nativo (`scripts/mcp_server.py`) con 3 herramientas (`get_next_task`, `verify_phase_gate`, `mark_task_completed`).
- `pyproject.toml` para empaquetado e instalación vía `uvx` / `pip`.

### Documentación y distribución (Fase 3)
- `scripts/install.sh` incluye `sg.py` en el bootstrap en lugar de invocar `state_manager.py` directamente.
- `MANUAL.md`: nuevas secciones para la capa `sg.py`, Gate Humano out-of-band, Hotfix bypass y Servidor MCP.
- `context-guard` deprecado; sus funcionalidades clave han sido consolidadas en este repositorio.

## [2.4.0] - 2026-07-17

### Changed
- **Separación `phases/` vs `skills/`**: Las 8 fases core (invocación determinística por CLI) se mueven de `skills/<fase>/<fase>.md` a `phases/<fase>.md` como archivos planos. Las skills discoverable (invocación por agente vía frontmatter YAML) permanecen en `skills/<skill>/SKILL.md`.
- **Contratos compartidos divididos**: Los contratos específicos de fases (`transaction-protocol.md`, `persistence-contract.md`, `phase-common.md`, `context-injection.md`, `test-runner-detection.md`) se mueven a `phases/_shared/`. Los contratos globales del agente (`memory-guard.md`, `capabilities.md`, `convention.md`) permanecen en `skills/_shared/`.
- **`context-injection.md` → `phases/_shared/`**: Se determinó que su contenido es exclusivamente sobre fases (tabla de dependencias de las 8 fases, secuencia de ejecución inline/delegada). No aplica a skills discoverable.
- **`convention.md` → permanece en `skills/_shared/`**: Es un contrato global (incluye rutas de skills no-fase como hotfix, init, checkpoint; schema de state.ini).
- **`boot/boot.md` → `boot/SKILL.md`**: Corrige inconsistencia previa; boot es un meta-skill que debe seguir la convención SKILL.md con frontmatter.
- **Scripts de instalación actualizados**: `scripts/install.sh` y `tests/install_test.sh` ahora copian `phases/` y `skills/` por separado.

## [2.3.0] - 2026-07-17

### Changed
- **Fases core a Markdown plano**: Las 8 fases core (`explore`, `propose`, `spec`, `design`, `tasks`, `apply`, `verify`, `archive`) dejan de usar `SKILL.md` con frontmatter YAML y pasan a archivos `<fase>.md` en Markdown plano (ej. `skills/explore/explore.md`). El frontmatter YAML (`name`, `description`, `license`, `metadata`) se elimina; el contenido instructivo se conserva intacto.
- **Scripts de instalación actualizados**: `scripts/install.sh` y `tests/install_test.sh` ahora detectan ambos formatos (`<fase>.md` para fases core, `SKILL.md` para skills descubiertas por el agente).
- **Referencias actualizadas**: Se actualizaron todas las referencias en `_shared/memory-guard.md`, `_shared/phase-common.md`, `_shared/context-injection.md`, `skills/new/SKILL.md`, `skills/ff/SKILL.md` y `MANUAL.md`.

### Note
- `skills/skill-registry/` y las custom skills del usuario **mantienen** el formato `SKILL.md` con frontmatter, ya que son descubiertas dinámicamente por el agente (no invocadas determinísticamente).

## [2.2.0] - 2026-07-08

### Added
- **Auto-descubrimiento de Skills (Zero-Config)**: El script de instalación ahora lee dinámicamente el *frontmatter* YAML de cada `SKILL.md` para generar los *slash commands* al vuelo para OpenCode.

### Changed
- **Bootstrap Universal**: Se simplificó radicalmente la inyección de contexto. El contrato `memory-guard` ahora se inyecta directamente como prompt nativo en `opencode.jsonc` y `GEMINI.md`, eliminando la necesidad de archivos intermediarios.

### Removed
- Se eliminó por completo el directorio `integrations/` y todos sus archivos estáticos (`AGENTS.md`, JSONs y comandos Markdown heredados), reduciendo drásticamente la duplicación de código.
- 
## [2.1.1] - 2026-07-08

### Changed
- **Refactor de Naming**: Se eliminaron los prefijos de todos los directorios de skills, archivos de comandos e integraciones.
- **Actualización de Rutes**: Se actualizaron todas las referencias internas, scripts y prompts para reflejar los nuevos nombres de comandos (ej. `/split` en lugar de `/agentify-split`).
- **Skills Base**: Se conservaron los nombres de los archivos base en `_shared/` para distinguirlos de los comandos ejecutables.

### Fixed
- Se corrigieron rutas rotas causadas por el renombrado masivo en `scripts/install.sh`, `scripts/cleanup.sh` y comandos internos.

## [2.1.0] - 2026-07-08

### Changed
- **Migración de Estado**: Se reemplazó `state.yaml` por `state.ini` para mejorar la compatibilidad nativa con bash.
- **Gestión de Locks**: Se introdujo `_lock_utils.py` aislando la lógica de locks del negocio, resolviendo conflictos de concurrencia.
- **Límite de Tokens**: Se implementó un límite duro de ~2000 caracteres en el `session_summary` de `state-guard-checkpoint` para evitar el agotamiento de contexto.
- **Simplificación de Instalación**: Se eliminaron `packager.py` e `install.ps1`. La inyección ahora la maneja exclusivamente `install.sh` con marcadores unificados (`<!-- state-guard:begin -->`) para todos los modelos.

### Fixed
- Se diferenciaron los exit codes en `state_manager.py` para un mejor manejo de errores en el orquestador.
- Se agregó el recordatorio explícito de transacciones (BEGIN/COMMIT) en las 8 skills de fase para evitar la deriva de memoria.

## [2.0.3]

### Changed — Arquitectura: De Despachador CLI a Harness de Memoria Transaccional

- **Memory Guard**: Nuevo contrato unificado (`_shared/memory-guard.md`) que reemplaza a `core.md`, `delegation.md` y `state.md`. El agente ahora ejecuta fases inline con delegación inteligente en lugar de despachar todo a sub-agentes CLI.
- **Transaction Protocol**: Nuevo protocolo de transacciones (`_shared/transaction-protocol.md`) con ciclo BEGIN → EXECUTE → COMMIT/ROLLBACK. Reemplaza el Return Envelope (`### Lock Phase`) por escritura directa en `state.yaml`.
- **state.yaml v2**: Schema extendido con campos transaccionales (`schema_version`, `txn_status`, `txn_phase`, `txn_started_at`). Migración automática v1→v2 vía `fix`.
- **Capabilities Adapter**: Nuevo módulo unificado (`_shared/capabilities.md`) que reemplaza las 4 integraciones separadas con detección automática del agente host.
- **Context Injection**: Simplificado `context.md` → `context-injection.md` eliminando la distinción orquestador/sub-agente.
- **Presupuestos de tokens flexibles**: Eliminados los límites rígidos de palabras por fase (400 proposal, 650 spec, 800 design, 530 tasks).
- **Todas las skills de fase** (explore, propose, spec, design, tasks, apply, verify, archive): Refactorizadas con sección de Transacción integrada, sin Return Envelope, sin dependencia del orquestador.
- **Meta-skills** (new, continue, ff): Refactorizadas para ejecución inline directa con transacciones secuenciales.
- **checkpoint**: Ahora opera en modo dual (automático post-COMMIT + manual bajo demanda).
- **fix**: Añadida migración v1→v2 y resolución de transacciones incompletas.
- **status**: Muestra `txn_status` en la tabla de estado.
- **Integraciones**: OpenCode y Antigravity CLI reducidas a stubs mínimos que cargan `memory-guard.md`. Se eliminó por completo la integración obsoleta de `gemini-cli` y se renombró `antigravity` a `antigravity-cli` en todos los instaladores, scripts y documentación.
- **install.sh / cleanup.sh**: Actualizados para soportar exclusivamente `antigravity-cli` y retirar la opción de `gemini-cli`.
- **Estructura del agente**: Inicialización de la estructura del agente en el proyecto (`/init`) creando `openspec/config.yaml` y generando el índice de habilidades `.state-guard/skill-registry.md`.

### Removed

- `_shared/core.md` — Absorbido en `memory-guard.md`
- `_shared/delegation.md` — Absorbido en `memory-guard.md`
- `_shared/state.md` — Absorbido en `transaction-protocol.md`
- `_shared/execution-contract.md` — Absorbido en `transaction-protocol.md`
- `_shared/commands.md` — Absorbido en `memory-guard.md`
- `_shared/context.md` — Reemplazado por `context-injection.md`

### Added

- `_shared/memory-guard.md` — Contrato unificado de Memory Guard
- `_shared/transaction-protocol.md` — Protocolo de transacciones con ciclo BEGIN/COMMIT/ROLLBACK
- `_shared/capabilities.md` — Adapter de capacidades por agente host
- `_shared/context-injection.md` — Protocolo simplificado de inyección de contexto
- `integrations/system-prompt.md` — Template unificado de system prompt
