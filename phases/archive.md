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

### 3. Sincronizar specs delta con specs principales

Para cada spec en `.spec-guard/changes/{change-name}/specs/`:

**Si existe la spec principal** (`.spec-guard/specs/{dominio}/spec.md`):
- Requisitos AGREGADOS → agregar a la spec principal
- Requisitos MODIFICADOS → reemplazar el requisito coincidente
- Requisitos ELIMINADOS → eliminar el requisito coincidente
- PRESERVAR todos los requisitos no mencionados en el delta

**Si NO existe la spec principal:**
- La spec delta es completa. Copiarla directamente a
  `.spec-guard/specs/{dominio}/spec.md`.

### 4. Mover al archivo y limpiar sesión (SESSION.md)

1. **Archivado del cursor de sesión**: Si existe `SESSION.md` en la raíz del
   repositorio:
   - Copiar o mover `SESSION.md` a
     `.spec-guard/changes/{change-name}/SESSION.md` como registro histórico
     de la ejecución.
   - Eliminar `SESSION.md` de la raíz del repositorio (`rm -f SESSION.md`)
     para dejar el espacio de trabajo limpio para futuros cambios.

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
**Cursor SESSION.md**: Archivado y limpiado de la raíz

### Specs Sincronizadas
| Dominio   | Acción             | Detalles                                       |
|-----------|--------------------|------------------------------------------------|
| {dominio} | Creado/Actualizado | {N agregados, M modificados, K eliminados}     |

### Ciclo del Agente Completo
El cambio ha sido planificado, implementado, verificado y archivado.
Listo para el siguiente cambio.
```

## Reglas

- NUNCA archivar si `verify-report.md` contiene issues CRITICAL
- SIEMPRE verificar git status antes de sincronizar specs
- Al fusionar, PRESERVAR los requisitos no mencionados en el delta
- El archivo es un rastro de auditoría — nunca eliminar ni modificar
  cambios archivados
- Si la fusión sería destructiva, ADVERTIR y pedir confirmación
- Aplicar cualquier `rules.archive` de `.spec-guard/config.yaml`
