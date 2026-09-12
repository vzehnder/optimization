# UX-000 · Acordar fronteras y registrar la línea base

Estado: In Review. Prioridad: P0. Dependencias: ninguna. Tamaño: S.

Evidencia preparada: [línea base, recorridos, capturas y propuesta de fronteras](../evidencia/ux-000/README.md). Falta la confirmación del usuario para cerrar UX-000; UX-001 no ha comenzado.

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

## Resolución

- Responsable: Codex.
- Fecha de inicio y entrega para revisión: 2026-09-12.
- Fecha de aceptación / persona que acepta: pendientes del usuario.
- Estado: In Review; no marcar Done hasta confirmar las fronteras.
- PR o commits: commit de preparación `docs(ux): record reproducible UX-000 baseline`, sobre `428b6adf90f7c7204ff9e72585f83ee06f7162a9`; resolución pendiente de aceptación.
- Trabajo preparado: servidor SQLite en memoria con fixtures existentes, registrador exploratorio, cinco identidades, C6 comprobado, siete recorridos, 17 PNG y registro JSON. [Evidencia y repetición](../evidencia/ux-000/README.md).
- Criterios satisfechos: línea base nueva, tarea principal reproducible sin datos de trabajo, capacidades a conservar y resultados explícitos de regresión. [Lista de aceptación](../evidencia/ux-000/README.md#aceptación-pendiente).
- Fronteras: F1/F2 y F3 condicional propuestas para UX-001; confirmación pendiente. F4 no aplica. [Acuerdo y primer comportamiento](../evidencia/ux-000/README.md#fronteras-propuestas-para-aprobación).
- RED → GREEN: no aplica a UX-000; no hay pruebas nuevas ni cambios de producto. Primer ciclo preparado: «Crear modelo» desde escenario sin draft, por F2 y luego recorrido F1.
- Regresiones: 62 Vitest, 6 Playwright (incluido axe/teclado), 18 Python; todas aprobadas. Build TypeScript/Vite correcto. [Comandos y resultados](../evidencia/ux-000/README.md#regresiones-ejecutadas-en-esta-base).
- Visual: proyecto/escenario a 1280×720, 1440×900 y 320×900; capturas de tareas, consola, portal y catálogo. Foco observado en BODY al abrir editor; registrado para UX-001.
- Conservación funcional: raíces, proyectos/escenarios, editor, hidráulica, variantes, JSON/versiones, corridas, datos, informes, consolas y acciones de administración identificadas. [Alcance de evidencia por fila](../evidencia/ux-000/README.md#capacidades-a-conservar-en-ux-001).
- Compatibilidad/permisos: C6 inactivo, lectura canónica solo para cuenta interna de verificación; acceso externo separado y regresión API de capacidades/revocación aprobada. No se afirma validación de C6 activo ni PostgreSQL.
- Limitaciones: tiempos automatizados sin participantes; solver y resultados smoke sintéticos; comparación con fixture indexado existente. Julia real, suite completa, zoom alto y lector de pantalla no ejecutados; no eran cambios de este ticket.
