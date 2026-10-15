# Protocolo de Contexto para Fases

Cada fase del agente tiene reglas estrictas de lectura y escritura. Cuando ejecutás una fase inline, leés los artefactos directamente del filesystem (`requirements.md` / `design.md` en la raíz o `.spec-guard/`). Cuando delegás a un sub-agente, le pasás las **rutas** (no el contenido completo).

## Token Anchoring (Glosario Estricto y Stack Obligatorio)

En todo proyecto que use el **2-File Root Protocol**:
1. **Glosario Estricto (`requirements.md §2`):** Cada concepto del dominio tiene un único nombre permitido. Queda estrictamente prohibido usar sinónimos prohibidos en código, comentarios, tests o documentación (`sg glossary-check`).
2. **Stack Obligatorio (`design.md §1`):** Queda prohibido proponer librerías, dependencias o motores que no figuren en la sección de Stack o hayan sido aprobados previamente por el usuario.
3. **Inyección Compacta:** Usá `sg context` para obtener una proyección JSON rápida y económica en tokens.

## Dependencias de Contexto por Fase

### Modo Raíz (2-File Root Protocol - Recomendado)
| Fase | Lee dependencias de | Escribe artefacto |
| --- | --- | --- |
| `plan` | `requirements.md` (RF del scope, glosario), `design.md` (stack) | `tasks.md`, deltas en `requirements.md` / `design.md` |
| `execute` | `requirements.md`, `design.md`, `tasks.md` | Código en `src/`, tests en `tests/`, `SESSION.md` |
| `verify` | `tasks.md`, `requirements.md` (CRIT-XX del scope), código y tests | `verify-report.md`, `sg mark-rf` al archivar |

### Modo Legacy
| Fase | Lee dependencias de (OpenSpec) | Escribe artefacto |
| --- | --- | --- |
| `plan` | Nada (o specs existentes) | `objective.md`, `design.md`, `specs/` delta |
| `execute` | objective.md, design.md, specs | `tasks.md` (creado y actualizado) |
| `verify` | specs, tasks.md | `verify-report.md` |

## Secuencia de Ejecución por Fase

```text
Inline:   Cargá el archivo de fase (ej. `phases/plan.md`) → Leé dependencias del disco → Ejecutá → Persistí artefacto → COMMIT vía `sg commit` → Reportá al usuario
Delegada: Pasá rutas → Sub-agente ejecuta y persiste artefacto → Recibís resumen → COMMIT vía `sg commit` → Reportá al usuario
```

## Contrato de Resultados (para fases delegadas)

Cuando delegás a un sub-agente, éste debe retornarte: `status`, `executive_summary`, `artifacts`, `risks`.

El sub-agente NO actualiza `state.ini` — eso es responsabilidad exclusiva del Memory Guard (`sg commit`).

Cuando ejecutás inline, no hay "retorno" — vos mismo persistís el artefacto e invocás `sg commit` para avanzar la transacción.

