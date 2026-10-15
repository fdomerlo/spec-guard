# Protocolo de Intake y Doubt-Driven Spec Builder

## Propósito
Transformar un requerimiento expresado por el usuario en lenguaje natural crudo en un Requerimiento Funcional formal (`RF-XXX`) en `requirements.md` y sus contratos en `design.md`, erradicando suposiciones silenciosas y sin escribir código prematuro.

## Las 5 Etapas del Protocolo

### 1. INTAKE (Captura del Pedido Crudo)
- El usuario plantea una necesidad en lenguaje natural (ej. *"quiero permitir que los odontólogos registren la evolución del paciente"*).
- **REGLA ABSOLUTA:** PROHIBIDO escribir código, crear archivos fuente o dar por hecho aspectos técnicos/funcionales no expresados.

### 2. CONFLICT SCAN (Escaneo Preventivo)
Antes de interactuar con el usuario, el agente debe:
- Consultar `sg context` para proyectar el Glosario Estricto (`requirements.md §2`), Stack Obligatorio (`design.md §1`), Roles y Fuera del Alcance (Out of Scope).
- Verificar si el pedido:
  * Usa términos prohibidos (ej. si el usuario dijo *"historial"* o *"ficha"* cuando el término unívoco es *"Historia Clínica"*).
  * Choca contra un ítem explícitamente listado en *Fuera del Alcance*.
  * Duplica o modifica requerimientos funcionales (`RF-XXX`) ya existentes.

### 3. ASK / DOUBT (Modo Entrevistador Guiado por la Duda)
Si existen ambigüedades, decisiones de interfaz, flujos alternativos o modelado de datos sin definir:
- Formular hasta **7 preguntas concisas**, numeradas.
- Cada pregunta DEBE incluir:
  * Opciones cerradas identificadas con letras (A, B, C).
  * Una opción sugerida con la marca `(Recomendada)`.
  * Razón técnica breve (alineada al stack en `design.md` o patrones del proyecto).
- **STOP OBLIGATORIO:** El agente debe frenar su ejecución y esperar la respuesta del usuario. No asumir respuestas por omisión.

### 4. DRAFT (Redacción Formal en Documentos Raíz)
Una vez obtenidas las respuestas del usuario:
1. Consultar el próximo ID secuencial disponible:
   ```bash
   sg next-rf-id [--module RF-XXX]
   ```
2. Redactar el nuevo bloque en `requirements.md`:
   ```markdown
   ### [ ] RF-XXX: {Título del Requerimiento}
   - **Módulo:** {RF-Módulo Padre}
   - **Descripción:** {Descripción precisa con vocabulario del glosario}
   - **Criterios de Aceptación:**
     - [ ] CRIT-XXX-1 [automated]: {Comportamiento comprobable por test}
     - [ ] CRIT-XXX-2 [manual]: {Verificación humana si aplica}
   - **Flujo de Excepción:** {Manejo de errores o validaciones}
   ```
3. Si el requerimiento introduce modelos o endpoints, redactar los contratos correspondientes en `design.md` (§2 Modelo de Datos, §3 Endpoints/HTMX).

### 5. REVIEW (Revisión Adversarial Acotada)
- Validar formalmente los documentos:
  ```bash
  sg validate-spec
  sg glossary-check
  ```
- Ciclo de duda adversarial: ¿Hay supuestos no validados? ¿Se respetó el Glosario Estricto y el Stack Obligatorio?
- Presentar el borrador al usuario para confirmación e inicializar el change transaccional:
  ```bash
  sg init-change --change {change-name} --rf RF-XXX
  ```
