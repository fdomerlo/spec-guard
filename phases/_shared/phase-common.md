# Contrato Común de Transacción — Fases del agente

## Propósito

Este archivo define el protocolo estándar que TODAS las skills de fase del agente DEBEN seguir para integrar la persistencia transaccional del Memory Guard. Centraliza el contrato para eliminar duplicación entre skills.

## Protocolo de Transacción por Fase

Toda skill de fase DEBE seguir este ciclo:

### 1. BEGIN — Al inicio de la fase

Actualiza el estado invocando `state_manager.py` en la terminal:

```yaml
txn_status: in_progress
txn_phase: {nombre-de-la-fase}   # ej: "plan", "execute", "verify"
txn_started_at: "{timestamp ISO 8601}"
```

### 2. EXECUTE — Trabajo de la fase

Ejecutar las instrucciones del archivo de fase (ej. `phases/spec.md`). Persistir el artefacto resultante en disco **antes** de actualizar `state.ini`.

### 3. COMMIT — Al completar exitosamente

Actualiza el estado invocando `state_manager.py` en la terminal:

```text
state_manager.py commit --change {nombre-del-cambio} --next-phase {siguiente-fase-segun-DAG}
```

El middleware atómicamente:
- Avanza el DAG (`current_phase`, `lock_phase`, `completed_phases`, `pending_phases`)
- Restaura `txn_status` a `idle`
- **Auto-genera un `session_summary` determinístico** con el estado actual del grafo (fase completada, siguiente, completadas, pendientes) — no necesitás construirlo vos
- Libera el lock de fase

Si necesitás un checkpoint más rico (con `archivos_modificados`, `decisiones_clave`), ejecutá `/checkpoint` después del COMMIT.

### 4. ROLLBACK — Si la fase falla

```yaml
txn_status: failed
txn_phase: {fase que falló}
# NO modificar current_phase, lock_phase, completed_phases, pending_phases
```

Reportar el error al usuario.

## Reporte al Usuario (Post-COMMIT)

Después de ejecutar COMMIT, reportá al usuario un resumen conciso. No hay formato rígido — usá markdown con las secciones que aporten valor para cada fase:

| Sección | Cuándo incluir |
|---------|----------------|
| **Resumen ejecutivo** | Siempre (máx 3 líneas) |
| **Artefactos creados/modificados** | Siempre (lista de rutas) |
| **Riesgos** | Si se identificaron riesgos |
| **Próxima acción** | Siempre (comando del agente sugerido) |
| **Reporte detallado** | Solo si la fase produce análisis extenso (ej: verify) |

## Regla de Glosario

Si existe `.spec-guard/config.yaml` con sección `glossary`, cargar los términos y usarlos consistentemente en todos los artefactos generados. Si no existe, continuar normalmente (es opcional).

## Referencia en Skills

Cada skill de fase incluye en su sección de transacción:

> Seguí el protocolo de transacción definido en `phases/_shared/phase-common.md`
