# MESA-004 · Consulta eléctrica por componente

Fecha: 2026-10-20. Responsable: Codex. Interfaces S1 navegador y S2 HTTP,
confirmadas en MESA-001. No cambia el motor ni el contrato ejecutable.
Estado: Done después de revisión técnica AFK y visual.

## Recorrido y contrato

La configuración de vistas ofrece los BESS, demandas y renovables del modelo
actual, identificados por tipo, clave técnica y objeto vinculable. Los nombres
son etiquetas; un registro archivado se excluye. Las pestañas y preferencias de
MESA-003 siguen guardándose por usuario y caso.

Las entradas provienen de la revisión canónica vinculada o de la fuente de la
variante legacy. Los parámetros BESS y la penalización renovable aparecen como
escalares de la preparación actual, en un detalle separado de los gráficos.
Las señales usan `TIME_SERIES_SIGNAL_CATALOG` y `DISPATCH_SIGNAL_KEY_CATALOG`;
los nombres y unidades de parámetros corresponden al contrato del editor.

`GET /api/scenarios/{scenario_id}/mesa?case_id=…&variant_id=…` conserva su contrato
y añade `run_id` opcional, `context.model_contract`, `parameters`, `runs` y
`selected_run`. Cada salida identifica `run_id`, `scenario_version_id` y
`source=asset_dispatch`. La ruta React conserva el run en `?run=…`.
OpenAPI y tipos se regeneraron.

El selector ofrece ejecuciones exitosas v1/v2 del escenario y variante. Las
ejecuciones antiguas sin variante registrada solo se ofrecen en la variante
predeterminada. Un ID ajeno, de otra variante o sin éxito devuelve 404.
La lectura valida la presencia del activo en el snapshot y empareja filas por
`asset_id`, `asset_type`, columna e intervalos; nunca reparte el total del sistema
entre sus activos. Usa primero el índice por activo y, si falta, el CSV registrado
con la validación de rutas existente. No modifica índices, entradas ni snapshots.

Las salidas ausentes, columnas vacías, duraciones incompatibles y pérdida del
artefacto producen estado no disponible, sin ceros sustitutos. Las unidades MW
y MWh tienen gráficos/tablas separados. Las entradas y parámetros siguen
identificados como preparación actual al seleccionar una salida histórica; la
comparación antes/después pertenece a MESA-009.

La zona de un resultado se obtiene de su procedencia congelada o de la revisión
canónica inmutable identificada por ID y hash. Un snapshot legacy sin zona puede
consultarse en sus horas originales, con «zona no registrada»; no se le permite
un recorte por instantes con offset. Las duraciones con zona se suman en UTC.

Cambiar de run conserva las vistas locales sin guardar. Mientras llega la nueva
consulta se ocultan las muestras previas; caso, variante, rango y run forman la
clave de consulta y las solicitudes reciben cancelación.

## Ciclos rojo → verde observados

Se ejecutó cada comportamiento antes de su implementación. Las observaciones
de las pruebas usan HTTP y navegador; el acceso al almacén prepara fixtures.

| Ciclo | Interfaz / conducta | Rojo observado | Verde |
| --- | --- | --- | --- |
| 1 | S2, BESS y disponibilidad renovable sin run | Faltaban `battery_1` y `solar_north` en el inventario. | Disponibilidad [3, 5] MW; cinco salidas sin muestras. |
| 2 | S2, parámetros escalares y contrato | Faltaba `model_contract`. | Energía inicial 4 MWh, eficiencia 0.95 y límites, sin puntos horarios. |
| 3 | S2, consultar un run v1/v2 | Descarga devolvía `[]`. | Descarga [2, 0] MW y generación utilizada [2, 4] MW, con run/snapshot. |
| 4 | S2, índice ausente | La carga devolvía `[]` después de retirar el índice. | CSV existente devuelve [0, 1] MW. |
| 5 | S1, familias eléctricas | No existía el panel BESS ni su etiqueta de salida. | Parámetros, disponibilidad solar, vacío BESS, tabla/gráfico y recarga. |
| 6 | S2, inventario con nombres iguales | El BESS archivado seguía apareciendo. | Identidades separadas y exclusión del archivado. |
| 7 | S1, selección de ejecución | No existía «Resultados de ejecución». | Run recuperable en URL, descarga/energía y procedencia visibles. |
| 8 | S2, zona del resultado | Rango con offset devolvía `[]` para timestamps sin offset. | Zona America/Santiago aplicada desde procedencia congelada. |
| 9 | S2, duración incompatible | Se devolvía `available` para una fila de 2 h en un snapshot de 1 h. | Estado no disponible. |
| 10 | S1, conservar vista local | Desaparecía «Mi vista local» al cambiar de run. | Vista y aviso de cambios sin guardar conservados. |
| 11 | S2, zona desde revisión canónica | Al usar el linaje real sin campo timezone directo, volvía a devolver `[]`. | Se consulta la revisión sellada por ID/hash, sin consultar la revisión mutable actual. |
| 12 | S2, run legacy sin zona | No se podían consultar sus valores originales. | Se leen sin convertirlos a instantes; un recorte absoluto se rechaza con explicación. |

Además pasan pruebas S2 de selección de run fuera de contexto/sin éxito y columna
faltante/vacía. Son comprobaciones de regresión de las guardas incorporadas en
el ciclo de resultados, no ciclos rojos adicionales.

## Comandos y resultados

- API y regresiones: **98 descubiertas, 93 OK y cinco PostgreSQL omitidas** por
  ausencia de `POSTGRES_TEST_DATABASE_URL`. Incluye las 17 pruebas específicas
  de consulta de mesa (diez nuevas). [Log final](api-final.txt).
- Navegador MESA: **13/13 OK**, tres nuevas y diez de regresión.
  [Log final](playwright-final.txt).
- Regresión general de navegador: **4/4 OK**, autenticación, escenario,
  preparación y resultados. [Log](playwright-regression.txt).
- Frontend: **336/336 OK** en 37 archivos, con un worker para evitar los
  timeouts por contención observados en entregas anteriores. [Log](vitest-final.txt).
- Build, TypeScript, ESLint y [OpenAPI/tipos](api-schema-final.txt) OK.
  El [check global](check-final.txt) falla únicamente por el formato de los
  mismos 16 archivos preexistentes, sin cambios respecto de HEAD. El
  [formato de los archivos modificados](check-changed-files.txt) pasa.

```powershell
# Desde la raíz
.venv/Scripts/python.exe -m unittest -v tests.test_optimization_mesa tests.test_mesa_preferences tests.test_ts3_case_variant_api tests.test_ts7_009_run_materialization tests.test_react_auth tests.test_configuration_layer_access tests.test_ts4_result_indexing tests.test_results_review

# Desde frontend
npm.cmd run api:generate
npm.cmd run api:check
npm.cmd run build
npx.cmd playwright test --config=playwright.mesa.config.ts
npx.cmd playwright test e2e/react-foundation.spec.ts -g "React auth handles|React analyst workspace|UX-005|UX-006"
npm.cmd test -- --maxWorkers=1
npm.cmd run check
npx.cmd prettier --check src/OptimizationMesa.tsx src/MesaPreferences.tsx src/optimizationMesa.css e2e/optimization-mesa.spec.ts src/api/schema.ts openapi.json
```

## Revisión e incidencias

- La fixture del editor necesitaba `display_name`, no `name`, para conservar
  las etiquetas al registrar los componentes. Se corrigió la preparación; sus
  fallos no cuentan como rojo funcional.
- El editor vigente genera v2 incluso sin hidro; la expectativa inicial v1 se
  corrigió contra ese contrato. Los resultados se comprueban con snapshots v1 y v2.
- El primer comando de navegador se ejecutó desde la raíz y no encontró el
  servidor; se repitió desde `frontend`, como exige el runner existente.
- La primera regresión de navegador obtuvo 11/13: el mensaje de demanda sin fuente
  y la expectativa exacta del contexto necesitaban alinearse con el texto ampliado.
  Se conservó el mensaje específico de demanda y se verificó el contrato v2 en
  la expectativa. [Ejecución inicial](playwright-initial.txt).
- La primera regresión Python descubrió 98 tests: 92 OK, cinco PostgreSQL
  omitidos y una fixture TS-4 inválida. Referenciaba la variante inexistente 7
  antes de consultar resultados. Se corrigió esa fixture creando su variante y
  snapshot reales, conservando las guardas de ejecución. Su prueba aislada pasó.
  [Ejecución inicial](api-initial.txt).
- La revisión técnica eliminó la búsqueda cuadrática por timestamp. El listado
  de runs solo consulta las revisiones congeladas para el run seleccionado.
  No hay migraciones ni cambios al worker o a Julia.

Las salidas de prueba son artefactos deterministas persistidos e indexados, no
una ejecución nueva de Julia. Esta entrega valida consulta; la ejecución desde
la mesa corresponde a MESA-007. No se presenta esta evidencia como validación
física del solver ni como aceptación humana de MESA-014.

Capturas de implementación, sin sobrescribir las referencias originales:

- [Familias eléctricas a 1440×900](mesa-electricas-1440.png).
- [Familias eléctricas a 390 px](mesa-electricas-390.png).
- [Consulta de resultados](mesa-resultados-1440.png).

Entorno: Chromium de Playwright 1.61.0, DPR 1, idioma en-US, America/Santiago,
tema claro y movimiento reducido. Conserva la cabecera del producto y la matriz
de la referencia A. Los parámetros se despliegan dentro del panel; las series
múltiples usan desplazamiento local. No se crean baselines automáticas.

Revisión AFK completada por Codex: siete criterios satisfechos, lecturas aisladas
por contexto, sin resultados inventados ni escrituras al seleccionar un run.
Geometría, teclado, foco y Axe de las regresiones de mesa pasan; la nueva consulta
se adapta a 390 px sin desbordamiento horizontal global. Los cambios locales
previos se conservaron. Siguiente entrega recomendada: MESA-005.

Verificación documental: 24 Markdown, estados de los 14 tickets coherentes con
el tracker (cuatro Done y diez Todo), enlaces locales resueltos y dependencias
sin ciclos. Los hashes originales del HTML y ambos PNG, y sus dimensiones,
permanecen intactos. `git diff --check` sin errores de whitespace.
