---
name: changelog
description: >
  Genera automáticamente un CHANGELOG.md en la raíz del proyecto a partir de los cambios archivados en .spec-guard/changes/archive/.
  Disparador: Cuando el usuario ejecuta /changelog o quiere generar un changelog desde los cambios archivados.
license: MIT
metadata:
  author: fdomerlo@gmail.com (136bits)
  version: "1.0"
---

# Changelog Skill

## Propósito

Eres un sub-agente responsable de **generar el changelog** del proyecto. Leés todos los cambios archivados en `.spec-guard/changes/archive/` y generás un archivo `CHANGELOG.md` estructurado en la raíz del proyecto.

## Qué Recibís

Del orquestador:

- Nombre del proyecto (opcional, usa el directorio actual por defecto)

## Referencia

Consultar `skills/_shared/convention.md` para el schema de `state.ini`.

## Qué Hacer

### Paso 1: Detectar el Directorio del Proyecto

Determiná la raíz del proyecto y el directorio de archive:

```text
PROJECT_ROOT=.
ARCHIVE_DIR=.spec-guard/changes/archive/
```

### Paso 2: Listar Cambios Archivados

Listá todas las carpetas en el directorio de archive que coincidan con el patrón `YYYY-MM-DD-*`:

```text
.spec-guard/changes/archive/
├── 2026-01-15-fix-auth-bug/
├── 2026-02-01-agregar-modo-oscuro/
└── 2026-03-01-mejora-rendimiento/
```

### Paso 3: Extraer Metadatos de Cada Cambio

Para cada carpeta archivada, leé el archivo `proposal.md` y extraé:

- **Título**: Nombre del cambio (del nombre de la carpeta, sin la fecha)
- **Intención**: Sección "## Intención" del proposal.md
- **Alcance**: Sección "### Dentro del Alcance" del proposal.md

### Paso 4: Generar CHANGELOG.md

Creá el archivo `CHANGELOG.md` en la raíz del proyecto con el siguiente formato:

```markdown
# Changelog

Todos los cambios completados y archivados en el proyecto.

Generado el: {Fecha de generación en formato ISO}

---

## [{Fecha}] {Nombre-del-Cambio}

**Intención**: {resumen de la intención}

**Alcance**:
- {item 1}
- {item 2}

---

## [{Fecha}] {Nombre-del-Cambio}

**Intención**: {resumen de la intención}

**Alcance**:
- {item 1}
```

**Ordenar los cambios por fecha (más reciente primero).**

### Paso 5: Manejar Archive Vacío

Si no hay cambios archivados, generá un CHANGELOG.md con el encabezado pero sin cambios:

```markdown
# Changelog

Todos los cambios completados y archivados en el proyecto.

Generado el: {Fecha}

---

Aún no hay cambios archivados. Los cambios aparecerán aquí después de ser archivados con /archive.
```

### Paso 6: Devolver Resumen

Devuelve al orquestador:

```markdown
## Changelog Generado

**Ubicación**: CHANGELOG.md
**Cambios incluidos**: {N}
**Fecha de generación**: {ISO date}

### Cambios Registrados
| Fecha       | Cambio              | Intención                              |
|-------------|---------------------|----------------------------------------|
| 2026-01-15 | fix-auth-bug        | Corregir bug en autenticación         |
| 2026-02-01  | agregar-modo-oscuro | Añadir tema oscuro a la aplicación    |

### Archivo
{CHANGELOG.md generado exitosamente / CHANGELOG.md actualizado}
```

## Reglas

- SIEMPRE extraer la intención y el alcance del proposal.md
- SIEMPRE ordenar los cambios por fecha (más reciente primero)
- Si el directorio de archive no existe, crear CHANGELOG.md vacío
- Si ya existe un CHANGELOG.md, regenerarlo completamente
- Usar el nombre de la carpeta (sin la fecha) como título del cambio
- Aplicar cualquier `rules.changelog` de `.spec-guard/config.yaml` si existe
