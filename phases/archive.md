# ARCHIVE Step

## Propósito

Paso final del ciclo, ejecutado automáticamente por VERIFY cuando el
veredicto es APROBADO o APROBADO CON ADVERTENCIAS. No existe un comando
separado para archivar manualmente — es la misma invocación de `/continue`
que corrió VERIFY.

## Qué Hacer

### 1. Control de bloqueantes

Verificar que `verify-report.md` no contenga issues **CRITICAL** y que
`verify-crit` haya retornado exit code 0. Si existen criterios no cubiertos
o tests rotos, ABORTAR.

### 2. Verificar estado git

```bash
git status --porcelain
```

- Salida vacía → repositorio limpio, continuar
- Salida no vacía → BLOQUEAR el archivado y exigir commit al usuario

### 3. Cerrar requerimientos / sincronizar specs

Detectá el modo del change: si `.spec-guard/changes/{change-name}/objective.md`
existe → **legacy**; si no (change con `[Scope] rf_ids`) → **raíz**.

**Modo raíz (2-File Root Protocol)** — `requirements.md` es la fuente de verdad,
no hay specs delta que fusionar. Por cada RF del scope (`sg rf-status --change {change-name}`):

```bash
sg mark-rf --change {change-name} --rf RF-XXX
```

`mark-rf` solo marca `[x]` (RF y sus criterios) si `lock_phase=verify`, el RF
está en el scope y `verify-crit` no tiene fallas. Si rechaza (exit 2/3/4),
ABORTAR el archivado y reportar. Nunca edites los checkbox de la raíz a mano.

**Modo legacy** — para cada spec en `.spec-guard/changes/{change-name}/specs/`:

**Si existe la spec principal** (`.spec-guard/specs/{dominio}/spec.md`):
- Requisitos AGREGADOS → agregar a la spec principal
- Requisitos MODIFICADOS → reemplazar el requisito coincidente
- Requisitos ELIMINADOS → eliminar el requisito coincidente
- PRESERVAR todos los requisitos no mencionados en el delta

**Si NO existe la spec principal:**
- La spec delta es completa. Copiarla directamente a
  `.spec-guard/specs/{dominio}/spec.md`.

### 4. Mover al archivo y limpiar sesión (SESSION.md)

1. **Archivado del cursor de sesión**: Si existe `.spec-guard/SESSION.md`:
   - Copiarlo a `.spec-guard/changes/{change-name}/SESSION.md` como registro
     histórico de la ejecución.
   - Eliminar `.spec-guard/SESSION.md` (`rm -f .spec-guard/SESSION.md`) para
     dejar el cursor limpio para futuros cambios. Si quedara un `SESSION.md`
     legacy en la raíz del repositorio, eliminarlo también.

2. **Mover directorio del cambio al archivo**:
```text
.spec-guard/changes/{change-name}/
  → .spec-guard/changes/archive/YYYY-MM-DD-{change-name}/
```

Usar la fecha de hoy en formato ISO.

### 5. Reportar archivado

```markdown
## Cambio Archivado

**Cambio**: {change-name}
**Archivado en**: .spec-guard/changes/archive/{YYYY-MM-DD}-{change-name}/
**Cursor SESSION.md**: Archivado y limpiado de `.spec-guard/`

### RF Cerrados (modo raíz) / Specs Sincronizadas (modo legacy)
| Dominio   | Acción             | Detalles                                       |
|-----------|--------------------|------------------------------------------------|
| {dominio} | Creado/Actualizado | {N agregados, M modificados, K eliminados}     |

### Ciclo del Agente Completo
El cambio ha sido planificado, implementado, verificado y archivado.
Listo para el siguiente cambio.
```

## Reglas

- NUNCA archivar si `verify-report.md` contiene issues CRITICAL
- SIEMPRE verificar git status antes de cerrar RF o sincronizar specs
- En modo raíz, los RF se cierran SOLO con `sg mark-rf` (nunca editando `requirements.md` a mano)
- Al fusionar, PRESERVAR los requisitos no mencionados en el delta
- El archivo es un rastro de auditoría — nunca eliminar ni modificar
  cambios archivados
- Si la fusión sería destructiva, ADVERTIR y pedir confirmación
- Aplicar cualquier `rules.archive` de `.spec-guard/config.yaml`
