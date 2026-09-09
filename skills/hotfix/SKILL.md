---
name: hotfix
description: >
  Inicia un flujo directo (Bypass / Fast-Track) saltando la fase de plan.
  Ideal para cambios menores o hotfixes. El cambio comienza directamente
  en la fase execute, con bypass auditado del gate humano de plan.
  Disparador: Cuando el usuario ejecuta /hotfix para un cambio directo.
license: MIT
metadata:
  author: fdomerlo@gmail.com (136bits)
  version: "2.1"
---

# Hotfix Skill

## Propósito

Esta skill proporciona un modo Bypass / Fast-Track para cambios menores o
hotfixes. Salta la fase de planificación (PLAN) e inicia directamente en
EXECUTE, con un gate humano auditado en 2 pasos via `sg hotfix-init` y `sg hotfix-confirm`.

## Requisitos del Usuario

**OBLIGATORIO**: El usuario DEBE proveer las instrucciones directas de código
en su prompt. Como se salta la fase PLAN, no existirán `objective.md` ni `design.md`.

## Protocolo de Ejecución (ACID)

### Paso 1: Inicialización del Estado (Bypass con gate humano en 2 pasos)

El humano debe ejecutar desde su propia terminal (estos comandos NO pueden ser invocados
por el agente — utilizan un token out-of-band):

1. Preparar el token out-of-band:
```bash
sg hotfix-init --change {change-name} --reason "descripción breve del hotfix"
```

2. Confirmar y consumir el token (en terminal humana):
```bash
sg hotfix-confirm --change {change-name} --token <CÓDIGO>
```

El comando `hotfix-confirm`:
1. Consume y elimina el token seguro generado fuera del workspace en `~/.spec-guard-gate/`.
2. Crea el directorio `.spec-guard/changes/{change-name}/` con `state.ini` v2.
3. Registra el bypass con razón en `state.ini[Gate]` (audit trail completo).
4. Avanza automáticamente el DAG: plan queda en `completed_phases`, `lock_phase=execute`.

### Paso 2: Iniciar la transacción de ejecución

```bash
sg begin --change {change-name} --phase execute
```

### Paso 3: Ejecución del Código

Aplica los cambios de código solicitados por el usuario directamente en los
archivos fuente del proyecto.

### Paso 4: Commit y Avance

Una vez aplicados los cambios con éxito, avanza la transacción hacia verificación:

```bash
sg commit --change {change-name} --next-phase verify
```
