# Definition of Done (Condensada)

Barra transversal permanente que todo cambio debe cumplir antes de ser considerado completo.

## Checklist Obligatorio

### 1. Correctness (Corrección)
- [ ] Todos los criterios de aceptación (CRIT-XX) del cambio o RF están cumplidos y verificados.
- [ ] El código corre y se comporta como se espera en tiempo de ejecución (no solo compila/pasa tipos).
- [ ] Cada nuevo comportamiento está cubierto por tests deterministas (TDD: falla sin el cambio, pasa con él).
- [ ] La suite completa de tests preexistente sigue en verde (sin regresiones).
- [ ] Flujos de excepción y casos de borde manejados, no solo el camino feliz.

### 2. Quality (Calidad y Simplicidad)
- [ ] El código revela intención por su estructura y nombres; sin comentarios que expliquen *qué* hace.
- [ ] Glosario Estricto respetado: cero sinónimos prohibidos (`sg glossary-check`).
- [ ] Stack Obligatorio respetado: sin dependencias no aprobadas ni librerías fuera de `design.md §1`.
- [ ] Sin duplicación de lógica de negocio (DRY).
- [ ] Sin código muerto, print de debug o bloques comentados residuales.
- [ ] Formateo y linters limpios.

### 3. Integration (Integración y Persistencia)
- [ ] Cambios de esquema o migraciones de base de datos declaradas y reversibles.
- [ ] Retrocompatibilidad preservada en interfaces públicas o contratos existentes.
- [ ] Archivos de sesión y estado efímeros confinados a `.spec-guard/`.

### 4. Ship-readiness (Listura de Entrega)
- [ ] Checklist de seguridad revisado para entradas de usuario y auth.
- [ ] Trazabilidad determinista verificada con `sg verify-crit`.
- [ ] Aprobación humana explícita del plan y verificación de cierre.
