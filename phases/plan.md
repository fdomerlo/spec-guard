
# PLAN Phase

## Propósito

La fase **PLAN** absorbe el trabajo de exploración, propuesta, especificación y diseño técnico en un único bloque de planificación. Produce los artefactos `objective.md` y `design.md` y los somete a un **gate de revisión humana obligatorio** antes de emitir el lock que habilita EXECUTE.

**Sub-flujo interno (no salteable):**

```
draft  →  gate (revisión humana)  →  lock
```

El lock es el evento que cierra PLAN y habilita EXECUTE. **El modelo NO puede emitir el lock sin confirmación explícita del humano.**

## Qué Hacer

### Sub-paso 1: DRAFT — Generar el plan

Investiga, analiza y produce el borrador del plan. Este paso es ejecutado por el LLM.

#### 1.1 Auto-descubrimiento del stack

Antes de analizar, entiende el entorno físico:

```bash
ls package.json pyproject.toml composer.json go.mod Cargo.toml docker-compose.yml 2>/dev/null
```

Lee los manifiestos encontrados para identificar stack, framework y herramientas clave.

#### 1.2 Exploración y análisis

- ¿Es nueva funcionalidad? ¿Bug? ¿Refactor?
- Lee el código relevante: puntos de entrada, módulos afectados, tests existentes
- Compara enfoques si hay alternativas

#### 1.3 Propuesta

- Intención clara: qué problema resuelve y por qué.
- **Alcance y Delimitación:**
  - `Dentro del Alcance`: Entregables y comportamientos que sí cubre este cambio.
  - `Fuera del Alcance (Out of Scope)`: **OBLIGATORIO.** Declarar explícitamente qué queda deliberadamente fuera de este cambio para prevenir *scope creep* y refactorizaciones no autorizadas.
- **Criterios de Aceptación (`CRIT-XX`):**
  - **OBLIGATORIO.** Asignar identificadores secuenciales únicos (`- [ ] CRIT-01: ...`, `- [ ] CRIT-02: ...`).
  - Todo criterio automatizado debe ser testeable y mapearse 1:1 a un caso de prueba (`test('CRIT-01: ...')` o `def test_crit_01_...()`).
  - Criterios que solo un humano puede validar deben marcarse explícitamente: `- [ ] CRIT-03: (manual) ...`.
- Preguntas abiertas (bloqueantes marcadas con `[!]`).

#### 1.4 Especificación (si el cambio lo requiere)

Para cada dominio afectado, escribe specs delta en:

```
.state-guard/changes/{change-name}/specs/{dominio}/spec.md
```

Usa formato Given/When/Then y palabras clave RFC 2119 (MUST, SHALL, SHOULD, MAY).
Si no existen specs del dominio, escribe una spec completa (no delta).

#### 1.5 Diseño técnico

Lee el código real afectado antes de diseñar. Documenta:

- Enfoque técnico de alto nivel
- Áreas afectadas (tabla con rutas)
- Decisiones de arquitectura con justificación (la tabla Elección/Alternativas/Justificación)
- Flujo de datos (ASCII o Mermaid)
- Tabla de archivos: Archivo | Acción | Descripción
- Interfaces / contratos
- Estrategia de testing
- Riesgos y plan de rollback

#### 1.6 Persistir el DRAFT

Crea los artefactos en disco **antes** de pasar al gate:

```
.state-guard/changes/{change-name}/
├── objective.md         ← qué y por qué
├── design.md            ← cómo, arquitectura, flujo de datos
└── specs/
    └── {dominio}/
        └── spec.md      ← specs delta o completas
```

Formato de `objective.md`:

```markdown
# Objective: {Título del Cambio}

## Intención
{Qué problema resuelve y por qué}

## Alcance
### Dentro del Alcance
- {entregable}
### Fuera del Alcance
- {diferido}

## Criterios de Éxito
- [ ] {resultado medible 1}

## Preguntas Abiertas
- [ ] {pregunta no resuelta — si bloquea, marcá con [!]}
```

Formato de `design.md`:

```markdown
# Design: {Título del Cambio}

## Enfoque Técnico
{Estrategia general}

## Áreas Afectadas
| Área | Impacto | Descripción |
|------|---------|-------------|

## Decisiones de Arquitectura
### Decisión: {Título}
**Elección**: {qué elegimos}
**Alternativas**: {qué descartamos}
**Justificación**: {por qué}

## Flujo de Datos
{diagrama ASCII o Mermaid}

## Archivos Afectados
| Archivo | Acción | Descripción |
|---------|--------|-------------|

## Estrategia de Testing
| Capa | Qué testear | Enfoque |
|------|-------------|---------|

## Riesgos
| Riesgo | Probabilidad | Mitigación |
|--------|-------------|-----------|

## Plan de Rollback
{Cómo revertir si algo sale mal}
```

---

### Sub-paso 2: GATE — Revisión humana obligatoria

**CRÍTICO: El modelo NO puede avanzar a Sub-paso 3 por su cuenta. El gate es una barrera que solo el humano puede cruzar.**

Una vez generado el draft, el modelo DEBE:

1. Presentar `objective.md` y `design.md` al usuario con un resumen ejecutivo
2. Listar explícitamente las decisiones de arquitectura y las preguntas abiertas
3. Antes de solicitar la aprobación del gate, validar la estructura del spec ejecutando:
   ```bash
   python3 scripts/sg.py validate-spec --change {change-name}
   ```
   Si devuelve `ok: false`, el modelo NO ejecuta `plan-approve` — corrige los problemas indicados en los artefactos y reintenta la validación.
4. Ejecutar el comando de preparación del gate out-of-band:
   ```bash
   python3 scripts/sg.py plan-approve --change {change-name}
   ```
5. Emitir el siguiente bloque textual y esperar a que el humano confirme en su propia terminal:

```
═══════════════════════════════════════════════════════════
 GATE DE REVISIÓN — PLAN listo para tu aprobación
═══════════════════════════════════════════════════════════

Revisá objective.md y design.md. El código de confirmación fue mostrado
en tu terminal (/dev/tty) y su hash guardado en ~/.state-guard-gate/{change-name}.token

Para APROBAR y proceder a EXECUTE, ejecutá en tu propia terminal:
  sg plan-confirm --change {change-name} --token <CÓDIGO>

Si deseás solicitar cambios o cancelar, indícalo por este chat.
═══════════════════════════════════════════════════════════
```

El modelo DEBE permanecer en estado de espera. Si el usuario no ejecuta `plan-confirm`, el estado permanece en PLAN y cualquier intento de `commit` será rechazado por el middleware con `EXIT_GATE_REQUIRED (5)`.

---

### Sub-paso 3: LOCK — Emitir el lock y cerrar PLAN

Una vez que el usuario confirma en su terminal ejecutando `sg plan-confirm --change {change-name} --token <CÓDIGO>` (lo cual consume el archivo out-of-band y registra la aprobación en `state.ini[Gate]`):

1. Ejecutar COMMIT en el middleware:
   ```bash
   python3 scripts/state_manager.py commit --change {change-name} --next-phase execute
   ```
2. Reportar al usuario que PLAN está bloqueado y EXECUTE está habilitado.

El COMMIT:
- Avanza `lock_phase` a `execute`
- Libera el lock de fase
- Genera auto-checkpoint del estado del DAG

---

## Reglas

- El LLM NUNCA puede emitir el lock sin respuesta aprobatoria explícita del humano
- Si el humano pide revisiones, re-generar únicamente las secciones indicadas, no los artefactos completos
- Las preguntas abiertas bloqueantes (`[!]`) DEBEN resolverse antes de pasar al gate
- SIEMPRE leer el código real — nunca asumir sobre el código base
- Los artefactos de propuesta son `objective.md` y `design.md`, cada uno con su propósito específico (ver plantillas). NO fusionarlos en un solo archivo.
- Aplicar cualquier `rules.plan` de `.state-guard/config.yaml`

> Transacción: BEGIN antes de Sub-paso 1, COMMIT en Sub-paso 3 (solo tras aprobación humana). Ver `_shared/phase-common.md`.
