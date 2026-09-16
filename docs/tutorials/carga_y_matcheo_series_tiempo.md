# Tutorial detallado: carga y matcheo de series de tiempo

> Revisado contra la aplicación del repositorio el 2026-09-15. Incluye la
> importación guiada, las fuentes por componente y la preparación de ejecuciones.

Este tutorial amplía las secciones 6, 7 y 8 de la
[Guía del analista](./guia_analista.md). Está pensado para un analista que ya
tiene el caso modelado y necesita llevar precios, demanda, disponibilidad
renovable e hidrología desde un archivo o una API hasta una corrida trazable.

Al terminar deberías poder:

- preparar un CSV o XLSX con una grilla temporal válida;
- mapear cada columna de origen a una señal canónica del catálogo;
- decidir cuándo conviene crear un set ancho, un set por señal o un set por
  activo;
- vincular cada señal requerida por el caso con el set correcto;
- elegir un rango que todos los bindings cubran exactamente;
- corregir errores de unidades, huecos, resoluciones incompatibles y variantes
  desactualizadas;
- comprobar en el detalle de la corrida qué revisión y hash se consumieron.

> **Resumen corto:** importar guarda datos; asociar una fuente genérica la hace
> disponible para un objeto; usar una revisión fija el binding de la variante.
> Después se revisa la preparación para el período elegido y se ejecuta.
> Ninguno de los pasos anteriores a ejecutar crea una corrida.

## 1. El flujo completo

```text
CSV / XLSX / API JSON
        |
        |  1. Selección de timestamp, duración y columnas de valores
        v
Mapeo de columnas de origen a señales canónicas
        |
        |  2. Validación temporal, física y de unidades
        v
Set versionado en el catálogo del proyecto
        |
        |  3. Transformaciones explícitas, si hacen falta
        v
Set listo para optimización
        |
        |  4. Asociación al objeto, si es una fuente genérica en TS-7
        |     Binding objeto + necesidad -> señal + revisión exacta + hash
        v
Variante de entrada
        |
        |  5. Período [inicio, fin) -> Revisar preparación
        |     Preparado para ejecutar este período -> Ejecutar variante
        v
Snapshot inmutable -> corrida -> resultados y lineage
```

Hay dos “matcheos” que conviene distinguir:

1. **Mapeo de importación:** una columna física, por ejemplo `demanda_mw`, se
   interpreta como la señal canónica `load_demand_mw`.
2. **Uso en el caso:** la señal y su revisión se asignan, por ejemplo, al activo
   `load_centro` y no a `load_norte`. En el recorrido protegido, una fuente
   genérica se asocia primero al objeto y después se fija su uso en la variante.

El primer paso da significado y unidad al dato. El segundo le da destino
dentro del modelo.

### 1.1 Reconocer el recorrido disponible

En **Datos** del escenario, la aplicación muestra el modo permitido por el
servidor:

| Lo que ves | Cómo continuar |
| --- | --- |
| Selectores **Serie ...** y **Confirmar fuentes** | Camino de compatibilidad: elige los sets y confirma los cambios antes de revisar la preparación. |
| Fuentes con revisión fijada y enlaces **Corregir**, **Revisar fuente** o **Ver fuentes del componente** | Recorrido protegido: revisa el objeto, asocia la fuente genérica si falta y confirma la revisión para la variante. |
| **Elegir la necesidad del modelo para importar**, en el editor | Abre **Datos** y parte desde el componente; el asistente de conjuntos nuevos no está habilitado para ese destino. |

Si la variante todavía usa compatibilidad y tu cuenta tiene acceso al catálogo
genérico, **Elegir fuente del catálogo genérico para ...** abre las fuentes del
objeto registrado, incluso antes de la primera vinculación. Desde allí, sigue
**Asociar fuente al objeto** y luego **Usar revisión en una variante**. Los
desplegables de compatibilidad consultan los sets del proyecto; cuando están
vacíos y existe ese acceso al catálogo genérico, se muestra el enlace para elegir
la fuente sin presentar un desplegable vacío.

Después del cambio al escritor canónico C6, o si la variante tiene bindings
canónicos activos, el servidor exige el recorrido protegido. La habilitación de
lectura del catálogo no decide qué escrituras están permitidas. Si aparece
**La edición de estas fuentes aún no está habilitada para tu cuenta**, consulta
al responsable de la instalación; el [manual, sección 7.1](./manual_completo_uso_pagina_web.md#71-disponibilidad-del-catálogo-ts-7)
explica el acceso durante la migración.

## 2. Vocabulario mínimo

| Término | Significado operativo |
| --- | --- |
| Fuente | Archivo CSV/XLSX subido o respuesta JSON obtenida por un conector. Conserva procedencia y checksum. |
| Columna de origen | Nombre que trae el archivo o la API, por ejemplo `spot`, `demanda_sic` o `q_laja`. |
| Señal canónica | Nombre entendido por la aplicación y el motor, por ejemplo `price_usd_per_mwh` o `natural_inflow_m3s`. |
| Set | Conjunto de uno o más señales que comparten periodos, zona horaria, versión y revisión. |
| Versión | Etiqueta lógica del set, por ejemplo `v1`, `base_2027` o `programa_2026_08_01`. |
| Revisión | Estado inmutable del contenido. Una corrección agrega una revisión; no reescribe la anterior. |
| `content_hash` | Huella SHA-256 del contenido exacto de una revisión. Cambia cuando cambian datos o metadatos relevantes. |
| Variante de entrada | Configuración nombrada de bindings entre los requerimientos del caso y sets del catálogo. |
| Asociación | Hace disponible una fuente genérica para una necesidad del objeto; no crea su uso en una variante. |
| Serie específica | Fuente que pertenece solo a un objeto; no aparece en el catálogo global ni requiere asociación de catálogo. |
| Binding | Uso de una señal para un objeto y necesidad en una variante. Fija una revisión exacta y su hash; no copia valores. |
| Rango | Intervalo de ejecución `[inicio, fin)`: incluye `inicio` y excluye `fin`. |
| Stale / desactualizado | Estado que bloquea la corrida porque cambió una serie, la topología, los parámetros o un origen derivado desde la última validación. |

## 3. Señales canónicas disponibles

La siguiente tabla reúne las señales relevantes para el flujo descrito en la
guía.

| Señal canónica | Unidad | Alcance | Cuándo se requiere | Valores negativos |
| --- | --- | --- | --- | --- |
| `price_usd_per_mwh` | `USD/MWh` | Grid / caso | Precio simétrico para importar y exportar. Es la opción más simple para el flujo de variantes. | Permitidos. |
| `import_price_usd_per_mwh` | `USD/MWh` | Grid / caso | Precio pagado por energía importada cuando se usan precios separados. | Permitidos. |
| `export_price_usd_per_mwh` | `USD/MWh` | Grid / caso | Precio recibido por energía exportada cuando se usan precios separados. | Permitidos. |
| `load_demand_mw` | `MW` | `component:load` | Una por cada activo `load`. | No permitidos. |
| `renewable_available_power_mw` | `MW` | `component:renewable` | Una por cada solar/eólica `renewable`. Representa disponibilidad antes de curtailment. | No permitidos. |
| `hydro_inflow_m3s` | `m3/s` | `component:hydro` | Una por cada hidro one-bus simple. | No permitidos. |
| `natural_inflow_m3s` | `m3/s` | `hydraulic_node` | Una por cada nodo del diagrama hidráulico que declare afluente natural externo. | No permitidos. |
| `minimum_flow_m3s` | `m3/s` | `hydraulic_reach` | Una por cada tramo cuyo `flow_min_source` sea `series`. | No permitidos. |

### 3.1 Precio único frente a precios separados

El motor soporta dos contratos:

- **precio único:** cada periodo tiene `price_usd_per_mwh`;
- **precios separados:** cada periodo debe tener **ambos** campos,
  `import_price_usd_per_mwh` y `export_price_usd_per_mwh`.

No mezcles los dos enfoques accidentalmente. En particular, no cargues solo
uno de los dos precios separados: Julia rechaza un periodo que tenga precio de
importación sin precio de exportación, o viceversa.

El descubrimiento de necesidades one-bus agrupa la familia de precio en un
requerimiento. En compatibilidad muestra el selector **Serie de precio
(`price_usd_per_mwh`)**. Acepta como candidato un set con cualquiera de las
tres claves, pero el binding resuelve una clave concreta. Por eso:

- para el camino normal de variantes, usa `price_usd_per_mwh` si importación y
  exportación pueden compartir precio;
- no supongas que seleccionar un set con las dos columnas separadas hará que
  ambas se materialicen automáticamente;
- si el caso necesita precios asimétricos, comprueba que el preview ejecutable
  tenga las dos claves en todos los periodos y valida con Julia antes de crear
  la versión. El mapeo legacy del draft sí permite mapear ambas columnas; el
  selector de compatibilidad todavía no presenta dos bindings de precio
  independientes. En el recorrido protegido, revisa además el rol funcional
  de cada uso; la presencia de ambas señales en el catálogo no demuestra que
  el snapshot vaya a contenerlas.

### 3.2 Señales con entidad

Precio es una señal global del grid. Demanda, renovable e hidrología se
vinculan además a una entidad concreta.

Por ejemplo, un caso con dos cargas genera dos requerimientos distintos:

```text
component:load / load_norte / load_demand_mw
component:load / load_sur   / load_demand_mw
```

Aunque ambos usan la misma clave canónica, no son intercambiables. El nombre
del set y la selección de la variante deben dejar claro cuál alimenta a cada
activo.

## 4. Diseñar la estructura de los sets antes de importar

Una buena estructura evita casi todos los errores de matcheo posteriores.

### 4.1 Un set ancho con señales diferentes

Si precio, demanda y solar comparten exactamente la misma grilla temporal,
pueden vivir en un set:

```csv
timestamp,duration_hours,spot_usd_mwh,demanda_mw,solar_disponible_mw
2026-01-01T00:00:00-03:00,1,52.4,18.2,0.0
2026-01-01T01:00:00-03:00,1,49.8,17.6,0.0
2026-01-01T02:00:00-03:00,1,47.1,16.9,0.3
```

Mapeo:

| Columna | Señal canónica |
| --- | --- |
| `spot_usd_mwh` | `price_usd_per_mwh` |
| `demanda_mw` | `load_demand_mw` |
| `solar_disponible_mw` | `renewable_available_power_mw` |

Luego el mismo set puede seleccionarse en los tres requerimientos de la
variante. Cada binding extrae solo la señal que necesita.

### 4.2 Un set por activo cuando se repite la misma familia

La importación directa permite una sola aparición de cada `signal_key` dentro
del mismo pedido de importación. Si el archivo tiene dos cargas, no intentes
mapear dos columnas distintas a `load_demand_mw` en el mismo set.

Usa una de estas estrategias:

1. crear un archivo/set por activo; o
2. subir un archivo ancho una sola vez e importarlo varias veces, eligiendo en
   cada importación una columna diferente.

Ejemplo de fuente reutilizada:

```csv
timestamp,duration_hours,demanda_norte_mw,demanda_sur_mw
2026-01-01T00:00:00-03:00,1,12.0,7.5
2026-01-01T01:00:00-03:00,1,11.8,7.2
```

Primera importación:

```text
set: Demanda norte - base 2026
demanda_norte_mw -> load_demand_mw
```

Segunda importación sobre la misma fuente:

```text
set: Demanda sur - base 2026
demanda_sur_mw -> load_demand_mw
```

En la variante, asigna cada set al ID de carga correspondiente.

Aplica el mismo patrón cuando haya varios renovables, varios activos hidro,
varios nodos hidráulicos con afluentes o varios tramos con caudal mínimo.

### 4.3 Convención de nombres recomendada

El selector de compatibilidad muestra nombre y etiqueta de versión; el
recorrido protegido también muestra revisión, propietario y alcance. Usa
nombres que permitan reconocer la fuente antes de inspeccionarla:

```text
Precio spot SEN - base - 2026
Demanda load_norte - forecast - 2026-08-01
Solar pv_1 - P50 - 2027
Afluente reservoir_laja - seco - 2026
Caudal mínimo reach_laja_rucue - programa oficial - 2026
```

Una convención útil es:

```text
<señal o variable> - <entidad> - <escenario/fuente> - <horizonte o emisión>
```

## 5. Preparar correctamente el archivo

### 5.1 Reglas para CSV

- Codificación UTF-8; se acepta BOM UTF-8.
- Primera fila con encabezados.
- Separador coma para evitar ambigüedades con la lectura estándar.
- Encabezados no vacíos y preferentemente únicos.
- Decimales con punto, por ejemplo `12.5`, no `12,5`.
- Una fila por periodo.
- Sin títulos, notas, subtotales ni filas decorativas antes del encabezado.
- Todos los valores que se mapearán deben ser escalares numéricos finitos; no
  uses `NaN`, `Inf`, `-Inf`, `N/A` ni guiones.

### 5.2 Reglas adicionales para XLSX

- La primera fila de la hoja seleccionada es el encabezado.
- Si hay varias hojas, se elige una después de subir el archivo.
- No se admiten celdas combinadas.
- No se admiten tablas estructuradas de Excel.
- No se admiten fórmulas. Reemplázalas por sus valores antes de subir.
- Los encabezados deben ser no vacíos y únicos.

Si el XLSX es solo un vehículo de intercambio, exportarlo a CSV UTF-8 suele
dar un flujo más predecible.

### 5.3 Timestamps y duración

Cada fila representa el periodo:

```text
[timestamp, timestamp + duration_hours)
```

Ejemplo:

```text
timestamp = 2026-01-01T03:00:00-03:00
duration_hours = 1
periodo = [03:00, 04:00)
```

Usa ISO-8601. Son válidos, entre otros:

```text
2026-01-01T03:00:00
2026-01-01T03:00:00-03:00
2026-01-01T06:00:00Z
```

La importación solicita además una zona IANA, por ejemplo
`America/Santiago` o `UTC`:

- si el timestamp no trae offset, se interpreta en la zona indicada;
- si trae offset, se convierte a la zona indicada;
- la zona debe ser un nombre IANA, no `CLT`, `GMT-3` ni un texto libre.

Para Chile, revisa con especial cuidado cambios de horario de verano. Todos
los sets que se vincularán juntos deben terminar con los mismos instantes,
offsets y límites de periodo. Evita mezclar timestamps naive, UTC y offset
local sin haber comprobado el resultado normalizado.

### 5.4 Orden, duplicados, huecos y solapes

Durante la importación al catálogo:

- los timestamps deben estar ordenados ascendentemente;
- no puede repetirse el mismo timestamp;
- `duration_hours` debe ser numérico, finito y mayor que cero;
- un periodo no puede empezar antes de que termine el anterior;
- el catálogo puede almacenar una fuente con huecos, pero una corrida no puede
  consumir un rango que los contenga.

Ejemplos:

```text
00:00 duración 1 h -> termina 01:00
01:00 duración 1 h -> contiguo, correcto
02:00 duración 1 h -> contiguo, correcto
```

```text
00:00 duración 1 h -> termina 01:00
02:00 duración 1 h -> hueco [01:00, 02:00)
```

```text
00:00 duración 2 h -> termina 02:00
01:00 duración 1 h -> solape, la importación se rechaza
```

Aunque la validación de catálogo admite duraciones variables positivas,
mantén una resolución uniforme salvo que el modelo realmente la necesite. El
`resample` exige un origen uniforme y el matcheo compara duración por duración
entre todos los sets.

### 5.5 Unidades y dominio físico

La aplicación valida la unidad declarada, pero **no convierte valores**.

Ejemplos:

- `kW` no se convierte automáticamente a `MW`;
- `$/MWh` no se toma como sinónimo de `USD/MWh`;
- `l/s` no se convierte a `m3/s`.

El campo **Source unit** vacío toma por defecto la unidad canónica. Si lo
completas, debe coincidir con la unidad canónica ignorando mayúsculas y
espacios, pero no símbolos o factores de conversión.

Convierte los datos antes de importar. Además:

- demanda, disponibilidad renovable y caudales deben ser mayores o iguales a
  cero;
- los precios pueden ser negativos;
- todos los valores deben ser finitos.

### 5.6 Lista de control previa

Antes de abrir la aplicación, confirma:

- [ ] Sé qué señal canónica representa cada columna.
- [ ] Sé a qué activo, nodo o tramo corresponde cada señal con entidad.
- [ ] Todas las unidades ya están convertidas a `USD/MWh`, `MW` o `m3/s`.
- [ ] Los timestamps están ordenados y no se repiten.
- [ ] Cada duración es positiva.
- [ ] No hay solapes.
- [ ] Identifiqué los huecos deliberados o accidentales.
- [ ] Los sets que usaré juntos tienen la misma grilla temporal.
- [ ] Elegí una zona IANA coherente.
- [ ] El nombre del set identifica fuente, entidad y escenario de datos.

## 6. Importar un archivo desde el modelo

La entrada está en **Modelo → Series de tiempo → Importar series de tiempo**.
Guarda el modelo primero. Si aparece **Elegir la necesidad del modelo para
importar**, sigue el recorrido por objeto de la sección 10.7 y la carga de la
sección 6.6. Los pasos del asistente que siguen corresponden al destino
**conjunto nuevo del proyecto**, cuando está permitido.

### 6.0 Asistente de importación

Sigue **Archivo → Columnas → Revisión → Importación**:

1. Selecciona **Archivo CSV o XLSX** y pulsa **Continuar a columnas**. Se guarda
   una fuente temporal, todavía sin crear el conjunto.
2. Para XLSX, elige **Hoja**. Completa **Nombre del conjunto** y **Zona horaria
   (IANA)**; revisa las columnas de fecha/hora y duración en horas.
3. Por cada señal, elige **Columna de valores N**, **Señal N** y **Unidad de
   origen N**. Usa **Agregar señal** si hace falta. Las propuestas por nombre
   de cabecera requieren revisión: comprueba los ejemplos y las unidades.
4. En **Metadatos del conjunto**, revisa **Etiqueta de versión** y **Clase de
   datos**. Pulsa **Confirmar columnas y revisar**.
5. Comprueba o corrige las filas y pulsa **Comprobar datos**.
6. Cuando la validación termine sin errores, usa **Continuar a importación**,
   revisa destino y contenido, y pulsa **Confirmar importación**.

**Comprobar datos** valida todas las filas. Los errores con ubicación llevan a la
hoja/fila/columna; corrige la celda, **Guardar correcciones en la fuente temporal**
y vuelve a comprobar. La tabla muestra 50 filas por página y conserva cambios al
retroceder, cambiar de página y volver a una hoja ya visitada. El resumen muestra
cobertura, resolución, señales, destino y hasta cinco filas normalizadas.

El enlace final abre el conjunto persistido. Después vuelve a **Datos** del
escenario y confirma su uso en la variante. La validación del archivo y la
revisión de preparación de la corrida son comprobaciones distintas.

Al salir se explica qué fuente está guardada y qué decisiones locales se pierden.
Una respuesta de importación incierta requiere comprobar el catálogo antes de
reenviar; una fuente cambiada tras la revisión exige comprobarla nuevamente.
No hay conversiones de unidades ni relleno de huecos implícitos.

Las secciones 6.1–6.3 y 6.5 siguientes describen los controles conservados en
**Herramientas de compatibilidad: fuente del modelo y extracción**. No es necesario
abrirlos para una importación habitual. Transformaciones, reemplazo e ingesta por
API mantienen sus accesos independientes.

### 6.1 Subir la fuente con las herramientas de compatibilidad

1. Entra al proyecto y abre el escenario.
2. Presiona **Modelo** y abre **Series de tiempo → Herramientas de
   compatibilidad: fuente del modelo y extracción**.
3. Guarda cualquier cambio pendiente con **Guardar modelo**. La carga queda
   deshabilitada si el draft tiene cambios sin guardar.
4. En la sección de series, busca **Source file**.
5. Selecciona un `.csv` o `.xlsx`.
6. Presiona **Upload source**.
7. Si el XLSX tiene varias hojas, selecciona **Sheet**. Para cambiar de hoja
   puede ser necesario volver a seleccionar el archivo local.

La sección **Time-series source** muestra:

- nombre del archivo;
- tipo `csv` o `xlsx`;
- ID interno de la fuente;
- hoja seleccionada, si corresponde;
- columnas detectadas;
- una previsualización de las primeras 5 filas.

La previsualización no limita la importación: el backend lee y valida todas
las filas.

### 6.2 Corregir filas antes de importar, si hace falta

La sección **Editable rows** permite corregir celdas puntuales de la fuente:

1. edita la celda;
2. presiona **Save rows**;
3. espera el mensaje **Rows saved**.

Consideraciones:

- se muestran como máximo las primeras 50 filas;
- el guardado conserva obligatoriamente la cantidad original de filas;
- no es un editor para agregar, borrar o reordenar periodos;
- para una corrección masiva o posterior a la fila 50, corrige el archivo y
  vuelve a subirlo;
- si ya existía un mapeo legacy guardado, **Save rows** vuelve a validarlo.

### 6.3 Completar “Import mapped columns to catalog”

Esta sección hace una importación nueva y directa. Es independiente del panel
legacy **Column mapping** explicado en la sección 7.

Completa los campos:

1. **Catalog set name**: nombre estable y descriptivo.
2. **Catalog version label**: por ejemplo `v1`, `base_2026` o
   `forecast_20260801`.
3. **Catalog data kind**:
   - `real`: medición o dato realizado;
   - `programmed`: programa externo;
   - `forecast`: pronóstico;
   - `simulated`: salida de otra simulación;
   - `synthetic`: dato construido artificialmente;
   - `mixed`: mezcla explícita de orígenes.
4. **Catalog timezone**: zona IANA, por ejemplo `America/Santiago`.
5. **Catalog timestamp column**: columna que marca el inicio del periodo.
6. **Catalog duration column**: duración expresada en horas.

Luego revisa **Signal mappings**. Para cada señal:

1. en **Mapped source column N**, elige la columna del archivo;
2. en **Canonical signal N**, elige la clave canónica;
3. en **Source unit N**, confirma la unidad;
4. usa **Add signal mapping** para agregar otra señal;
5. usa **Remove mapping N** para quitar una asignación sobrante.

El botón **Import to catalog** se habilita cuando hay nombre, versión, zona,
columnas temporal/duración y al menos un mapeo completo.

### 6.4 Restricciones del mapeo directo

Dentro de una importación:

- una columna de origen no puede mapearse dos veces;
- una señal canónica no puede mapearse dos veces;
- cada columna elegida debe existir;
- cada señal debe pertenecer al catálogo permitido;
- cada unidad debe coincidir con la canónica;
- una celda vacía en una columna mapeada no se imputa: falla como no numérica;
- no hay conversión de unidades, resampling ni interpolación implícita.

Si necesitas dos `load_demand_mw`, importa dos sets como se explicó en 4.2.

### 6.5 Confirmar la creación

Después de importar aparece **Catalog import created**, con:

- nombre;
- señales incluidas;
- versión y número de versión;
- zona horaria;
- revisión;
- cantidad de periodos;
- checksum o `content_hash`.

Vuelve a la página del proyecto y abre **Catálogo de series de tiempo**. Entra
al set y revisa, como mínimo:

- **Horizonte**: primer inicio y último fin;
- **Señales**: claves y unidades correctas;
- **Valores**: primeras y últimas filas, mínimos, máximos y signos;
- **Revisión** e **Historial de revisiones**;
- **Origen** y hash.

No pases al binding solo porque la importación terminó: valida que el set
represente la entidad que dice su nombre.

### 6.6 Cargar CSV o XLSX para una serie específica

Desde **Ver fuentes del componente**, abre **Asociar fuente al objeto**,
declara la necesidad y elige **Crear específica para este objeto**. Completa
la definición y pulsa **Guardar definición**. La serie queda `awaiting_data`.

En su paso de datos:

1. Selecciona **Archivo para esta serie** y pulsa **Subir archivo temporal**.
2. Elige **Hoja del archivo** si es XLSX.
3. Asigna **Columna de inicio**, **Columna de duración en horas** y **Columna
   de valor**. El destino es la señal de esta definición.
4. Pulsa **Confirmar columnas y validar archivo**. Revisa errores, cobertura,
   vista previa y hash del lote, que aún no está publicado.
5. Continúa a **Impacto y confirmación**, escribe el motivo y confirma
   **Publicar revisión de esta serie**. Comprueba la revisión sellada.

Para corregir valores, modifica el archivo y vuelve a subirlo; puedes corregir
el mapeo en el mismo lote. Como alternativa, el formulario de puntos usa
instante ISO, **duración en segundos** y valor, sin encabezado. No confundas
los segundos de ese formulario con las horas de la columna del archivo.

La serie queda en el resumen de su objeto, fuera del catálogo global. Publicar
sus datos no crea un binding. La interfaz todavía no ofrece un selector de
específicas existentes para usarlas en una variante ni para reabrir una carga:
esas operaciones requieren la API de series del objeto y bindings. Consulta
los límites y pasos en el [manual, sección 15.8](./manual_completo_uso_pagina_web.md#158-crear-y-cargar-una-serie-específica).

## 7. Camino legacy: “Column mapping” y extracción posterior

El draft conserva un camino anterior en que las filas validadas quedan
embebidas en el documento editable. Sirve para fuentes antiguas y para generar
un preview desde el draft, pero no es la opción preferida para datos nuevos.

### 7.1 Guardar el mapeo legacy

En **Column mapping** selecciona:

- **Timestamp column**;
- **Duration column**;
- **Legacy price column**, o las dos columnas **Import price column** y
  **Export price column**;
- una columna por cada renovable, carga o hidro simple que exista en el draft.

Los selectores de activos se generan desde los IDs del modelo. Esto es una
ventaja: el mapeo deja explícito, por ejemplo, que `demanda_sic` corresponde a
`load_sic`.

Presiona **Save mapping**. El sistema valida el archivo completo y muestra:

```text
Valid mapped rows: N
```

Si hay errores, corrige **Editable rows** o el archivo y vuelve a guardar.

Para precios separados, mapea siempre las dos columnas. Para un activo sin
serie no selecciones una columna “parecida” solo para superar la validación;
corrige primero la topología o prepara la serie que falta.

### 7.2 Extraer la fuente validada

Cuando el mapeo está válido aparece **Extract legacy series to catalog**.

1. Completa **Extraction set name**.
2. Completa **Extraction version label**.
3. Elige **Extraction data kind**.
4. Indica **Extraction timezone**.
5. Presiona **Extract to catalog**.

La extracción:

- reutiliza las filas ya normalizadas por el mapeo;
- no modifica el draft;
- crea un set nuevo;
- registra procedencia hacia el draft y la fuente originales.

Para trabajo nuevo, especialmente con múltiples entidades de la misma
familia, prefiere la importación directa y sets separados por entidad. La
extracción legacy se conserva principalmente para migrar datos ya existentes.

## 8. Carga desde el conector HTTP JSON

En el **Catálogo de series de tiempo** del proyecto, la sección **Ingesta de
pronóstico (conector externo)** permite traer datos desde una API.

La respuesta puede ser una lista en la raíz:

```json
[
  {
    "period_start": "2026-08-02T00:00:00-04:00",
    "hours": 1,
    "spot": 54.2
  },
  {
    "period_start": "2026-08-02T01:00:00-04:00",
    "hours": 1,
    "spot": 51.8
  }
]
```

O estar anidada:

```json
{
  "data": {
    "records": [
      {
        "period_start": "2026-08-02T00:00:00-04:00",
        "hours": 1,
        "spot": 54.2
      }
    ]
  }
}
```

En el segundo caso, usa `data.records` como **Ruta de registros en el JSON**.

Completa:

- URL del conector;
- ruta de registros, si la lista está anidada;
- token Bearer, si corresponde;
- nombre y versión del set;
- zona horaria;
- nombres de las columnas de timestamp y duración;
- uno o más pares columna de origen -> señal canónica.

Sin **Programa oficial**, el set queda como `forecast`. Al marcar **Programa
oficial**, queda como `programmed` y se exigen:

- emisor;
- fecha de emisión;
- vigencia desde;
- vigencia hasta.

Las tres fechas deben usar ISO-8601 con offset de zona. La vigencia debe ser
coherente y contener el intervalo que declara el programa.

La API debe responder HTTP 200 y JSON. El conector usa GET, admite Bearer y
tiene un timeout acotado. Después de obtener las filas aplica las mismas reglas
de catálogo que un archivo: timestamps, duración, unidades, señales y dominio
físico.

Una nueva consulta puede:

- crear el set;
- converger sin nueva revisión si el contenido no cambió;
- agregar una revisión si cambió.

## 9. Normalizar antes del binding

La corrida nunca rellena ni remuestrea datos. Si los sets no son compatibles,
normalízalos en el catálogo antes de vincularlos.

### 9.1 Escalar una señal

En el detalle del set, **Transformaciones** -> `scale_signal`:

1. elige la señal;
2. indica un factor finito;
3. define nombre y versión del set de salida;
4. aplica la transformación.

Úsalo, por ejemplo, para crear una sensibilidad `P90 = P50 * 0.85`. No lo uses
para ocultar una unidad mal declarada: la unidad de entrada ya debe ser la
canónica.

### 9.2 Bajar resolución

En `resample`:

1. define una resolución objetivo mayor que la original;
2. elige el método permitido para cada señal;
3. crea el set derivado.

El flujo actual admite downsampling, no upsampling. El origen debe ser
uniforme, contiguo y agrupar exactamente en la resolución objetivo. El método
disponible para las señales canónicas actuales es `mean`.

### 9.3 Interpolar huecos pequeños

En `interpolate_gaps`:

1. usa método `linear`;
2. fija `max_gap_hours`;
3. crea el set derivado;
4. revisa en **Valores** las filas con badge **interpolado**.

La transformación falla si el hueco supera el máximo o no está acotado por
valores a ambos lados. Elegir el máximo es una decisión analítica, no solo
técnica: documéntala.

### 9.4 Combinar señales

El panel de catálogo permite `combine_signals` para construir un set nuevo con
señales de varios sets. Los orígenes deben compartir la misma grilla y no
pueden aportar dos veces la misma identidad de señal.

Combinar es útil cuando quieres que precio, demanda y solar viajen como un
paquete coherente. No resuelve dos entidades que usan la misma clave; para eso
mantén sets por entidad.

### 9.5 Derivados desactualizados

Toda transformación guarda receta, parámetros, inputs, revisiones y hashes.
Si cambia un origen:

1. el derivado muestra **Desactualizado**;
2. abre el derivado;
3. presiona **Regenerar set derivado**;
4. se agrega una revisión al mismo set derivado;
5. revalida las variantes que lo consumen.

No es posible revalidar y correr usando un derivado stale; la política es
fail-closed.

## 10. Matchear los sets con el caso

### 10.1 Preparar el caso

Antes del binding:

1. guarda el draft;
2. confirma IDs estables y descriptivos para grid, cargas, renovables e
   hidros;
3. genera el preview para inspeccionar topología y parámetros;
4. si el preview usa una fuente embebida ya validada, valida también con
   Julia. Si trabajas exclusivamente con catálogo + variante, las series se
   insertan recién al materializar el rango: en ese caso la validación
   decisiva es la de la variante y el snapshot creado al correr;
5. vuelve a la página del escenario.

La aplicación descubre los requerimientos desde la topología actual. Si
agregas `load_norte` después de preparar la variante, aparecerá un nuevo
requerimiento y la variante quedará desactualizada.

### 10.2 Elegir o clonar una variante

En **Datos** del escenario, panel **Variante de entrada**:

- usa **Default** para la configuración base;
- para una sensibilidad, selecciona la base, abre **Gestionar variantes**,
  escribe un nombre y usa **Clonar variante activa**;
- cambia solo los bindings que diferencian la sensibilidad.

Ejemplo:

```text
Default
  precio -> Spot base 2027
  demanda -> Demanda P50
  solar -> Solar P50

Precios estresados 2027
  precio -> Spot estrés 2027
  demanda -> Demanda P50
  solar -> Solar P50
```

Clonar evita duplicar topología y parámetros y hace más clara la comparación
entre corridas.

### 10.3 Leer la lista “Señales requeridas”

Cada fila muestra el nombre funcional, la clave y el componente, y si falta
vincular o existe un uso. Cuando hay una fuente confirmada, también muestra
nombre, revisión y estado: **Revisión fijada**, **Obsoleta: revisar** o
**Inválida: corregir**, según corresponda. La parte técnica conserva textos como:

```text
<signal_key> (<entity_id>): vinculada (set #N)
```

o:

```text
<signal_key> (<entity_id>): falta vincular
```

Ejemplo híbrido:

```text
price_usd_per_mwh (grid_1): falta vincular
load_demand_mw (load_norte): falta vincular
renewable_available_power_mw (pv_1): falta vincular
hydro_inflow_m3s (hydro_1): falta vincular
```

En un diagrama hidráulico también pueden aparecer:

```text
natural_inflow_m3s (reservoir_laja): falta vincular
minimum_flow_m3s (reach_laja_rucue): falta vincular
```

### 10.4 Criterios para seleccionar un set

Para cada necesidad, tanto en los selectores de compatibilidad como en el
recorrido protegido, confirma estas seis condiciones:

1. **Señal:** el detalle del set contiene la clave requerida.
2. **Entidad:** el nombre/procedencia del set corresponde al ID mostrado.
3. **Unidad:** coincide con la canónica.
4. **Horizonte:** cubre todo el rango a ejecutar.
5. **Grilla:** timestamps y duraciones coinciden con los demás bindings.
6. **Vigencia:** el set o derivado no está desactualizado y su revisión es la
   que quieres consumir.

El desplegable de compatibilidad puede mostrar sets del proyecto que no contienen la señal
requerida. La presencia de un set en la lista no demuestra compatibilidad:
abre el catálogo y verifica sus señales antes de seleccionarlo.

En el recorrido protegido, **Buscar fuentes candidatas** consulta al servidor;
**Fuentes anteriores** y **Más fuentes** recorren las páginas. Por defecto se
muestran las fuentes compatibles con la necesidad y el objeto elegidos. Activa
**Mostrar todas las series** para ver también las incompatibles, bloqueadas con
su explicación. El cambio de filtro vuelve a la primera página y descarta la
selección anterior, conservando la búsqueda. **Necesidad funcional** solo ofrece
roles admitidos para el objeto: los precios se asignan a **System**, la demanda
a `load_1` y la disponibilidad renovable a `solar_1`. Cambiar la necesidad
descarta la selección anterior: vuelve a revisar objeto, señal y fuente.

El panel **Destino de la vinculación** muestra proyecto, escenario, caso,
variante y objeto, con sus nombres e identificadores, en todos los pasos.
**Revisar objetos del escenario** regresa a los datos de la misma variante
para elegir otro componente. **Paso anterior** retrocede dentro del recorrido;
**Volver a la pantalla de origen** sale hacia el destino original conservando
sus filtros. Asociar una fuente al objeto y usar su revisión en una variante
son acciones separadas.

### 10.5 Ejemplo de matriz de matcheo

| Requerimiento del caso | Set elegido | Qué se comprueba |
| --- | --- | --- |
| Grid `grid_1` / `price_usd_per_mwh` | `Precio spot SEN - base 2026` | Contiene `price_usd_per_mwh`, `USD/MWh`. |
| Load `load_norte` / `load_demand_mw` | `Demanda load_norte - P50 2026` | Corresponde a `load_norte`, no a otra carga. |
| Renewable `pv_1` / `renewable_available_power_mw` | `Solar pv_1 - P50 2026` | Disponibilidad, no generación ya recortada. |
| Hydro `hydro_1` / `hydro_inflow_m3s` | `Afluente hydro_1 - medio 2026` | Hidro simple one-bus. |
| Hydraulic node `reservoir_laja` / `natural_inflow_m3s` | `Afluente reservoir_laja - seco 2026` | Nodo correcto y `m3/s`. |
| Hydraulic reach `reach_1` / `minimum_flow_m3s` | `Caudal mínimo reach_1 - programa 2026` | Tramo correcto y `m3/s`. |

### 10.6 Qué hace el binding con una señal de entidad

Al vincular `load_demand_mw` al requerimiento de `load_norte`, la aplicación
materializa cada valor bajo el ID del activo:

```json
{
  "timestamp": "2026-01-01T00:00:00",
  "duration_hours": 1.0,
  "load_demand_mw": {
    "load_norte": 12.0
  }
}
```

Con dos cargas correctamente vinculadas:

```json
{
  "timestamp": "2026-01-01T00:00:00",
  "duration_hours": 1.0,
  "load_demand_mw": {
    "load_norte": 12.0,
    "load_sur": 7.5
  }
}
```

Por eso el set no “sabe” por sí solo a qué activo va destinado en el caso: el
binding agrega ese contexto. Un nombre de set ambiguo facilita errores humanos
aunque la validación técnica pase.

### 10.7 Asociar una fuente y fijar su revisión en el recorrido protegido

1. En **Datos**, comprueba **Variante activa** y abre **Ver fuentes del
   componente** de la necesidad que vas a resolver. El enlace conserva
   escenario, variante y regreso.
2. Si la fuente genérica aún no está asociada, abre **Asociar fuente al objeto**,
   declara **Necesidad funcional** y elige **Reutilizar una fuente genérica**.
3. Busca una candidata compatible; revisa su revisión, hash, cobertura,
   propietario y alcance. En **Impacto y confirmación**, revisa la
   prevalidación y confirma **Asociar fuente al objeto**.
4. Abre **Usar revisión en una variante** para esa fuente. Comprueba escenario,
   variante, objeto y necesidad; selecciona la fuente y revisa la revisión
   exacta. Si reemplaza otro uso, compara el antes/después y completa el motivo.
5. Revisa el impacto y confirma **Usar revisión en una variante**. Si hay un
   conflicto, pulsa **Revisar de nuevo** antes de intentar confirmar.
6. Vuelve al objeto y comprueba **Usada en {variante}**, revisión y hash. Usa
   **Volver al escenario** o **Volver al origen** y revisa el período.

**Corregir** y **Revisar fuente** pueden abrir directamente el recorrido de uso;
si falta la asociación de la fuente genérica, resuélvela primero desde el objeto.
La asociación por sí sola no deja la variante lista para ejecutar. Para una
serie específica, aplican los límites de interfaz de la sección 6.6.

## 11. Elegir y validar el rango

### 11.1 Semántica `[inicio, fin)`

Para correr 24 periodos horarios del 1 de enero:

```text
Inicio de rango: 2026-01-01T00:00:00-03:00
Fin de rango:    2026-01-02T00:00:00-03:00
```

El fin no es el timestamp de la última fila; es el extremo final del último
periodo.

Si las filas comienzan a las 00:00, 01:00 y 02:00 con duración de 1 hora, el
rango de las tres filas es:

```text
[00:00, 03:00)
```

### 11.2 Completar el período y revisar su preparación

Completa **Inicio del período**, **Fin del período**, **Offset de inicio** y
**Offset de fin**. Conserva el offset de las fuentes y comprueba la zona,
duración y resumen `[inicio, fin)`. **Entrada ISO avanzada** permite editar
los valores literales del ejemplo anterior.

Revisa cualquier sugerencia inicial. Cambiar de fuente conserva el rango
digitado; **Usar cobertura disponible** lo sustituye solo cuando tú lo pides
y el servidor ha comprobado la cobertura común. Si no aparece, define un
período cubierto por todas las fuentes y resuelve los problemas indicados.

El mensaje local **Rango valido para correr** no basta. Con las fuentes
confirmadas, pulsa **Revisar preparación**. La ejecución se habilita al ver
**Preparado para ejecutar este período**. Cambiar fuentes, bindings o período,
o fallar la actualización de su consulta, exige revisar de nuevo.

### 11.3 Validaciones exactas

Para cada binding, el rango debe:

- empezar exactamente en el inicio de un periodo;
- terminar exactamente en el fin de un periodo;
- tener al menos un periodo;
- estar cubierto sin huecos ni solapes;
- tener un valor para la señal en cada periodo.

Entre bindings, además debe haber:

- igual cantidad de periodos;
- mismos timestamps en el mismo orden;
- igual `duration_hours` en cada timestamp.

No hay tolerancia temporal ni remuestreo implícito. Dos grillas que representan
conceptualmente la misma hora, pero quedan almacenadas con límites u offsets
distintos, se consideran incompatibles.

### 11.4 Confirmar fuentes, revisar y ejecutar

1. En compatibilidad, selecciona las fuentes y pulsa **Confirmar fuentes**.
   En el modo protegido, confirma los usos mediante la sección 10.7.
2. Define el período y pulsa **Revisar preparación**.
3. Espera **Preparado para ejecutar este período**.
4. Pulsa **Ejecutar variante** una vez y espera la navegación o el error.

Confirmar fuentes y revisar preparación no crean una versión ni una corrida.
El botón final usa los bindings ya confirmados; no vuelve a guardarlos. Al
ejecutar, el servidor:

1. vuelve a comprobar dependencias, revisiones, cobertura y grilla;
2. materializa las filas desde las revisiones fijadas para el rango;
3. congela topología, parámetros, variante, rango y lineage;
4. crea la versión inmutable y la corrida;
5. encola la ejecución y abre su detalle.

No se leen valores “en vivo” durante la ejecución. La corrida usa el snapshot
que acaba de crearse.

Si **Confirmar fuentes** falla parcialmente, el mensaje cuenta los cambios
aceptados y conserva los pendientes. Consulta el estado actualizado antes de
reintentar. Si aparece **No pudimos confirmar el envío** al ejecutar, abre
**Consultar historial de ejecuciones**: la corrida puede haberse aceptado.
Solo después de comprobarlo usa **Ya consulté el historial: preparar otro
intento**, si corresponde, y revisa de nuevo. No hay reenvío automático.

## 12. Revalidación y cambios posteriores

### 12.1 Qué vuelve stale una variante

- Una corrección manual agrega una revisión al set vinculado.
- Un reemplazo de archivo agrega una revisión.
- Una nueva ingesta del conector cambia el contenido.
- Se regenera un derivado.
- Un derivado vinculado queda stale respecto de sus inputs.
- Cambia la topología del caso.
- Cambian parámetros del caso.

### 12.2 Procedimiento correcto

Cuando aparece **Variante desactualizada: revalida antes de correr**:

1. lee todos los motivos del banner;
2. si hay un derivado stale, regénéralo primero;
3. confirma en el catálogo la nueva revisión y el nuevo hash;
4. revisa el rango;
5. si un binding canónico está obsoleto o inválido, abre **Revisar fuente** y
   confirma el uso de la revisión elegida con su motivo e impacto;
6. presiona **Revisar preparación** en **Datos** del escenario;
7. espera **Preparado para ejecutar este período** y comprueba variante,
   fuentes y rango;
8. presiona **Ejecutar variante**.

En compatibilidad, la revisión valida las dependencias actuales. En canónico,
**Revisar preparación** comprueba las revisiones fijadas: no reemplaza un
binding obsoleto ni elige automáticamente la revisión más reciente. Conservar
explícitamente una revisión histórica como `pinned` requiere el flujo API;
el recorrido React ofrece la vigente. Las corridas anteriores conservan sus
snapshots y hashes en todos los casos.

### 12.3 Corregir un set

En el detalle del set hay dos caminos:

- **Valores** -> editar celdas -> **Guardar correcciones**;
- **Reemplazar con nuevo archivo** -> subir CSV/XLSX -> remapear ->
  **Reemplazar set**.

Con contenido distinto se registra una revisión nueva; una operación sin
cambios puede reutilizar el contenido existente. Comprueba la respuesta, el
historial y el hash. El nombre y la etiqueta de versión del set se
mantienen en un reemplazo; cambian el número de revisión y el `content_hash`.

Para una fuente `global`, el reemplazo tras C6 exige la confirmación de impacto
compartido. Si aparece `TS_LINK_CONFIRMATION_REQUIRED`, sigue **Publicar para
todos** en el [manual, sección 15.9](./manual_completo_uso_pagina_web.md#159-cambiar-una-fuente-compartida-desde-el-objeto),
con una cuenta admin. Repetir el formulario de reemplazo no resuelve ese requisito.

Usa **Resumen del cambio** o **Resumen del reemplazo** para dejar una
explicación auditable, por ejemplo:

```text
Se corrige demanda de 2026-01-03 14:00 por dato oficial del operador.
```

## 13. Recetas completas

Las recetas siguientes describen los datos, mapeos y destinos esperados. Para
crear conjuntos nuevos usa el asistente de la sección 6.0 cuando esté habilitado;
para fuentes canónicas existentes usa la sección 10.7. Si el destino requiere
una serie específica, consulta la sección 6.6 y su límite para crear el binding.
Termina cada receta confirmando las fuentes, revisando la preparación y ejecutando.

### 13.1 BESS + grid con precio único

Archivo:

```csv
timestamp,duration_hours,spot
2026-01-01T00:00:00-03:00,1,52.4
2026-01-01T01:00:00-03:00,1,49.8
2026-01-01T02:00:00-03:00,1,47.1
```

Importación:

```text
Nombre del conjunto: Precio spot - base 2026-01-01
Etiqueta de versión: v1
Clase de datos: Real (real)
Zona horaria (IANA): America/Santiago
Columna de fecha y hora: timestamp
Columna de duración (horas): duration_hours
spot -> price_usd_per_mwh -> USD/MWh
```

Binding:

```text
Serie de precio (price_usd_per_mwh)
  -> Precio spot - base 2026-01-01 - v1
```

Rango:

```text
[2026-01-01T00:00:00-03:00, 2026-01-01T03:00:00-03:00)
```

### 13.2 Caso híbrido en un set ancho

Archivo:

```csv
timestamp,duration_hours,spot,load_norte,pv_1_available
2026-01-01T00:00:00-03:00,1,52.4,18.2,0.0
2026-01-01T01:00:00-03:00,1,49.8,17.6,0.0
2026-01-01T02:00:00-03:00,1,47.1,16.9,0.3
```

Mapeos del mismo set:

```text
spot           -> price_usd_per_mwh
load_norte     -> load_demand_mw
pv_1_available -> renewable_available_power_mw
```

Bindings:

```text
grid_1 / price_usd_per_mwh                 -> set híbrido
load_norte / load_demand_mw                -> set híbrido
pv_1 / renewable_available_power_mw        -> set híbrido
```

Esto funciona porque las tres claves canónicas son distintas y comparten la
misma grilla.

### 13.3 Dos cargas en una fuente

Archivo:

```csv
timestamp,duration_hours,load_norte,load_sur
2026-01-01T00:00:00-03:00,1,12.0,7.5
2026-01-01T01:00:00-03:00,1,11.8,7.2
```

Importa dos veces:

```text
Demanda load_norte - base
  load_norte -> load_demand_mw

Demanda load_sur - base
  load_sur -> load_demand_mw
```

Matchea:

```text
Serie load_demand_mw (load_norte) -> Demanda load_norte - base
Serie load_demand_mw (load_sur)   -> Demanda load_sur - base
```

### 13.4 Diagrama hidráulico

Fuente:

```csv
timestamp,duration_hours,q_laja,q_min_reach_1
2026-01-01T00:00:00-03:00,1,35.0,12.0
2026-01-01T01:00:00-03:00,1,34.5,12.0
```

Puede importarse como un set porque las claves son distintas:

```text
q_laja        -> natural_inflow_m3s
q_min_reach_1 -> minimum_flow_m3s
```

Bindings:

```text
reservoir_laja / natural_inflow_m3s -> set hidráulico
reach_1 / minimum_flow_m3s          -> set hidráulico
```

Si hay dos nodos con `natural_inflow_m3s`, crea un set por nodo o importa la
misma fuente varias veces, igual que en el ejemplo de dos cargas.

## 14. Diagnóstico de errores frecuentes

| Mensaje o síntoma | Causa probable | Qué revisar |
| --- | --- | --- |
| No se puede avanzar en la importación | Falta una columna, señal, unidad u otro campo, hay cambios sin comprobar o falló la validación. | Revisa **Columnas**, guarda las correcciones y usa **Comprobar datos** antes de confirmar. En compatibilidad revisa **Signal mappings**. |
| `timestamp ... must be ISO-8601` | Formato no ISO, celda vacía o fecha decorativa de Excel. | Usa `YYYY-MM-DDTHH:MM:SS` con offset opcional. |
| `duplicate timestamp` | Dos filas representan el mismo inicio después de normalizar zona. | Elimina duplicado o corrige zona/offset. |
| `periods must be ordered` | Filas fuera de orden. | Ordena ascendentemente el archivo. |
| `period starts before ... ends` | `duration_hours` genera un solape. | Corrige duración o timestamp siguiente. |
| `must be numeric` | Celda vacía, coma decimal, texto, `N/A` o fórmula no materializada. | Usa número con punto decimal. |
| `must be finite` | `NaN` o infinito. | Sustituye por un valor válido o trata el hueco explícitamente. |
| `must be nonnegative` | Demanda, renovable o caudal negativo. | Corrige dato/unidad; no lo silencies con valor absoluto sin justificación. |
| `source unit ... does not match canonical unit` | Unidad distinta o alias no reconocido. | Convierte valores y declara exactamente la unidad canónica. |
| `column ... is mapped more than once` | Reutilizaste una columna en dos filas de mapeo. | Deja una asignación por columna. |
| `signal_key ... is mapped more than once` | Dos columnas se intentan cargar bajo la misma clave en un set. | Crea sets separados por entidad. |
| Set visible pero falla el binding | El selector de compatibilidad lista sets del proyecto y el elegido no contiene la señal. | Abre el set y comprueba **Señales**. En el recorrido protegido, lee la incompatibilidad de la candidata. |
| `missing required bindings` | Falta al menos un requerimiento de topología. | Revisa toda la lista **Señales requeridas**. |
| `missing coverage for [A, B)` | El rango excede el set o contiene un hueco. | Acorta rango, reemplaza fuente o interpola explícitamente. |
| `first period starts ... before requested range start` | Inicio no coincide con límite de periodo. | Copia el `timestamp_start` exacto del catálogo. |
| `last period ends ... after requested range end` | Fin corta un periodo. | Usa el `timestamp_end` exacto del último periodo. |
| `horizon incompatible ... no implicit resampling` | Cantidad, timestamps o duraciones difieren entre sets. | Resamplea/combina antes o elige sets con la misma grilla. |
| `missing value for period` | El set tiene periodo pero no valor para esa señal. | Revisa importación/revisión y reemplaza el set. |
| Julia exige ambos precios separados | Solo llegó importación o solo exportación. | Usa precio único o materializa ambas claves en cada periodo. |
| **Variante desactualizada** | Cambió serie, derivado, topología o parámetros. | Lee motivos, regenera si aplica, resuelve usos canónicos obsoletos y pulsa **Revisar preparación**. |
| Rango válido pero **Ejecutar variante** deshabilitado | Falta confirmar fuentes o revisar la preparación vigente. | Confirma los usos y espera **Preparado para ejecutar este período**. |
| **No pudimos confirmar el envío** | No se pudo confirmar la respuesta a la solicitud de ejecución. | Consulta el historial antes de preparar otro intento; puede existir una corrida aceptada. |
| `TS_BINDING_EXECUTION_BLOCKED` | Hay usos canónicos obsoletos o inválidos. | Revisa cada fuente desde su objeto y confirma la revisión; después revisa la preparación. |
| Serie específica sin uso en variante | Publicar datos no crea el binding. | Comprueba la revisión sellada y prepara el uso mediante la API; consulta la sección 6.6. |
| Derivado **Desactualizado** | Cambió uno de sus inputs. | **Regenerar set derivado** y luego revalidar variante. |
| Corrida `failed` pese a rango válido | Contrato incompleto, parámetros inviables o error de solver. | Revisa snapshot, error estructurado, stdout y stderr del run. |

## 15. Verificación posterior a la corrida

En el detalle de un run exitoso, abre **Detalle técnico y auditoría → Series
de entrada** y contrasta el lineage de la versión. Para cada binding comprueba:

- `signal_key`;
- `entity_type` y `entity_id`, si corresponden;
- ID del set;
- etiqueta y número de versión;
- número de revisión;
- `content_hash`;
- rango validado.

Para usos TS-7, comprueba también `binding_id`, `linkable_object_id`,
`binding_role_key`, `signal_id` y `set_revision_id` en `series_bindings` de la
metadata de generación de la versión. Esa es la referencia congelada de la
corrida, aunque la fuente haya cambiado después.

Ejemplo conceptual:

```text
load_demand_mw (load_norte)
set #42 - Demanda load_norte - P50
version v1 / revision 3
sha256:...
[2026-01-01T00:00:00-03:00, 2026-01-02T00:00:00-03:00)
```

Compara este lineage con tu matriz de matcheo. Si el resultado parece extraño,
antes de cuestionar el solver confirma:

1. entidad correcta;
2. señal correcta;
3. revisión correcta;
4. rango correcto;
5. unidad y escala correctas.

## 16. Checklist final antes de correr

### Catálogo

- [ ] Cada set tiene nombre inequívoco.
- [ ] Las señales canónicas son las correctas.
- [ ] Las unidades son canónicas y los valores ya fueron convertidos.
- [ ] Los valores físicos no negativos cumplen esa restricción.
- [ ] Horizonte, zona y resolución están verificados.
- [ ] No hay huecos dentro del rango de corrida.
- [ ] Los derivados están vigentes.
- [ ] Conozco revisión y hash que espero consumir.

### Variante

- [ ] Elegí la variante correcta y comprobé el contexto al volver del objeto.
- [ ] Cada requerimiento tiene una fuente confirmada, no solo seleccionada.
- [ ] Cada binding corresponde al objeto y necesidad mostrados.
- [ ] Las fuentes contienen la señal requerida y fijan la revisión esperada.
- [ ] Inicio y fin son límites exactos de periodos.
- [ ] Usé **Revisar preparación** y veo **Preparado para ejecutar este período**.
- [ ] La variante no está desactualizada.
- [ ] Ningún binding canónico aparece obsoleto, inválido o bloqueado.

### Corrida

- [ ] El preview es correcto y, cuando contiene series embebidas, la
  validación Julia también.
- [ ] Presioné **Ejecutar variante** una sola vez y esperé la redirección.
- [ ] Si el envío quedó incierto, consulté el historial antes de otro intento.
- [ ] En el detalle del run verifiqué set, revisión, hash, entidad y rango.

## 17. Referencias internas

- [Guía del analista](./guia_analista.md).
- [Manual completo de la aplicación](./manual_completo_uso_pagina_web.md).
- [Catálogo global y series específicas TS-7](../series_tiempo/iter7/spec_ts7_catalogo_global_y_series_especificas.md).
- [Importación guiada: comportamiento implementado](../mejora_experiencia_usuario/evidencia/ux-003/README.md).
- [Fuentes desde la necesidad del modelo](../mejora_experiencia_usuario/evidencia/ux-004/README.md).
- [Preparación y ejecución de variantes](../mejora_experiencia_usuario/evidencia/ux-005/README.md).
- [Semántica del catálogo de series](../series_tiempo/iter2/decision_record_ts2_catalog_semantics.md).
- [Semántica de variantes y bindings](../series_tiempo/iter3/decision_record_ts3_variant_semantics.md).
- [Arquitectura final de transformaciones, conectores y schedules](../series_tiempo/iter6/architecture_ts6_final.md).
- [Semántica de transformaciones](../series_tiempo/iter6/decision_record_ts6_transformation_semantics.md).
- [Pruebas manuales TS-2](../series_tiempo/iter2/pruebas_manuales_ts2.md).
- [Pruebas manuales TS-3](../series_tiempo/iter3/pruebas_manuales_ts3.md).
- [Pruebas manuales TS-6](../series_tiempo/iter6/pruebas_manuales_ts6.md).
