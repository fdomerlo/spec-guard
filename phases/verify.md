
# VERIFY Phase

## Propósito

La fase **VERIFY** es la puerta de calidad final. Demuestra —con evidencia de ejecución real— que la implementación está completa, es correcta y cumple conductualmente con las specs. El análisis estático por sí solo NO es suficiente. DEBÉS ejecutar el código.

Al final de VERIFY, si el veredicto es APROBADO, se ejecuta el **paso de archivado** como parte de esta fase.

## Qué Hacer

### Paso 1: Leer el Contexto

Antes de verificar, leé las dependencias:

1. **Specs delta** — `.spec-guard/changes/{change-name}/specs/`
2. **Plan** — `.spec-guard/changes/{change-name}/objective.md` y `design.md`
3. **Tareas** — `.spec-guard/changes/{change-name}/tasks.md`

**REGLA CRÍTICA:** PROHIBIDO cargar `specs/` completo del proyecto. Solo specs delta del cambio activo.
**REGLA CRÍTICA:** PROHIBIDO buscar en todo el código base. Solo archivos mencionados en las tareas del cambio.

### Paso 2: Verificar Completitud

```text
Leer tasks.md
├── Contar total de tareas
├── Contar tareas completadas [x]
├── Listar tareas incompletas [ ]
└── Marcar: CRITICAL si tareas centrales incompletas
         WARNING si tareas de limpieza incompletas
```

También invocar el middleware para conteo determinista:

```bash
python3 scripts/state_manager.py check-completion --change {change-name}
```

### Paso 2b: Verificación Determinista de Criterios (CRIT-XX)

Invocar el validador determinista de criterios de aceptación:

```bash
python3 -m spec_guard.cli verify-crit --change {change-name}
# o alternativamente:
./scripts/verify-crit.sh {change-name}
```

```text
verify-crit:
├── Extrae criterios CRIT-XX de tasks.md, design.md u objective.md
├── Verifica anotaciones: [automated] vs [manual]
├── Para cada criterio [automated]:
│   └── Busca trazabilidad en archivos de test (tests/, test/, spec/, src/)
└── Retorna:
    ├── 0 si todos los criterios automatizados están cubiertos por tests
    └── 2 (BLOQUEANTE) si existen criterios automatizables sin tests
```

**REGLA CRÍTICA:** Si `verify-crit` retorna código de salida 2 o detecta criterios automatizables sin trazabilidad en tests, el veredicto es **RECHAZADO** (CRITICAL). La fase no puede aprobarse ni archivarse con criterios de aceptación huérfanos.

### Paso 3: Verificar Corrección (coincidencia con specs)

```text
PARA CADA REQUISITO en specs/:
├── Buscar evidencia de implementación en el código base
├── PARA CADA ESCENARIO:
│   ├── ¿La precondición GIVEN está manejada?
│   ├── ¿La acción WHEN está implementada?
│   ├── ¿El resultado THEN se produce?
│   └── ¿Los casos límite están cubiertos?
└── Marcar: CRITICAL si falta el requisito, WARNING si escenario parcialmente cubierto
```

### Paso 4: Verificar Coherencia (coincidencia con el plan)

```text
PARA CADA DECISIÓN en design.md:
├── ¿Se usó realmente el enfoque elegido?
├── ¿Se implementaron accidentalmente las alternativas rechazadas?
├── ¿Los cambios de archivos coinciden con la tabla del plan?
└── Marcar: WARNING si se encontró una desviación
```

### Paso 5: Verificar Testing

```text
Buscar archivos de test relacionados con el cambio
├── ¿Existen tests para cada escenario de spec?
├── ¿Los tests cubren caminos felices?
├── ¿Los tests cubren casos límite?
├── ¿Los tests cubren estados de error?
└── Marcar: WARNING si hay escenarios sin tests
         SUGGESTION si la cobertura puede mejorar
```

### Paso 5b: Ejecutar Tests (ejecución real)

CRÍTICO: Ejecutar usando terminal real. PROHIBIDO simular o inferir el resultado.

Detectar el test runner consultando `phases/_shared/test-runner-detection.md`.

### Paso 5c: Build y verificación de tipos (ejecución real)

```text
Detectar comando de build desde:
├── .spec-guard/config.yaml → rules.verify.build_command (máxima prioridad)
├── package.json → scripts.build → también ejecutar tsc --noEmit si existe tsconfig.json
├── pyproject.toml → python -m build o equivalente
├── Makefile → make build
└── Fallback: omitir y reportar como WARNING (no CRITICAL)
```

### Paso 5d: Validación de cobertura (si configurado)

Solo ejecutar si `rules.verify.coverage_threshold` está definido en `.spec-guard/config.yaml`.

### Paso 6: Matriz de Cumplimiento de Specs

```text
PARA CADA REQUISITO en specs/:
  PARA CADA ESCENARIO:
  ├── Encontrar tests que cubren este escenario
  ├── Consultar el resultado de ese test desde el Paso 5b
  ├── Asignar estado:
  │   ├── ✅ CUMPLE   → el test existe Y pasó
  │   ├── ❌ FALLANDO → el test existe PERO falló (CRITICAL)
  │   ├── ❌ SIN TEST → no existe test para este escenario (CRITICAL)
  │   └── ⚠️ PARCIAL  → el test existe, pasa, pero cubre solo parte (WARNING)
  └── Registrar: requisito, escenario, archivo de test, nombre, resultado
```

### Paso 7: Persistir el Reporte

```bash
# Escribir en disco
.spec-guard/changes/{change-name}/verify-report.md
```

Formato:

```markdown
## Reporte de Verificación

**Cambio**: {change-name}

### Completitud
| Métrica            | Valor |
|--------------------|-------|
| Tareas totales     | {N}   |
| Tareas completas   | {N}   |
| Tareas incompletas | {N}   |

### Ejecución de Build y Tests
**Build**: ✅ Pasó / ❌ Falló
**Tests**: ✅ {N} pasaron / ❌ {N} fallaron / ⚠️ {N} omitidos
**Cobertura**: {N}% / umbral: {N}% → ✅/⚠️/➖

### Matriz de Cumplimiento de Specs
| Requisito | Escenario | Test | Resultado |
|-----------|-----------|------|-----------|
| {REQ-01}  | {Nombre}  | `{test}` | ✅ CUMPLE |

### Trazabilidad de Criterios de Aceptación (CRIT-XX)
**Comando**: `python3 -m spec_guard.cli verify-crit --change {change-name}`
| Criterio | Tipo | Evidencia / Ubicación de Test | Estado |
|----------|------|-------------------------------|--------|
| {CRIT-01}| auto | `tests/unit/test_*.py`        | ✅ CUBIERTO / ❌ SIN TEST |

### Problemas Encontrados
**CRITICAL**: {Lista o "Ninguno"}
**WARNING**: {Lista o "Ninguno"}
**SUGGESTION**: {Lista o "Ninguno"}

### Veredicto
{APROBADO / APROBADO CON ADVERTENCIAS / RECHAZADO}
```

### Paso 8: Decidir

```text
Si hay issues CRITICAL o verify-crit falló (exit 2):
  → Ejecutar ROLLBACK y reportar los problemas al usuario
  → El cambio vuelve a EXECUTE para corrección

Si veredicto es APROBADO o APROBADO CON ADVERTENCIAS:
  → Ejecutar COMMIT (verify es la fase final del DAG)
  → Cargá `phases/archive.md` y ejecutá el archivado inmediatamente
```

## Reglas

- SIEMPRE leer el código fuente real — no confiar en resúmenes
- SIEMPRE ejecutar tests — el análisis estático solo no es verificación
- Un escenario de spec solo es CUMPLIDO cuando un test que lo cubre ha PASADO
- Los issues CRITICAL = deben resolverse antes de archivar
- Los WARNING = deberían resolverse pero no bloquean
- Las SUGGESTION = mejoras, no bloqueantes
- NO corregir ningún problema durante VERIFY — solo reportarlos
- Aplicar cualquier `rules.verify` de `.spec-guard/config.yaml`

> Transacción: BEGIN antes de este contenido, COMMIT al terminar (Paso 8). Ver `_shared/phase-common.md`.
> Archivado: ver `phases/archive.md`, cargado solo si el veredicto es APROBADO.
