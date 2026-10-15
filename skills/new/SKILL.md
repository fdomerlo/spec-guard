---
name: new
description: >
  Inicia un nuevo cambio transaccional ejecutando la fase PLAN completa
  (exploración → propuesta → spec → diseño → gate humano → lock)
  Disparador: Cuando el usuario ejecuta /new para iniciar un cambio.
license: MIT
metadata:
  author: fdomerlo@gmail.com (136bits)
  version: "4.0"
---

# New Skill (Doubt-Driven Spec Builder)

## Propósito

Meta-skill responsable de inicializar un nuevo cambio transaccional. Si el usuario ingresa un requerimiento en lenguaje natural crudo, activa el modo entrevistador guiado por la duda para redactar el `RF-XXX` formal en `requirements.md`, calcula el próximo ID con `sg next-rf-id`, abre el change vinculado y ejecuta la fase PLAN completa.

## Qué Hacer

### Paso 0: Intake y Modo Entrevistador (Doubt-Driven Intake)

Si el usuario plantea una funcionalidad o cambio en lenguaje natural:
1. Consultá `phases/_shared/spec-intake.md`.
2. Ejecutá `sg context` para verificar Glosario Estricto, Stack Obligatorio y Fuera del Alcance.
3. Si hay ambigüedades, formulá hasta 7 preguntas numeradas con opciones (A, B, C) y recomendación `(Recomendada)`. **Frená tu turno (STOP)** y esperá las respuestas.
4. Con las respuestas definidas, calculá el siguiente ID de requerimiento:
   ```bash
   sg next-rf-id [--module RF-XXX]
   ```
5. Redactá formalmente el bloque `### [ ] RF-XXX: ...` con sus criterios `CRIT-XXX-N` en `requirements.md` y los contratos técnicos en `design.md`.

### Paso 1: Inicializar el Change Vinculado

```bash
sg init-change --change {nombre-del-cambio} --rf RF-XXX
```

### Paso 2: Ejecutar PLAN (Transacción única)

Cargá `phases/plan.md` y ejecutá inline, siguiendo los sub-pasos:
1. **Sub-paso 1 (DRAFT):** Validación formal con `sg validate-spec --change {nombre-del-cambio}`.
2. **Sub-paso 2 (GATE):** Presentar plan al humano y esperar confirmación.
3. **Sub-paso 3 (LOCK):** Solo tras aprobación, COMMIT hacia `execute`.

### Paso 3: Reportar al Usuario

Mostrá un resumen del plan aprobado y el próximo comando:
```
✅ PLAN aprobado y bloqueado.
   Próximo paso: /execute {nombre-del-cambio}
   o directamente: sg begin --change {nombre-del-cambio} --phase execute
```

