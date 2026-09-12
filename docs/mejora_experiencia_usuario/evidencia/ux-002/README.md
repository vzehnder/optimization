# UX-002 · Edición progresiva del modelo

Base: `9c24c1b`. Responsable: Codex. Fecha: 2026-09-12. Estado: In Review.
Commit solicitado por el usuario: `feat(ux): add progressive model editing and protect unsaved changes`.
Aceptación de producto pendiente; no se ha creado una PR.

El usuario confirmó «Confirmo F1 y F2 para UX-002» antes de la primera prueba:
F1, navegador con React y FastAPI aislado; F2, interfaz React con HTTP controlado.
Alcance: guardado/recarga, conservación de campos avanzados, errores, foco,
respuestas fallidas o tardías y protección de navegación. F3 solo ejecutó
regresiones existentes; no se modificaron contratos ni lógica matemática.

Primer ciclo: seleccionar una batería, modificar su capacidad, guardar y
reabrir el modelo con el valor aceptado. Se implementa una conducta por ciclo.

Línea base API: 20 pruebas aprobadas de `test_structured_draft_editor`,
`test_draft_generated_system_case` y `test_stale_hierarchy_validation`, en
7,557 segundos con SQLite en memoria. No se ejecuta Julia real.

## Comportamiento implementado

- La lista de componentes muestra tipo, nombre o ID y errores detectados. Solo
  se abre el componente seleccionado; agregar y quitar mantienen sus acciones
  y confirmaciones. Los parámetros se agrupan por capacidad/límites, estado
  inicial, operación y economía.
- Las condiciones terminales, curvas hidráulicas e identificación técnica se
  despliegan por separado. El texto visible identifica la curva del embalse
  obligatoria. Red y punto de conexión mantienen los límites habituales; IDs,
  esquema y solver quedan en opciones técnicas.
- El documento y los textos JSON permanecen en el formulario padre. Guardar un
  campo básico conserva propiedades omitidas, `null`, ceros, booleanos y JSON
  avanzado. Se serializan los JSON editados sin materializar valores de relleno
  en campos que el usuario no tocó.
- Guardando, Guardado, Cambios sin guardar y Error al guardar describen el estado
  del envío. Una respuesta tardía conserva los cambios posteriores. Guardar y
  abrir el diagrama hidráulico navega después de aceptar el envío; si hay cambios
  más recientes, mantiene el formulario abierto.
- Los errores tienen enlaces que seleccionan el componente, abren el panel y
  enfocan el control con su descripción. La sintaxis JSON incorrecta conserva
  su mensaje específico.
- Atrás, Adelante y los enlaces internos usan la confirmación de cambios
  pendientes. Tab queda dentro de la confirmación, Escape permite continuar y
  el foco se restaura. Recarga/cierre mantienen `beforeunload`; abrir un enlace
  en otra pestaña conserva la edición original.

Se adaptó el router de `App` a `createBrowserRouter` para usar `useBlocker` con
el historial del navegador, manteniendo `/react` y las rutas existentes. La
creación y limpieza de su suscripción se realizan en un efecto compatible con
Strict Mode. La regresión completa incluye las tres raíces, autenticación,
permisos, portal, consola y navegación por enlace directo.

## Ciclos TDD

Se siguió la [habilidad local](../../../../.agents/skills/tdd/SKILL.md), con una
conducta por ciclo. [Extractos RED → GREEN](tdd-cycles.txt):

| Ciclo | Frontera | RED observado | GREEN |
| --- | --- | --- | --- |
| 1 | F2 | No existe el selector de batería | Seleccionar, editar capacidad, guardar y reabrir |
| 2 | F2 | No existe operación avanzada | Condición terminal y capacidad persisten al cerrar/cambiar panel |
| 3 | F2 | La curva con error queda fuera del panel visible | Resumen enlazado, selección y foco sin perder batería |
| 4 | F1 | Atrás sale sin confirmación | Protección mediante historial y opción de continuar/descartar |
| 5 | F2 | No existen opciones técnicas del modelo | Límites habituales separados de solver JSON, con reapertura |
| 6 | F1 | Guardar agrega options/sources vacíos y borra una curva null | Lectura pública devuelve exactamente el documento esperado |
| 7 | F2 | Guardar JSON editado bloquea la entrada a hidráulica | El envío aceptado permite navegar antes de normalizar el texto |
| 8 | F2 | La descripción de sintaxis JSON se sustituye por curva requerida | Mensaje específico en español asociado al campo |

La prueba complementaria de respuesta tardía al abrir hidráulica pasó desde
su primera ejecución; no se contabiliza como un RED nuevo. Se conservaron las
pruebas existentes de guardado fallido y respuesta tardía del guardado normal.
Los cambios de etiquetas/ubicación se trasladaron a las pruebas de regresión.
Se corrigieron errores del registrador (forma de la respuesta de creación,
espera de una recarga cancelada y evento de nueva pestaña) antes de registrar
el recorrido final. No se presentan esos errores como defectos del producto.

## Comandos y resultados finales

Desde `frontend/`:

```powershell
npm.cmd test -- --maxWorkers=2
npm.cmd test -- src/DraftExperience.test.tsx
$env:DATABASE_URL = 'sqlite:///:memory:'
npm.cmd run test:browser
npm.cmd run check
npm.cmd exec prettier -- --check src/DraftEditor.tsx src/DraftExperience.test.tsx src/App.tsx src/App.test.tsx src/WorkspaceNavigation.test.tsx src/VariantPreparation.test.tsx src/styles.css e2e/react-foundation.spec.ts e2e/smoke-accessibility.spec.ts
```

Desde la raíz:

```powershell
$env:DATABASE_URL = 'sqlite:///:memory:'
.\.venv\Scripts\python.exe -m unittest tests.test_structured_draft_editor tests.test_draft_generated_system_case tests.test_stale_hierarchy_validation tests.test_iter5_acceptance tests.test_hydro_diagram_acceptance -v
git diff --check
```

| Comprobación | Resultado | Evidencia |
| --- | --- | --- |
| Vitest completo, 18 archivos | 201 aprobadas; 68,09 s | [Salida](vitest-final.txt) |
| F2 focalizada | 6 aprobadas; 9,05 s | [Salida](vitest-focused.txt) |
| Playwright completo y build | 17 aprobadas; 1,5 min | [Salida](playwright-final.txt) |
| API y aceptación hidráulica | 25 aprobadas; 9,224 s | [Salida](python-final.txt) |
| TypeScript y ESLint | Aprobados antes de la etapa Prettier | [Salida de check](check-final.txt) |
| Formato del frontend modificado | Aprobado en los 9 archivos | Comando focalizado anterior |
| `git diff --check` | Aprobado | Revisión local del diff |
| `npm.cmd run check` global | Falla solo por formato previo en 23 archivos sin cambios | [Lista completa](check-final.txt) |

Total final sin duplicar línea base ni repeticiones: **243 pruebas aprobadas**.
Una ejecución anterior con concurrencia predeterminada agotó la espera de un
segundo del primer caso de `RunExperience.test.tsx`; sus 16 casos pasaron
aislados y la suite completa pasó con dos workers, sin ampliar timeouts.
El build conserva el aviso previo de un chunk mayor de 500 kB.

## Conservación funcional comprobada

Filas afectadas de la [matriz](../../03_matriz_funcional.md):

| Capacidad | Acceso final | Evidencia |
| --- | --- | --- |
| Guardar, recuperar errores y conservar pendientes | Guardar modelo y confirmación de salida | F1/F2 nuevas; App y prueba estructurada existente |
| Red/PCC, batería, demanda, renovable, hidro y solver | Selector, red y opciones técnicas | F1 compara documento completo por API; F2 conserva opciones; App y aceptación iter5 |
| Hidráulica v3 | Guardar y abrir diagrama hidráulico; acceso desde escenario | Playwright de nodos/curvas y aceptación hidráulica existente |
| Generar preview, validar y promover | Caso generado, bajo el editor | Playwright de camino estructurado/experto y regresiones de caso generado/validación obsoleta |
| Importación y series existentes | Time-series metadata | Playwright de carga, mapeo, filas y validación; App |

No se reescribe el canvas v3. `test_stale_hierarchy_validation` comprueba que
mover el layout no invalida la validación; la aceptación hidráulica conserva
compatibilidad v1/v2/v3. Guardar sigue separado
de validar/promover y las versiones permanecen inmutables. No cambian permisos,
C6, TS-7, revisiones, materialización ni endpoints de producción.

## Revisión visual y accesibilidad

Se inspeccionaron las cinco capturas finales en Chromium: formulario a
1440×900, 1280×720 y 320×900; ampliación CSS al 200 % desde 1280×900; y error
hidráulico enfocado. Se corrigió el margen global de `role=status` que agrandaba
la barra y se adaptó la grilla al ancho real del formulario con container queries.
El recorrido comprueba ausencia de desbordamiento horizontal. El textarea con
error queda visible bajo la barra de guardado. Axe no detecta impactos
serious/critical en el formulario con error; pasa también el smoke existente.

Capturas locales, excluidas de Git y regeneradas por la prueba F1 de navegación:
`capturas/modelo-1440.png`, `capturas/modelo-1280.png`, `capturas/modelo-320.png`,
`capturas/modelo-zoom200.png`, `capturas/error-hidro.png`. Playwright las escribe
primero en su carpeta `test-results/react-foundation-UX-002-…`.

Esta revisión no equivale a pruebas con participantes ni a una auditoría con
lectores de pantalla. La ampliación CSS no sustituye la comprobación de zoom
nativo de todos los navegadores. El servidor smoke usa SQLite aislado y dobles
de Julia; no se ejecutaron Julia real, PostgreSQL ni toda la suite Python.

Los tutoriales [guía del analista](../../../tutorials/guia_analista.md) y
[manual completo](../../../tutorials/manual_completo_uso_pagina_web.md) se
actualizaron conservando los recorridos avanzados. La revisión no requirió una
reestructuración general del editor; posibles extracciones quedan para una
revisión posterior y no son requisito de este ticket.
