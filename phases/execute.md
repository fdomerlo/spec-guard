
# EXECUTE Phase

## Propósito

La fase **EXECUTE** absorbe el trabajo de desglose en tareas (`tasks`) e implementación (`apply`). Es la única fase que produce cambios en el código fuente del proyecto.

**Prerequisito:** `lock_phase == execute` — esto solo ocurre después de que el humano aprobó el lock de PLAN.

## Qué Hacer

### Paso 1: Leer el Contexto e Inicializar el Cursor de Sesión

Para garantizar el **mínimo consumo de tokens**, la fase EXECUTE opera en dos niveles:

1. **Arranque inicial de la fase (solo la primera vez):**
   - Leer `tasks.md` (o generarlo en el Paso 2 si no existe).
   - Inicializar el cursor liviano `SESSION.md` (~250 tokens) en la raíz del repo:
     ```bash
     sg session-checkpoint --change {change-name} --action "Comenzar primera tarea"
     ```
2. **Iteraciones sucesivas durante EXECUTE (regla de bajo consumo):**
   - **PROHIBIDO releer `objective.md` y `design.md` completos en cada ciclo.**
   - El agente lee **únicamente `SESSION.md`** y los archivos de código y test involucrados en la tarea inmediata.
   - Verificar integridad de Git:
     ```bash
     git merge-base --is-ancestor <base-commit> HEAD
     ```
     Si el comando falla (código != 0), la rama divergió (rebase, reset, force-push). **DETENÉTE inmediatamente** y alertá al usuario.

### Paso 2: Generar tasks.md con Trazabilidad `CRIT-XX`

A partir del plan aprobado, produce el desglose de tareas atómicas vinculadas a los criterios de aceptación:

```markdown
# Tareas: {Título del Cambio}

## Fase 1: {Nombre}
- [ ] [T001] CRIT-01: {Descripción con ruta de archivo específica}
- [ ] [T002] CRIT-02: {Descripción atómica}

## Fase 2: {Nombre}
- [ ] [T003] CRIT-03: (manual) {Verificación que requiere criterio humano}
```

Reglas del desglose:
- Cada tarea = un archivo o módulo lógico (sin tareas monstruo).
- IDs de tarea en formato `[Txxx]` y mapeo a `CRIT-XX` cuando corresponda a un criterio de la spec.
- Criterios manuales llevan `(manual)`.

### Paso 3: Detectar Modo de Implementación

```text
Detectar modo TDD (en orden de prioridad):
├── .spec-guard/config.yaml → rules.apply.tdd (true/false)
├── Skills instaladas del usuario (ej: tdd/SKILL.md existe)
├── Patrones de test existentes en el código base
└── Por defecto: TDD obligatorio para correcciones/criterios CRIT-XX
```

### Paso 4: Implementar Tareas (TDD RED → GREEN)

Para cada tarea con criterio automatizado `CRIT-XX`:
1. **RED**: Escribir la prueba unitaria o de integración cuyo nombre incluya la etiqueta exacta (`test('CRIT-01: ...')` o `def test_crit_01_...()`). Confirmar que FALLA.
2. **GREEN**: Implementar el código mínimo de producción para que la prueba PASE.
3. **REFACTOR**: Limpiar el código sin alterar comportamiento. Confirmar suite en verde.
4. **CHECKPOINT**: Marcar tarea en `tasks.md` (`sg mark-task`) y actualizar el cursor:
   ```bash
   sg session-checkpoint --change {change-name} --action "Siguiente tarea" --completed "CRIT-XX implementado"
   ```

> CRÍTICO: Ejecutar tests con una terminal real. PROHIBIDO simular o inferir resultados.

### Paso 5: Verificar progreso con el middleware

```bash
sg check-completion --change {change-name}
```

Reporta `total`, `completed`, `all_complete`, `last_completed_id`.

### Paso 6: Reportar

```markdown
## Progreso de Implementación

**Cambio**: {change-name}
**Modo**: {TDD | Estándar}

### Tareas Completadas
- [x] [T001] {descripción}
- [x] [T002] {descripción}

### Archivos Modificados
| Archivo | Acción | Qué se hizo |
|---------|--------|-------------|
| `ruta/archivo.ext` | Creado/Modificado | {descripción} |

### Desviaciones del Plan
{Lista o "Ninguna — la implementación coincide con el plan."}

### Problemas Encontrados
{Lista o "Ninguno."}

### Estado
{N}/{total} tareas completas. {Listo para VERIFY / Siguiente lote pendiente}
```

## Reglas

- SIEMPRE leer las specs antes de implementar — son los criterios de aceptación
- SIEMPRE seguir las decisiones de arquitectura del plan — no improvisar
- SIEMPRE ajustarse a los patrones de código existentes
- Marcar las tareas `[x]` en `tasks.md` al completarlas
- Si el plan es incorrecto/incompleto, ANOTARLO — no desviarse en silencio
- Si una tarea está bloqueada, DETENERSE y reportar
- Aplicar cualquier `rules.apply` de `.spec-guard/config.yaml`

> Transacción: BEGIN antes de este contenido, COMMIT al terminar. Ver `_shared/phase-common.md`.
