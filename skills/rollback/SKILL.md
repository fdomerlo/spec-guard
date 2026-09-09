---
name: rollback
description: >
  Skill de emergencia para revertir un cambio activo. Purgar la carpeta del cambio y
  restaurar el entorno git al estado anterior. Disparador: Cuando el usuario ejecuta /rollback para revertir un cambio.
license: MIT
metadata:
  author: fdomerlo@gmail.com (136bits)
  version: "2.0"
---

# Rollback Skill

## Propósito

Skill responsable de **revertir completamente un cambio activo** en el DAG del agente. Skill de emergencia que purga la carpeta del cambio y restaura el entorno git a su estado anterior.

## Qué Recibís

- El nombre del cambio a revertir (opcional, usa el activo por defecto)

## Referencia

No cargues `skills/_shared/convention.md` por adelantado. Abrilo solo si
necesitás verificar un campo específico del schema de `state.ini` que no
te quede claro por el propio comportamiento del CLI.

## Qué Hacer

### Paso 1: Detectar Cambio Activo

Buscá el archivo `state.ini` con `status: active` en el directorio:

```text
.spec-guard/changes/*/state.ini
```

Si no existe ningún cambio activo, devolvé un error indicando que no hay cambio activo.

### Paso 2: Obtener Nombre del Cambio

Extrae el nombre del cambio desde el campo `change` del `state.ini` activo.

### Paso 3: Confirmar con el Usuario

Mostrá el siguiente mensaje de confirmación:

```text
⚠️ ¿Estás seguro de revertir el cambio "{nombre}"?
Esta acción es destructiva y eliminará:
- La carpeta .spec-guard/changes/{nombre}/
- Cualquier modificación no comprometida en el directorio de trabajo

Escribe "CONFIRMAR" para proceder o cualquier otra cosa para cancelar.
```

Si el usuario no confirma, cancelá la operación y salí sin acción.

### Paso 4: Purgar Carpeta del Cambio

Eliminá el directorio:

```text
.spec-guard/changes/{nombre}/
```

### Paso 5: Restaurar Entorno Git

Ejecutá los siguientes comandos desde la raíz del proyecto:

```bash
git restore -- .
```

### Paso 6: Devolver Resultado

Devolvé el resultado en el formato:

```markdown
## Resultado del Rollback

**status**: ok | error

### detailed_report
- Cambio revertido: {nombre}
- Estado: purged & restored
- Ubicación previa: .spec-guard/changes/{nombre}/
```

## Reglas

- SIEMPRE confirmar antes de ejecutar operaciones destructivas
- Si no hay cambio activo, mostrar error
- El mensaje de confirmación debe ser claro y advertir sobre la destrucción
- Verificar que git restore tenga éxito
- Este skill no debe usarse para cambios finalizados (todas las fases completadas, o cambio ya archivado)
