# UX-003 · Importación guiada de series de tiempo

Estado: Todo. Prioridad: P1. Dependencias: UX-002. Tamaño: L.

## Problema y resultado

Subir una fuente, mapear columnas, corregir valores e importarlos al catálogo son acciones separadas cuyo resultado puede confundirse. La persona debe conocer en cada paso qué tiene preparado y qué recurso se creará.

## Código y contratos

- `frontend/src/DraftEditor.tsx`: subida, mapping, tabla de filas, importación al catálogo y extracción legacy.
- `frontend/src/timeSeriesCatalogMapping.ts`, `frontend/src/Workspace.tsx`: reemplazo de archivo de set.
- `frontend/src/ProtectedMutationJourney.tsx`: ingesta específica y compartida TS-7; no crear otro escritor.
- `app/main.py`: `/draft/time-series-sources/*`, importación/reemplazo e ingesta canónica; `app/time_series_ingestion.py`.
- Regresión: `App.test.tsx`, `tests/test_csv_time_series_ingestion.py`, `tests/test_ts2_acceptance.py`, `tests/test_ts7_011_object_specific_file_ingestion.py` y Playwright de ingestión.

## Pasos de implementación

1. Añadir el flujo Archivo → Hoja/columnas → Revisión → Importación, reutilizando controles y endpoints. En CSV no mostrar una selección de hoja inútil.
2. Explicar el destino: fuente temporal del draft, set de proyecto o revisión de serie específica/compartida. Elegir el camino existente compatible con el estado del servidor; no deducir C6 del flag de lectura ni abrir un canal de mutación paralelo.
3. Conservar archivo/identificador de staging, hoja, mapeo y valores editados al retroceder. Si se abandona, indicar qué quedó guardado en staging y qué no fue publicado; no prometer reversión transaccional de varios requests.
4. Ofrecer sugerencias de mapeo solo cuando haya correspondencia inequívoca; marcarlas como propuestas y requerir confirmación. Mostrar señal, componente, unidad, timestamp, duración y ejemplos de cada columna elegida.
5. Mostrar errores con hoja/fila/columna cuando el contrato los provea. Si falta una ubicación estructurada, agregarla de manera compatible en el backend en un ciclo F3; no parsear textos de error con regex frágiles.
6. Mantener previews/tablas acotados, indicar total y ventana visible y conservar métodos existentes de consultar más filas. Rechazar números ambiguos, huecos o incompatibilidades; nunca corregir tiempos, unidades o valores silenciosamente.
7. Mostrar resumen antes de confirmar: destino, cobertura, resolución, señales y efecto sobre una revisión existente. Para TS-7 conservar prevalidación/commit y confirmación de impacto del recorrido protegido.
8. Al terminar, enlazar al recurso importado y a la necesidad original. No considerar importación equivalente a asociación o binding ya confirmado.

## Secuencia TDD sugerida

F1/F2 y F3 solo si cambia contrato:

1. RED: importar un CSV corto mediante pasos y abrir su recurso final con los dos valores esperados escritos literalmente en el fixture. GREEN: primer recorrido completo.
2. RED: retroceder desde revisión conserva mapeo y correcciones; confirmar genera un solo recurso para el envío aceptado. GREEN: estado y bloqueo durante envío.
3. RED: un XLSX con dos hojas permite elegir la correcta y el valor inválido se identifica en su fila/columna. GREEN: selección y error contextual.
4. RED: corregir el dato inválido permite completar; un fallo de red conserva el trabajo y no dispara un reenvío automático de publicación. GREEN: recuperación.
5. RED para el alcance TS-7 modificado: confirmar una revisión específica por el recorrido existente conserva origen/alcance y revisión exacta; reintentar con precondición vieja recibe rechazo. GREEN: integración, sin atajos de commit.

## Aceptación

- CSV y XLSX completan el flujo sin introducir claves de esquema manualmente para las tareas habituales.
- Se distingue claramente fuente subida, datos importados y fuente utilizada por el caso.
- Error/cancelación no dejan la UI afirmando éxito ni pierden silenciosamente el trabajo local.
- Reemplazo mantiene identidad del set y crea revisión conforme al contrato. Las revisiones antiguas siguen consultables.
- Transformaciones, extracción legacy, series hidráulicas e ingesta API conservan sus accesos; no deben entrar obligatoriamente en el asistente nuevo.

Entregar evidencia de CSV, XLSX, corrección y ambos estados de compatibilidad TS-7 que afecte el cambio. Separar revisión de componentes de los ciclos de implementación.
