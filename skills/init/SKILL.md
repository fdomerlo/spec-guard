---
name: init
description: >
  Inicializa el entorno de ejecución con memoria transaccional en cualquier proyecto. Detecta el stack, las convenciones e inicializa el backend de persistencia activo.
  Disparador: Cuando el usuario quiere inicializar SpecGuard en un proyecto, o dice "iniciar spec-guard", "spec-guard init".
license: MIT
metadata:
  author: fdomerlo@gmail.com (136bits)
  version: "2.0"
---

# Init Skill (2-File Root Protocol)

## Propósito

Inicializar SpecGuard en el repositorio bajo el **2-File Root Protocol**: establece `requirements.md` (PRD) y `design.md` (SAD) como fuentes de verdad en la raíz del proyecto, configura contratos `AGENTS.md` y `CLAUDE.md`, y prepara la infraestructura transaccional `.spec-guard/`.

## Qué Hacer

### Paso 1: Ejecutar `sg init`

Ejecutá el comando determinista de inicialización:

```bash
sg init
# o: python3 -m spec_guard.cli init
```

Esto garantiza:
- Creación de plantillas raíz si no existen: `requirements.md` y `design.md` con el stack precargado y placeholders limpios.
- Instalación de contratos del agente: `AGENTS.md` y `CLAUDE.md` en la raíz.
- Estructura `.spec-guard/` con `config.yaml` y `.spec-guard/bin/verify-crit.sh`.

### Paso 2: Entrevista Inicial de Definición (Opcional pero recomendada)

Si el proyecto es nuevo o los documentos raíz recién se crearon con placeholders:
1. Ofrecé una breve entrevista guiada por dudas (`phases/_shared/spec-intake.md`) para definir:
   - **Visión General (`requirements.md §1`):** Problema central y objetivo principal.
   - **Glosario Estricto (`requirements.md §2`):** Las 2 o 3 entidades nodales del dominio con sus sinónimos prohibidos.
   - **Stack Obligatorio (`design.md §1`):** Confirmar motor de base de datos y dependencias iniciales.
2. Reemplazá los placeholders `{...}` en los documentos raíz con las respuestas del usuario.

### Paso 3: Validación de Arranque

Verificá que las especificaciones iniciales sean coherentes:

```bash
sg context
sg validate-spec
```

### Paso 4: Devolver Resumen

Informá al usuario que el proyecto está listo para trabajar:

```text
## SpecGuard Inicializado (2-File Root Protocol)

**Proyecto**: {nombre del proyecto}
**Fuentes de Verdad**:
- `requirements.md` (PRD: Visión, Glosario, Roles, RFs)
- `design.md` (SAD: Stack obligatorio, Modelo, Endpoints, Reglas)

Listo para recibir requerimientos: podés iniciar tu primer cambio con `/new {nombre-del-cambio}` o plantear una funcionalidad en lenguaje natural.
```

