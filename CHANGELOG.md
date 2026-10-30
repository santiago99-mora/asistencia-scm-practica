# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2026-09-10
### Added
- Función `obtener_reporte_estadistico` para extraer resumen de métricas e historial de asistencias.

## [2.0.1] - 2026-09-08
### Fixed
- Manejo de excepciones y validación de tipos nulos para el campo DNI en `registrar_asistencia`.

## [2.0.0] - 2026-09-05
### Changed
- **BREAKING CHANGE**: La función `registrar_asistencia` ahora recibe un diccionario con metadatos (`dni`, `materia`) en lugar de un `str` plano.

## [1.1.0] - 2026-09-03
### Added
- Acumulador y contador global de asistencias en tiempo de ejecución.

## [1.0.1] - 2026-08-20
### Fixed
- Eliminación de espacios en blanco en el DNI escaneado.

## [1.0.0] - 2026-08-01
### Added
- Lanzamiento inicial con validación básica de DNI.