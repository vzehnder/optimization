# Pruebas Manuales TS-2

## Objetivo

Este archivo sirve como checklist manual para revisar el catalogo generico de
series de tiempo entregado en TS-2. El foco es comprobar que CSV y XLSX se
importan a BBDD como sets versionados, que el catalogo es navegable por
proyecto, que ediciones manuales y reemplazos de archivo generan revisiones
auditables con hash recalculado, y que los errores de validacion quedan
atados a fila/columna (o a edicion/periodo) de origen.

Tambien cubre regresiones que no deben romperse:

- Iteracion 3 a 6: flujo web draft/hidro -> `ScenarioVersion` -> `Run`,
  publicaciones y portal cliente.
- TS-1: procedencia de topologia/parametros sobre versiones existentes.

## Registro De Prueba

| Campo | Valor |
| --- | --- |
| Fecha | |
| Tester | |
| Rama/commit | |
| Navegador | |
| URL local | |
| Resultado general | Pendiente |

## Preparacion Local

Ejecutar desde la raiz del repositorio. Editar `DB_PASSWORD` en `.env` para
que coincida con el rol local de PostgreSQL.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Abrir:

```text
http://127.0.0.1:8000/
```

Si el puerto `8000` esta ocupado, usar otro puerto con `--port 8001` y ajustar
la URL de revision.

## Datos De Prueba

| Tipo | Valor sugerido |
| --- | --- |
| Project | `TS-2 Manual Check` |
| Scenario | `Catalog import` |
| Set CSV | `Price and demand Jan 2026` (multi-senal) |
| Set XLSX | `Renewable availability Jan 2026` (mono-senal, hoja seleccionable) |

## Flujo Feliz: Importar Y Navegar El Catalogo

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Subir un CSV con dos senales (precio y demanda) en el draft del escenario. | El preview muestra columnas y filas de muestra antes de confirmar. | Pendiente |
| 2 | Mapear columnas a `price_usd_per_mwh` y `load_demand_mw` y confirmar el import. | Se crea el set version 1, revision 1, con hash `sha256:...` y ambas senales listadas. | Pendiente |
| 3 | Subir un XLSX con mas de una hoja. | El dropdown de hoja lista todas las hojas del libro. | Pendiente |
| 4 | Elegir la hoja con datos y mapear la columna a `renewable_available_power_mw`. | El preview se refresca con los datos de la hoja elegida y el import crea un segundo set version 1. | Pendiente |
| 5 | Abrir el catalogo del proyecto. | Se listan ambos sets con nombre, version, revision, hash, cantidad de senales y de periodos. | Pendiente |
| 6 | Abrir el detalle de cada set. | Se ven senales (clave canonica, unidad, entidad), horizonte (cantidad de periodos + inicio/fin) y procedencia de la fuente (incluyendo hoja XLSX si aplica). | Pendiente |

## Flujo Feliz: Edicion Manual Y Reemplazo De Archivo

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | En el set CSV, editar un valor de precio en la tabla de valores con un resumen de cambio. | Se crea la revision 2 con hash distinto; la revision 1 sigue visible en el historial con su hash original sin cambios. | Pendiente |
| 2 | En el set XLSX, reemplazar la fuente subiendo un CSV/XLSX corregido. | Se crea la revision 2 (nombre/version_label sin cambio) con nuevo hash, nuevos valores y nuevo nombre de archivo de fuente. | Pendiente |
| 3 | Revisar el historial de revisiones de ambos sets. | Cada revision muestra autor, fecha, resumen de cambio, hash y `superseded_revision_number` correcto. | Pendiente |

## Errores Manuales A Revisar

| Caso | Como provocarlo | Resultado esperado | Estado |
| --- | --- | --- | --- |
| Timestamp duplicado en import | Subir CSV con dos filas con el mismo `period_start`. | Mensaje explicito `row N: duplicate timestamp ...` con nombre de archivo; no se crea set parcial. | Pendiente |
| Valor no numerico en import | Subir CSV con un valor de precio no numerico. | Mensaje `row N: ... must be numeric` con nombre de archivo; no se crea set parcial. | Pendiente |
| Edicion manual invalida | Editar un valor de demanda a negativo. | Mensaje `edit N: ... must be nonnegative`; el set permanece en su revision anterior sin cambios. | Pendiente |
| Reemplazo con error | Reemplazar con un archivo que tenga timestamp duplicado. | Mismo mensaje de fila compartido con import; el set permanece en su revision anterior con el mismo hash. | Pendiente |

## Revision Visual

| Componente | Verificacion | Estado |
| --- | --- | --- |
| Catalogo del proyecto | Lista legible con nombre, version, revision, hash truncado, cantidad de senales/periodos. | Pendiente |
| Detalle del set | Tabla de senales, horizonte y procedencia de fuente legibles. | Pendiente |
| Tabla de edicion | Grilla periodo x senal editable, con boton de guardar/descartar y campo de resumen de cambio. | Pendiente |
| Panel de reemplazo | Formulario de carga con dropdown de hoja (XLSX) y mapeo de columnas coherente con el import original. | Pendiente |
| Historial de revisiones | Cada fila muestra hash, autor, fecha y resumen de cambio sin romper el resto del panel. | Pendiente |

## Verificacion Automatizada Complementaria

Estas pruebas no reemplazan la revision manual, pero sirven como referencia de
aceptacion de TS-2.

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ts2_acceptance -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

TS-2 no cambia contratos Julia, formatos de artefactos ni comportamiento del
optimizador. Ejecutar Julia solo si un cambio posterior los toca:

```powershell
julia --project=. -e "import Pkg; Pkg.test()"
```

## Cierre TS-2

Antes de aceptar la iteracion, ejecutar la suite automatizada enfocada y luego
la suite Python completa:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ts2_acceptance -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

No se requiere Julia para este cierre salvo que el cambio haya tocado
contratos Julia, formatos de artefactos o comportamiento del optimizador.

| Area | Resultado | Evidencia / notas |
| --- | --- | --- |
| Import CSV multi-senal | Pendiente | |
| Import XLSX con seleccion de hoja | Pendiente | |
| Catalogo navegable por proyecto | Pendiente | |
| Edicion manual crea revision y hash | Pendiente | |
| Reemplazo de archivo crea revision y hash | Pendiente | |
| Errores atados a fila/columna/edicion | Pendiente | |
| Regresion iter3-iter6 y TS-1 | Pendiente | |
| Revision visual/responsive | Pendiente | |

Decision final:

```text
Aceptado / Rechazado / Aceptado con observaciones
```
