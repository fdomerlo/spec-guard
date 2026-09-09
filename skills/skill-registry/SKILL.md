---
name: skill-registry
description: >
  Escanea los directorios de skills personalizados (Global en $HOME/.skills-custom y Local en ./skills-custom) e identifica skills de terceros.
  Genera un índice en ./.spec-guard/skill-registry.md con nombre, descripción, trigger y ubicación de cada skill descubierta.
license: MIT
metadata:
  author: fdomerlo@gmail.com (136bits)
  version: "2.1"
---

# Skill-Registry Skill

## Disparador

Ejecutar al inicio de una tarea o manualmente para actualizar el índice de skills de terceros disponibles.

## Propósito

Eres un sub-agente responsable de **escanear y registrar skills personalizadas** disponibles para el usuario y el proyecto. Tu objetivo es generar un índice actualizado de todas las skills instaladas en `$HOME/.skills-custom` (Global) y `./skills-custom` (Local) que el orquestador puede usar además de las fases conocidas.

## Qué Recibís

Del orquestador:

- Nada (el script escanea automáticamente las rutas estándar global y local)

## Qué Hacer

### Paso 1: Ejecutar el Script de Escaneo

Ejecuta el script bash POSIX incluido en este skill:

```sh
sh skills/skill-registry/scan.sh
```

El script:

- Escanea `$HOME/.skills-custom` y `./skills-custom`
- Ignora directorios que comienzan con `_shared`
- Extrae nombre, descripción, trigger y ubicación de cada `SKILL.md`
- Genera el índice en `./.spec-guard/skill-registry.md`

### Paso 2: Devolver Resumen

## Reglas

- Ejecutar el script desde la raíz del proyecto
- El script es POSIX puro (`#!/bin/sh`), no requiere bash ni dependencias externas
- El índice generado sobrescribe el anterior si existe
- Si no hay skills adicionales, el índice debe indicarlo explícitamente
