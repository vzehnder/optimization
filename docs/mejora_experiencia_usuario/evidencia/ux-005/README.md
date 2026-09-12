# UX-005 · Revisión de preparación y ejecución

Base: `e4eec65`. Responsable: Codex. Inicio: 2026-09-12.

F1 (navegador → React → FastAPI aislado), F2 (React renderizado con HTTP controlado)
y F3 (API pública: capacidades C6, validación y ejecución) confirmadas por el usuario
con «confirmo» en esta conversación, antes de escribir la primera prueba.
No cambia la lógica matemática ni la materialización. F4 no se incorpora.

Primer ciclo: una señal faltante se identifica, permite ir a corregirla y mantiene
bloqueada la ejecución. Cada ciclo se implementa después de observar su RED.

Estado: In Review. Entrega: `feat(ux): guide variant preparation and execution`,
sobre `e4eec65`, en commit solicitado por el usuario; sin PR. La aceptación del resultado de UX-001 y UX-005
permanece pendiente. [Ticket y resolución](../../issues/UX-005-revisar-y-ejecutar.md).

## Resultado y contrato público

La preparación separa **Confirmar fuentes**, **Revisar preparación** y
**Ejecutar variante**. Indica necesidades pendientes y destinos de corrección,
conserva selección de variante y clonación bajo **Gestionar variantes** y permite
revisar fuentes, período y duración antes de crear la corrida. Confirmar o revisar
no crea una versión. El botón final no vuelve a escribir bindings.

El detalle de variante añade `preparation`, calculado por backend:

| Campo | Significado |
| --- | --- |
| `binding_mode` | `protected` cuando C6 está activo o existen bindings canónicos activos; `legacy` en compatibilidad. No se deriva del flag de lectura. |
| `model_status` | `available` o `unavailable`, según la generación existente del modelo estructurado/hidráulico. |
| `bindings_revision` | Revisión pública del conjunto de bindings para las precondiciones canónicas. |
| `required_signals` | Necesidades del modelo y estado de vinculación; `linkable_object_id` cuando existe un destino inequívoco. |
| `sources` | Fuente, revisión, hash, estado y timezone; identidad del binding/objeto para el recorrido protegido. |
| `available_coverage` | Intervalo común comprobado con los resolvers existentes, o `null` si hay huecos/incompatibilidad. |

`/validate` reutiliza la validación existente en compatibilidad y comprueba fuentes
canónicas exactas, dependencias y período en modo protegido. Respeta
`expected_bindings_revision`, ya admitido por el payload backend. La revisión
canónica es de lectura: no reemplaza revisiones ni crea snapshots/corridas.
`/run` conserva su implementación y vuelve a comprobar las precondiciones.
El campo es aditivo; el contrato OpenAPI generado no presenta diferencias.

El formulario de período mantiene los valores ISO literales y añade fecha/hora,
offsets explícitos, zona y duración. Cambiar una fuente no borra un rango digitado.
Adoptar la cobertura es una acción explícita. Una edición, un cambio público de
binding o una consulta fallida invalida la preparación mostrada como lista.

En canónico se enlaza al recorrido TS-7 existente, con sus prevalidaciones y
confirmación de impacto. Si la lectura canónica no está habilitada para la cuenta,
se explica la limitación sin ofrecer un destino inaccesible. El flag solo controla
el acceso a esa interfaz; el servidor decide cómo pueden escribirse los datos.

## Ciclos RED → GREEN

Se escribió y ejecutó una conducta por vez, con HTTP como frontera del doble.
Las aserciones nuevas observan React, navegador o API autenticada. Las fixtures
pueden preparar el almacén; las comprobaciones F3 no consultan tablas privadas.

| Frontera y conducta | RED observado | GREEN |
| --- | --- | --- |
| F2: necesidad faltante | No existe el enlace para corregir la señal | Estado pendiente, enlace y foco en selector; ejecutar bloqueado |
| F3: capacidad antes/después de C6 | El detalle no expone preparación | Modo de vinculación calculado por backend, independiente de lectura |
| F2: confirmar, revisar y ejecutar | Falta confirmar por separado | Guardado explícito, revisión y ejecución sin repetir bindings |
| F3: revisión canónica | La validación legacy no acepta las fuentes canónicas del caso | Resolver revisiones exactas sin crear versiones ni corridas |
| F3: cobertura con hueco | Falta cobertura comprobada en el detalle | Intersección validada con los resolvers existentes; `null` con hueco |
| F2: fuente canónica fijada | Se conserva el selector legacy | Fuente/revisión y enlace al recorrido protegido |
| F2: cambiar fuente conservando período | Falta la entrada habitual de fecha/hora y offset | Fecha/hora, offset y entrada ISO avanzada conservan el rango |
| F2: respuesta incierta al ejecutar | Falta aviso de incertidumbre e historial | Bloqueo, consulta de historial y nuevo intento explícito sin reenvío automático |
| F2: confirmación parcialmente aceptada | No informa los cambios aceptados | Cuenta aceptados, conserva pendientes y refresca el estado público |
| F2: modelo no disponible | Falta acción de corrección | Mensaje de bloqueo y destinos de modelo estructurado/hidráulico |
| F2: doble clic durante envío | Los datos revisados siguen editables | Inputs bloqueados y una sola solicitud de corrida |
| F2: usar cobertura | Falta acción explícita | Adopción deliberada e invalidación de revisión anterior |
| F3: destino de necesidad canónica | Falta ID del objeto en la necesidad | Destino inequívoco calculado en el detalle público |
| F2: necesidad canónica faltante | El enlace apunta a compatibilidad | Enlace a la necesidad en el recorrido protegido |
| F2: falla al refrescar preparación | Se pierde el formulario o queda una revisión utilizable | Conservar período, mostrar error y exigir revisión tras recuperar |
| F2: recorrido no habilitado para la cuenta | Se ofrece un enlace a una ruta oculta | Explicación de acceso no habilitado |
| F2: catálogo legacy no disponible con fuentes canónicas | El error de catálogo sustituye la preparación | Carga legacy solo cuando ese modo la necesita |
| F2: otra sesión cambia el binding durante revisión | La selección local puede figurar confirmada | Comparar con el estado público actualizado y mantener el cambio pendiente |

Cobertura suplementaria que pasó desde su primera ejecución: F1 completo, F3 de
ejecución después de migrar C6 con actor/revisión/rango e histórico conservados,
y la edición literal de offset en el caso existente. No se cuentan como nuevos
RED. Se corrigió una fixture canónica que enviaba un offset distinto de sus
timestamps originales y se retiró `exact` de opciones de Testing Library;
esos errores de preparación tampoco se cuentan como RED funcional.

Pruebas nuevas: [13 casos F2](../../../../frontend/src/VariantPreparation.test.tsx),
[4 casos F3](../../../../tests/test_ux005_preparation.py) y el caso UX-005 de
[Playwright](../../../../frontend/e2e/react-foundation.spec.ts). Las regresiones
existentes de `App.test.tsx` se adaptaron a confirmar/revisar/ejecutar y a la
gestión desplegable de variantes conservando las aserciones de ejecución.

## Validación ejecutada

Línea base: 64 pruebas existentes de `App.test.tsx` y `WorkspaceNavigation.test.tsx`
aprobadas antes de implementar. Comprobación final:

| Comando | Resultado |
| --- | --- |
| `npm.cmd test` desde `frontend/` | 16 archivos, **179 aprobadas**, 46,53 s. [Salida](vitest-final.txt) |
| `npm.cmd run test:browser` con SQLite en memoria | Build y **14 aprobadas**, 1,2 min. [Salida](playwright-final.txt) |
| Suites Python indicadas abajo | **57 aprobadas, 13 omitidas**, 53,762 s. [Salida](python-final.txt) |
| `npm.cmd run api:check` | Aprobado; sin drift de OpenAPI/tipos generados |
| `npm.cmd run check` | TypeScript y ESLint aprobados; Prettier falla en 24 archivos previos sin cambios. [Salida](check-final.txt) |
| Prettier sobre los 7 archivos frontend modificados/nuevos | Aprobado |
| `git diff --check` | Aprobado |

Total sin duplicar reejecuciones: **250 pruebas funcionales aprobadas**. Tras la
revisión de formato/layout se repitieron los 4 casos F3, los 13 F2 y el recorrido
UX-005 con build; todos aprobados. No se modificó lógica después de la suite
completa. Las capturas finales pertenecen a la reejecución visual.

Desde la raíz, con `.venv` y SQLite aislado:

```powershell
$env:DATABASE_URL = 'sqlite:///:memory:'
.venv/Scripts/python.exe -m unittest tests.test_ux005_preparation tests.test_ts3_case_variant_api tests.test_variant_staleness tests.test_ts7_009_run_materialization tests.test_ts7_008_case_time_series_bindings tests.test_ts7_022_c6_cutover tests.test_configuration_layer_access -v
```

Para repetir solo la nueva cobertura frontend:

```powershell
cd frontend
npm.cmd test -- src/VariantPreparation.test.tsx
$env:DATABASE_URL = 'sqlite:///:memory:'
npm.cmd run test:browser -- --grep UX-005
```

Prettier conserva fallos previos en `e2e/global-setup.ts`, `eslint.config.js`,
`index.html`, `package-lock.json`, `package.json`, `playwright.config.ts`,
`scripts/check-generated.mjs`, `scripts/export-openapi.mjs`, `src/api/client.test.ts`,
`src/ErrorBoundary.test.tsx`, `src/ErrorBoundary.tsx`,
`src/hydro/HydraulicInflowPanel.test.tsx`, `src/hydro/inflowImport.test.ts`,
`src/hydro/inflowImport.ts`, `src/main.tsx`, `src/ProtectedMutationJourney.test.tsx`,
`src/ProtectedMutationJourney.tsx`, `src/RunResults.tsx`, `src/test/setup.ts`,
`src/timeSeriesCatalogMapping.ts`, `tsconfig.app.json`, `tsconfig.json`,
`tsconfig.node.json` y `vite.config.ts`. No se reformatean archivos ajenos al ticket.
`client.ts`, modificado en este issue, queda correctamente formateado.

## Paridad, revisión visual y límites

- Variantes: Default, selección, clonación y fuentes persistentes tras recarga.
- Preparación: modelo, necesidades, huecos, período, pendientes, errores de
  consulta, aceptación parcial y revisión invalidada por cambios remotos.
- Ejecución: snapshot automático con rango exacto, actor y revisión; rechazo de
  modelo cambiado sin alterar la corrida histórica. Doble clic y resultado
  incierto cubiertos en F2; una sola corrida consultable en F1.
- TS-7: fuentes exactas, modo C6 activo/inactivo, lectura canónica independiente,
  permisos por API y recorrido protegido existente. No se introduce otro escritor.
- Expertos e hidráulica: regresiones de edición/guardado hidráulico, validación,
  promoción, JSON experto, versiones y corrida manual aprobadas en navegador.
  Los controles siguen accesibles bajo Avanzado.
- Regresiones transversales: autenticación, roles, revocación, portal, consola,
  catálogo, resultados y publicaciones incluidas en las suites frontend existentes.

Se inspeccionaron las capturas de preparación a 1440×900, 1280×720 y 320×900,
el estado inicial pendiente y ampliación CSS al 200 %. Se ajustaron separación
de acciones y ancho de fechas. Sin desbordamiento horizontal; el enlace de la
necesidad admite teclado y lleva el foco al selector. Axe no detectó impactos
serious/critical en la vista comprobada. Las cinco capturas se conservan en
`capturas/`, excluidas de Git según la preferencia ya registrada para este plan.
Playwright las regenera en `frontend/test-results/.../preparacion-*.png`.

No se ejecutó PostgreSQL dedicado (13 omisiones) ni toda la suite Python. No se
cambian transacciones, migración C6 ni esquema persistente. Julia real no se
ejecutó: no cambia generación, materialización ni matemática; el navegador usa
el servidor smoke y sus dobles de proceso externo. No se midió mejora de tiempo
con participantes ni se hizo una auditoría con lector de pantalla. El warning
de tamaño de chunks de Vite se conserva. Desplegar el backend aditivo antes del
frontend: si falta `preparation`, la UI bloquea la ejecución y pide actualizar
la consulta. No se aplicaron migraciones ni cambios a datos de uso habitual.
