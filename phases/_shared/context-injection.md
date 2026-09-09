# Protocolo de Contexto para Fases

Cada fase del agente tiene reglas de lectura y escritura. Cuando ejecutás una fase inline, leés los artefactos directamente del filesystem (`.spec-guard/`). Cuando delegás a un sub-agente, le pasás las **rutas** (no el contenido).

## Dependencias de Contexto por Fase

| Fase | Lee dependencias de (OpenSpec) | Escribe artefacto |
| --- | --- | --- |
| `plan` | Nada (o specs existentes) | `objective.md`, `design.md`, `specs/` delta |
| `execute` | objective.md, design.md, specs | `tasks.md` (creado y actualizado) |
| `verify` | specs, tasks.md | `verify-report.md` |

## Secuencia de Ejecución por Fase

```text
Inline:   Cargá el archivo de fase (ej. `phases/plan.md`) → Leé dependencias del disco → Ejecutá → Persistí artefacto → COMMIT vía `state_manager.py` → Reportá al usuario
Delegada: Pasá rutas → Sub-agente ejecuta y persiste artefacto → Recibís resumen → COMMIT vía `state_manager.py` → Reportá al usuario
```

## Contrato de Resultados (para fases delegadas)

Cuando delegás a un sub-agente, éste debe retornarte: `status`, `executive_summary`, `artifacts`, `risks`.

El sub-agente NO actualiza `state.ini` — eso es responsabilidad exclusiva del Memory Guard.

Cuando ejecutás inline, no hay "retorno" — vos mismo persistís el artefacto y invocás `state_manager.py commit` para avanzar la transacción.
