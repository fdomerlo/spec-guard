---
name: boot
description: >
  Despierta a SpecGuard, carga el contrato del DAG y sincroniza el estado actual sin modificar nada.
  Disparador: Para iniciar o retomar una sesión sin alterar el hilo de ejecución.
license: MIT
---

# Boot Skill (Arranque en Frío & Ignición SDD)

## Propósito
Activar SpecGuard, sincronizar el contexto unívoco del proyecto (Token Anchoring) mediante `sg context` y aplicar el protocolo **Read-First** sin alterar el hilo de ejecución ni generar código prematuro.

## Instrucciones OBLIGATORIAS (Ejecutar en orden estricto)

1. **Cargar el Contrato Base y Estado:**
   - Averigua dónde estamos parados ejecutando `sg status`.
   - Consulta el estado de transacción y la fase activa en `lock_phase`.

2. **Ignición de Contexto (Token Anchoring & Read-First):**
   - Ejecuta `sg context` (o `python3 -m spec_guard.cli context`) para proyectar el glosario estricto, stack obligatorio, roles y progreso de RFs de los documentos raíz (`requirements.md` y `design.md`).
   - **REGLA ABSOLUTA: Lectura y asimilación únicamente.** NO generes código ni edites archivos en este paso.
   - Identifica:
     * El stack tecnológico principal y motor de base de datos (`design.md §1`).
     * Las entidades principales del dominio y sus sinónimos prohibidos (`requirements.md §2`).
     * Los requerimientos funcionales pendientes y completados.
   - Si las plantillas raíz siguen con placeholders sin resolver o glosario vacío, alerta al usuario sugiriendo completarlas antes de iniciar el desarrollo.

3. **Reporte y Standby:**
   - Responde con un resumen conciso en **bullet points**:
     * Estado del framework y cambio activo (si existe).
     * Stack tecnológico y base de datos asimilados.
     * Entidades canónicas del glosario fijadas en memoria (y sinónimos que rechazarás).
     * Progreso de RFs (N total, M completados, K pendientes).
   - Pregunta final: *"¿Listo para recibir la primera orden de desarrollo?"*.
   - Queda a la espera de instrucciones del usuario, sugiriendo el siguiente paso (`/continue` si hay un cambio en curso, o `/new` si está libre).

