# PRD TS-2: Catalogo Generico De Series De Tiempo En BBDD

Fecha: 2026-07-03

## Grill-Me Questions And Recommended Answers

1. **Debe el Excel/CSV seguir siendo la fuente de verdad?**

   Respuesta recomendada: no. El archivo debe ser una fuente auditable de carga.
   Despues de importar, la fuente operativa deben ser tablas de BBDD.

2. **Debe un set contener una sola senal o muchas senales?**

   Respuesta recomendada: debe soportar ambas formas. El sistema debe permitir
   sets tipo paquete con varias senales alineadas y sets pequenos con una senal
   principal.

3. **Que se versiona: el set completo o cada punto?**

   Respuesta recomendada: el set completo con revisiones. Versionar punto a
   punto haria dificil auditar horizontes coherentes.

4. **Que pasa cuando se edita manualmente una version usada por runs?**

   Respuesta recomendada: se crea una nueva revision y cambia el hash vigente.
   Las corridas antiguas siguen apuntando al hash/revision exacto que usaron.

5. **La version visible y la revision tecnica son lo mismo?**

   Respuesta recomendada: no necesariamente. `version_label` es la etiqueta que
   entiende el usuario; `revision_number` registra cambios internos sobre esa
   version visible.

6. **Debe TS-2 conectar las series a casos?**

   Respuesta recomendada: no. TS-2 crea la biblioteca de series. Los bindings a
   casos y variantes quedan para TS-3.

7. **Debe TS-2 soportar conversion de unidades?**

   Respuesta recomendada: debe registrar unidad origen y unidad canonica, pero
   conversiones automaticas complejas pueden quedar fuera. El PRD puede incluir
   conversiones triviales solo si son necesarias.

8. **Como se maneja timezone?**

   Respuesta recomendada: guardar timestamps como instantes y guardar timezone
   IANA del set para interpretacion y visualizacion, con `America/Santiago` como
   caso importante.

## Problem Statement

Las series de tiempo del sistema hoy aparecen en varios lugares: archivos
subidos al draft, filas validadas dentro de documentos JSON, algunas tablas
hidraulicas especificas y `system_case_json` ya materializados. Esto permite
correr, pero no permite construir una biblioteca reutilizable de datos.

El usuario quiere que las series vivan en BBDD, que Excel/CSV sirva para
cargarlas o corregirlas, y que despues se pueda seleccionar una version para
correr. Para llegar a eso, primero hace falta una capa generica de series
versionadas independiente del caso.

## Solution

Crear un catalogo generico de series de tiempo por proyecto:

```text
TimeSeriesSource
-> TimeSeriesSet
-> TimeSeriesSetRevision
-> TimeSeriesPeriod
-> TimeSeriesSignal
-> TimeSeriesValue
```

El usuario podra importar CSV/XLSX, mapear columnas a senales canonicas,
validar periodos y valores, guardar valores en BBDD, editar correcciones
manuales acotadas y reemplazar una version mediante una nueva carga. El sistema
mantendra trazabilidad de fuente, revision, usuario, fecha y hash.

## User Stories

1. As an analyst, I want to upload a CSV as a time-series source, so that spreadsheet data enters the database.
2. As an analyst, I want to upload an XLSX and choose a sheet, so that Excel workflows remain supported.
3. As an analyst, I want to preview source columns and rows, so that I can confirm the file is correct before import.
4. As an analyst, I want to map source columns to canonical signals, so that arbitrary spreadsheet names do not leak into the model.
5. As an analyst, I want imported values stored in BBDD, so that I can reuse them without reopening the file.
6. As an analyst, I want a named time-series set, so that I can recognize data packages later.
7. As an analyst, I want version labels on sets, so that I can distinguish business versions such as `v1`, `dry_year`, or `corrected`.
8. As an analyst, I want revisions inside a set version, so that corrections are auditable.
9. As an analyst, I want content hashes, so that runs can freeze exact data revisions.
10. As an analyst, I want to edit values manually in a bounded table, so that small corrections do not require rebuilding a file.
11. As an analyst, I want to replace or update a set by uploading another CSV/XLSX, so that corrected source data can become a new revision.
12. As an analyst, I want validation errors tied to source row and column, so that I can fix bad data quickly.
13. As an analyst, I want duplicate timestamps rejected, so that horizons are unambiguous.
14. As an analyst, I want nonpositive durations rejected, so that period accounting is valid.
15. As an analyst, I want negative values rejected for physical nonnegative signals, so that invalid inputs fail early.
16. As an analyst, I want set timezone visible, so that Chile DST and local calendar interpretation are clear.
17. As an analyst, I want to browse a project catalog of time-series sets, so that I can see available data.
18. As an analyst, I want to inspect signals in a set, so that I know whether it contains prices, demand, renewables or inflows.
19. As a backend developer, I want signal validation centralized, so that CSV, XLSX and manual edits share rules.
20. As a backend developer, I want a deep import module, so that parsing, mapping and validation can be tested without UI.
21. As a backend developer, I want bulk insert behavior for values, so that realistic files import efficiently.
22. As a backend developer, I want revisions to record source metadata, so that audit trails survive file replacement.
23. As a product owner, I want this catalog independent from case bindings, so that the data library can mature before dropdown runs.

## Implementation Decisions

- Excel and CSV remain accepted input formats, but imported values live in BBDD.
- Time-series sources store provenance such as file name, media type, checksum, sheet name and metadata.
- Time-series sets are project-scoped and carry name, version number, version label, data kind, timezone, status and content hash.
- Set revisions record changes without requiring every historical point to be duplicated if source snapshots or hashes are sufficient for the MVP.
- Periods store ordered start/end timestamps and duration.
- Signals store canonical `signal_key`, unit, entity metadata when known, role and aggregation convention.
- Values use a long format keyed by set, signal and period.
- A signal catalog defines allowed keys, expected units and validation rules.
- Manual edits and file replacements create revisions and recalculate hashes.
- TS-2 does not bind sets to optimization cases; that is TS-3.
- Deep modules should cover source parsing, mapping validation, value normalization, hash calculation and revision creation.

## Testing Decisions

- Tests should cover behavior at API/domain boundaries, not table implementation details.
- CSV import tests should cover preview, mapping, valid import, invalid timestamps, duplicate timestamps, nonnumeric values and negative physical values.
- XLSX import tests should cover sheet selection, invalid sheet, unsupported workbook features and shared validation.
- Manual edit tests should prove revision creation, hash updates and validation reuse.
- Catalog tests should prove list/detail behavior and signal visibility.
- Existing draft ingestion tests are useful prior art, but new tests should assert BBDD-backed persistence.
- React tests should focus on import flow, validation display and catalog/detail views.

## Out of Scope

- Binding series to cases.
- Running cases from selected series variants.
- Result series storage.
- Resampling and interpolation.
- External API connectors.
- Complex unit conversion.
- Migrating existing hydraulic-specific series tables.

## Further Notes

This iteration creates the raw material for the dropdown run experience. It is
complete when time-series sets are first-class database objects, even if no case
uses them yet.
