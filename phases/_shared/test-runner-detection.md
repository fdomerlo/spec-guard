# Detección de Test Runner

## Propósito

Este helper contiene el pseudocódigo compartido para detectar el test runner del proyecto.

## Pseudocódigo

Detectar test runner desde:
├── .spec-guard/config.yaml → rules.{fase}.test_command (máxima prioridad)
├── package.json → scripts.test
├── pyproject.toml / pytest.ini → pytest
├── Makefile → make test
└── Fallback: reportar que los tests no pudieron ejecutarse automáticamente

## Uso

Para usar este helper:

- En `execute`: usar `rules.execute.test_command` como clave de configuración
- En `verify`: usar `rules.verify.test_command` como clave de configuración
