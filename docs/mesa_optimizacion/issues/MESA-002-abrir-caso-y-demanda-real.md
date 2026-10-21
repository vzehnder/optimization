# MESA-002 · Abrir un caso real y consultar demanda en la mesa

Status: Done
Type: AFK
Triage: ready-for-agent
Assignee: Codex
Source: [Plan de implementación](../plan_implementacion.md)
User stories covered: HU-01, HU-03, HU-10, HU-11

## What to build

Entregar el primer recorrido real desde el escenario a la mesa: seleccionar su contexto, descubrir un componente de demanda y mostrar su entrada en tabla y gráfico desde la misma fuente canónica. Resolver identidad, unidades, cobertura y permisos en el backend. Si se necesita una proyección de lectura nueva, incluirla junto con su consumidor; no crear otro almacén de muestras.

## Acceptance criteria

- [x] La entrada a la mesa conserva proyecto, escenario, caso y variante seleccionados y no muestra datos de otro contexto.
- [x] El componente se identifica por su identidad de dominio, no por el nombre visible; la UI distingue dato de entrada, parámetro y resultado.
- [x] Una misma serie de demanda se observa con idénticos valores, unidad y fechas en tabla y gráfico; aún no se ofrece edición.
- [x] El inventario y los valores se leen por contratos públicos, con estados vacío, carga, sin cobertura, error y reintento.
- [x] El servidor rechaza identidades fuera del contexto y permisos insuficientes; la nueva ruta no amplía capacidades de la consola externa.
- [x] Recargar la página vuelve a consultar los datos reales y conserva un contexto identificable.
- [x] Un test de navegador/API demuestra el recorrido con una fixture independiente y evidencia rojo → verde.

## Blocked by

- [MESA-001 · Acordar el alcance de la mesa y sus contratos observables](MESA-001-acordar-alcance-y-contratos.md)

## Validación TDD

Interfaces acordadas: S1 + S2

Primer test: abrir un caso con demanda conocida, alternar tabla/gráfico y recargar; verificar los mismos valores mediante la interfaz. Añadir un caso de identidad/permisos incorrectos en S2.

Aplicar la [estrategia TDD](../validacion_tdd.md) y la definición de terminado del plan. Las interfaces S1/S2 y S3 condicional fueron confirmadas por el usuario el 2026-10-20; registrar en MESA-001 cualquier interfaz adicional antes de probarla. Cada ciclo implementa un solo comportamiento observable.

## Demostración de cierre

Desde un escenario existente se abre la mesa y se consulta una serie real sin visitar otro editor.

## Evidencia y seguimiento

- Inicio: 2026-10-20, por Codex. Dependencia MESA-001 Done; interfaces S1/S2 ya confirmadas. Primer ciclo: consulta de demanda canónica por HTTP; después recorrido de navegador, aislamiento y estados de consulta.
- Evidencia: [ciclos TDD, comandos, revisión y límites](../evidencia/MESA-002/validacion.md).
- Implementación: ruta interna `/react/scenarios/:scenarioId/mesa?case=…&variant=…`,
  abierta desde **Escenario → Datos → Variante activa → Abrir mesa de optimización**.
  El backend deriva el proyecto y valida la pertenencia del caso y la variante.
- Contrato HTTP: `GET /api/scenarios/{scenario_id}/mesa?case_id=…&variant_id=…`.
  Admite `range_start` y `range_end` opcionales, ambos ISO con zona, para consultar
  intervalos exactos [inicio, fin). La selección de fechas para ejecutar pertenece
  a MESA-007. OpenAPI y tipos sincronizados.
- La proyección usa los requerimientos del modelo, los objetos vinculables y las
  revisiones de los bindings canónicos. Conserva lectura de variantes anteriores
  mediante su fuente existente. No crea tablas, muestras duplicadas ni migraciones.
- Pruebas: siete nuevas HTTP y tres de navegador; 336 regresiones Vitest;
  37 pruebas Python OK y cinco PostgreSQL omitidas por falta de base configurada.
  Cuatro regresiones de navegador cubren autenticación, escenario, preparación y resultados.
- TypeScript, ESLint, API check y formato de archivos modificados OK. El chequeo
  global de Prettier sigue señalando 16 archivos preexistentes no modificados;
  ver el log, sin atribuir ese resultado a un éxito global.
- Capturas revisadas: [gráfico 1440×900](../evidencia/MESA-002/mesa-demanda-1440.png)
  y [tabla móvil 390×844](../evidencia/MESA-002/mesa-tabla-390.png). Panel completo,
  teclado y Axe verificados; referencia A conservada. Matriz/pestañas en MESA-003.
- Revisión técnica AFK: identidad por clave y registro, permisos internos,
  consultas separadas por contexto/rango y cancelables, fuente única para tabla
  y gráfico, vacío/cobertura/error explícitos. No requiere aceptación HITL.
- Cierre y responsable: **Done**, Codex, 2026-10-20. Revisión técnica AFK y
  visual completadas; siete criterios satisfechos. MESA-003 es la siguiente
  entrega recomendada, con su dependencia satisfecha.
