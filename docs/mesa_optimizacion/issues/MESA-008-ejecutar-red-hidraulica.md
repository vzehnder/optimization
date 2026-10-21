# MESA-008 · Ejecutar una red hidráulica desde la misma mesa

Status: Done
Type: AFK
Triage: ready-for-agent
Assignee: Codex
Source: [Plan de implementación](../plan_implementacion.md)
User stories covered: HU-05, HU-11

## What to build

Adaptar el recorrido de ejecución a una red hidráulica válida, conservando sus opciones reales de preparación. Reutilizar preparación hidráulica, validación, huella de contenido, snapshot, worker y avance. Demostrar el camino con una central y un embalse; no equiparar el modelo v3 con el modelo eléctrico.

## Acceptance criteria

- [x] Seleccionar una red/versionado válido y el período desde la mesa, con identidad de todos los componentes incluidos.
- [x] Exponer objetivo económico/energético, selección de CMg, valor terminal del agua y opciones admitidas necesarias para ese caso.
- [x] La preparación muestra cobertura y remuestreo explícito cuando el servicio lo aplique; no hereda silenciosamente reglas incompatibles del camino eléctrico.
- [x] Congelar entradas y configuración exactas y comprobar la huella de preparación al ejecutar; cambios intermedios bloquean el envío.
- [x] Una corrida real de red mínima entrega resultados consultables por central y embalse y recupera su estado después de recargar.
- [x] Los errores de topología, entrada o capacidad del motor señalan el componente afectado sin inventar resultados.
- [x] Si la entrega inicial exige cooptimización mixta, no cerrar este ticket sin la dependencia de motor acordada y su prueba pública. No se exige según los contratos aceptados de MESA-001; se conserva v3 por su camino propio.
- [x] Confirmar integración del trabajo previo de simulación/progreso antes de reutilizarlo; preservar los flujos hidráulicos existentes.

## Blocked by

- [MESA-005 · Consultar centrales, embalses y otros objetos hidráulicos](MESA-005-consultar-serie-hidraulica.md)
- [MESA-006 · Editar entradas en tablas y guardar revisiones auditables](MESA-006-editar-entradas-versionadas.md)
- [MESA-007 · Ejecutar un caso eléctrico por fechas y recuperar su avance](MESA-007-ejecutar-caso-electrico-por-fechas.md)

## Validación TDD

Interfaces acordadas: S1 + S2; S3 solo si se modifica el motor.

Primer test: preparar y ejecutar una red mínima por API/UI y verificar la presencia de resultados de sus entidades. Probar aparte huella obsoleta y objetivo/precio incompatibles.

Aplicar la [estrategia TDD](../validacion_tdd.md) y la definición de terminado del plan. Las interfaces S1/S2 y S3 condicional fueron confirmadas por el usuario el 2026-10-20; registrar en MESA-001 cualquier interfaz adicional antes de probarla. Cada ciclo implementa un solo comportamiento observable.

## Demostración de cierre

Elegir la fecha y objetivo, ejecutar la serie hidráulica y consultar potencia y volumen sin salir de la mesa.

## Evidencia y seguimiento

- Inicio: 2026-10-21, por Codex. Dependencias Done; S1 navegador y S2 HTTP ya confirmadas. Primer ciclo: red mínima con worker real, resultados por entidad y recuperación HTTP. Se conserva el motor actual.
- Evidencia: [nueve ciclos rojo → verde, contrato, comandos y revisión](../evidencia/MESA-008/validacion.md).
- Pruebas nuevas: once HTTP y tres de navegador, incluyendo una corrida de red mínima con worker/Julia reales. 30 MW y 9.7336 hm³ observados por entidad, recarga y doble clic.
- Capturas: preparación/resultados a 1440/390 px inspeccionados. Teclado, Axe y geometría existente verificados; referencias originales intactas.
- Decisiones: ejecución desde versión promovida explícita, UTC y remuestreo hidráulico existente; snapshot/diagrama/run atómicos, huella revalidada e idempotencia por actor. Sin cambios del motor ni esquema de tablas.
- Verificación final: 145 Python, 26 navegador MESA, cinco regresiones generales y 336 Vitest OK. OpenAPI, build, TypeScript, ESLint y formato modificado OK; el check global conserva los 16 avisos previos de formato ajenos a la entrega.
- Cierre: **Done**, Codex, 2026-10-21, después de revisión técnica AFK y visual. PostgreSQL no está configurado; concurrencia comprobada con dos conexiones SQLite. Siguiente: MESA-009.
