# Manual Técnico — SpecGuard

Este manual cubre la arquitectura técnica, configuración y flujos avanzados del sistema **SpecGuard v3.0.0**, el motor de Specification-Driven Development (SDD) y persistencia transaccional para agentes de código. SpecGuard soporta nativamente la estructura `.spec-guard/` a la vez que mantiene compatibilidad hacia atrás completa con proyectos que utilicen `.state-guard/`.

-## Arquitectura Memory Guard

### Contrato Unificado

El Memory Guard es el contrato central que el agente carga al iniciar una sesión. En lugar de un orquestador que despacha comandos CLI a sub-agentes, el agente ejecuta fases directamente (inline) protegido por un protocolo de persistencia transaccional.

```
Memory Guard (memory-guard.md)
    │
    ├── Carga transaction-protocol.md → Protocolo BEGIN/COMMIT/ROLLBACK
    ├── Carga capabilities.md         → Detecta capacidades del host
    ├── Carga persistence-contract.md → Resuelve el modo de persistencia
    ├── Carga convention.md           → Prepara rutas y schema
    │
    ├── Ejecuta inline → plan     (draft → gate humano obligatorio → lock)
    ├── Ejecuta inline → execute  (tasks.md + implementación; delega si > 10 tareas y host soporta)
    └── Ejecuta inline → verify   (tests + archive como Paso 9)
```

### Módulos del Memory Guard

Los contratos compartidos se distribuyen en dos directorios:

**`skills/_shared/`** — Contratos globales del agente:

| Archivo | Propósito |
|---------|-----------|
| `memory-guard.md` | Contrato unificado: identidad del agente, ejecución de fases, delegación inteligente, recovery |
| `capabilities.md` | Detección de capacidades del agente host y regla de delegación inteligente |
| `convention.md` | Convención de filesystem, schema state.ini v2, tabla de transiciones de lock_phase |

**`phases/_shared/`** — Contratos específicos de fases:

| Archivo | Propósito |
|---------|-----------|
| `transaction-protocol.md` | Protocolo de transacciones: ciclo BEGIN/COMMIT/ROLLBACK, campos txn_* en state.ini, auto-checkpoint |
| `phase-common.md` | Protocolo de transacción común a todas las fases |
| `persistence-contract.md` | Contrato de persistencia: inline vs delegada, protocolo de comunicación |
| `context-injection.md` | Dependencias de contexto por fase y secuencia de ejecución |
| `test-runner-detection.md` | Pseudocódigo para la detección automática del test runner del proyecto |

### Autodetección y Delegación Inteligente

El agente determina su comportamiento en tiempo de ejecución analizando las reglas de `capabilities.md`. Detecta dinámicamente el host (por ejemplo, verificando la presencia de `.gemini` o `.config/opencode/`) y activa o desactiva capacidades según la plataforma.

El Memory Guard ejecuta fases **inline por defecto**: carga el archivo `.md` correspondiente a la fase (ej. `phases/execute.md`) y sigue sus instrucciones como propias. Delega el trabajo pesado a un sub-agente real bajo estas condiciones:

1. La fase es `execute` con más de 10 tareas pendientes en `tasks.md`, **Y**
2. El agente host detectado soporta sub-agentes reales (OpenCode o Antigravity CLI).

En la ejecución delegada, el sub-agente ejecuta las tareas e interactúa con el disco, pero **nunca** escribe en `state.ini`. El Memory Guard asume exclusivamente la responsabilidad del COMMIT transaccional al finalizar la delegación.

### Skill Registry Dinámico

El sistema incluye un **registry dinámico de skills** que permite el descubrimiento automático de herramientas:

- Script bash POSIX en `skills/skill-registry/scan.sh`
- Índice generado en `.state-guard/skill-registry.md`
- El Memory Guard lee este índice al iniciar para conocer las herramientas disponibles

El registry escanea los directorios global (`$HOME/.skills-custom`) y local (`./skills-custom`), extrayendo nombre, descripción, trigger y ubicación de cada `SKILL.md`.

---

## Compilación Condicional vs Runtime

### Compilación Estática (Target OpenCode)
Los modelos de entrada tienden a sufrir de "pereza de herramientas" y les cuesta inferir que deben leer el contexto dinámicamente si no se les inyecta explícitamente en el *system prompt*.
Además, el empaquetador reescribe dinámicamente las directivas de los *slash commands* (como `apply.md`) para usar lenguaje imperativo (ej. `INSTRUCCIÓN CRÍTICA: DEBES usar tu herramienta read_file INMEDIATAMENTE en la ruta...`), forzando al modelo a realizar el *tool-calling* esperado.

### Context Streaming (Targets Avanzados)
Para modelos de frontera como Antigravity CLI y OpenCode, el empaquetador evita el inlining pesado. Despliega un *system prompt* minimalista conservando la filosofía de **Lazy Loading** (Context Streaming). El agente carga dinámicamente las habilidades compartidas y específicas bajo demanda, respetando las referencias modulares limpias para mantener la ventana de contexto sumamente ligera.

---

## State Machine Transaccional

### Estructura de state.ini

El archivo `state.ini` es el núcleo del sistema de estados. Se encuentra en:

```text
.state-guard/changes/{nombre-del-cambio}/state.ini
```

**Schema (formato INI, manejado por `state_manager.py`):**

```ini
[Metadata]
last_updated = 2026-07-02T10:30:00.000000

[Transaction]
txn_status = idle          ; idle | in_progress
txn_phase = None           ; fase actual si in_progress, sino None
txn_started_at = None

[Graph]
current_phase = plan       ; Descriptivo: última fase completada
lock_phase = execute       ; Prescriptivo: única fase autorizada a ejecutarse AHORA
completed_phases = plan
pending_phases = execute, verify

[Session]
session_summary = ...      ; opcional — bloque generado por checkpoint, ≤500 tokens (enforced en código: máx 2000 chars)
```

### Protocolo de Transacciones (transaction-protocol.md)

Cada fase del agente se ejecuta como una transacción ACID atómica gobernada estrictamente por `transaction-protocol.md`:

```text
IDLE → BEGIN → EXECUTE → COMMIT (éxito) o ROLLBACK (fallo) → IDLE
```

El ciclo de vida de la transacción exige la actualización de los nuevos campos transaccionales obligatorios en `state.ini`:

| Paso | Qué ocurre |
|------|-----------|
| **BEGIN** | Registra el inicio marcando `txn_status: in_progress`, `txn_phase: {fase}` y capturando el timestamp actual en `txn_started_at` dentro de `state.ini`. |
| **EXECUTE** | El agente ejecuta la fase encomendada, persistiendo los artefactos generados (código, diseño, specs) en disco de forma segura. |
| **COMMIT** | Consolida la operación. Actualiza atómicamente `current_phase` y `lock_phase`, mueve la fase a `completed_phases`, y reinicia `txn_status: idle` y `txn_phase: null`. |
| **ROLLBACK** | Si ocurre un fallo, aborta seteando `txn_status: failed`, dejando sin alterar el registro de fases para preservar la integridad estructural del DAG. |

**Anti-batching por protocolo**: Cada fase requiere su propio ciclo BEGIN → COMMIT ineludiblemente. Al ser `txn_phase` un valor escalar y no una lista, es mecánicamente imposible ejecutar múltiples fases bajo una misma transacción.

### Mitigación de Fuga de Contexto

Como mecanismo crucial post-COMMIT, `transaction-protocol.md` establece un procedimiento para la **mitigación de fuga de contexto**. 
Una vez que el estado es exitosamente consolidado en `state.ini`, el protocolo exige emitir una **advertencia de purga de chat**. Esta instrucción sirve para alertar al usuario y al agente sobre la necesidad de limpiar el historial de la conversación (o disparar una recarga de contexto / inicio de un nuevo sub-hilo) antes de proceder con la siguiente fase de desarrollo. Esto erradica la acumulación de directivas obsoletas, evitando severas "alucinaciones" durante transiciones prolongadas.

### Recovery Automático

Al detectar un `state.ini` con `txn_status: in_progress` (crash durante ejecución):

1. Verifica si el artefacto de `txn_phase` se persistió en disco
2. Si **SÍ** → ejecuta COMMIT (la fase se completó pero el estado no se persistió)
3. Si **NO** → ejecuta ROLLBACK (restaura `txn_status: idle` sin modificar phases)

### Propiedades ACID

**Atomicidad (Atomicity):** Cada fase se completa completamente o no se completa. El COMMIT solo ocurre después de que el artefacto se persistió en disco exitosamente.

**Consistencia (Consistency):** El schema de `state.ini` v2 está validado. Las transiciones siguen un orden estricto definido por el grafo de dependencias y los campos transaccionales garantizan detección de estado intermedio.

**Aislamiento (Isolation):** Cada cambio tiene su propio `state.ini`. Múltiples cambios pueden ejecutarse en paralelo sin interferir entre sí.

**Durabilidad (Durability):** El estado persiste en el filesystem del proyecto. Sobrevive a recargas de sesión, compactaciones de contexto y reinicios del IDE. Los campos transaccionales permiten recovery automático.

### Prevención de Colisiones

El Memory Guard detecta cambios concurrentes mediante:

1. Lectura del `state.ini` antes de cada transacción
2. Verificación del campo `lock_phase` (única fase autorizada)
3. Bloqueo de fases si `status` es `blocked`
4. Detección de transacciones incompletas (`txn_status: in_progress`)

### Migración v1 → v2

> **Nota histórica:** La migración v1→v2 de `state.ini` a `state.ini` fue completada. Los archivos `state.ini` actuales ya usan el schema basado en INI con secciones `[Transaction]`, `[Graph]` y `[Session]`. No hay migración automática pendiente.

---

## Capa `sg.py` — CLI, Gate Humano y Hotfix

`sg.py` es el único punto de entrada CLI de alto nivel recomendado para la interacción con State Guard. Actúa como un wrapper seguro que encapsula las llamadas a `state_manager.py`, formateando la salida en JSON estándar y administrando los mecanismos de autorización humana fuera de banda.

### Arquitectura de `sg.py`

- **Wrapper JSON**: Todas las operaciones para agentes devuelven respuestas JSON estructuradas y respetan los códigos de salida numéricos.
- **Acceso Exclusivo**: Mutar el manifiesto `state.ini` debe realizarse a través de `sg.py` para asegurar que las validaciones de esquema, bloqueos transaccionales y autorizaciones de gate se apliquen de forma consistente.

### Mecanismo de Gate Humano Out-of-Band

El Gate Humano asegura que los agentes no puedan avanzar de la fase de `plan` a `execute` sin la confirmación explícita de un usuario en una terminal real.

1. **Aprobación fuera de banda**: El comando `sg plan-approve --change <nombre>` genera un token aleatorio que es impreso **únicamente** en la terminal de control (`/dev/tty`). El token nunca viaja por `stdout` ni se almacena en plano.
2. **Almacenamiento seguro**: Solo se guarda el hash SHA-256 del token en la sección `[Gate]` del manifiesto `state.ini`.
3. **Confirmación en 2 pasos**: El humano debe ejecutar en la terminal interactiva `sg plan-confirm --change <nombre> --token <CODIGO>`. Si el hash coincide, el gate queda marcado como autorizado y se permite que el comando `commit` del agente promueva la fase.

### Flujo de Hotfix Bypass

En situaciones de emergencia donde un error debe ser corregido sin pasar por la fase completa de planificación:

1. El humano inicia un hotfix ejecutando `sg hotfix-init --change <nombre> --reason "..."`.
2. Al igual que el gate de plan, este comando imprime un token en `/dev/tty`.
3. El humano confirma con `sg hotfix-confirm --change <nombre> --token <CODIGO>`.
4. Esto registra la autorización del hotfix en `[Gate]` indicando la razón, permitiendo a `begin` saltar directamente a `execute`.

### Integración de Hooks de Git (`sg install-hooks`)

El comando `sg install-hooks` instala un hook `post-commit` en el repositorio Git.
- **Función**: Ejecuta automáticamente `sg status` después de cada commit de git para mostrar el estado actual del manifiesto.
- **Comportamiento**: Es estrictamente **informativo** y no bloquea las operaciones de git, a diferencia del gate de `commit` que sí es bloqueante.

### Subcomandos Principales de `sg.py`

- **Validación de Especificaciones**: `sg validate-spec --change <nombre>` valida estructuralmente `objective.md` y `design.md` comprobando que no contengan preguntas abiertas bloqueantes (`[!]`), placeholders ni secciones faltantes antes de habilitar el gate humano.
- **Gestión de Agent Hooks**: `sg hooks-start`, `sg hooks-stop` y `sg hooks-status` permiten iniciar, detener y verificar el estado del daemon de observabilidad de filesystem.

### Tabla de Códigos de Salida (Exit Codes)

| Código | Constante | Descripción |
|--------|-----------|-------------|
| `0` | `EXIT_OK` | Operación exitosa. |
| `1` | `EXIT_GENERIC` | Error genérico o `state.ini` no encontrado. |
| `2` | `EXIT_LOCK_CONFLICT` | Conflicto de lock activo por otra sesión (reintentable). |
| `3` | `EXIT_BAD_TRANSITION` | Transición inválida en el DAG de fases (no reintentar). |
| `4` | `EXIT_VALIDATION` | Datos de entrada inválidos (ej. summary excede límite, spec incompleto). |
| `5` | `EXIT_GATE_REQUIRED` | Gate humano no cumplido; requiere intervención en terminal. |

---

## Configuración con config.yaml

### Ubicación

```text
.state-guard/config.yaml
```

### Glosario de Configuraciones

| Campo | Descripción |
|-------|-------------|
| `schema` | Versión del schema del agente. Valor actual: `spec-driven` |
| `context` | Descripción del stack tecnológico del proyecto |
| `rules` | Reglas específicas por fase (proposal, specs, design, tasks, apply, verify, archive) |
| `glossary.terms` | (Opcional) Definiciones de términos del dominio |

### Convenciones de Nomenclatura

El sistema usa **kebab-case** para todas las configuraciones:

```yaml
rules:
  apply:
    - Usar rutas en kebab-case para nombres de cambios
    - Los nombres de archivos de skills también usan kebab-case
```

### Scripts de Mantenimiento y Desarrollo

El directorio `scripts/` incluye herramientas adicionales de soporte:
- `cleanup.sh`: Desinstala stubs y limpia los datos temporales del framework en los diferentes agentes de IA. Soporta el flag `--hard` para purgar históricos.
- `install_test.sh`: Suite de tests unitarios y de integración para validar el correcto funcionamiento del script de instalación en diferentes entornos.

### Parámetro test_command

Define el comando para ejecutar tests durante la fase de verificación:

```yaml
rules:
  verify:
    test_command: "npm test"  # o "pytest", "cargo test", etc.
```

Si no se define, la verificación reportará que los tests no pudieron ejecutarse automáticamente.

---

## Flujos Avanzados

### /split — División de Proposals

El comando `/split` analiza una proposal monolítica y la divide en sub-cambios manejables.

**Cuándo usarlo:**

- La proposal abarca múltiples dominios
- El alcance es demasiado grande para una sola iteración
- Hay dependencias entre funcionalidades que deberían implementarse por separado

**Cómo funciona:**

1. Lee la proposal original
2. Analiza los requisitos y alcance
3. Identifica puntos de división naturales
4. Genera múltiples proposals más pequeñas

**Ejemplo de uso:**

```text
/split mi-cambio-grande
```

### /ff — Avance Rápido (Fast-Forward)

El comando `/ff` permite ejecutar secuencialmente las fases de planificación y ejecución (`plan`, `execute`) sin pausas intermedias (el gate humano de `plan` sigue siendo obligatorio).

**Cuándo usarlo:**

- Al iniciar un cambio nuevo bien definido donde no necesitas revisar manualmente cada artefacto intermedio.

**Anti-Batching Transaccional:**
A diferencia de pedirle al LLM que "haga todas las fases de una vez" en un solo prompt (lo que corrompe el DAG), `/ff` ejecuta 4 transacciones secuenciales independientes. Cada fase tiene su propio ciclo BEGIN → COMMIT, y si el agente crashea entre la transacción 2 y la 3, el Recovery Protocol continúa automáticamente desde donde quedó.

### /checkpoint — Guardado de Estado

El comando `/checkpoint` genera un **bloque YAML estructurado** analizando proactivamente
`tasks.md` y `design.md` del cambio activo. El resultado se guarda en el campo `session_summary`
de `state.ini`, posibilitando una recuperación de contexto eficiente (**Warm-Boot**).

**Dos modos de operación:**

1. **Automático** (post-COMMIT): El protocolo de transacción genera un `session_summary` compacto después de cada fase. Esto es suficiente para la mayoría de los casos.
2. **Manual** (`/checkpoint`): Genera un checkpoint de alta fidelidad con análisis proactivo de todos los artefactos. Útil antes de operaciones riesgosas o para refrescar el contexto.

El checkpoint es **agnóstico al DAG**: puede ejecutarse en cualquier momento sin modificar
`lock_phase`, `current_phase` ni el flujo de fases activo.

**Cuándo usarlo manualmente:**

- Antes de realizar operaciones riesgosas
- Al interrumpir un lote de `apply` para preservar el estado
- Al restablecer el contexto de trabajo forzando al LLM a recargar el panorama

**Ejemplo de uso:**

```text
/checkpoint
```

### Archive (Paso 9 de VERIFY — no es un comando separado)

El archivado de un cambio ocurre automáticamente como **Paso 9** dentro de la fase `verify`, una vez que el veredicto es APROBADO. No existe un slash command `/archive` independiente — invocar `/continue` cuando `lock_phase=verify` ejecuta todo el flujo de verificación y archivado en una sola operación.

**Requisito previo para que el archivado no falle:**

1. Ejecutar la fase `verify` (`/continue` con `lock_phase=verify`).
2. Antes de que `verify` pueda archivar, el árbol de trabajo git debe estar limpio — todos los cambios de código commiteados (`git add . && git commit -m "..."`).

El Paso 9 fusiona las specs delta (`changes/{nombre}/specs/`) en las specs principales (`.state-guard/specs/`) y mueve el directorio del cambio a `.state-guard/changes/archive/YYYY-MM-DD-{nombre}/`.

### /review — Auditoría Estática

El comando `/review` compara el código implementado contra las especificaciones sin ejecutar tests.

**Cuándo usarlo:**

- Antes de un merge a main
- Como revisión previa a la verificación completa
- Para identificar desviaciones de diseño

**Qué analiza:**

- Cumplimiento de requisitos de specs
- Consistencia con decisiones de diseño
- Patrones de código aplicados correctamente

**Ejemplo de uso:**

```text
/review mi-cambio
```

### /rollback — Revertir un Cambio

El comando `/rollback` purga la carpeta del cambio y restaura los archivos modificados desde git.

**⚠️ ADVERTENCIA: Pérdida de Trabajo**

Este comando **elimina permanentemente** todo el trabajo no commiteado en el directorio del cambio. Antes de ejecutar:

1. Confirma que no hay cambios sin guardar
2. Ejecuta `git status` para verificar el estado
3. Solo usar cuando el cambio no tiene solución o debe reiniciarse completamente

**Ejemplo de uso:**

```text
/rollback mi-cambio
```

---

## Estructura de Archivos

```text
.state-guard/
├── config.yaml                    ← Configuración del proyecto
├── skill-registry.md              ← Índice dinámico de skills
├── specs/                         ← Specs actuales (fuente de verdad)
│   └── {dominio}/
│       └── spec.md
└── changes/                       ← Cambios activos y archivados
    ├── archive/
    │   └── YYYY-MM-DD-{change}/
    └── {change-name}/
        ├── state.ini              ← Estado del DAG + sesión (manejado por middleware)
        ├── .lock                  ← Lock de fase (manejado por middleware)
        ├── .write-lock            ← Mutex de escritura de archivo (manejado por middleware)
        ├── proposal.md            ← Propuesta
        ├── exploration.md         ← Investigación inicial (opcional)
        ├── specs/                 ← Specs delta
        │   └── {dominio}/
        │       └── spec.md
        ├── design.md              ← Diseño técnico
        ├── tasks.md               ← Checklist de tareas
        ├── verify-report.md       ← Reporte de verificación
        └── (otros artefactos)
```

---

## Convenciones de Estilo

### Idioma

Todos los artefactos deben escribirse en **español (castellano)**. Esto incluye:

- Propuestas y especificaciones
- Diseños y tareas
- Descripciones de código

### Formato de Specs

Las specs usan el formato **GIVEN/WHEN/THEN**:

```markdown
#### Escenario: Nombre del escenario
- GIVEN precondición
- WHEN acción
- THEN resultado esperado
- AND resultado adicional
```

### Palabras Clave RFC 2119

| Palabra | Significado |
|---------|-------------|
| **MUST / SHALL** | Requisito obligatorio |
| **SHOULD** | Recomendado, puede haber excepciones |
| **MAY** | Opcional |

---

## Integración con Herramientas

State Guard soporta múltiples agentes de IA. El Memory Guard se adapta automáticamente a las capacidades de cada host:

| Herramienta | Ejecución Inline | Sub-agentes | Delegación Inteligente |
|------------|:----------------:|:-----------:|:---------------------:|
| OpenCode | ✅ | ✅ | Apply pesados |
| Antigravity CLI | ✅ | ✅ | Apply pesados |

La instalación varía según la herramienta. Ejecuta `scripts/install.sh` y selecciona tu herramienta. Cada integración es un stub mínimo que carga `memory-guard.md` como contrato central.

---

## Guía de Integración: Custom Skills

El framework de State Guard es extensible mediante "Custom Skills", permitiendo integrar herramientas especializadas que no son parte nativa del framework (por ejemplo, herramientas de desarrollo frontend, diseño o base de datos).

### 1. Ubicación Física

Toda nueva skill personalizada o de terceros debe residir en su propio directorio siguiendo la convención de alcance dual:
- **Global:** `$HOME/.skills-custom/` para herramientas transversales a todos los proyectos.
- **Local:** `./skills-custom/` para herramientas específicas del proyecto en curso.

**Regla:** Asegúrate de nombrar la carpeta de forma representativa (por ejemplo, `./skills-custom/frontend-design/`).

### 2. Archivo de Contrato (`SKILL.md`)

Toda skill **DEBE** contener un archivo `SKILL.md` en su raíz. Este archivo actúa como el contrato de integración, las instrucciones directas que el agente carga inline cuando necesita ejecutar la skill. Sin este archivo, la skill no existirá.

### 3. Indexación (`skill-registry`)

Una vez añadida la skill, el desarrollador (o el sistema) debe registrarla para que pueda ser descubierta. Para esto, ejecuta el comando:

```text
/skill-registry
```

Esto escaneará las rutas global y local, y actualizará el archivo de repositorio local en `.state-guard/skill-registry.md`.

### 4. Uso por el Memory Guard

El Memory Guard lee `.state-guard/skill-registry.md` al inicializar contexto y mapea cada entrada como una herramienta ejecutable. Al analizar la necesidad de un usuario, se basará en atributos declarados como `name` y `description` para cargar proactivamente la skill relevante.

### Ejemplo Boilerplate (`frontend-design/SKILL.md`)

```markdown
---
name: frontend-design
description: Agente especialista en diseño UI/UX. Crea componentes web hermosos y listos para producción evitando la estética genérica por defecto de IA.
trigger: Cuando el usuario quiere crear un sitio web, un nuevo panel y componente frontend interactivo.
---

# Funcionalidad Principal
Actúas como un desarrollador y diseñador de componentes Vue/React/HTML...

# Reglas
1. Siempre sigue fielmente los colores y el design system nativo.
2. Evita usar frameworks pesados si no se solicita.
```

---

## Servidor MCP

SpecGuard expone un servidor MCP nativo sobre `stdio` (`spec_guard.mcp.server`), permitiendo a clientes compatibles (ej. Claude Desktop, Cursor, OpenCode) interactuar con herramientas auxiliares, recursos URI y de verificación de estado.

### Herramientas Expuestas (Tools)

| Tool | Argumentos | Descripción | Salida |
|------|------------|-------------|--------|
| `get_next_task` | `change: str` | Retorna la próxima tarea pendiente de `tasks.md` para el change especificado. | JSON con el objeto tarea o `null` si no hay pendientes. |
| `verify_phase_gate` | `change: str, phase: str` | Verifica si la fase solicitada está autorizada por el DAG antes de ejecutarla. | JSON con `{"authorized": true/false}`. |
| `mark_task_completed` | `change: str, task_id: str` | Marca una tarea como completada por ID en `tasks.md` (idempotente). | JSON con el resultado de la actualización. |
| `get_active_changes` | ninguna | Lista todos los cambios activos registrados y su fase actual. | JSON con array de cambios activos. |

### Recursos Expuestos (Resources)

SpecGuard expone las especificaciones de diseño como recursos MCP URI de solo lectura:
- `spec://{change}/objective` — Contenido de `objective.md`.
- `spec://{change}/design` — Contenido de `design.md`.

### Decisiones de Diseño

- **Comandos Transaccionales**: `begin`, `commit`, `rollback`, `checkpoint` **NO** se exponen como herramientas MCP. Se mantienen como invocaciones CLI (`sg begin`, `sg commit`, etc.) para preservar la separación explícita entre el canal MCP de utilidades y la capa de control transaccional estricta.
- **Gates Humanos**: `plan-approve`, `plan-confirm`, `hotfix-init`, `hotfix-confirm` tampoco se exponen por MCP; son comandos exclusivos de terminal interactiva para garantizar interacción humana out-of-band con tokens SHA-256 y protección de 3 intentos.

### Configuración en Clientes MCP

#### Opción A: Vía `uvx` (Recomendada para zero-install)

Agrega el siguiente bloque a tu archivo de configuración de cliente MCP (`claude_desktop_config.json` o equivalente):

```json
{
  "mcpServers": {
    "spec-guard": {
      "command": "uvx",
      "args": [
        "git+https://github.com/fdomerlo/state-guard.git"
      ]
    }
  }
}
```

#### Opción B: Instalación Local Aislada

Clona e instala en modo editable con `uv` o `pip`:

```bash
git clone https://github.com/fdomerlo/state-guard.git ~/.local/share/mcp-servers/spec-guard
cd ~/.local/share/mcp-servers/spec-guard
uv venv && uv pip install -e '.[mcp]'
```

Configuración en el cliente MCP:

```json
{
  "mcpServers": {
    "spec-guard": {
      "command": "/ruta/a/tu/home/.local/share/mcp-servers/spec-guard/.venv/bin/spec-guard-mcp"
    }
  }
}
```

---

## Agent Hooks

Agent Hooks permite a agentes headless observar el sistema de archivos del proyecto y reaccionar automáticamente ante eventos de guardado (`on_save`).

### Modelo de Confianza (Arquitectura vs. Derivados)

Para evitar la alteración no supervisada de la arquitectura o la evasión de controles, las acciones automáticas se dividen estrictamente entre artefactos de arquitectura y artefactos derivados:

| Acción | Quién la dispara | Gate humano |
|--------|------------------|-------------|
| `plan-approve` / `plan-confirm` (aprobar `objective.md`/`design.md`) | Solo humano, siempre | Sí — sin cambios |
| `hotfix-init` / `hotfix-confirm` | Solo humano, siempre | Sí — sin cambios |
| Actualizar tests derivados de un cambio | Hook automático permitido | **No** |
| Sincronizar documentación (README/MANUAL secciones autogeneradas) | Hook automático permitido | **No** |
| `mark_task_completed` en `tasks.md` | Hook automático permitido | **No** |
| Cualquier escritura dentro de `objective.md` o `design.md` | **Prohibido para hooks** | N/A — un hook nunca toca estos dos archivos |

### Configuración (`.spec-guard/hooks.yaml` o `.state-guard/hooks.yaml`)

Las reglas declarativas se definen en `.spec-guard/hooks.yaml` (o `.state-guard/hooks.yaml`):

```yaml
hooks:
  - name: sync-tests-on-save
    pattern: "**/spec_guard/**/*.py"
    events: ["on_save"]
    prompt: >
      Se modificó {path}. Revisá si los tests unitarios correspondientes en
      tests/unit/ siguen reflejando el comportamiento actual.
    agent_command: ["claude", "-p", "--dangerously-skip-permissions"]
    timeout: 180
```

### Registro de Auditoría (`hooks.log.jsonl`)

Toda acción ejecutada por un hook queda registrada de forma append-only en `hooks.log.jsonl` con el timestamp, nombre de la regla, archivo modificado, estado (`triggered`, `done`, `error`) y código de salida.

### Gestión del Daemon (`sg hooks-*`)

- **Iniciar**: `sg hooks-start` (lanza el daemon en background y registra el PID en `hooks.pid`).
- **Estado**: `sg hooks-status` (informa si el daemon está activo).
- **Detener**: `sg hooks-stop` (detiene el proceso de forma limpia vía `SIGTERM`).

---

## Resolución de Problemas

### El estado no avanza

1. Verificar que `state.ini` existe en `.spec-guard/changes/{change-name}/` (o `.state-guard/changes/...`)
2. Verificar `txn_status` vía `sg status`: si es `in_progress`, hay una transacción incompleta.
3. Ejecutar `/continue` para que el Recovery Protocol intente resolver automáticamente.

### Los artefactos no persisten

1. Verificar que el directorio `.spec-guard/` (o `.state-guard/`) existe
2. Revisar permisos de escritura
3. Confirmar que el cambio tiene un `state.ini` válido

### Transacción incompleta detectada

1. El Recovery Protocol intenta resolver automáticamente al ejecutar `/continue`
2. Como último recurso, revertir mediante `sg rollback --change {nombre}`

### Conflictos entre cambios

1. Usar `sg status` para ver todos los cambios activos (incluye columna de estado transaccional)
2. Archivar cambios completados antes de iniciar nuevos
3. No trabajar en el mismo cambio desde múltiples sesiones simultáneas

---

*Manual técnico — SpecGuard v3.0.0 — Motor SDD y Persistencia Transaccional*
