---
name: checkpoint
description: >
  Genera un resumen de alta fidelidad del estado del cambio activo y lo guarda en el campo
  session_summary del state.ini. Permite recuperación rápida de sesión tras reload del IDE.
  Disparador: Cuando el usuario ejecuta /checkpoint para guardar estado, o automáticamente post-COMMIT.
license: MIT
metadata:
  author: fdomerlo@gmail.com (136bits)
  version: "3.1"
---

# Checkpoint Skill

## Propósito

Skill responsable de **generar un checkpoint de sesión de alta fidelidad**. Detecta el cambio activo, ejecuta un análisis proactivo de sus artefactos (`tasks.md`, `design.md`) y del contexto actual, y guarda un bloque estructurado en el campo `session_summary` del `state.ini` **a través del middleware**, nunca editando el archivo directamente.

**Dos modos de operación:**

2. **Manual** (`/checkpoint`): Genera un checkpoint de alta fidelidad con análisis proactivo de todos los artefactos. Útil antes de operaciones riesgosas o para refrescar el contexto.

## Qué Hacer

### Paso 1: Detectar Cambio Activo

Buscar `state.ini` con `status: active` en `.spec-guard/changes/*/state.ini`.

### Paso 2: Leer Estado Base

### Paso 3a: Obtener estado_tareas vía middleware

**No cuentes checkboxes manualmente.** Invocá:

```text
sg check-completion --change {nombre-del-cambio}
```

El comando parsea `tasks.md` de forma determinista y devuelve `estado_tareas`, `total`, `completed`, `all_complete`, `last_completed_id`, `last_completed_desc`. Usá el valor de `estado_tareas` tal cual viene — ya tiene el formato `"{X}/{Y} — última: [{ID}] {descripción breve}"`. Si el archivo no existe, devuelve `estado_tareas=N/A` directamente.

### Paso 3b: Extraer archivos_modificados

```text
Fuente primaria:   Tabla "### Archivos Modificados" del último resumen de execute
Fuente secundaria: Campo `archivos_modificados` del session_summary existente
Fallback:          Lista vacía []
```

Máximo 10 archivos, rutas relativas al root.

### Paso 3c: Extraer decisiones_clave del design.md

Si existe `design.md`: extraer las primeras 2 decisiones de la sección `## Decisiones de Arquitectura`, truncar a 100 chars cada una.

### Paso 4: Persistir vía middleware

Ensamblá el bloque `session_summary` (estado_tareas + archivos_modificados + decisiones_clave) como un único string. **No lo escribas en ningún archivo directamente.** Invocá en terminal:

```text
sg checkpoint --change {nombre-del-cambio} --summary "{bloque generado}"
```

Esperá `SUCCESS|CHECKPOINT` antes de reportar al usuario. Si el comando falla, reportá el error tal cual lo devuelve el middleware — no reintentes editando el archivo como fallback.

### Paso 5: Reportar

```markdown
## Resultado del Checkpoint

**status**: ok | error
**Cambio**: {nombre-del-cambio}

### session_summary generado
{bloque generado, el mismo que se pasó a --summary}
```

## Reglas

- Si no hay cambio activo, mostrar error
- Si no existe `tasks.md`, usar `estado_tareas: "N/A"`
- El bloque `session_summary` NO debe superar 500 tokens
- **AGNOSTICISMO DE LOCK**: este skill nunca toma ni verifica el lock de fase (`.lock`/DAG). Puede ejecutarse con una transacción de fase en progreso sin conflicto — el middleware serializa la escritura internamente.
- **PROHIBIDO** editar `state.ini` con `edit_file`/`write_file` bajo cualquier circunstancia, incluso para este campo no-DAG.
