# Manual Técnico — SpecGuard

Este manual cubre la arquitectura técnica, configuración y flujos avanzados del sistema **SpecGuard v3.0.0**, el motor de Specification-Driven Development (SDD) y persistencia transaccional para agentes de código. SpecGuard soporta nativamente la estructura `.spec-guard/` a la vez que mantiene compatibilidad hacia atrás completa con proyectos que utilicen `.state-guard/`.

## Arquitectura Unificada Single-Skill

### Contrato Unificado (`AGENTS.md` + `SKILL.md`)

SpecGuard opera mediante un contrato SDD auto-contenido (`AGENTS.md` y `SKILL.md` en la raíz del repositorio) gobernado por el motor CLI `sg`:

```
Contrato SDD (AGENTS.md / SKILL.md)
    │
    ├── Read-First Ignition (sg context + sg status)
    │
    ├── Ejecuta → plan     (Doubt-Driven Spec Intake → validate-spec → gate humano → commit)
    ├── Ejecuta → execute  (begin [sella spec_hash] → TDD → session-checkpoint en state.ini[Session])
    └── Ejecuta → verify   (verify-crit [--run-tests] → glossary-check → mark-rf → archive)
```

### Componentes del Sistema

| Componente | Propósito |
|---------|-----------|
| `SKILL.md` | Skill canónica auto-contenida en la raíz: ciclo DAG (`PLAN -> EXECUTE -> VERIFY`), *Doubt-Driven Spec Intake*, *Definition of Done* y *Security Checklist* |
| `install.sh` | Instalador y desinstalador (`--uninstall`) universal en la raíz del repositorio |
| `spec_guard/templates/` | Plantillas para inicialización de proyectos (`AGENTS.md.template`, `requirements.md.template`, `design.md.template`, `verify-crit.sh`) |
| `spec_guard/core/state_manager.py` | Máquina de estados ACID sobre `state.ini` con locks POSIX (`fcntl.flock`), `spec_hash` SHA-256 y cursor `[Session]` |
| `spec_guard/core/root_docs.py` | Parser del *2-File Root Protocol* (`requirements.md` y `design.md`), `RF-XXX`, `CRIT-XX` y Glosario Estricto |
| `spec_guard/cli.py` | Interfaz CLI (`sg`) con salida JSON determinista, auditoría `verify-crit` e instalación de hooks Git bloqueantes |

---

## State Machine Transaccional

### Estructura de state.ini

El archivo `state.ini` es el núcleo del sistema de estados. Se encuentra en:

```text
.spec-guard/changes/{nombre-del-cambio}/state.ini
```

**Schema (formato INI, manejado por `state_manager.py`):**

```ini
[Metadata]
last_updated = 2026-07-02T10:30:00.000000
schema_version = 2

[Transaction]
txn_status = idle          ; idle | in_progress
txn_phase = None           ; fase actual si in_progress, sino None
txn_started_at = None
base_commit = 0d9d308...   ; SHA capturado en BEGIN para validación de ancestría Git

[Graph]
current_phase = plan       ; Descriptivo: última fase completada
lock_phase = execute       ; Prescriptivo: única fase autorizada a ejecutarse AHORA
completed_phases = plan
pending_phases = execute, verify

[Session]
session_summary = ...      ; opcional — bloque generado por checkpoint, ≤500 tokens (enforced en código: máx 2000 chars)
```

### Protocolo de Transacciones (transaction-protocol.md)

Cada fase del agente se ejecuta como una transacción ACID atómica gobernada estrictamente por `transaction-protocol.md`:

```text
IDLE → BEGIN → EXECUTE → COMMIT (éxito) o ROLLBACK (fallo) → IDLE
```

El ciclo de vida de la transacción exige la actualización de los campos transaccionales obligatorios en `state.ini`:

| Paso | Qué ocurre |
|------|-----------|
| **BEGIN** | Registra el inicio marcando `txn_status: in_progress`, `txn_phase: {fase}`, `base_commit` y capturando el timestamp actual en `txn_started_at` dentro de `state.ini`. |
| **EXECUTE** | El agente ejecuta la fase encomendada, persistiendo los artefactos generados (código, diseño, specs) en disco de forma segura. |
| **COMMIT** | Consolida la operación. Actualiza atómicamente `current_phase` y `lock_phase`, mueve la fase a `completed_phases`, y reinicia `txn_status: idle` y `txn_phase: None`. |
| **ROLLBACK** | Si ocurre un fallo, aborta restaurando `txn_status: idle` y `txn_phase: None`, liberando el lock de fase y dejando sin alterar el registro de fases para preservar la integridad estructural del DAG. |

**Anti-batching por protocolo**: Cada fase requiere su propio ciclo BEGIN → COMMIT ineludiblemente. Al ser `txn_phase` un valor escalar y no una lista, es mecánicamente imposible ejecutar múltiples fases bajo una misma transacción.

### Mitigación de Fuga de Contexto

Como mecanismo crucial post-COMMIT, `transaction-protocol.md` establece un procedimiento para la **mitigación de fuga de contexto**. 
Una vez que el estado es exitosamente consolidado en `state.ini`, el protocolo exige emitir una **advertencia de purga de chat**. Esta instrucción sirve para alertar al usuario y al agente sobre la necesidad de limpiar el historial de la conversación (o disparar una recarga de contexto / inicio de un nuevo sub-hilo) antes de proceder con la siguiente fase de desarrollo. Esto erradica la acumulación de directivas obsoletas, evitando severas "alucinaciones" durante transiciones prolongadas.

### Recovery Automático

Al detectar un `state.ini` con `txn_status: in_progress` y `lock_state: STALE` (crash durante ejecución):

1. Verifica si el artefacto de `txn_phase` se persistió en disco
2. Si **SÍ** → ejecuta COMMIT (la fase se completó pero el estado no se persistió)
3. Si **NO** → ejecuta ROLLBACK (restaura `txn_status: idle` sin modificar phases)

### Propiedades ACID

**Atomicidad (Atomicity):** Cada fase se completa completamente o no se completa. El COMMIT solo ocurre después de que el artefacto se persistió en disco exitosamente.

**Consistencia (Consistency):** El schema de `state.ini` v2 está validado. Las transiciones siguen un orden estricto definido por el grafo de dependencias y los campos transaccionales garantizan detección de estado intermedio.

**Aislamiento (Isolation):** Cada cambio tiene su propio `state.ini` y `.lock` POSIX. Múltiples cambios pueden ejecutarse en paralelo sin interferir entre sí.

**Durabilidad (Durability):** El estado persiste en el filesystem del proyecto. Sobrevive a recargas de sesión, compactaciones de contexto y reinicios del IDE. Los campos transaccionales permiten recovery automático.

### Prevención de Colisiones

El Memory Guard detecta cambios concurrentes mediante:

1. Lectura del `state.ini` vía `sg status` antes de cada transacción
2. Verificación del campo `lock_phase` (única fase autorizada) y `lock_state` (`FREE` | `ACTIVE` | `STALE`)
3. Detección de transacciones en curso (`txn_status: in_progress`)

### Migración v1 → v2

> **Nota histórica:** Los archivos `state.ini` actuales usan el schema v2 basado en INI con 3 fases (`plan`, `execute`, `verify`) y secciones `[Metadata]`, `[Transaction]`, `[Graph]`, `[Gate]`, `[Scope]` y `[Session]`. Si se detecta un `state.ini` con `schema_version = 1`, `sg migrate --change <c>` o `sg begin` lo migra automáticamente a v2.

---

## Capa `sg` (`spec_guard.cli`) — CLI, Gate Humano y Hotfix

`sg` (`spec_guard/cli.py`) es el único punto de entrada CLI de alto nivel para la interacción con SpecGuard. Actúa como un wrapper seguro que encapsula las llamadas a `state_manager.py`, formateando la salida en JSON estándar y administrando los mecanismos de autorización humana.

### Arquitectura de `sg`

- **Wrapper JSON (100% Python Stdlib)**: Todas las operaciones devuelven respuestas JSON estructuradas y respetan los códigos de salida numéricos sin depender de paquetes externos.
- **Acceso Exclusivo**: Mutar el manifiesto `state.ini` debe realizarse a través de `sg` para asegurar que las validaciones de esquema, bloqueos transaccionales y autorizaciones de gate se apliquen de forma consistente.

### Modos de Compuerta Humana (`gate.mode: chat | strict`)

El Gate Humano asegura que los agentes no puedan avanzar de la fase de `plan` a `execute` sin la confirmación explícita de un usuario:

1. **Modo `chat` (Predeterminado — Cero Fricción)**:
   - El agente presenta el plan y ejecuta un **STOP** obligatorio en la conversación.
   - Una vez que el usuario aprueba en el chat, el agente ejecuta `sg commit --change <nombre> --next-phase execute --approval-text "<respuesta textual del humano>"`.
   - El middleware verifica que `--approval-text` contenga una expresión de aprobación válida y la registra en `[Gate].plan_approved_by`.
2. **Modo `strict` (Out-of-Band en `/dev/tty`)**:
   - Configurado con `gate.mode: strict` en `.spec-guard/config.yaml` (o `SPECGUARD_GATE_MODE=strict`).
   - El comando `sg plan-approve --change <nombre>` genera un token aleatorio impreso **únicamente** en la terminal física (`/dev/tty`) y almacena solo su hash SHA-256 fuera del workspace (`~/.spec-guard-gate/`).
   - El humano confirma en su terminal interactiva con `sg plan-confirm --change <nombre> --token <CODIGO>` (con revocación automática tras 3 intentos fallidos).

### Flujo de Hotfix Bypass

En situaciones de emergencia donde un error debe ser corregido sin pasar por la fase completa de planificación:

1. El humano inicia un hotfix ejecutando `sg hotfix-init --change <nombre> --reason "..."`.
2. Al igual que el gate en modo `strict`, este comando imprime un token en `/dev/tty`.
3. El humano confirma con `sg hotfix-confirm --change <nombre> --token <CODIGO>`.
4. Esto registra la autorización del hotfix en `[Gate]` indicando la razón y avanza `lock_phase` directamente a `execute`.

### Integración de Hooks de Git (`sg install-hooks`)

El comando `sg install-hooks` instala tres hooks en `.git/hooks/`:
- **`pre-commit` (Bloqueante)**: Impide commitear archivos de código mientras exista un cambio activo en `lock_phase = plan` (permitiendo únicamente `.md`, `.txt`, `.markdown` y `.spec-guard/`).
- **`commit-msg` (Bloqueante)**: Exige formato Conventional Commits y, durante `lock_phase = execute`, obliga a que el mensaje referencie el `<change>` activo o un identificador `RF-XXX`.
- **`post-commit` (Informativo)**: Ejecuta `sg status` tras cada commit para mostrar el estado actual del manifiesto.

### Subcomandos Principales de `sg`

- **Ignición de Contexto (`sg context`)**: Extrae en JSON el glosario estricto, el stack obligatorio, los roles, el *Out of Scope* y el progreso de RFs desde los documentos raíz (`requirements.md` y `design.md`).
- **Validación de Especificaciones (`sg validate-spec`)**: Valida estructuralmente los documentos raíz (`requirements.md` y `design.md`) o `objective.md` y `design.md` (modo legacy) comprobando que no contengan preguntas abiertas bloqueantes (`[!]`), placeholders sin resolver ni secciones faltantes (incluyendo `Fuera del Alcance` / `Out of Scope`).
- **Auditoría de Glosario (`sg glossary-check`)**: Contrasta el diff de Git o rutas específicas contra la tabla de términos permitidos y sinónimos prohibidos de `requirements.md §2`.
- **Trazabilidad de Criterios (`sg verify-crit`)**: Extrae determinísticamente los criterios `CRIT-XX` de `requirements.md` (RFs en scope) o `tasks.md`/`design.md`/`objective.md` y comprueba en `tests/`, `test/`, `spec/`, `src/` que cada criterio `[automated]` cuente con un test asociado. Retorna exit code 0 si todos están cubiertos, o código 2 (bloqueante) si hay criterios huérfanos.
- **Cierre Determinista de RFs (`sg mark-rf`)**: Durante la fase `verify`, valida que todos los criterios automatizados del RF estén cubiertos por tests y marca `### [x] RF-XXX` en `requirements.md`.
- **Cursor de Sesión Transaccional (`sg session-checkpoint`)**: Actualiza atómicamente `state.ini[Session]` y valida la ancestría Git (`git merge-base --is-ancestor <base-commit> HEAD`).
- **Bootstrap Universal (`sg init`)**: Inicializa `requirements.md`, `design.md`, `AGENTS.md`, `CLAUDE.md` y `.spec-guard/` (incluyendo `.spec-guard/bin/verify-crit.sh`).
- **Gestión de Agent Hooks**: `sg hooks-start`, `sg hooks-stop` y `sg hooks-status` permiten iniciar, detener y verificar el estado del daemon de observabilidad de filesystem.

### Tabla de Códigos de Salida (Exit Codes)

| Código | Constante | Descripción |
|--------|-----------|-------------|
| `0` | `EXIT_OK` | Operación exitosa. |
| `1` | `EXIT_GENERIC` | Error genérico o `state.ini` no encontrado. |
| `2` | `EXIT_LOCK_CONFLICT` / `CRIT_UNCOVERED` | Conflicto de lock activo por otra sesión o criterios `CRIT-XX` sin test en `verify-crit`. |
| `3` | `EXIT_BAD_TRANSITION` | Transición inválida en el DAG de fases (no reintentar). |
| `4` | `EXIT_VALIDATION` | Datos de entrada inválidos, violación crítica de glosario o spec incompleto. |
| `5` | `EXIT_GATE_REQUIRED` | Gate humano no cumplido o token incorrecto/bloqueado. |

---

## Configuración con config.yaml

### Ubicación

```text
.spec-guard/config.yaml
```

### Glosario de Configuraciones

| Campo | Descripción |
|-------|-------------|
| `schema` | Versión del schema del agente. Valor actual: `spec-driven` |
| `gate.mode` | Modo de compuerta humana: `chat` (default, cero fricción) o `strict` (tokens en `/dev/tty`) |
| `glossary.severity` | Severidad de sinónimos prohibidos en código general: `warning` (default) o `critical` |
| `rules` | Reglas específicas por fase (`plan`, `execute`, `verify`, `archive`) |

### Convenciones de Nomenclatura

El sistema usa **kebab-case** para los nombres de cambios transaccionales:

```yaml
schema: spec-driven

gate:
  mode: chat

rules:
  change_naming: kebab-case
  execute:
    - Seguir patrones y convenciones existentes
  verify:
    - build_command: pytest
    - Criterios CRIT-XX automatizables deben contar con tests
```

### Instalación y Desinstalación Universal

El script raíz `install.sh` administra la instalación y desinstalación del sistema:
- `bash install.sh`: Instala el paquete `spec_guard`, la skill canónica `SKILL.md`, los enlaces simbólicos (`sg`, `spec-guard`, `sg-verify-crit`, `sg-init`) y las integraciones de orquestadores.
- `bash install.sh --uninstall`: Desinstala skills, symlinks y limpia las inyecciones de configuración de SpecGuard en los diferentes agentes de IA (`~/.agents/skills/spec-guard`, `~/.gemini/GEMINI.md`, `opencode.jsonc`).
- `tests/install_test.sh`: Suite de tests de integración para validar el correcto funcionamiento del script de instalación.

### Parámetro build_command / test_command y Compuertas Físicas

Define el comando para ejecutar pruebas o build durante la fase de verificación:

```yaml
project:
  test_command: "pytest"  # o "npm test", "cargo test", etc.
rules:
  verify:
    build_command: "pytest"
```

Si no se define, `sg verify-crit --change <nombre> --run-tests` autodetectará el test runner del proyecto (`tests/run_tests.py`, `pytest`, `npm test`, `cargo test`, `go test ./...`).

Además, **SpecGuard** incorpora tres compuertas determinísticas de integridad física:
1. **Hooks Git Bloqueantes (`sg install-hooks`)**: Instala `.git/hooks/pre-commit` (bloquea commits de archivos de código mientras un cambio esté en `lock_phase = plan`) y `.git/hooks/commit-msg` (exige formato Conventional Commits y referencia al `<change>` o `RF-XXX` durante `execute`).
2. **Inmutabilidad de Especificación (`spec_hash`)**: Al ejecutar `sg begin --phase execute`, se registra el hash SHA-256 (`spec_hash`) de las especificaciones en `state.ini`. Si los requisitos o el diseño se alteran durante la implementación sin reabrir `plan`, `sg verify-crit` rechaza la verificación (código `2`).
3. **Auditoría Anti-Bypass (`--no-verify`) y `--run-tests`**: `sg verify-crit` inspecciona `git log <base_commit>..HEAD` para detectar commits de código que hayan omitido la referencia al cambio/RF y permite ejecutar la suite de tests real con `--run-tests`.

---

## Flujos Avanzados

### /split — División de Proposals

El comando `/split` analiza una proposal monolítica y la divide en sub-cambios manejables.

**Cuándo usarlo:**

- La proposal abarca múltiples dominios
- El alcance es demasiado grande para una sola iteración
- Hay dependencias entre funcionalidades que deberían implementarse por separado

**Cómo funciona:**

1. Lee la proposal original
2. Analiza los requisitos y alcance
3. Identifica puntos de división naturales
4. Genera múltiples proposals más pequeñas

**Ejemplo de uso:**

```text
/split mi-cambio-grande
```

### /ff — Avance Rápido (Fast-Forward)

El comando `/ff` permite ejecutar secuencialmente las fases de planificación y ejecución (`plan`, `execute`) como transacciones independientes (el gate humano de `plan` sigue siendo obligatorio).

**Cuándo usarlo:**

- Al iniciar un cambio nuevo bien definido donde deseas avanzar automáticamente de `plan` a `execute` tras aprobar el gate.

**Anti-Batching Transaccional:**
A diferencia de pedirle al LLM que "haga todas las fases de una vez" en un solo prompt (lo que corrompe el DAG), `/ff` ejecuta **2 transacciones secuenciales independientes** (`plan` → `execute`). Cada fase tiene su propio ciclo BEGIN → COMMIT, y si el agente crashea entre ambas transacciones, el Recovery Protocol continúa automáticamente desde donde quedó.

### /checkpoint — Guardado de Estado

El comando `/checkpoint` genera un **bloque YAML estructurado** analizando proactivamente
`tasks.md` y `design.md` del cambio activo. El resultado se guarda en el campo `session_summary`
de `state.ini`, posibilitando una recuperación de contexto eficiente (**Warm-Boot**).

**Dos modos de operación:**

1. **Automático** (post-COMMIT): El protocolo de transacción genera un `session_summary` compacto después de cada fase. Esto es suficiente para la mayoría de los casos.
2. **Manual** (`/checkpoint`): Genera un checkpoint de alta fidelidad con análisis proactivo de todos los artefactos. Útil antes de operaciones riesgosas o para refrescar el contexto.

El checkpoint es **agnóstico al DAG**: puede ejecutarse en cualquier momento sin modificar
`lock_phase`, `current_phase` ni el flujo de fases activo.

**Cuándo usarlo manualmente:**

- Antes de realizar operaciones riesgosas
- Al interrumpir un lote de `execute` para preservar el estado
- Al restablecer el contexto de trabajo forzando al LLM a recargar el panorama

**Ejemplo de uso:**

```text
/checkpoint
```

### Archive (Paso final de VERIFY — no es un comando separado)

El archivado de un cambio ocurre automáticamente dentro de la fase `verify`, una vez que el veredicto es APROBADO. No existe un slash command `/archive` independiente — invocar `/continue` cuando `lock_phase=verify` ejecuta todo el flujo de verificación y archivado en una sola operación.

**Requisito previo para que el archivado no falle:**

1. Ejecutar la fase `verify` (`/continue` con `lock_phase=verify`).
2. Antes de que `verify` pueda archivar, el árbol de trabajo git debe estar limpio — todos los cambios de código commiteados (`git add . && git commit -m "..."`).

En el **2-File Root Protocol**, el archivado cierra cada RF cubierto ejecutando `sg mark-rf` y mueve el directorio del cambio a `.spec-guard/changes/archive/YYYY-MM-DD-{nombre}/`. En modo legacy, fusiona las specs delta (`changes/{nombre}/specs/`) en `.spec-guard/specs/`.

### /review — Auditoría Estática

El comando `/review` compara el código implementado contra las especificaciones sin ejecutar tests.

**Cuándo usarlo:**

- Antes de un merge a main
- Como revisión previa a la verificación completa
- Para identificar desviaciones de diseño

**Qué analiza:**

- Cumplimiento de requisitos de specs
- Consistencia con decisiones de diseño
- Patrones de código aplicados correctamente

**Ejemplo de uso:**

```text
/review mi-cambio
```

### /rollback — Revertir un Cambio

El comando `/rollback` purga la carpeta del cambio y restaura los archivos modificados desde git.

**⚠️ ADVERTENCIA: Pérdida de Trabajo**

Este comando **elimina permanentemente** todo el trabajo no commiteado en el directorio del cambio. Antes de ejecutar:

1. Confirma que no hay cambios sin guardar
2. Ejecuta `git status` para verificar el estado
3. Solo usar cuando el cambio no tiene solución o debe reiniciarse completamente

**Ejemplo de uso:**

```text
/rollback mi-cambio
```

---

## Estructura de Archivos

```text
<raíz-del-proyecto>/
├── requirements.md                ← PRD raíz (Visión, Glosario Estricto, Roles, RF-XXX, Out of Scope)
├── design.md                      ← SAD raíz (Stack Obligatorio, Modelo de Datos, Endpoints, Reglas)
├── AGENTS.md                      ← Contrato universal de agentes SDD
├── CLAUDE.md                      ← Puntero @AGENTS.md
└── .spec-guard/
    ├── config.yaml                ← Configuración del proyecto (gate.mode, glossary, rules)
    ├── bin/
    │   └── verify-crit.sh         ← Script local de auditoría determinista CRIT-XX
    ├── specs/                     ← Specs actuales (modo legacy)
    │   └── {dominio}/
    │       └── spec.md
    └── changes/                   ← Cambios activos y archivados
        ├── archive/
        │   └── YYYY-MM-DD-{change}/
        └── {change-name}/
            ├── state.ini          ← Estado del DAG + Gate + Scope + Session (manejado por sg)
            ├── .lock              ← Lock POSIX de fase (manejado por middleware)
            ├── .write-lock        ← Mutex de escritura de archivo (manejado por middleware)
            ├── objective.md       ← Objetivo y Out of Scope (modo legacy)
            ├── design.md          ← Diseño técnico del cambio (modo legacy)
            ├── specs/             ← Specs delta (modo legacy)
            ├── tasks.md           ← Checklist de tareas con trazabilidad CRIT-XX
            └── verify-report.md   ← Reporte de verificación
```

---

## Convenciones de Estilo

### Idioma

Siguiendo el contrato `AGENTS.md`:

- **Código fuente, comentarios, mensajes de error y mensajes de commit**: **Inglés (English)**.
- **Conversación en chat con el humano**: Idioma preferido del usuario (español por defecto en este entorno).
- **Artefactos de especificación y reportes (`requirements.md`, `design.md`, `objective.md`, `tasks.md`)**: Español (castellano), respetando estrictamente los términos canónicos del Glosario Estricto (`requirements.md §2`).

### Formato de Specs

Las specs delta (modo legacy) usan el formato **GIVEN/WHEN/THEN**:

```markdown
#### Escenario: Nombre del escenario
- GIVEN precondición
- WHEN acción
- THEN resultado esperado
- AND resultado adicional
```

En el **2-File Root Protocol** (modo predeterminado), cada requerimiento funcional (`### [ ] RF-XXX: ...` en `requirements.md`) desglosa criterios numerados `CRIT-<rf>-<n>` clasificados como `[automated]` o `[manual]`.

### Palabras Clave RFC 2119

| Palabra | Significado |
|---------|-------------|
| **MUST / SHALL** | Requisito obligatorio |
| **SHOULD** | Recomendado, puede haber excepciones |
| **MAY** | Opcional |

---

## Integración con Herramientas

SpecGuard soporta múltiples agentes de IA. El Memory Guard se adapta automáticamente a las capacidades de cada host:

| Herramienta | Ejecución Inline | Sub-agentes | Delegación Inteligente |
|------------|:----------------:|:-----------:|:---------------------:|
| OpenCode | ✅ | ✅ | Execute pesados (> 10 tareas) |
| Antigravity | ✅ | ✅ | Execute pesados (> 10 tareas) |

Ejecuta `bash install.sh` para instalar de forma universal el CLI `sg`, la skill nativa y los contratos de arranque (o `bash install.sh --uninstall` para desinstalar).

---

## Guía de Integración: Custom Skills

El framework de SpecGuard es extensible mediante "Custom Skills", permitiendo integrar herramientas especializadas que no son parte nativa del framework (por ejemplo, herramientas de desarrollo frontend, diseño o base de datos).

### 1. Ubicación Física

Toda nueva skill personalizada o de terceros debe residir en su propio directorio siguiendo la convención de alcance dual:
- **Global:** `$HOME/.skills-custom/` para herramientas transversales a todos los proyectos.
- **Local:** `./skills-custom/` para herramientas específicas del proyecto en curso.

**Regla:** Asegúrate de nombrar la carpeta de forma representativa (por ejemplo, `./skills-custom/frontend-design/`).

### 2. Archivo de Contrato (`SKILL.md`)

Toda skill **DEBE** contener un archivo `SKILL.md` en su raíz. Este archivo actúa como el contrato de integración, las instrucciones directas que el agente carga inline cuando necesita ejecutar la skill. Sin este archivo, la skill no existirá.

### 3. Indexación (`skill-registry`)

Una vez añadida la skill, el desarrollador (o el sistema) debe registrarla para que pueda ser descubierta. Para esto, ejecuta el comando:

```text
/skill-registry
```

Esto escaneará las rutas global y local, y actualizará el archivo de repositorio local en `.spec-guard/skill-registry.md`.

### 4. Uso por el Memory Guard

El Memory Guard lee `.spec-guard/skill-registry.md` al inicializar contexto y mapea cada entrada como una herramienta ejecutable. Al analizar la necesidad de un usuario, se basará en atributos declarados como `name` y `description` para cargar proactivamente la skill relevante.

### Ejemplo Boilerplate (`frontend-design/SKILL.md`)

```markdown
---
name: frontend-design
description: Agente especialista en diseño UI/UX. Crea componentes web hermosos y listos para producción evitando la estética genérica por defecto de IA.
trigger: Cuando el usuario quiere crear un sitio web, un nuevo panel y componente frontend interactivo.
---

# Funcionalidad Principal
Actúas como un desarrollador y diseñador de componentes Vue/React/HTML...

# Reglas
1. Siempre sigue fielmente los colores y el design system nativo.
2. Evita usar frameworks pesados si no se solicita.
```

---

## Agent Hooks

Agent Hooks permite a agentes headless observar el sistema de archivos del proyecto y reaccionar automáticamente ante eventos de guardado (`on_save`).

### Modelo de Confianza (Arquitectura vs. Derivados)

Para evitar la alteración no supervisada de la arquitectura o la evasión de controles, las acciones automáticas se dividen estrictamente entre artefactos de arquitectura y artefactos derivados:

| Acción | Quién la dispara | Gate humano |
|--------|------------------|-------------|
| `plan-approve` / `plan-confirm` (aprobar `objective.md`/`design.md`) | Solo humano, siempre | Sí — sin cambios |
| `hotfix-init` / `hotfix-confirm` | Solo humano, siempre | Sí — sin cambios |
| Actualizar tests derivados de un cambio | Hook automático permitido | **No** |
| Sincronizar documentación (README/MANUAL secciones autogeneradas) | Hook automático permitido | **No** |
| `mark_task_completed` en `tasks.md` | Hook automático permitido | **No** |
| Cualquier escritura dentro de `objective.md` o `design.md` | **Prohibido para hooks** | N/A — un hook nunca toca estos dos archivos |

### Configuración (`.spec-guard/hooks.yaml` o `.state-guard/hooks.yaml`)

Las reglas declarativas se definen en `.spec-guard/hooks.yaml` (o `.state-guard/hooks.yaml`):

```yaml
hooks:
  - name: sync-tests-on-save
    pattern: "**/spec_guard/**/*.py"
    events: ["on_save"]
    prompt: >
      Se modificó {path}. Revisá si los tests unitarios correspondientes en
      tests/unit/ siguen reflejando el comportamiento actual.
    agent_command: ["claude", "-p", "--dangerously-skip-permissions"]
    timeout: 180
```

### Registro de Auditoría (`hooks.log.jsonl`)

Toda acción ejecutada por un hook queda registrada de forma append-only en `hooks.log.jsonl` con el timestamp, nombre de la regla, archivo modificado, estado (`triggered`, `done`, `error`) y código de salida.

### Gestión del Daemon (`sg hooks-*`)

- **Iniciar**: `sg hooks-start` (lanza el daemon en background y registra el PID en `hooks.pid`).
- **Estado**: `sg hooks-status` (informa si el daemon está activo).
- **Detener**: `sg hooks-stop` (detiene el proceso de forma limpia vía `SIGTERM`).

---

## Resolución de Problemas

### El estado no avanza

1. Verificar que `state.ini` existe en `.spec-guard/changes/{change-name}/` (o `.state-guard/changes/...`)
2. Verificar `txn_status` vía `sg status`: si es `in_progress`, hay una transacción incompleta.
3. Ejecutar `/continue` para que el Recovery Protocol intente resolver automáticamente.

### Los artefactos no persisten

1. Verificar que el directorio `.spec-guard/` (o `.state-guard/`) existe
2. Revisar permisos de escritura
3. Confirmar que el cambio tiene un `state.ini` válido

### Transacción incompleta detectada

1. El Recovery Protocol intenta resolver automáticamente al ejecutar `/continue`
2. Como último recurso, revertir mediante `sg rollback --change {nombre}`

### Conflictos entre cambios

1. Usar `sg status` para ver todos los cambios activos (incluye columna de estado transaccional)
2. Archivar cambios completados antes de iniciar nuevos
3. No trabajar en el mismo cambio desde múltiples sesiones simultáneas

---

*Manual técnico — SpecGuard v3.0.0 — Motor SDD y Persistencia Transaccional*
