---
name: ff
description: >
  Ejecuta plan y execute en secuencia
  Disparador: Cuando el usuario ejecuta /ff.
license: MIT
metadata:
  author: fdomerlo@gmail.com (136bits)
  version: "3.0"
---

# FF Skill

## Propósito

Meta-skill responsable del avance rápido (Fast-Forward) de un cambio transaccional. Ejecuta secuencialmente las fases PLAN y EXECUTE como 2 transacciones ACID independientes para preservar la integridad de SpecGuard.

> **Nota:** El gate de revisión humana de PLAN sigue siendo obligatorio. Tras aprobar el gate de PLAN, `/ff` inicia inmediatamente la transacción de EXECUTE sin requerir una invocación manual adicional.

## Qué Hacer

### Secuencia de Fases

Ejecuta en orden estricto, saltando las fases que ya estén en `completed_phases`:

1. `plan`
2. `execute`

### Guard de Lock Semántico (OBLIGATORIO — antes de CADA fase)

```text
PARA CADA fase en la secuencia (plan → execute):
  SI fase_solicitada NO ES IGUAL A state.lock_phase:
    IMPRIMIR:
    │   ERROR: Transición inválida de lock semántico.
    │     Fase esperada por state.ini: {state.lock_phase}
    │     Fase solicitada: {fase_solicitada}
    │     STOP — Reportá el error al usuario para que decida manualmente.
    ABORTAR la secuencia de /ff.
```

### Ejecución por Fase

Para cada fase que pase el guard semántico:

1. **Cargar:** Leé el archivo `.md` correspondiente (`phases/plan.md`, `phases/execute.md`).
2. **Transaccionar:** Ejecutá inline respetando el ciclo BEGIN → TRABAJO → COMMIT.
3. **Verificar:** Validá que el COMMIT fue exitoso (lock avanzó) antes de continuar.

**Atención sobre PLAN:** En modo FF, el gate de revisión humana de PLAN se ejecuta igual — FF NO lo omite. Tras generar el draft, FF presenta el gate al usuario y espera su aprobación. Si el usuario cancela, FF se detiene en PLAN.

### Resultado

1. Reportá las fases completadas con éxito
2. Mostrá el estado transaccional actual (`sg status --change {nombre}`)
3. Indicá el próximo paso. Si finalizó hasta `execute`, sugerí `/verify`
