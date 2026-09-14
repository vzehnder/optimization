# UX-003 · Importación guiada

Base: `19fc31c`; árbol limpio al iniciar. Responsable: Codex.
Estado: In Review. Fecha local de validación: 2026-09-12.

El usuario confirmó «Confirmo F1, F2 y F3 condicional para UX-003» antes de
escribir la primera prueba. F1: navegador React/FastAPI aislado, importación
CSV/XLSX, correcciones, retroceso y recurso persistido. F2: interfaz React
con HTTP controlado, errores, conservación del trabajo y envío único.
F3: API pública autenticada para revisión previa, ubicación estructurada de
errores y garantías de revisión/reemplazo si cambia el contrato. F4 no aplica.

Línea base: 33 pruebas API aprobadas y 16 PostgreSQL omitidas en
`test_csv_time_series_ingestion`, `test_ts2_acceptance` y
`test_ts7_011_object_specific_file_ingestion` (16,704 s). No se suman al cierre.

## Resultado

Archivo → Columnas → Revisión → Importación en el editor del modelo. CSV no
ofrece hoja; XLSX conserva las decisiones de cada hoja visitada. Las coincidencias
exactas de fecha/duración se explican como propuestas y se confirman junto con
señales y unidades, con ejemplos y alcance. El resumen separa la fuente temporal,
el conjunto/revisión importado y el uso posterior en una variante.

Las filas se editan en ventanas de 50 con navegación; se guardan mediante el
endpoint existente. La revisión valida todas las filas y muestra cinco como
máximo. Los errores numéricos y temporales tienen ubicación estructurada y un
enlace de corrección que enfoca incluso una celda de otra página. No hay
conversiones ni relleno de huecos implícitos.

Retroceder conserva archivo, staging, hoja, columnas y valores pendientes. Una
subida fallida no descarta el archivo anterior. Al salir se informa qué fuente
está guardada y qué decisiones locales se perderán; no se promete rollback.
La confirmación bloquea dobles envíos y no reintenta automáticamente. Si la
respuesta es incierta, exige comprobar el catálogo antes de habilitar otro intento.

El servidor decide `project_catalog` o `protected` según el estado C6 real,
independientemente del flag de lectura. La carga específica CSV/XLSX se integra
en `ProtectedMutationJourney`: conserva el lote al retroceder y al corregir
columnas, consume el contexto de los rechazos 422 y publica mediante el token,
ETag, clave de idempotencia y confirmación de impacto existentes. El cierre enlaza
al objeto y aclara que falta elegir la revisión para una variante. La carga de
puntos y el recorrido compartido se conservan.

## Contrato y compatibilidad

- `GET /api/scenarios/{id}/draft/time-series-import-options`: destino según C6.
- `POST /api/scenarios/{id}/draft/time-series-sources/{source}/catalog-preview`:
  validación sin crear un conjunto; cobertura, resolución, señales, muestra y hash.
- `expected_preview_hash` es opcional en el import existente. El asistente lo
  envía y un cambio de contenido devuelve 409 antes de escribir. Los consumidores
  anteriores conservan su contrato. No hay un segundo escritor canónico.
- Los errores del import/preview agregan `location` sin quitar los campos previos.
  El cliente conserva también `context` de los problemas TS-7 sin reinterpretar
  mensajes mediante regex.
- OpenAPI regenerado con las herramientas del repositorio; `api:check` aprobado.

## TDD y revisión posterior

Los [extractos RED/GREEN](tdd-cycles.txt) conservan 24 pares de salidas. Cada
prueba se escribió en una frontera confirmada y se hizo pasar antes del ciclo
siguiente. Las salidas completas permanecen en `.tmp/ux003-*.txt`. Los logs
versionados normalizan los espacios finales sin modificar su contenido.

| Ciclos | Comportamiento observado primero en RED |
| --- | --- |
| preview, location | Revisión API sin escritura y ubicación de un número XLSX ambiguo |
| csv, back, xlsx | Recorrido React, correcciones conservadas y selección de hoja |
| c6, routing | Estado real del servidor y entrada al recorrido protegido |
| gap | Hueco localizado antes de confirmar |
| protected | CSV específico usando staging y publicación existentes |
| network, leave, window | Respuesta incierta, salida explicada y acceso a filas posteriores |
| browser | Dos señales CSV hasta recurso persistido y ejecución por variante |
| xlsx-browser | Corrección 70 conservada al cambiar de hoja y volver |
| examples, stale | Ejemplos de columnas y rechazo de fuente cambiada tras revisar |
| protected-xlsx, problem | Elección de hoja con columnas pendientes y contexto del rechazo real |
| temporal, focus | Errores de fecha/duración y foco fuera de la primera página |
| protected-location | Corrección del mapeo específico tras un error con ubicación |
| reupload | Volver por el botón principal conserva los cambios locales |
| protected-link, failed-file | Enlace final TS-7 y archivo anterior conservado tras una subida fallida |

El recorrido F1 detectó además desbordamiento a 320 px y una tabla desplazable
sin acceso por teclado; ambos se corrigieron antes de darlo por aprobado. La
revisión posterior comprobó componentes, escrituras existentes, estados de error,
historial y accesos expertos. Los dos últimos hallazgos se resolvieron con nuevos
ciclos, separados de la implementación inicial. Se aplicó formato a los archivos
modificados; no se realizó una refactorización general.

La prueba explícita de doble clic con HTTP pendiente y la comprobación API de
selección parcial de hoja pasaron sobre la implementación existente. Son
regresiones suplementarias, no ciclos RED ficticios. Se corrigieron fixtures
antiguos para abrir el desplegable de compatibilidad y se corrigió su texto UTF-8.
Un intento de regresión Python nombró incorrectamente un módulo; se repitió con
el nombre real. Un chequeo concurrente con Playwright encontró su directorio
temporal en recreación; el chequeo final se ejecutó por separado.

## Validación

**367 pruebas aprobadas**, sin sumar repeticiones ni línea base:

| Verificación | Resultado y salida |
| --- | --- |
| Frontend completo | 19 archivos, 214 pruebas; [salida](vitest-final.txt) |
| Navegador completo | 19 pruebas; [salida](playwright-final.txt) |
| Python afectado | 190 ejecutadas: 134 aprobadas y 56 PostgreSQL omitidas; [salida](python-final.txt) |
| Revisión final del recorrido protegido | 14 aprobadas; [salida](protected-link-green.txt) |
| Recuperación final de archivos | 10 aprobadas; [salida](failed-file-green.txt) |
| Navegador tras revisión/capturas | 2 recorridos UX-003; [salida](playwright-focused.txt) |
| Contrato generado | [api:check](api-check.txt) aprobado |
| TypeScript / ESLint / formato | TypeScript y ESLint pasan; `check` falla solo por 21 archivos previos sin formato, [lista exacta](check-final.txt) |

Desde `frontend/`:

```powershell
npm.cmd test -- --maxWorkers=2
$env:DATABASE_URL = 'sqlite:///:memory:'
npm.cmd run test:browser
npm.cmd run api:check
npm.cmd run check
```

El `check` debe ejecutarse separado de Playwright. Su fallo de Prettier no se
cuenta como aprobado. Build pasa con el aviso existente de tamaño del bundle.
Los 21 archivos enumerados por Prettier no tienen cambios de esta implementación;
los dos archivos del recorrido protegido que ya se tocaron quedaron formateados.

Desde la raíz:

```powershell
$env:DATABASE_URL = 'sqlite:///:memory:'
.venv/Scripts/python.exe -m unittest tests.test_ux003_import_preview tests.test_csv_time_series_ingestion tests.test_ts2_acceptance tests.test_ts2_time_series_catalog tests.test_ts7_011_object_specific_file_ingestion tests.test_ts7_022_c6_cutover tests.test_ts7_010_object_specific_series tests.test_ts7_013_shared_generic_revision -v
```

Paridad comprobada: importación CSV/XLSX, validación legacy, extracción, unidades,
reemplazo con identidad e historial preservados, transformaciones TS-2, archivo
específico, revisión compartida TS-7 y corte C6. Los controles hidráulicos,
expertos y de generación siguen en los recorridos existentes; las suites de
navegador y componentes conservan su acceso y funcionamiento.

## Evidencia visual y límites

Cinco capturas regenerables en `capturas/`, excluidas de Git: columnas a 1440 px,
confirmación a 1440×900, 1280×720 y 320×900, y ampliación CSS al 200 % sobre 1280 px.
Se inspeccionaron las imágenes; las tablas conservan desplazamiento propio. Axe
no detecta impactos serious/critical en columnas ni confirmación. El teclado
alcanza la confirmación y los errores enfocan la celda pertinente.

F1 usa Chromium y FastAPI/SQLite aislado del servidor habitual. CSV persiste
55/60 USD/MWh y demanda 2/2,5 MW; XLSX corrige `1,234` a 70 explícitamente y
persiste 70/60 tras recarga. La ejecución de humo usa un solver sintético, no
valida resultados matemáticos. Los estados C6 se verifican por API en almacenes
temporales; TS-7 de interfaz se comprueba en F2 con HTTP controlado y se respalda
con sus contratos públicos reales.

No se ejecutaron PostgreSQL, Julia real, toda la suite Python, sesiones con
participantes ni una auditoría completa de lectores de pantalla. No se cambiaron
transacciones, constraints, migraciones, materialización ni lógica del solver.
La aceptación de producto queda pendiente, por eso el ticket está In Review.
