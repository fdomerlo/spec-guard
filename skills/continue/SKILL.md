---
name: continue
description: >
  Continúa un cambio transaccional desde donde se quedó
  Disparador: Cuando el usuario ejecuta /continue.
license: MIT
metadata:
  author: fdomerlo@gmail.com (136bits)
  version: "3.1"
---

# Continue Skill

## Propósito

Meta-skill responsable de continuar un cambio transaccional existente. Consulta el middleware para determinar el estado real (no lee `state.ini` directamente) y ejecuta la siguiente fase inline.

## Qué Hacer

### Paso 1: Consultar Estado

```text
Invocar: state_manager.py status --change {nombre} [--ttl {segundos}]
```

Si no hay argumento `{nombre}`, explorar `.spec-guard/changes/` para identificar el cambio activo antes de invocar `status`.

Si `state.ini` no existe para el cambio → STOP:
```
Reportar al usuario que el estado es inconsistente/corrupto — no hay skill de reparación automática.
```

### Paso 2: Decidir Según `lock_state`

La lógica de decisión completa (qué hacer ante `FREE`/`ACTIVE`/`STALE`, y el criterio de recovery cuando `txn_status=in_progress`) vive en `memory-guard.md` §Recovery Protocol — no la dupliques acá. Resumen de bifurcación:

```text
lock_state == ACTIVE   → STOP, reportar conflicto al usuario (otra sesión tiene el lock).
lock_state == STALE    → aplicar Recovery Protocol de memory-guard.md antes de continuar.
lock_state == FREE
  y txn_status == idle → proceder directamente al Paso 3.
  y txn_status == in_progress
                        → esto es un estado inconsistente (lock liberado pero txn abierta).
                          Reportar al usuario que el estado es inconsistente/corrupto — no hay skill de reparación automática.
```

### Paso 3: Ejecutar Siguiente Fase

Usar `lock_phase` (devuelto por `status`) para determinar qué skill invocar:

| lock_phase  | Skill a ejecutar | Descripción |
|-------------|------------------|-------------|
| `plan`      | `phases/plan.md`     | Genera draft, espera gate humano, emite lock |
| `execute`   | `phases/execute.md`  | Desglosa tareas e implementa |
| `verify`    | `phases/verify.md`   | Verifica + archiva (Paso 9) |

> **Migración v1:** Si el state.ini todavía tiene fases v1 (`explore`, `propose`, `spec`, `design`, `tasks`, `apply`, `archive`), ejecutar primero `sg migrate --change {nombre}` para migrar al esquema v2. La migración es automática al ejecutar cualquier `begin`.

La transacción (BEGIN/COMMIT/ROLLBACK) la maneja la propia skill invocada, según `transaction-protocol.md`. `continue` no toma el lock de fase directamente — delega esa responsabilidad a la skill de la fase correspondiente.
