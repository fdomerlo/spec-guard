# Security Checklist (Condensada)

Checklist de seguridad para aplicaciones web y APIs antes de cerrar la fase VERIFY.

## Pre-Commit y Secretos
- [ ] Sin secretos en código ni commits (`grep -i "password\|secret\|api_key\|token"` en diff).
- [ ] `.gitignore` cubre `.env`, `*.pem`, `*.key`, tokens locales.
- [ ] Secretos provistos exclusivamente mediante variables de entorno en runtime.

## Autenticación y Autorización
- [ ] Passwords con hash seguro (bcrypt, argon2, pbkdf2).
- [ ] Cookies de sesión configuradas con flags `HttpOnly`, `Secure`, `SameSite=Lax/Strict`.
- [ ] Rate limiting o throttling en endpoints de autenticación y operaciones sensibles.
- [ ] Verificación de propiedad/rol en cada acceso a recursos (prevención de IDOR).
- [ ] Tokens JWT o sesiones validados en firma, expiración y emisor.

## Validación de Entradas e Inyecciones
- [ ] Toda entrada de usuario validada en el límite del sistema (schemas, formularios, serializers).
- [ ] Consultas a base de datos parametrizadas mediante ORM o sentencias preparadas (cero concatenación SQL).
- [ ] Sanitización y escape contextual de salidas HTML/templates (prevención de XSS).
- [ ] Carga de archivos validada en extensión, tipo MIME real y tamaño máximo.

## Exposición y Manejo de Errores
- [ ] Errores en producción nunca exponen stack traces ni detalles internos de infraestructura.
- [ ] Headers de seguridad básicos activos (CSP, X-Content-Type-Options: nosniff, X-Frame-Options: DENY).
- [ ] CORS configurado restrictivamente a dominios autorizados (sin wildcard `*` con credenciales).
