# MESA-001 · Acordar el alcance de la mesa y sus contratos observables

Status: Done
Type: HITL
Triage: ready-for-agent
Assignee: Codex
Source: [Plan de implementación](../plan_implementacion.md)
User stories covered: HU-01, HU-05, HU-06, HU-11

## What to build

Revisar las decisiones propuestas contra un caso real de uso y fijar qué significa preparar, ejecutar y comparar desde la mesa. La aprobación conceptual del prototipo ya existe; este ticket resuelve ubicación, contexto, capacidades del motor, significado de «antes», persistencia visual e interfaces públicas de prueba. Registrar las decisiones para que las entregas AFK no dependan de interpretaciones distintas.

## Acceptance criteria

- [x] Registrar A · Paneles como diseño principal o el ajuste indicado por el usuario, manteniendo la pantalla única solicitada. Registrado conforme a la referencia conceptual en la propuesta del 2026-10-20.
- [x] Confirmar superficie interna del analista, contexto de caso/variante y alcance de la configuración por usuario/caso. Registro aceptado por el usuario el 2026-10-20.
- [x] Documentar qué combinaciones de BESS, demanda, renovables y red hidráulica son ejecutables hoy. Resolver si el caso objetivo exige cooptimización en un único modelo; si falta soporte, agregar una entrega vertical del motor y enlazarla como dependencia antes de prometer ejecución mixta. El usuario confirmó el alcance con los modelos existentes el 2026-10-20; no se requiere la extensión mixta v3 en este corte.
- [x] Acordar las reglas de entradas, outputs sin referencia, ejecución de referencia y Δ; no aceptar ceros o series ficticias como comparación. Registro aceptado el 2026-10-20.
- [x] Confirmar S1 (navegador), S2 (HTTP) y S3 condicional (contrato público del motor) con el usuario antes de escribir tests, conforme a la habilidad TDD. Confirmado el 2026-10-20.
- [x] Revisar granularidad, dependencias y clasificación AFK/HITL del tracker y registrar cambios sin dar por aprobadas decisiones no discutidas. El usuario pidió mantener el desglose propuesto el 2026-10-20.
- [x] Comprobar disponibilidad e integración del trabajo local de simulación hidráulica y progreso; registrar cualquier dependencia externa concreta. Integrado localmente en `d206e78`, con regresiones verificadas.

## Blocked by

Ninguna. Revisión HITL completada el 2026-10-20.

## Validación TDD

Interfaces acordadas: S1, S2 y uso condicional de S3, confirmadas el 2026-10-20. No escribir pruebas como parte de este trabajo de planificación.

Evidencia: decisión fechada con alternativas resueltas, aprobación de interfaces de prueba y tracker actualizado. No se marca Done por haber creado este documento.

Aplicar la [estrategia TDD](../validacion_tdd.md) y la definición de terminado del plan. Las interfaces S1/S2 y S3 condicional fueron confirmadas por el usuario el 2026-10-20; registrar en MESA-001 cualquier interfaz adicional antes de probarla. Cada ciclo implementa un solo comportamiento observable.

## Demostración de cierre

Un caso eléctrico y una red hidráulica de ejemplo ilustran el recorrido y sus diferencias; cada dato «antes» tiene una procedencia definida.

## Evidencia y seguimiento

- Trabajo iniciado el 2026-10-20 por Codex, a petición del usuario de ejecutar la
  siguiente entrega del tracker. HEAD inicial `817bf25`, árbol limpio.
- Entregable: [registro de alcance y contratos](../decision_record_mesa001.md).
  Incluye matriz v1/v2/v3, contexto y persistencia visual, antes/después/Δ,
  diferencias temporales, ejemplos eléctrico/hidráulico e integración comprobada.
- Diseño: A · Paneles conservado; PNG/HTML de referencia sin cambios. No se
  generaron capturas de implementación porque esta entrega no construye UI.
- TDD: S1/S2 y S3 condicional conservan su aprobación anterior. No se escribieron
  pruebas nuevas ni se modificó producto; el ticket excluye tests nuevos durante
  planificación. Las regresiones siguientes comprueban capacidades existentes y
  no se etiquetan como rojo → verde funcional de MESA-001.
- Conformidad HITL: el usuario respondió «confirmo» el 2026-10-20 a la propuesta
  de contratos con los modelos actuales. Quedan aceptados diseño, superficie
  interna, contexto, preferencias por usuario/caso y reglas antes/después/Δ.
- Alcance aprobado: contratos existentes, incluido hidro simple v2 integrado
  al balance eléctrico y red hidráulica v3 por su camino propio. La cooptimización
  de red v3 con BESS/demanda/renovables queda fuera de este corte; no se agrega
  una entrega de motor ni se modifica el grafo de las 14 entregas.
- Cierre: **Done**, responsable Codex, 2026-10-20, con revisión humana documentada.
  MESA-002 sigue Todo y tiene su dependencia satisfecha.

### Verificación ejecutada

Desde la raíz del repositorio:

```powershell
.\.venv\Scripts\python.exe -m unittest -v tests.test_hydraulic_simulation tests.test_ts3_case_variant_api tests.test_run_progress.RunProgressTests.test_api_exposes_progress_before_process_exit_and_keeps_it_after_timeout
```

Resultado inicial: 29 pruebas, 27 OK y 2 fallidas por `SystemError: longpath:
Acceso denegado` al cargar el entorno de Julia dentro del sandbox. Se repitieron
únicamente esas dos pruebas con permisos de ejecución ampliados:

```powershell
.\.venv\Scripts\python.exe -m unittest -v tests.test_hydraulic_simulation.HydraulicSimulationApiTests.test_economic_run_reaches_results_with_the_real_julia_executor tests.test_hydraulic_simulation.HydraulicSimulationApiTests.test_water_value_reaches_the_solver_and_preserves_water
```

Resultado: **2/2 OK**, 135.731 s. Las 29 pruebas seleccionadas quedan verificadas
entre ambas ejecuciones. Los tests HTTP usan SQLite aislado; los dos de solver
ejecutan Julia/HiGHS real y leen estado/resultados por HTTP. Las otras pruebas
usan dobles del validador/cola o del proceso, por lo que no prueban ejecución real.
El aviso de deprecación de Starlette/httpx no impidió la verificación.

Desde `frontend`:

```powershell
npm.cmd test -- src/HydraulicSimulation.test.tsx src/RunProgress.test.tsx
```

Resultado: **6/6 OK**, dos archivos, 7.74 s. Son regresiones React existentes
con dobles de HTTP/jsdom, complementarias; no equivalen a una prueba S1 en
navegador de la mesa.

Demostración con CLI pública existente, usando permisos ampliados por la misma
restricción del sandbox y escribiendo resultados solo en `.tmp/mesa001`:

```powershell
julia --project=. scripts/run_system_case.jl data/cases/hybrid_system/system_case.json --output-root .tmp/mesa001/v1 --run-timestamp 2026-10-20T00:00:00
julia --project=. scripts/run_system_case.jl data/cases/linear_hydro_system/system_case.json --output-root .tmp/mesa001/v2 --run-timestamp 2026-10-20T00:00:00
```

Resultado v1: **OPTIMAL / FEASIBLE_POINT**, cuatro períodos, demanda
[1, 1, 5, 0] MW, objetivo −3.763157894736845 USD.
Resultado v2: **OPTIMAL / FEASIBLE_POINT**, generación hidro 2 MWh, volumen
final 2.644 hm³ y objetivo 206.44 USD. La ejecución CLI demuestra disponibilidad;
no añade ni modifica pruebas S3.

Verificación documental: 20 Markdown, 14 tickets y 130 enlaces locales resueltos;
estados del tracker coincidentes y dependencias sin ciclos. Los tamaños y hashes
SHA-256 de HTML y ambos PNG coinciden con el manifest original; las dos imágenes
conservan 1440×900. `git diff --check` sin errores.
