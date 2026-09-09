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

Consultar `skills/_shared/convention.md` para el schema de `state.ini`.

## Qué Hacer

### Paso 1: Encontrar Archivos de Estado

Busca todos los archivos `state.ini` en el directorio `.spec-guard/changes/`:

```text
.spec-guard/changes/*/state.ini
```

### Paso 2: Parsear cada State.ini

Para cada archivo encontrado, extrae los siguientes campos:

- `change`: Nombre del cambio
- `current_phase`: Fase actual (plan, execute, verify)
- `status`: Estado actual (active, done, blocked)
- `started_at`: Fecha de inicio en formato ISO 8601
- `blocked_reason`: Razón del bloqueo (si aplica)

### Paso 3: Filtrar Cambios Archivados

Ignora los cambios que tengan:

- `status: done`
- Cambios completados (todas las fases en `completed_phases`)

### Paso 4: Calcular Tiempo Transcurrido

Para cada cambio activo, calcula el tiempo desde `started_at` hasta ahora:

- Formato de salida: "Xh Ym" (horas y minutos)
- Si ha pasado menos de 1 hora, mostrar solo minutos: "30m"
- Si ha pasado más de 24 horas, mostrar "24h+"

### Paso 5: Determinar Estado con Semáforo

Aplica la lógica de semáforo:

```text
| Condición | Emoji | Significado |
|-----------|-------|-------------|
| `status == "blocked"` | 🟡 | Bloqueado |
| `status == "done"` | 🔴 | Completado (no debería aparecer) |
| `status == "active"` | 🟢 | Activo |
```

### Paso 6: Formatear Tabla Markdown

Genera una tabla con las siguientes columnas:

```text
| Cambio | Fase Actual | Tiempo Transcurrido | Estado | Txn |
|--------|-------------|---------------------|--------|-----|
| feat-auth | Apply | 2h 30m | 🟢 | idle |
```

- **Cambio**: Nombre del cambio (de `change`)
- **Fase Actual**: Current_phase con primera letra mayúscula (de `current_phase`)
- **Tiempo Transcurrido**: Formato "Xh Ym" (del cálculo)
- **Estado**: Emoji del semáforo

### Paso 7: Manejar Casos Edge

- **Sin cambios activos**: Mostrar mensaje informativo, no tabla vacía
- **Archivo corrupto**: Continuar con los demás archivos, mostrar advertencia

### Paso 8: Devolver Resultado

Devuelve la tabla Markdown con el estado de todos los cambios activos.

## Reglas

- SIEMPRE filtrar cambios completados (todas las fases en completed_phases)
- Si no hay cambios activos, mostrar mensaje informativo
- Manejar gracefully archivos malformados (continuar, no fallar)
- El formato de fase debe ser legible (primera letra mayúscula)
