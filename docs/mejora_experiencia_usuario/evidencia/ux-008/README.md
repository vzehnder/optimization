# UX-008 · Configuración y preparación de la consola

Base: `a1b47e1`, árbol limpio al iniciar. Responsable: Codex.
Fecha: 2026-09-14. Estado: **In Review; F1/F2 confirmadas**.
El usuario respondió «confirmo» antes de escribir la primera prueba nueva.

## Resultado implementado

- Parámetros mediante campos: componente y escalar numérico del modelo,
  etiqueta, unidad, mínimo, máximo y valor inicial. No se duplica el catálogo
  de señales; gráficos, tablas y columnas consultan los catálogos existentes.
- Resultados habituales mediante indicadores, gráficos y tablas. Se conservan
  decimales, signo, énfasis, series, columnas, unidades y límite de filas.
- Un documento completo para formulario y **Editar JSON avanzado**. JSON
  inválido conserva el texto; los campos numéricos incompletos impiden el cambio
  de modo. Un error en resultados plegados abre la sección y enfoca el control.
- Revisión de partida conservada mientras se edita. El refetch no reemplaza
  cambios locales; el conflicto explica que no se guardaron y ofrece descarte
  explícito con carga vigente. Una consulta fallida permite reintentar.
- Activación/desactivación separadas y bloqueadas durante edición/guardado;
  tras el guardado aceptado usan la revisión devuelta por el servidor.
- Preparación externa con período, pendientes por parámetro/grupo y enlaces
  de teclado al destino. Guarda parámetros y grupos por separado, respetando
  `run_gate`. **Actualizar preparación** permite recuperar una consulta o
  comprobar si terminó el bloqueo de otro operador sin borrar los pendientes.
- La pérdida de sesión de edición conserva las celdas y explica cómo recuperar
  edición. Se mantienen revisión de ingeniería, reparación interna, control
  de fuentes, virtualización, pegado, diff opcional, historial y deshacer.
- El historial muestra el estado actual de la ejecución abierta cuando la
  consulta de detalle avanza, evitando «En espera» junto a un resultado listo.

Producción: `OperatorConsole.tsx`, nuevo `ConsoleResultsConfiguration.tsx` y
estilos acotados a la consola. No cambian API, esquema, permisos, validadores,
materialización ni motor. Se actualizó el manual, se añadió la prueba
`ConsoleExperience.test.tsx` y un recorrido a `react-foundation.spec.ts`.
`ux008_smoke_fixture.py` prepara únicamente el servidor aislado de pruebas.
Resolución: `feat(ux): simplify console configuration and execution preparation`,
sobre `a1b47e1`. La aceptación de producto permanece pendiente.

## Ciclos RED → GREEN

Los ciclos se ejecutaron secuencialmente en F2; no se anticipó una batería de
pruebas a la implementación. [Extractos de las salidas reales](tdd-cycles.txt)
conservan el fallo y el GREEN de cada ciclo. Los logs completos temporales
siguen en `.tmp/ux008-NN-{red,green}.txt`.
Los archivos de evidencia versionados normalizan finales de línea y espacios
finales de la salida de PowerShell, sin modificar los resultados registrados.

| Ciclo | RED observado | GREEN observable |
| --- | --- | --- |
| 01 | Falta el control de máximo | Guardar y reabrir el límite 6 MW sin JSON |
| 02 | Falta modo experto completo | Conservar resultados avanzados al editar identidad |
| 03 | Falta selector de componente/campo | Agregar un escalar numérico del modelo y reabrirlo |
| 04 | Falta formulario de resultados | Guardar KPI, gráfico y tabla con sus opciones |
| 05 | Refetch sustituye edición/revisión | Conflicto conserva cambios hasta descarte explícito |
| 06 | Estructura JSON inválida rompe el render | Texto conservado, guardado y cambio de modo bloqueados |
| 07 | Activar sigue disponible con edición pendiente | Esperar guardado aceptado y activar revisión vigente |
| 08 | Error de consulta desmonta edición | Reintentar conservando formulario |
| 09 | Falta resumen de preparación | Período y enlace al parámetro pendiente; ejecutar tras guardar |
| 10 | Falta guía al perder sesión de edición | Mantener celdas, recuperar edición y guardar |
| 11 | Número vacío se convierte en null al abrir JSON | Mantener formulario y foco para completar |
| 12 | Falta actualización recuperable de preparación | Consulta fallida conserva valores y cierra ejecución |
| 13 | Campo inválido queda en sección plegada | Abrir resultados y enfocar antes de guardar |
| 14 (F1) | Resultado disponible con historial aún «En espera» | Estado actualizado a «Lista» desde el detalle actual |

F1 comprobó después la integración de esos comportamientos. Su primer recorrido
detectó [contraste insuficiente en botones secundarios](browser-contrast-red.txt);
se corrigieron contraste, espaciado, casillas y distribución adaptable. La
revisión visual posterior ajustó la alineación de Inicio/Fin en escritorio.
La última captura mostró el estado desactualizado del historial: se observó
[RED en el recorrido real](tdd-14-red.txt) y luego [GREEN](playwright-focused.txt)
con el estado y el gráfico renderizado antes de capturar.

## Validación final

**443 pruebas funcionales aprobadas**, sin duplicar repeticiones focalizadas.
Las salidas se conservan junto a este documento. La línea base de 214 pruebas
que aparece más abajo no se vuelve a sumar.

| Comprobación | Resultado | Evidencia |
| --- | --- | --- |
| Vitest completo, 21 archivos | 258 aprobadas | [vitest-final.txt](vitest-final.txt) |
| Playwright completo | 22 aprobadas, 2.4 min | [playwright-final.txt](playwright-final.txt) |
| API: `test_configuration_layer_console*.py` | 109 aprobadas | [api-console.txt](api-console.txt) |
| API: operador y accesos | 54 aprobadas | [api-access.txt](api-access.txt) |
| TypeScript, ESLint y build | Aprobados | build en salida de navegador; ESLint sin diagnósticos |
| Prettier de archivos frontend modificados | Aprobado | [format-final.txt](format-final.txt) |
| `npm.cmd run check` | Falla solo por 21 archivos previos sin formato | [check-final.txt](check-final.txt) |
| `git diff --check` | Aprobado; solo avisos LF/CRLF | [diff-check.txt](diff-check.txt) |

Tras la corrección final del estado del historial y del estilo de botones
deshabilitados, se repitieron [63 regresiones de consola/resultados](regression-after-review.txt)
y el [recorrido F1](playwright-focused.txt), ambos aprobados. Esas repeticiones
están incluidas en los 443 casos únicos, no se suman como pruebas adicionales.

Comandos desde `frontend/`, con `DATABASE_URL=sqlite:///:memory:` para navegador:

```powershell
npm.cmd test -- --maxWorkers=2
npm.cmd run test:browser
npm.cmd run test:browser -- --grep 'UX-008'
npm.cmd run check
npx.cmd eslint src/OperatorConsole.tsx src/ConsoleResultsConfiguration.tsx src/ConsoleExperience.test.tsx src/OperatorConsole.test.tsx e2e/react-foundation.spec.ts
npx.cmd prettier --check src/OperatorConsole.tsx src/ConsoleResultsConfiguration.tsx src/ConsoleExperience.test.tsx src/OperatorConsole.test.tsx src/styles.css e2e/react-foundation.spec.ts
```

El recorrido F1 usa cookies, CSRF y FastAPI/SQLite reales: guarda parámetro y
resultados, reabre, activa, valida variante, entra a prueba interna identificado
como `admin@example.local`, asigna `operate`, inicia sesión externa, guarda un
override y lo comprueba tras recarga, ejecuta, presenta resultados y deniega
acceso tras revocación. También comprueba que la respuesta externa no incluye
punteros, bindings, hashes, logs ni variante interna.

La presentación se comprueba a 1440×900, 1280×720, 320×900 y ampliación CSS al
200 %. Axe sin violaciones serious/critical en configuración y preparación;
el enlace de pendiente se activa con teclado y enfoca el campo. Las capturas
completas (nueve) se regeneran en `frontend/test-results/react-foundation-UX-008-*/`
y se copian localmente a `capturas/`, excluido de Git.

## Conservación y límites

| Capacidad | Evidencia conservada |
| --- | --- |
| Configuración completa y revisión | F2: round-trip avanzado, refetch, conflicto, JSON inválido y respuesta tardía |
| Activación, identidad y autorización | F1 real y regresiones de operador/accesos |
| Preparación por variante y linaje | Regresiones API de operador, fail-closed y selección de fuentes |
| Edición de series | Regresiones React de 8760 filas, pegado rectangular, columnas bloqueadas, diff opcional, historial, deshacer y cambio de fuente |
| Coordinación y reparación | Regresiones de leases y acciones internas; nuevo caso de pérdida/recuperación de sesión sin revisión de ingeniería |
| Resultados/comparación y privacidad | Regresiones `PortalResults`, operador, API de comparación y recorrido externo autorizado |

El servidor smoke utiliza validación y resultados sintéticos; no comprueba
Julia real ni valores matemáticos. No se ejecutó PostgreSQL, toda la suite
Python, sesiones con participantes ni una auditoría con lector de pantalla.
Los resultados de accesibilidad se limitan a las vistas ejercitadas.

Se corrigieron incidencias del arnés: expectativas de etiquetas/identidad que no
coincidían con el contrato, opciones `exact` no válidas en Testing Library y
orden del E2E nuevo respecto al bootstrap existente. Una corrida Vitest con
concurrencia por defecto produjo tres timeouts en pruebas ajenas; con los dos
workers usados en la evidencia previa pasan las 258. No se cambiaron esas pruebas.
ESLint detectó argumentos sin usar en el stub nuevo, corregidos antes del cierre.
Persisten avisos previos de tamaño del bundle, adaptador httpx y formato global.

## Lectura y alcance

El siguiente ticket recomendado es [UX-008](../../issues/UX-008-consola-de-operador.md).
Se revisaron los 25 Markdown del paquete, sus dos scripts de referencia,
el registro JSON y los diagnósticos/resultados de los 102 logs históricos.
Las 79 capturas previas se inspeccionaron mediante hojas de contacto locales;
esa inspección general no equivale a una auditoría detallada de cada pantalla.
Se leyeron la skill TDD local, `tests.md`, `mocking.md` y la arquitectura de
configuración. No se encontraron `AGENTS.md` ni `CONTEXT.md` en el repositorio.

La lectura y las regresiones siguientes prepararon el primer ciclo.

## Fronteras confirmadas

La [skill solicitada](../../../../.agents/skills/tdd/SKILL.md) exige:

> Before writing any test, write down the seams under test and confirm them with the user.

El acuerdo registrado para UX-001–007 no incluye este ticket, según la
[estrategia del plan](../../04_estrategia_tdd.md).
El usuario confirmó el alcance siguiente con «confirmo»:

| Frontera | Comportamiento a observar |
| --- | --- |
| F1: navegador → React → FastAPI/SQLite aislado | Configurar un límite sin JSON, guardar/reabrir, probar con identidad interna real y recorrer operación autorizada; persistencia, autenticación, teclado y presentación. |
| F2: React renderizado con HTTP controlado | Formularios y JSON avanzado conservados, errores de sintaxis, conflictos de revisión, consultas y respuestas tardías, pendientes por campo/grupo y bloqueos de operación. |

F3 solo ejecuta regresiones existentes. Si hace falta cambiar un contrato,
ampliar el acuerdo antes de agregar pruebas de API. F4 no aplica al alcance
previsto: se conservan generación, materialización y lógica matemática.

## Primer ciclo preparado

Condición inicial: consola del fixture de batería, parámetro de carga expuesto
con valor efectivo 4 MW y rango que permite ese valor.

Acción: el ingeniero cambia el máximo permitido a 6 MW mediante un campo
numérico, guarda y reabre la configuración. Después entra a Probar consola.

Resultado esperado: el máximo 6 MW persiste y se refleja en el control operativo;
la prueba identifica al ingeniero real. El modelo base y el estado de activación
conservan sus contratos. F2 demuestra primero edición/guardado/reapertura;
F1 comprueba después el recorrido integrado. No se escribirá el siguiente
comportamiento antes de completar RED → GREEN del actual.

## Hallazgos que guían los ciclos posteriores

- `ConsoleDocumentForm` mantiene identidad, grupos y JSON por separado. Los
  formularios deben editar el documento completo y conservar las propiedades
  soportadas que no se modifiquen. JSON inválido conserva el texto y bloquea
  guardado/salida del modo experto.
- `OperatorConsoleEditorView` usa `key={console.revision}` y toma la revisión
  actual de la consulta al guardar. Un refetch puede remontar el formulario
  y sustituir la edición; se debe conservar la revisión de partida hasta un
  guardado aceptado o un descarte explícito.
- Resultados usa la gramática compartida del portal. Los catálogos públicos
  existentes sirven para gráficos, tablas y señales; no duplicar sus listas.
  Los parámetros corresponden a escalares directos permitidos del modelo.
- La consola ya distingue bloqueo de ingeniería y edición de otra persona,
  y separa guardados de parámetros/series. El resumen nuevo debe enlazar a
  pendientes concretos y respetar `run_gate`, sin prometer guardado global.
- Hay regresiones de 8760 filas, pegado, diff opcional, leases, historial,
  deshacer, fuentes y comparación. La búsqueda en los E2E actuales no encontró
  un recorrido específico de consola; F1 deberá cubrirlo con API aislada.

## Línea base ejecutada

**214 pruebas existentes aprobadas**, sin duplicar ejecuciones:

| Comprobación | Resultado |
| --- | --- |
| `OperatorConsole.test.tsx` y `PortalResults.test.tsx` | 51 aprobadas, 2 archivos, 11.36 s |
| `test_configuration_layer_console*.py` | 109 aprobadas, 50.211 s |
| `test_configuration_layer_operator_console` y `test_configuration_layer_access` | 54 aprobadas, 28.402 s |

Desde `frontend/`:

```powershell
npm.cmd test -- src/OperatorConsole.test.tsx src/PortalResults.test.tsx
```

Desde la raíz, en procesos con SQLite de prueba:

```powershell
$env:DATABASE_URL = 'sqlite:///:memory:'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_configuration_layer_console*.py' -v
.\.venv\Scripts\python.exe -m unittest tests.test_configuration_layer_operator_console tests.test_configuration_layer_access -v
```

Las salidas se registraron en las herramientas de esta conversación. No se
presenta esta línea base como evidencia RED → GREEN ni validación del producto
nuevo. No se ejecutaron navegador, check global, Julia real, PostgreSQL ni toda
la suite Python en esta preparación. Las variables se limitaron a los procesos
de prueba; no se editó `.env` ni se usaron proyectos de trabajo.

Python emitió el aviso previo de deprecación del adaptador httpx de Starlette.
La lectura de un ignore global de Git fue denegada, sin impedir estado/diff.
Los intentos iniciales de generar hojas de contacto con Pillow fallaron por
dependencia ausente; se usó System.Drawing sin instalar paquetes. El primer
extractor de logs encontró un problema de codificación de consola, resuelto
configurando su salida UTF-8. Ninguno fue un fallo de producto.
