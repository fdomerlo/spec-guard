# OpenSpec File Convention (compartido entre todas las skills del agente)

## Estructura de Directorios

```text
.spec-guard/
├── config.yaml              ← Configuración del agente específica del proyecto
├── specs/                   ← Fuente de verdad (specs actuales del sistema)
│   └── {dominio}/
│       └── spec.md
└── changes/                 ← Cambios activos
    ├── archive/             ← Cambios completados (YYYY-MM-DD-{change-name}/)
    └── {change-name}/       ← Carpeta de cambio activo
        ├── state.ini        ← Estado del DAG + sesión (manejado por middleware)
        ├── .lock            ← Lock de fase (manejado por middleware)
        ├── .write-lock      ← Mutex de escritura de archivo (manejado por middleware)
        ├── objective.md     ← de plan (propósito, alcance y sección Out of scope)
        ├── specs/           ← de plan (specs delta)
        │   └── {dominio}/
        │       └── spec.md
        ├── design.md        ← de plan (diseño técnico)
        ├── tasks.md         ← de execute (desglose de tareas con CRIT-XX)
        ├── SESSION.md       ← de execute (cursor liviano ~250 tokens para bajo consumo)
        └── verify-report.md ← de verify

```

`.lock` y `.write-lock` son artefactos internos del middleware — nunca se referencian desde una skill ni se leen directamente.
`SESSION.md` es el cursor de ejecución de ultra-bajo consumo de tokens (~250 tokens). Se escribe atómicamente y se ancla también en la raíz del repo durante la fase `execute` para que las iteraciones de desarrollo no tengan que releer el macro-contrato completo.

## Rutas de Artefactos por Skill

| Skill | Crea / Lee | Ruta |
| --- | --- | --- |
| orquestador | Lee | `.spec-guard/changes/{change-name}/state.ini` |
| hotfix | Crea | `.spec-guard/changes/{change-name}/state.ini` (Inicialización Bypass) |
| init | Crea | directorios base y `config.yaml` |
| plan | Crea | `objective.md` (con Out of scope), `design.md` y `specs/{dominio}/spec.md` |
| execute | Crea | `tasks.md` (con `CRIT-XX`) y `SESSION.md` (cursor liviano) |
| execute | Actualiza | `SESSION.md` (estado inmediato y Next action) y `tasks.md` (marca `[x]`) |
| verify | Audita | `sg verify-crit` (trazabilidad 1:1 de `CRIT-XX` contra tests) |
| verify | Crea | `.spec-guard/changes/{change-name}/verify-report.md` |
| verify (Paso 9) | Mueve | `.spec-guard/changes/{change-name}/` → `archive/YYYY-MM-DD-{change-name}/` |
| checkpoint | Actualiza | `.spec-guard/changes/{change-name}/state.ini` y `SESSION.md` (vía `sg checkpoint` / `session-checkpoint`) |
| continue | Lee | `SESSION.md` (durante execute) y `state.ini` (vía `sg status`) |

## Schema de `state.ini` (Motor ACID)

El **Memory Guard** interactúa con este archivo EXCLUSIVAMENTE a través del script `scripts/sg.py` (wrapper) o `scripts/state_manager.py`. **Nunca se debe editar manualmente — incluida la sección `[Session]`.**

El archivo rastrea el estado del Grafo Acíclico Dirigido (DAG) y, opcionalmente, un snapshot de sesión no-DAG.

```ini
[Metadata]
last_updated = 2026-07-02T10:30:00.000000
schema_version = 2          ; 1 = esquema 8 fases (legacy), 2 = esquema 3 fases

[Transaction]
txn_status = idle          ; idle | in_progress
txn_phase = None           ; fase actual si in_progress, sino None
txn_started_at = None

[Graph]
current_phase = plan       ; Descriptivo: última fase completada
lock_phase = execute       ; Prescriptivo: única fase autorizada a ejecutarse AHORA
completed_phases = plan
pending_phases = execute, verify

[Session]
session_summary = ...      ; opcional — bloque generado por checkpoint, ≤500 tokens

```

`[Session]` es la sección que antes hubiera requerido un archivo `manifest.json` aparte (patrón heredado de context-guard, ya absorbido). Vive en el mismo `state.ini` para no duplicar la fuente de verdad del cambio, y su escritura no compite con el lock de fase — solo con el write-lock interno de escritura.

**Semántica `lock_phase` vs `current_phase`:**

| Campo | Rol | Cuándo cambia |
| --- | --- | --- |
| `current_phase` | Descriptivo — última fase completada | Al ejecutar COMMIT transaccional |
| `lock_phase` | Prescriptivo — única fase ejecutable | Al ejecutar COMMIT (avanza el DAG) |

**Tabla de transiciones de `lock_phase` (DAG v2, 3 fases — validada en código por `TRANSITIONS` en `state_manager.py`):**

| Fase completada | `lock_phase` resultante |
| --- | --- |
| `plan`    | `execute` |
| `hotfix`  | `execute` |
| `execute` | `verify` |

> **Migración v1:** Si el state.ini tiene `schema_version = 1` (o el campo ausente), `sg migrate --change {nombre}` lo convierte al esquema v2. La migración también ocurre automáticamente al ejecutar cualquier `begin`. El historial de transiciones anterior se preserva en `[Session].migrated_from_schema = v1`.

## Lectura de Artefactos

Cada skill lee sus dependencias desde el filesystem:

```text
Objective:      .spec-guard/changes/{change-name}/objective.md
Specs delta:    .spec-guard/changes/{change-name}/specs/
Diseño:         .spec-guard/changes/{change-name}/design.md
Tareas:         .spec-guard/changes/{change-name}/tasks.md
Configuración:  .spec-guard/config.yaml
Specs actuales: .spec-guard/specs/{dominio}/spec.md
Estado (DAG+sesión): .spec-guard/changes/{change-name}/state.ini (vía `sg status`)

```

### Configuración de Gate en `config.yaml`

```yaml
schema: spec-driven

gate:
  mode: chat  # Opciones: "chat" (predeterminado, STOP en chat) | "strict" (tokens fuera de banda en /dev/tty)
```

En modo `chat` (default), el gate de la fase PLAN se aprueba directamente tras la confirmación del usuario en la conversación (sin tokens en terminal física). En modo `strict`, `commit` exige token criptográfico out-of-band generado con `sg plan-approve`.

## Reglas de Escritura

* SIEMPRE invocar `state_manager.py` en la terminal para mutar el estado — incluyendo `[Session]`.
* SIEMPRE crear el directorio del cambio antes de escribir artefactos.
* Si un archivo ya existe, LEERLO primero y ACTUALIZARLO (no sobreescribir ciegamente).
* Todos los nombres de cambios transaccionales DEBEN usar formato **kebab-case** (`agregar-modo-oscuro`).
