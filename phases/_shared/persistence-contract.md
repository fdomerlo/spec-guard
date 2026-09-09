# Contrato de Persistencia (Compartido entre todas las skills del agente)

## Persistencia Directa (File System)

El framework utiliza el File System como único mecanismo de persistencia nativo. Todas las operaciones de lectura y escritura de artefactos se realizan bajo el directorio `.spec-guard/` siguiendo la convención [convention.md](../../skills/_shared/convention.md).

## Persistencia Transaccional del Estado

El Memory Guard persiste el estado del DAG en `.spec-guard/changes/{change-name}/state.ini` mediante el protocolo de transacciones (ver [transaction-protocol.md](./transaction-protocol.md)).

Cada transición de fase sigue el ciclo: BEGIN → EXECUTE (persistir artefacto) → COMMIT (invocar `state_manager.py commit` en la terminal).

**Responsabilidad de escritura:**

| Quién | Qué muta en state.ini |
|-------|---------------------------|
| Memory Guard (transacción) | Todos los campos de fase y transacción |
| `checkpoint` | Solo `session_summary` y `last_updated` |

## Ejecución Inline vs Delegada

### Ejecución Inline (por defecto)

Cuando ejecutás una fase inline, vos mismo sos responsable de:

1. Ejecutar BEGIN (invocar `state_manager.py begin` en la terminal)
2. Leer artefactos de dependencia del disco
3. Ejecutar la fase
4. Persistir el artefacto resultante en disco
5. Ejecutar COMMIT (invocar `state_manager.py commit` en la terminal)

### Ejecución Delegada (fases pesadas)

Cuando delegás a un sub-agente:

| Tarea | Quién lo hace |
|-------|---------------|
| Leer artefactos de dependencia | **El sub-agente** |
| Ejecutar la fase | **El sub-agente** |
| Persistir artefacto en disco | **El sub-agente** |
| Actualizar `state.ini` (COMMIT) | **Vos (Memory Guard)** |

El sub-agente NUNCA escribe en `state.ini`. Solo persiste sus artefactos y retorna un resumen.

## Protocolo de Comunicación (para fases delegadas)

**Fase con dependencias:**

```text
Lee estos artefactos antes de comenzar:
- {ruta del archivo para cada dependencia}
Si hay un glosario en .spec-guard/config.yaml, cargarlo y usarlo para terminología consistente.
Después de completar tu trabajo, persistí tu artefacto siguiendo convention.md.
```

**Fase sin dependencias:**

```text
Si hay un glosario en .spec-guard/config.yaml, cargarlo y usarlo para terminología consistente.
Después de completar tu trabajo, persistí tu artefacto siguiendo convention.md.
```

## Carga de Glosario

Al inicio de cada skill:

1. Buscar archivo `.spec-guard/config.yaml`
2. Si existe y contiene clave `glossary`, cargar los términos
3. Usar los términos definidos para mantener consistencia en el output
4. Si no existe el glosario, continuar normalmente (es opcional)

### Graceful Degradation

- Si `.spec-guard/config.yaml` NO existe → continuar sin glosario
- Si el archivo existe pero NO tiene sección `glossary:` → continuar sin glosario
- Si la sección `glossary:` existe pero está vacía o malformada → continuar sin glosario, sin lanzar error
