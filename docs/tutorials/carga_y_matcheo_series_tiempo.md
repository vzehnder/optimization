# Tutorial detallado: carga y matcheo de series de tiempo

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

> **Resumen corto:** cargar no es lo mismo que vincular. Primero se normalizan
> columnas y valores dentro del catálogo. Después, en la variante de entrada,
> se decide qué set alimenta a cada entidad concreta del caso.

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
        |  4. Binding señal + entidad -> set
        v
Variante de entrada
        |
        |  5. Selección y validación del rango [inicio, fin)
        v
Snapshot inmutable -> corrida -> resultados y lineage
```

Hay dos “matcheos” diferentes:

1. **Mapeo de importación:** una columna física, por ejemplo `demanda_mw`, se
   interpreta como la señal canónica `load_demand_mw`.
2. **Binding del caso:** el set que contiene `load_demand_mw` se asigna, por
   ejemplo, al activo `load_centro` y no a `load_norte`.

El primer paso da significado y unidad al dato. El segundo le da destino
dentro del modelo.

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
| Binding | Referencia desde una señal requerida —y, cuando corresponde, una entidad— hacia un set. No copia valores. |
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

La UI actual de **Variante de entrada** descubre un único requerimiento de
familia de precio y muestra el selector **Serie de precio
(`price_usd_per_mwh`)**. Acepta como candidato un set con cualquiera de las
tres claves, pero el binding resuelve una clave concreta. Por eso:

- para el camino normal de variantes, usa `price_usd_per_mwh` si importación y
  exportación pueden compartir precio;
- no supongas que seleccionar un set con las dos columnas separadas hará que
  ambas se materialicen automáticamente;
- si el caso necesita precios asimétricos, comprueba que el preview ejecutable
  tenga las dos claves en todos los periodos y valida con Julia antes de crear
  la versión. El mapeo legacy del draft sí permite mapear ambas columnas; el
  selector genérico de variantes todavía no presenta dos bindings de precio
  independientes.

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

El selector de variantes muestra principalmente nombre y etiqueta de versión.
Usa nombres que permitan decidir sin abrir cada set:

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

## 6. Camino recomendado: importar desde una fuente del draft al catálogo

La UI de carga vive en el editor del draft, aunque el resultado recomendado
para trabajo nuevo es un set reutilizable del catálogo del proyecto.

### 6.1 Subir la fuente

1. Entra al proyecto y abre el escenario.
2. Presiona **Abrir draft**.
3. Guarda cualquier cambio pendiente con **Guardar draft**. La carga queda
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

En **Variante de entrada**:

- usa **Default** para la configuración base;
- para una sensibilidad, selecciona la base, escribe un nombre y usa **Clonar
  variante activa**;
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

Cada fila muestra:

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

Para cada selector **Serie ...**, confirma estas seis condiciones:

1. **Señal:** el detalle del set contiene la clave requerida.
2. **Entidad:** el nombre/procedencia del set corresponde al ID mostrado.
3. **Unidad:** coincide con la canónica.
4. **Horizonte:** cubre todo el rango a ejecutar.
5. **Grilla:** timestamps y duraciones coinciden con los demás bindings.
6. **Vigencia:** el set o derivado no está desactualizado y su revisión es la
   que quieres consumir.

El desplegable puede mostrar sets del proyecto que no contienen la señal
requerida. La presencia de un set en la lista no demuestra compatibilidad:
abre el catálogo y verifica sus señales antes de seleccionarlo.

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

### 11.2 Valores propuestos por la UI

La UI propone el inicio y fin del primer set seleccionado. Revísalos: que sean
válidos para un set no garantiza que lo sean para los demás.

Cuando todos los bindings son compatibles aparece:

```text
Rango valido para correr.
```

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

### 11.4 Vincular y correr

Cuando todas las señales están seleccionadas, el rango es válido y la variante
no está stale, presiona **Vincular y correr variante**.

Esta acción:

1. guarda o actualiza cada binding seleccionado;
2. resuelve las revisiones actuales de los sets;
3. vuelve a validar cobertura y grilla en el backend;
4. materializa las filas del rango;
5. congela topología, parámetros, variante, rango y lineage;
6. crea la versión inmutable;
7. crea y lanza la corrida.

No se leen valores “en vivo” durante la ejecución. La corrida usa el snapshot
que acaba de crearse.

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
5. presiona **Revalidar variante**;
6. espera que desaparezca el banner;
7. vuelve a comprobar los selectores;
8. corre.

Revalidar significa aceptar explícitamente las dependencias actuales. No
modifica corridas anteriores ni cambia los hashes que ellas ya congelaron.

### 12.3 Corregir un set

En el detalle del set hay dos caminos:

- **Valores** -> editar celdas -> **Guardar correcciones**;
- **Reemplazar con nuevo archivo** -> subir CSV/XLSX -> remapear ->
  **Reemplazar set**.

Ambos crean una revisión nueva. El nombre y la etiqueta de versión del set se
mantienen en un reemplazo; cambian el número de revisión y el `content_hash`.

Usa **Resumen del cambio** o **Resumen del reemplazo** para dejar una
explicación auditable, por ejemplo:

```text
Se corrige demanda de 2026-01-03 14:00 por dato oficial del operador.
```

## 13. Recetas completas

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
Catalog set name: Precio spot - base 2026-01-01
Catalog version label: v1
Catalog data kind: real
Catalog timezone: America/Santiago
Catalog timestamp column: timestamp
Catalog duration column: duration_hours
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
| **Import to catalog** deshabilitado | Falta nombre, versión, zona, timestamp, duración o hay un mapeo incompleto. | Completa o elimina cada fila de **Signal mappings**. |
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
| Set visible pero falla el binding | El dropdown lista sets de todo el proyecto y el elegido no contiene la señal. | Abre el set y comprueba **Señales**. |
| `missing required bindings` | Falta al menos un requerimiento de topología. | Revisa toda la lista **Señales requeridas**. |
| `missing coverage for [A, B)` | El rango excede el set o contiene un hueco. | Acorta rango, reemplaza fuente o interpola explícitamente. |
| `first period starts ... before requested range start` | Inicio no coincide con límite de periodo. | Copia el `timestamp_start` exacto del catálogo. |
| `last period ends ... after requested range end` | Fin corta un periodo. | Usa el `timestamp_end` exacto del último periodo. |
| `horizon incompatible ... no implicit resampling` | Cantidad, timestamps o duraciones difieren entre sets. | Resamplea/combina antes o elige sets con la misma grilla. |
| `missing value for period` | El set tiene periodo pero no valor para esa señal. | Revisa importación/revisión y reemplaza el set. |
| Julia exige ambos precios separados | Solo llegó importación o solo exportación. | Usa precio único o materializa ambas claves en cada periodo. |
| **Variante desactualizada** | Cambió serie, derivado, topología o parámetros. | Lee motivos, regenera si aplica y revalida. |
| Derivado **Desactualizado** | Cambió uno de sus inputs. | **Regenerar set derivado** y luego revalidar variante. |
| Corrida `failed` pese a rango válido | Contrato incompleto, parámetros inviables o error de solver. | Revisa snapshot, error estructurado, stdout y stderr del run. |

## 15. Verificación posterior a la corrida

En el detalle de un run exitoso, revisa **Series de entrada** o el lineage de
la versión. Para cada binding deben aparecer:

- `signal_key`;
- `entity_type` y `entity_id`, si corresponden;
- ID del set;
- etiqueta y número de versión;
- número de revisión;
- `content_hash`;
- rango validado.

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

- [ ] Elegí la variante correcta, no otra guardada en el navegador.
- [ ] Cada requerimiento tiene un set seleccionado.
- [ ] Cada set corresponde a la entidad mostrada.
- [ ] Los sets contienen realmente la señal requerida.
- [ ] Inicio y fin son límites exactos de periodos.
- [ ] La UI muestra **Rango valido para correr**.
- [ ] La variante no está desactualizada.

### Corrida

- [ ] El preview es correcto y, cuando contiene series embebidas, la
  validación Julia también.
- [ ] Presioné **Vincular y correr variante** una sola vez y esperé la redirección.
- [ ] En el detalle del run verifiqué set, revisión, hash, entidad y rango.

## 17. Referencias internas

- [Guía del analista](./guia_analista.md).
- [Semántica del catálogo de series](../series_tiempo/iter2/decision_record_ts2_catalog_semantics.md).
- [Semántica de variantes y bindings](../series_tiempo/iter3/decision_record_ts3_variant_semantics.md).
- [Arquitectura final de transformaciones, conectores y schedules](../series_tiempo/iter6/architecture_ts6_final.md).
- [Semántica de transformaciones](../series_tiempo/iter6/decision_record_ts6_transformation_semantics.md).
- [Pruebas manuales TS-2](../series_tiempo/iter2/pruebas_manuales_ts2.md).
- [Pruebas manuales TS-3](../series_tiempo/iter3/pruebas_manuales_ts3.md).
- [Pruebas manuales TS-6](../series_tiempo/iter6/pruebas_manuales_ts6.md).
