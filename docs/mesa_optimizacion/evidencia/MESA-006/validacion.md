# MESA-006 · Edición canónica desde la mesa

Estado: Done. Fecha: 2026-10-20. Responsable: Codex.
Interfaces acordadas: S1 navegador y S2 HTTP; no se modifica el motor.

## Ciclos observados

| Ciclo | Conducta | Rojo | Verde |
| --- | --- | --- | --- |
| 1 · S2 | Editar demanda, recargar y consultar actor/procedencia | GET de edición devolvía 404. | `[10, 12]` → `[10, 15]`, revisión canónica recuperada por HTTP. La consulta de revisiones locales usa la ruta del objeto, no el catálogo genérico. |
| 2 · S2 | Editor concurrente | El segundo guardado devolvía 201 y reemplazaba 15 por 99. | 409 y lectura posterior `[10, 15]`. |
| 3 · S2 | Unidad de la entrada | Aceptaba MWh para una señal MW. | 400 sin publicación. |
| 4 · S2 | Cobertura e intervalos | Aceptaba quitar la segunda hora. | 400; solo se editan valores de los intervalos originales completos. |
| 5 · S2 | Confirmación del alcance | Publicaba con `confirm: false`. | 400 sin publicación. |
| 6 · S1 | Tabla → guardar → recargar → gráfico | No existía «Editar entrada». | Recorrido real con 15 MW y procedencia, sin salir de la mesa. Se corrigió también el Content-Type de la petición JSON durante este ciclo. |
| 7 · S2 | Segunda revisión de la copia local | 422: timestamps canónicos sin offset al volver a publicar. | Revisión 2 en la misma fuente, `[10, 18]`, conservando el instante y las revisiones anteriores. |
| 8 · S2 | Límite semántico | Aceptaba demanda −1. | 422 con límite del descriptor; sin definir ni publicar otra serie. |
| 9 · S1 | Cierre con borrador | Escape cerraba y perdía la edición sin advertencia. | Seguir editando conserva 99; descartar no publica y devuelve el foco. |
| 10 · S1 | Recuperación de conflicto | Faltaba «Recargar y comparar». | Tabla Original/Borrador/Actual `[12, 99, 15]`; cargar la revisión actual exige volver a confirmar. |
| 11 · S2 | Tipo numérico | Interpretaba `true` como 1. | 422; números estrictos y finitos. |
| 12 · S2 | Fuente modificada fuera de la mesa | Devolvía 400 genérico. | 409 explicativo; vínculo obsoleto de solo lectura hasta revisarlo desde Datos. |
| 13 · S1 | Mensaje de validación | Mostraba `Request failed (422)`. | El cliente interpreta `application/problem+json` y presenta el intervalo y límite rechazados. |
| 14 · S1 | Columna editable móvil | Ratio visible del input 0 a 390 px. | La columna editable cabe en el viewport; tabla con anchos adaptados, sin scroll horizontal global. |
| 15 · S1 | Desconexión y reintento | Reconectar reiniciaba el formulario y dejaba Guardar deshabilitado; después restablecía el modo del panel. | Borrador conservado, reintento guarda 15 y mantiene la tabla abierta; sin recarga automática al reconectar en entrada, consulta y preferencias. |

Comando focalizado: `.venv/Scripts/python.exe -m unittest -v tests.test_mesa_editing`.

## Alcance

Se compone publicación canónica de serie local y reemplazo de vínculo de variante
en una transacción. SQLite usa savepoints dentro de esta operación para impedir
que los servicios internos confirmen una publicación parcial. No hay tablas nuevas.

`GET /api/scenarios/{scenario_id}/mesa/inputs/{object_id}/{signal_key}` obtiene
la revisión completa, unidad, límites, actor, procedencia y alcance de copia/revisión.
`POST .../revisions` exige caso, variante, revisión/hash esperados, revisión de
bindings, unidad, todos los intervalos, motivo y confirmación. La identidad del
actor procede de la sesión, con permisos internos y CSRF existentes.

La primera edición crea una serie específica del objeto mediante los servicios
canónicos de definición, ingestión y publicación. Reemplaza exclusivamente el
binding de la variante seleccionada. Los demás consumidores mantienen su fuente.
Ediciones siguientes versionan esa copia cuando sigue siendo exclusiva; si otra
variante la comparte, vuelven a copiar. La procedencia original queda en los
metadatos de la copia y en el vínculo reemplazado (`supersedes_binding_id`), con
actor, motivo y revisión anterior recuperables por las rutas públicas existentes.

La publicación y el reemplazo se confirman juntos. El servidor compara las
precondiciones bajo bloqueo de escritura SQLite o los bloqueos canónicos de
variante/fuentes/objetos en PostgreSQL. Dos conexiones SQLite independientes
compitiendo por la misma revisión producen exactamente 201/409.

Guardar incrementa la revisión de bindings: la validación pública rechaza con 409
una preparación abierta antes del cambio. Los runs y snapshots previos conservan
sus resultados. Ejecutar y volver a validar desde la mesa corresponde a MESA-007.

El recorrido admite entradas canónicas vigentes de demanda, renovables y caudales
con los descriptores ya existentes. Outputs, escalares, referencias pinned,
fuentes legacy/no preparadas y entradas sin cobertura permanecen de solo lectura.
No se habilita edición global ni migración implícita de fuentes antiguas.

## Comprobaciones complementarias

- HTTP: aislamiento por caso/variante, CSRF, sesión anónima/externa, resultados de
  solo lectura, referencia histórica pinned y consumidores compartidos intactos.
- Edición sucesiva, conservación de timestamps America/Santiago y extensión del
  mismo contrato a disponibilidad renovable y aporte hidráulico canónico.
- Navegador: teclado, foco, advertencia al navegar atrás, números inválidos,
  conflicto, revisión actual y accesibilidad Axe.
- La fixture pinned inicialmente intentaba fijar la revisión actual; se corrigió
  publicando antes otra revisión, como exige el dominio. No fue un fallo de producto.
- El primer check detectó el nombre de una prop ref según la regla ESLint de
  inmutabilidad. Se corrigió a `closeRequestRef`, sin desactivar reglas.

## Evidencia y límites

Hay quince pruebas HTTP nuevas y cinco recorridos de navegador nuevos. Las
observaciones usan HTTP autenticado y UI pública; no se consultan tablas internas
ni se sustituyen colaboradores del guardado. Las fixtures preparan datos mediante
servicios de dominio; las salidas históricas son artefactos deterministas de prueba.

| Comprobación | Resultado | Evidencia |
| --- | --- | --- |
| API y regresiones canónicas, variantes y permisos | 204 descubiertas: 142 OK, 62 PostgreSQL omitidas | [Log](api-final.txt) |
| React/Vitest completo | 336 OK en 37 archivos | [Log](vitest-final.txt) |
| Navegador MESA completo | 20 OK | [Log](playwright-final.txt) |
| Regresiones de autenticación, workspace, hidráulica, UX-005 y UX-006 | 5 OK | [Log](playwright-regression.txt) |
| OpenAPI y tipos generados | OK | [Log](api-schema-final.txt) |
| Build de producción | OK; advertencia existente de chunks mayores de 500 kB | [Log](build-final.txt) |
| TypeScript y ESLint | OK; `check` falla después por formato previo de 16 archivos ajenos | [Log](check-final.txt) |
| Prettier de archivos de esta entrega | OK | [Log](format-final.txt) |
| ESLint tras el último ajuste de reconexión | OK | [Log](lint-final.txt) |
| Documentos, tracker y referencias originales | Verificados | [Log](docs-final.txt) |

PostgreSQL no está configurado (`POSTGRES_TEST_DATABASE_URL`); no se atribuye
validación de concurrencia a ese backend. SQLite en disco sí se comprueba con
dos conexiones independientes y lectura posterior por HTTP.

Comandos API, desde la raíz:

```powershell
.venv/Scripts/python.exe -m unittest -v tests.test_mesa_editing tests.test_optimization_mesa tests.test_mesa_hydraulic tests.test_mesa_preferences tests.test_ts7_008_case_time_series_bindings tests.test_ts7_009_run_materialization tests.test_ts7_010_object_specific_series tests.test_ts7_012_object_specific_binding_and_archive tests.test_ts7_013_shared_generic_revision tests.test_ts7_021_protected_journey_preconditions tests.test_ts3_case_variant_api tests.test_react_auth tests.test_configuration_layer_access
```

Desde `frontend`:

```powershell
npm.cmd run api:generate
npm.cmd run api:check
npm.cmd run build
npx.cmd playwright test --config=playwright.mesa.config.ts
npx.cmd playwright test e2e/react-foundation.spec.ts -g "React auth handles|React analyst workspace|UX-005|UX-006|React hydraulic diagram persists"
npm.cmd test -- --maxWorkers=1
npm.cmd run check
npx.cmd prettier --check src/MesaInputEditor.tsx src/MesaPreferences.tsx src/OptimizationMesa.tsx src/optimizationMesa.css src/api/client.ts src/api/schema.ts openapi.json e2e/optimization-mesa.spec.ts
```

Una ejecución intermedia conservó el bundle anterior a la corrección final de
reconexión y obtuvo 19/20 ([log](playwright-before-rebuild.txt)). Se reconstruyó
el frontend antes de la ejecución final; no se relajaron las aserciones.

Capturas de implementación:

- [Escritorio 1440×900](mesa-edicion-1440.png).
- [Móvil 390×844, página completa](mesa-edicion-390.png).

Entorno: Chromium de Playwright, DPR 1, en-US, America/Santiago, tema claro y
movimiento reducido. Se conserva la cabecera del producto y la organización por
paneles de la referencia A. La edición usa un diálogo para mantener visibles el
alcance, motivo y confirmación antes de publicar. Los dos intervalos corresponden
a datos canónicos de fixture; no a las 24 horas ficticias del prototipo. Incluye
Axe, teclado, foco y guardia de navegación. Las capturas finales se inspeccionaron:
alcance y controles legibles, columna editable visible y sin desbordamiento global.

No hay cambios del motor, migración de tablas ni despliegue externo.
Las referencias originales PNG/HTML se conservan; esta entrega no establece
baselines de aceptación humana para MESA-014.

Cierre AFK: revisadas precondiciones, permisos, alcance por variante, composición
transaccional, continuidad temporal, estados de error/conflicto y capturas finales.
MESA-006 pasa de In Review a Done. MESA-007 queda como siguiente entrega con sus
dependencias satisfechas; no se inicia en este cambio. Se preservaron los cambios
locales anteriores de MESA-001 a MESA-005.
