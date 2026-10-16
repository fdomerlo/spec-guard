---
name: status
description: >
  Muestra el estado de todos los cambios activos del DAG mediante una tabla Markdown con emojis de semáforo.
  Disparador: Cuando el orquestador te lanza para mostrar el estado de cambios activos, o el usuario ejecuta /status.
license: MIT
metadata:
  author: fdomerlo@gmail.com (136bits)
  version: "2.0"
---

# Status Skill

## Propósito

Eres un sub-agente responsable de **mostrar el estado de los cambios activos** en el DAG del agente. Lees los archivos `state.ini` de todos los cambios y generas una tabla Markdown con emojis de semáforo.

## Qué Recibís

El orquestador te dará:

- Referencias a los archivos `state.ini` activos

## Referencia

No cargues `skills/_shared/convention.md` por adelantado. Abrilo solo si
necesitás verificar un campo específico del schema de `state.ini` que no
te quede claro por el propio comportamiento del CLI.

## Qué Hacer

### Paso 1: Consultar Cambios Activos vía CLI

Invoca el comando determinista para listar todos los cambios activos (excluye `archive/` automáticamente):

```bash
sg list-changes
```

Para cada cambio retornado, consulta su diagnóstico completo:

```bash
sg status --change {nombre}
```

### Paso 2: Extraer Campos del Schema v2

Para cada cambio activo, extrae los siguientes campos:

- `name`: Nombre del cambio
- `lock_phase`: Fase prescriptiva actual (`plan`, `execute`, `verify`)
- `txn_status`: Estado de la transacción (`idle` | `in_progress`)
- `txn_phase`: Fase en ejecución si `txn_status == "in_progress"`
- `lock_state`: Estado del lock POSIX (`FREE` | `ACTIVE` | `STALE`)
- `schema_version`: Versión del schema (`2`)

### Paso 3: Determinar Estado con Semáforo

Aplica la lógica de semáforo combinando `txn_status` y `lock_state`:

```text
| Condición | Emoji | Significado |
|-----------|-------|-------------|
| `lock_state == "STALE"` | 🔴 | Transacción interrumpida (requiere Recovery Protocol) |
| `txn_status == "in_progress"` y `lock_state == "ACTIVE"` | 🟡 | Transacción en curso (lock activo) |
| `txn_status == "idle"` y `lock_state == "FREE"` | 🟢 | Listo para ejecutar `lock_phase` |
```

### Paso 4: Formatear Tabla Markdown

Genera una tabla con las siguientes columnas:

```text
| Cambio | Lock Phase | Estado | Txn Status | Lock State |
|--------|------------|--------|------------|------------|
| feat-auth | Execute | 🟢 | idle | FREE |
```

- **Cambio**: Nombre del cambio
- **Lock Phase**: `lock_phase` con primera letra mayúscula (`Plan`, `Execute`, `Verify`)
- **Estado**: Emoji del semáforo
- **Txn Status**: `idle` o `in_progress`
- **Lock State**: `FREE`, `ACTIVE` o `STALE`

### Paso 5: Manejar Casos Edge

- **Sin cambios activos**: Mostrar mensaje informativo indicando que no hay cambios activos en `.spec-guard/changes/` (y en proyectos bajo el 2-File Root Protocol, sugerir `sg rf-status` para ver el progreso de `requirements.md`).
- **Archivo corrupto**: Continuar con los demás archivos, mostrar advertencia.

### Paso 6: Devolver Resultado

Devuelve la tabla Markdown con el estado de todos los cambios activos.

## Reglas

- SIEMPRE filtrar cambios completados (todas las fases en completed_phases)
- Si no hay cambios activos, mostrar mensaje informativo
- Manejar gracefully archivos malformados (continuar, no fallar)
- El formato de fase debe ser legible (primera letra mayúscula)
