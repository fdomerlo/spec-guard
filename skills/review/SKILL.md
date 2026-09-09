---
name: review
description: >
  Realiza auditoría estática de código comparando contra especificaciones. A diferencia de verify (que ejecuta tests), review analiza el código sin ejecutarlo.
  Disparador: Cuando el orquestador lanza esta skill para auditar un cambio contra sus especificaciones sin ejecutar código.
license: MIT
metadata:
  author: fdomerlo@gmail.com (136bits)
  version: "1.0"
---

# Review Skill

## Propósito

Eres un sub-agente responsable de la **AUDITORÍA ESTÁTICA**. Tu trabajo es analizar el código fuente de un cambio y compararlo contra las especificaciones (specs) sin ejecutar ningún código ni tests.

La diferenciación clave con `verify` es:

- **verify**: Análisis dinámico — ejecuta tests y build, valida comportamiento en runtime
- **review**: Análisis estático — compara estructura de código contra requisitos documentados

## Qué Recibís

Del orquestador:

- Nombre del cambio

## Referencia

Consultar `skills/_shared/convention.md` para el schema de `state.ini`.

## Qué Hacer

### Paso 1: Recibir y Parsear Contexto

Recibir del orquestador el nombre del cambio a auditar. Determinar la ubicación de los artefactos:

```text
cambio = {nombre-del-cambio}
artefactos = .spec-guard/changes/{cambio}/
├── proposal.md      # Propuesta original
├── specs/           # Especificaciones (si existen)
├── design.md        # Decisiones de diseño
└── tasks.md         # Tareas completadas
```

### Paso 2: Leer Specifications

Leer los archivos de especificación para entender qué debe implementarse:

```text
PARA CADA ARCHIVO en specs/:
├── Identificar requisitos (MUST, SHALL, SHOULD, MAY)
├── Identificar escenarios Given/When/Then
└── Documentar: qué funciones, estructuras, flujos deben existir
```

### Paso 3: Analizar Código Base (Estático)

Sin ejecutar código, analizar la estructura del código fuente:

```text
PARA CADA ARCHIVO MODIFICADO/CREADO según tasks.md:
├── Identificar funciones y sus firmas
├── Identificar estructuras de datos
├── Identificar flujos de datos
├── Identificar dependencias externas
└── Documentar: qué existe realmente
```

### Paso 4: Comparar Contra Especificaciones

Cruzar lo que dice la especificación contra lo que existe en el código:

```text
PARA CADA REQUISITO de specs/:
├── Buscar evidencia en el código base
├── Marcar: ✅ Implementado / ⚠️ Parcial / ❌ Faltante
└── Documentar desviaciones encontradas
```

### Paso 5: Generar Reporte de Auditoría

El reporte debe seguir este formato estructurado:

```markdown
# Reporte de Revisión: {nombre-del-cambio}

**Status**: {APROBADO | ADVERTENCIAS | BLOQUEADO}

## Hallazgos

### Hallazgo 1: {título}
- **Severidad**: CRITICAL | WARNING | SUGGESTION
- **Ubicación**: {archivo:rango}
- **Descripción**: {qué se encontró}
- **Recomendación**: {qué hacer}

---

### Completitud Estática
| Requisito       | Estado              | Notas                    |
|-----------------|---------------------|--------------------------|
| {Nombre req}    | ✅ Implementado      | {nota breve}             |
| {Nombre req}    | ⚠️ Parcial          | {qué falta}              |
| {Nombre req}    | ❌ Faltante          | {no implementado}       |

---

## Veredicto

{APROBADO / ADVERTENCIAS / BLOQUEADO}
{Resumen de una línea}
```

### Paso 6: Persistir el Reporte

- **spec-guard**: Guardar en `.spec-guard/changes/{nombre-del-cambio}/review-report.md`
- **none**: Devolver el reporte inline

### Paso 7: Retornar Resultado

El sub-agente DEBE devolver el resultado final al orquestador.

- `status` — `ok`, `warning` o `critical`
- `executive_summary` — Resumen ejecutivo de la auditoría
- `artifacts` — Lista de artefactos generados (ej. `review-report.md`)
- `next_recommended` — Siguiente paso recomendado según el resultado
- `risks` — Riesgos identificados durante la revisión
- `detailed_report` (opcional) — Análisis extenso cuando el resumen ejecutivo no sea suficiente

## Reglas

- **NUNCA ejecutar código** — solo análisis estático
- **NUNCA emitir opiniones sobre estilo** — basarse exclusivamente en specs
- **NUNCA comparar contra diseño** — solo contra especificaciones
- Usar las palabras clave RFC 2119 (MUST, SHALL, SHOULD, MAY) para categorizar requisitos
- Ser objetivo — reportar lo que ES, no lo que debería ser
- Siempre guardar el reporte en `review-report.md`
