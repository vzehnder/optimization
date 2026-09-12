# UX-000 · Acordar fronteras y registrar la línea base

Estado: Todo. Prioridad: P0. Dependencias: ninguna. Tamaño: S.

## Resultado

El ingeniero inicia con un recorrido reproducible, el estado real de TS-7 conocido y las fronteras TDD confirmadas. Esta tarea prepara la implementación; no agrega comportamiento de producto.

## Referencias

- [Diagnóstico](../01_diagnostico.md), [matriz funcional](../03_matriz_funcional.md), [estrategia TDD](../04_estrategia_tdd.md) y [validación](../05_validacion_y_entrega.md).
- `frontend/e2e/global-setup.ts`, `scripts/run_react_smoke_app.py`, `frontend/playwright.config.ts`.
- `tests/auth_test_helpers.py`, decisiones TS-3/TS-7 y arquitectura de configuración enlazadas en el diagnóstico.

## Pasos

1. Anotar commit, cambios locales y decisiones vigentes; comprobar los archivos afectados por el primer ticket. Conservar trabajo ajeno.
2. Levantar únicamente un entorno de prueba y comprobar las tres identidades/superficies. Anotar corte C6 y cuentas con lectura canónica; no confundir ambas condiciones.
3. Ejecutar las pruebas existentes necesarias del primer ticket. Distinguir fallo funcional, dependencia faltante y restricción del entorno. Los 78 tests de la revisión no sustituyen esa comprobación en una base futura.
4. Recorrer las tareas de línea base y registrar tiempos de interacción, ayuda, errores y capturas con datos de prueba. No usar los tiempos del manual como medición real.
5. Presentar al usuario/responsable las fronteras F1–F3 y F4 solo si aplica. Registrar fecha, alcance y confirmación antes de escribir una prueba nueva, tal como exige la habilidad TDD local.
6. Seleccionar una conducta de UX-001 o de la primera entrega priorizada y redactar su condición inicial y resultado esperado. Reutilizar fixtures; solo agregar uno cuando el primer ciclo lo necesite.

## Aceptación

- Existe un registro de línea base en un archivo nuevo de evidencia dentro de esta carpeta o adjunto a la PR.
- Se puede repetir la tarea principal con datos conocidos y sin afectar proyectos de trabajo.
- Están identificadas las capacidades que no deben desaparecer y las fronteras confirmadas para la primera implementación.
- Las pruebas existentes ejecutadas tienen resultado y limitaciones explícitos.

## TDD y cierre

No escribir tests de «la línea base» ni validar la existencia de esta documentación mediante pruebas de producto. La primera prueba RED pertenece al comportamiento de UX-001 u otro ticket elegido, después de la confirmación. No escribir por adelantado todas las pruebas de este plan.
