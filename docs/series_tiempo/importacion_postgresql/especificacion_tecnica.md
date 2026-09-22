# Importación de series desde PostgreSQL

Fecha: 2026-09-21. Versión: 1.0.

Estado: alcance funcional confirmado por el usuario tras la entrevista `grill-me`.
Este documento especifica la implementación pendiente; no acredita que la funcionalidad ya exista.

Lectura sugerida: [decisiones](#1-objetivo-y-decisiones-confirmadas),
[interfaz](#3-experiencia-de-usuario), [matcheo](#5-selección-y-correspondencia-uno-a-uno),
[transformación](#7-contrato-temporal-y-transformación),
[actualización](#8-actualización-revisión-y-atomicidad),
[programación](#9-ejecución-automática), [persistencia](#11-persistencia-y-migraciones),
[API](#12-contrato-http-propuesto) y [aceptación](#15-criterios-de-aceptación-y-pruebas).

## 1. Objetivo y decisiones confirmadas

Permitir importar y actualizar series de tiempo desde una base PostgreSQL externa,
seleccionando tablas o vistas, IDs, columnas y filtros, con correspondencia explícita
uno a uno hacia series locales. Transformar la resolución antes de persistir los
puntos locales y publicar revisiones completas que puedan utilizarse en el proyecto.

| Tema | Decisión confirmada |
| --- | --- |
| Entregable de esta etapa | Especificación técnica en `docs`; implementación a cargo de una etapa posterior. |
| Motor de origen | Solo PostgreSQL. La base local conserva los motores ya soportados por el proyecto. |
| Forma de origen | Formato largo: columna de ID de serie, columna timestamp y columna valor. Una tabla o vista por selección; varias selecciones por importación. |
| Correspondencia | Cada ID seleccionado tiene exactamente un destino: serie existente o nueva. Dos IDs no pueden alimentar el mismo destino dentro de la importación. |
| Entrada a la interfaz | Desde el catálogo y desde las series de un objeto. Distinguir fuente compartida y serie específica del objeto. |
| Conexiones | Perfiles reutilizables privados por usuario, en panel plegable. Contraseña de sesión u opción de guardarla cifrada; las ejecuciones automáticas requieren esta última. |
| Resolución | Por serie. Detectar y mostrar la original, permitir declaración manual validada; heredar la del destino existente o elegirla para uno nuevo. Opción «Aplicar a todas». |
| Conversión | Ambos sentidos. Promedio/mantenimiento del valor para precios y medias de potencia/caudal; suma/reparto proporcional para energía/volumen por intervalo. |
| Ejecución | Manual o automática, con frecuencia configurable y configuración de importación reutilizable. |
| Actualización | Añadir datos y corregir el rango consultado; conservar lo que quede fuera y todas las revisiones anteriores. |
| Rango | Fijo o móvil. En automático, intervalos completos y retraso de disponibilidad configurable. |
| Filtros | Constructor visual por columnas, con grupos Y/O; IDs y fechas obligatorios. Combinaciones de tablas mediante vistas preparadas en origen. |
| Calidad | Huecos, duplicados, nulos o irregularidad bloquean el conjunto afectado. Otros conjuntos válidos pueden publicarse. No rellenar ni descartar silenciosamente. |
| Tiempo | Zona horaria explícita cuando no exista en la columna; indicar inicio/fin de intervalo; normalizar a UTC; rechazar horas ambiguas sin desambiguación. |
| Capacidad inicial | Hasta 100 series y 5.000.000 de puntos por ejecución, límites configurables, procesamiento en segundo plano, progreso y cancelación. |

Las decisiones de arquitectura, nombres de recursos, cuotas operativas y algoritmos
que siguen son la propuesta técnica concreta para cumplir ese alcance. Las cuotas
de tiempo y memoria son objetivos de validación, no mediciones del sistema actual.

Quedan fuera de este corte: otros motores, SQL libre, joins en la interfaz, formato
ancho, escritura sobre el origen, interpolación para reparar huecos, lectura de
contadores acumulativos, intervalos de duración variable y agregaciones por mes o
por día civil. Un intervalo de 24 horas tiene duración fija; una programación diaria
sí puede seguir el calendario de una zona horaria.

## 2. Base existente y cambios necesarios

La inspección del repositorio identificó estos puntos de integración:

| Componente existente | Aprovechamiento y cambio requerido |
| --- | --- |
| [React y FastAPI](../../../README.md) | Mantener React como interfaz y FastAPI como propietario de autenticación y API. |
| [GlobalCatalog.tsx](../../../frontend/src/GlobalCatalog.tsx), [ObjectTimeSeriesSummary.tsx](../../../frontend/src/ObjectTimeSeriesSummary.tsx) | Añadir enlaces de entrada. El catálogo conserva su superficie de lectura. |
| [ProtectedMutationJourney.tsx](../../../frontend/src/ProtectedMutationJourney.tsx), [journeyRoutes.ts](../../../frontend/src/journeyRoutes.ts) | Integrar la nueva intención de importar y conservar el retorno al contexto original. No publicar desde los componentes de lectura. |
| [ObjectSeriesFileImport.tsx](../../../frontend/src/ObjectSeriesFileImport.tsx), [GuidedImport.tsx](../../../frontend/src/GuidedImport.tsx) | Reutilizar patrones de mapeo, errores y preview. No convertir PostgreSQL en un archivo ficticio. |
| [main.py](../../../app/main.py), [client.ts](../../../frontend/src/api/client.ts) | Rutas, modelos y cliente tipado nuevos; regenerar OpenAPI y tipos. |
| [forecast_connector.py](../../../app/forecast_connector.py) | Precedente de aislamiento de un conector. El actual es HTTP/JSON y materializa listas; no sirve directamente para streaming PostgreSQL. |
| [transformations.py](../../../app/transformations.py) | `resample` admite `mean`/`sum`, solo resolución más gruesa, múltiplos enteros y periodos contiguos. Crear un núcleo por solapamiento para esta importación, sin cambiar silenciosamente el contrato TS-6. |
| [time_series_canonical.py](../../../app/time_series_canonical.py), [persistence.py](../../../app/persistence.py) | Usar el contenido canónico, revisiones selladas, hash y proyección transaccional. PostgreSQL usa `ts_next`; SQLite, sufijo `_next`. |
| [object_time_series.py](../../../app/object_time_series.py) | La ingesta actual exige objeto y admite `replace_full`/`append_tail`, canales JSON/CSV/XLSX. No admite el nuevo reemplazo de rango ni importación directa desde catálogo sin objeto. |
| [time_series_classification.py](../../../app/time_series_classification.py) | Semillas actuales: precio, potencia y caudal. Añadir tipos/unidades de energía y volumen si no existen en la instalación; no asumir que MWh o m³ ya están registrados. |
| [schedules.py](../../../app/schedules.py), [run_due_schedules.py](../../../scripts/run_due_schedules.py) | Precedente de cadencia y rango móvil para corridas Julia. Las importaciones requieren otra cola y otro ejecutor; no deben lanzar optimizaciones. |
| [auth.py](../../../app/auth.py) | Reutilizar roles `admin`, `analyst`, `external`; sumar propiedad privada de conexiones y planes. |

Contratos que deben conservarse: [modelo TS-7](../iter7/spec_ts7_catalogo_global_y_series_especificas.md),
[permisos](../../wayfinder/catalogo-global-series-genericas/04-alcance-global-permisos-y-promocion.md),
[integridad](../../wayfinder/catalogo-global-series-genericas/08-rendimiento-indices-e-integridad.md)
y [ingesta contextual](../../wayfinder/catalogo-global-series-genericas/12-api-y-archivos-series-especificas.md).
Esta especificación amplía la ingesta con un canal PostgreSQL y `replace_range`;
no relaja la inmutabilidad, la propiedad por objeto ni el pin de revisiones de los bindings.

Advertencias de implementación comprobadas en el código:

- `publish_canonical_set_revision` publica sets de catálogo y rechaza `object_specific`.
  El camino específico debe conservar su escritor y sus validaciones, compartiendo
  primitivas internas cuando corresponda. No llamar al escritor de catálogo para todos los destinos.
- El escritor de catálogo puede resolver un set por nombre cuando no se pasa `set_id`.
  El importador debe separar creación y actualización explícitas, y rechazar colisiones
  de nombre. Nunca inferir el destino por nombre durante una actualización.
- `time_series_sources.kind` tiene un `CHECK` que no admite `database`.
  Debe ampliarse por migración junto con normalizadores, descriptores y UI.
- El hash canónico actual no incluye `quality_flag` ni la procedencia. La sección 8
  define cómo evitar perder cambios de calidad sin modificar los hashes históricos.
- Los normalizadores/escritores actuales materializan algunas listas grandes.
  No basta con usar un cursor remoto: la publicación también debe procesar lotes.

## 3. Experiencia de usuario

### 3.1 Entradas y panel plegable

Acción «Importar desde base de datos» en catálogo y resumen de series del objeto.
Ambas abren el recorrido protegido, con proyecto, objeto opcional y destino opcional
preseleccionados. Desde catálogo sin proyecto, exigir elegir proyecto propietario.

Dentro del recorrido, una pestaña «Base de datos» contiene el panel plegable
«Conexión PostgreSQL». Al minimizarlo se ocultan los campos, se conservan las
decisiones del formulario y se muestra alias, estado de conexión y botón «Editar».
La contraseña nunca aparece en el resumen. Plegar no desconecta ni cancela un trabajo.

Campos: perfil guardado/nuevo, nombre, host, puerto (5432), base de datos, usuario,
contraseña, «Guardar contraseña cifrada», TLS y certificado de confianza registrado
en servidor cuando sea necesario. Acciones: guardar, probar conexión y cerrar sesión
de credenciales temporales. Mostrar «Contraseña guardada» mediante un booleano,
sin devolver una contraseña enmascarada como si fuera un valor reutilizable.

### 3.2 Pasos del importador

1. **Conexión:** elegir/guardar perfil y probar acceso de lectura.
2. **Origen:** seleccionar esquema y tabla/vista, mapear ID/timestamp/valor,
   elegir IDs con buscador paginado y agregar filtros. «Añadir tabla o vista»
   crea otra selección independiente dentro del mismo plan y conexión.
3. **Correspondencias:** una fila por identidad de origen; destino existente o
   nueva serie, tipo, clase de datos, unidad, semántica temporal y resoluciones.
4. **Rango y actualización:** fechas fijas o ventana móvil; ejecución manual o
   frecuencia automática; margen de disponibilidad y resumen de horarios.
5. **Validar y revisar:** extracción completa en segundo plano, preview transformado,
   estadísticas, intervalos efectivos, impactos y errores por conjunto.
6. **Publicar / activar actualización:** publicación manual explícita o activación
   de la política automática sobre una versión revisada del plan.

Vista de correspondencias, ilustrativa:

| Tabla/vista e ID | Destino | Significado/unidad | Original | Local | Regla |
| --- | --- | --- | --- | --- | --- |
| `medidas`, ID `101` | Demanda A, existente | Potencia media / MW | 15 min | 1 h, heredada | Promedio ponderado |
| `medidas`, ID `205` | Precio B, nueva | Precio de intervalo / USD/MWh | 1 h | 15 min | Mantener valor; estimado |

La resolución original indica «detectada, pendiente de confirmar», «confirmada»
o «declarada». Mostrar también diferencias mínima/máxima observadas y anomalías;
un valor detectado no certifica por sí solo la frecuencia nominal del origen.

«Aplicar a todas» previsualiza cuántas filas admite y cuáles tienen contrato fijo
incompatible. No modifica la resolución de una serie existente. Una selección de
objeto solo ofrece destinos propios o fuentes compartidas asociadas accesibles;
el usuario puede optar por derivar una específica mediante el recorrido existente.

### 3.3 Preview, progreso y recuperación

El preview debe mostrar, por serie: fechas originales y normalizadas de una muestra
cuando esté disponible, valores transformados, ambas resoluciones, método, unidades,
número de registros leídos, puntos generados, cobertura, puntos nuevos/cambiados/sin
cambio y datos que se conservarán fuera del rango. La muestra no sustituye la
validación completa. Nunca permitir publicar solo porque las primeras filas sean válidas.

La muestra original se devuelve transitoriamente, sin guardar puntos originales en
la base local. Al retomar un trabajo se garantiza el preview de su staging transformado;
una nueva muestra remota se etiqueta como lectura posterior, no como parte del snapshot validado.

Mostrar estados y contadores por fase, porcentaje solo cuando exista denominador,
cancelación, última ejecución, próxima ejecución e historial. Cerrar el navegador
no cancela un trabajo durable. Mostrar los commits ya realizados si se cancela un
lote parcialmente publicado. Un error conserva la configuración editable.

Requisitos de accesibilidad: etiquetas visibles, navegación por teclado,
`aria-expanded`/`aria-controls` en el panel, foco en el primer error, anuncio de
progreso con `aria-live` y estados que no dependan solo de color. Persistir únicamente
preferencias no sensibles de plegado; nunca credenciales en URL o almacenamiento del navegador.

## 4. Conexiones, autorización y secretos

La conexión remota la abre el backend/worker, nunca React. El host se interpreta
desde el servidor de la aplicación; aclararlo en la ayuda, especialmente para `localhost`.
Usar una conexión Psycopg independiente del adaptador de la base local.

| Recurso/operación | Regla |
| --- | --- |
| Crear, listar, editar, probar conexión | Usuario interno activo, solo sus propios perfiles. |
| Leer/escribir contraseña | Solo por servicio de secretos autorizado; ninguna API devuelve texto descifrado. |
| Plan y trabajo | Propietario interno; además, permisos vigentes sobre cada destino. |
| Set `project` | Matriz interna existente; no inventar membresías que el proyecto no tiene. |
| Set `global` | Solo `admin` puede publicar, también en automático. |
| Usuario `external` | Sin acceso a conexiones, metadatos remotos, planes, previews ni valores internos. |
| Administrador y conexiones ajenas | Puede desactivar automatizaciones por operación administrativa auditada; no obtiene secretos ni uso implícito del perfil ajeno. |

El plan privado no convierte en privados los datos del catálogo. Su historial de
ejecución es privado; la procedencia visible en la serie contiene solo información
curada. Reevaluar usuario activo, rol, propiedad, alcance y estado del destino al
extraer y al publicar. Desactivar un usuario o archivar un destino suspende las
automatizaciones afectadas; no ejecutarlas con identidad de administrador.

Para credenciales persistentes, añadir `cryptography` y usar AES-256-GCM con nonce
aleatorio de 96 bits único por cifrado y AAD que incluya propietario, conexión y
versión del secreto. Guardar `key_id`, nonce y ciphertext/tag; administrar las claves
fuera del repositorio y de la BBDD que contiene el ciphertext. Permitir rotación y
fallar cerrado si falta la clave. Estos requisitos se basan en la API de
[cifrado autenticado de cryptography](https://cryptography.io/en/stable/hazmat/primitives/aead/).

Modo sesión: secreto cifrado temporal vinculado a la sesión autenticada, con caducidad
no posterior a ella; purgar en logout/caducidad y no incluirlo en copias de historial.
El worker debe poder resolverlo mientras siga vigente. Logout impide nuevas lecturas
con ese secreto; un trabajo que lo necesite pasa a `needs_credentials`.
Modo guardado: reutilizable tras reinicio; obligatorio para activar programación.
Cambiar la contraseña invalida comprobaciones de conexión, pero no el significado
de los datos. Cambiar servidor, base, usuario o política TLS invalida la aprobación del plan.

TLS remoto por defecto `verify-full`, con CA de servidor administrada y validación
de nombre. No degradar automáticamente. Una excepción local de desarrollo debe ser
configurada por el despliegue. Diferencias entre modos documentadas por
[PostgreSQL/libpq](https://www.postgresql.org/docs/current/libpq-ssl.html).

La aplicación solo acepta parámetros de conexión conocidos; no admite DSN libre,
opciones arbitrarias de libpq ni rutas de certificados suministradas como archivos
del servidor. Configurar destinos de red permitidos en el despliegue, incluyendo
explícitamente las redes privadas/locales necesarias; validar resolución DNS/IP al
conectar y mantener verificación TLS. No usar la prueba de conexión como proxy genérico.
El rol PostgreSQL de origen debe disponer solo de `CONNECT`, `USAGE` y `SELECT`
necesarios. Nunca crear vistas, índices ni conceder permisos desde el importador.

Redactar contraseñas/DSN y parámetros sensibles en errores, logs y auditoría. El
servicio convierte errores del driver en códigos propios; no devuelve excepciones
crudas. Rotar o eliminar un perfil no altera revisiones ya publicadas.

## 5. Selección y correspondencia uno a uno

### 5.1 Identidad de origen

Una identidad de origen es la tupla tipada:

```text
(connection_id, connection_endpoint_version, schema, relation,
 id_column, id_type, id_value)
```

No se identifica solo por el número: ID `101` de dos tablas no es la misma serie.
Conservar tipos, mayúsculas y espacios significativos. En JSON, transportar los IDs
como `{ "type": "int8", "value": "101" }`, UUID o texto; así no se pierde precisión
con enteros mayores que el rango seguro de JavaScript. Rechazar ID nulo.
El valor seleccionado es un ID de serie repetido a través del tiempo, no la PK de cada medida.

Mapeo de columnas obligatorio: `series_id`, `timestamp`, `value`. Timestamp debe
ser `timestamp` o `timestamptz`; valor, numérico finito. Textos de fecha, epochs,
valores calculados o IDs compuestos se exponen mediante una vista de origen con
tipos explícitos. La columna de duración no es obligatoria: se deriva de la resolución
confirmada. Las columnas auxiliares solo se leen si las requieren filtros aprobados.

### 5.2 Destino e invariantes

- Cada fila tiene `mapping_id` estable y un destino discriminado:
  `existing_signal`, `new_catalog_signal` o `new_object_signal`.
- Existente: resolver `signal_id`, set, proyecto, propietario, clasificación, revisión
  base, contrato temporal y permisos desde la BBDD. No confiar en copias de React.
- Nueva: exigir nombre/clave, proyecto, tipo semántico, clase, unidad, resolución,
  zona de presentación y significado del valor. Una específica exige objeto real
  y rol compatible. Crear un set de una señal por nueva serie, evitando acoplar
  resoluciones/errores de IDs independientes.
- En un plan, unicidad de identidad de origen y unicidad de destino. Para nuevos
  destinos, usar referencia de creación estable y restricciones de nombre/clave.
  Repetir una ejecución reutiliza los IDs resueltos, nunca vuelve a crear la serie.
- Una misma fuente puede usarse en otro plan/proyecto; la relación uno a uno no es
  una prohibición global de reutilización. Un destino tiene como máximo una
  programación activa de importación: impedir dos automatizaciones competidoras.
- No inferir correspondencias por parecido del nombre. Las sugerencias requieren
  selección visible. No asociar ni cambiar bindings automáticamente al importar.

Un set existente puede tener varias señales con periodos compartidos. Agrupar sus
mapeos en una sola unidad de publicación, conservar las señales no seleccionadas
y exigir cobertura completa de todas sobre la grilla resultante. Si extender el
rango deja sin datos a una señal hermana, bloquear el set y pedir incorporarla al
plan o elegir otra serie. Nunca inventar valores para completar el rectángulo.

## 6. Consultas y filtros

Descubrir esquemas, tablas/vistas y columnas que la cuenta realmente pueda consultar,
incluyendo tipo, nulabilidad y claves disponibles. Las listas y búsqueda de IDs son
paginadas y acotadas, sin descargar todos los IDs al navegador. Un timeout de
exploración muestra un mensaje y conserva la selección, no un conteo ficticio de cero.

Representar filtros como árbol de datos tipado, no fragmentos SQL:

```json
{
  "op": "and",
  "children": [
    {"column": "calidad", "operator": "eq", "value": "validado"},
    {"op": "or", "children": [
      {"column": "zona", "operator": "eq", "value": "norte"},
      {"column": "zona", "operator": "eq", "value": "centro"}
    ]}
  ]
}
```

Operadores iniciales: `eq`, `ne`, `lt`, `lte`, `gt`, `gte`, `in`, `between`,
`is_null`, `is_not_null`, `contains`, `starts_with`; habilitarlos según tipo.
`between` incluye extremos; los rangos temporales de importación usan la convención
de la sección 7. Escapar `%`/`_` en búsqueda textual literal. No convertir `NULL` en
cadena ni usar `= NULL`. Limitar profundidad a 3, hojas a 30 y elementos de `in` a 100.

La condición final siempre es `IDs elegidos AND rango de lectura AND (filtro visual)`.
Un grupo O nunca puede ampliar los IDs/rango. Validar operadores y nombres contra
metadatos recién obtenidos. Identificadores con `psycopg.sql.Identifier`, valores
con parámetros del driver; no interpolar ninguno como SQL del usuario. Véase
[composición SQL de Psycopg](https://www.psycopg.org/psycopg3/docs/api/sql.html).

Lectura ordenada por ID y timestamp en una transacción remota
`REPEATABLE READ READ ONLY`, consistente entre selecciones de la misma conexión.
Utilizar cursor del servidor y lotes, cerrar cursor/conexión al terminar o cancelar.
Un cursor de servidor permite recuperar por partes; `fetchmany()` sobre un cursor
ordinario no garantiza que el resultado no esté ya cargado completo en el cliente.
Referencias: [cursores Psycopg](https://www.psycopg.org/psycopg3/docs/advanced/cursors.html)
y [aislamiento PostgreSQL](https://www.postgresql.org/docs/current/transaction-iso.html).

No mantener esa transacción abierta durante la revisión humana. Extraer, transformar,
validar y cerrar el origen; la confirmación publica el snapshot transformado ya
preparado, sin reconsultarlo. Si cambia el esquema seleccionado, invalidar el plan
afectado y exigir remapeo. La firma del esquema comprende relación y columnas
utilizadas con tipos; una columna irrelevante añadida no debe invalidar el trabajo.

Los filtros pueden producir huecos; en ese caso se aplica la política de calidad.
No interpretar «solo datos validados» como autorización para completar lo que falte.
Un índice remoto `(id_serie, timestamp)` suele ser el candidato a evaluar por el
administrador del origen; medir el plan real y no crearlo automáticamente.

## 7. Contrato temporal y transformación

### 7.1 Normalización

La representación interna es el intervalo semiabierto `[inicio, fin)` en UTC.
La metadata conserva zona de presentación y convención de origen. Para un destino
existente, mantener sus campos de contrato de revisión salvo cambio explícito;
normalizar los instantes a UTC no autoriza a cambiar la zona declarada o los bindings.
Para resolución original `ds`:

```text
period_start: inicio = timestamp;      fin = timestamp + ds
period_end:   inicio = timestamp - ds; fin = timestamp
```

Convertir primero el instante a UTC y sumar/restar duraciones reales. En `timestamptz`
el instante es autoritativo; el nombre de zona sirve para presentación. Para
`timestamp` sin zona, exigir una zona IANA de origen. Rechazar hora inexistente o
ambigua salvo que el origen la exponga desambiguada como `timestamptz`; no aplicar
automáticamente `fold=0` ni desplazarla. Validar por ida y vuelta UTC/zona y ambas
alternativas de fold, no solo asignando `tzinfo`.

Usar `zoneinfo`, declarar `tzdata` para portabilidad, especialmente Windows, y
registrar la versión disponible para reproducibilidad. Python documenta las horas
ambiguas y el suministro de datos horarios en
[zoneinfo](https://docs.python.org/3/library/zoneinfo.html).

Detección por ID: muestra acotada ordenada, diferencias positivas entre timestamps
distintos y candidato modal. Informar distribución y tamaño de muestra. Cero o un
registro no permite detectar; exigir declaración manual. La confirmación guarda
`source_resolution_seconds` en la versión del plan; las ejecuciones siguientes la
verifican, no la vuelven a adivinar. Guardar también un ancla de la grilla original
`source_grid_anchor_utc` obtenida de un inicio de intervalo confirmado. Verificar
su fase en las lecturas siguientes. Si hay múltiplos de la resolución, tratarlos
como posibles huecos, no cambiar la resolución para ocultarlos. Tras extraer el
rango completo, exigir intervalos contiguos, sin solapes, con duración y fase
compatibles. Una declaración manual tampoco puede ignorar anomalías.

Resoluciones de este corte: segundos enteros positivos; presets 1/5/15/30 minutos,
1/24 horas y entrada personalizada en segundos/minutos/horas. No limitar la razón
entre ambas a múltiplos enteros. Admitir timestamps con precisión de microsegundos
y hacer comparaciones temporales mediante enteros, sin tolerancias flotantes.

### 7.2 Grilla y rangos

Por destino guardar `target_resolution_seconds = dt` y `grid_anchor_utc = a`.
La grilla es `[a + k*dt, a + (k+1)*dt)`. Para existente heredar resolución y fase;
si no hay contrato explícito, derivarlas de la revisión regular vigente y confirmarlas.
Un destino irregular no es elegible en este corte. Para nuevo, proponer ancla en
medianoche UTC y mostrar/permitir ajustar un instante de referencia antes de aprobar
el plan. El ancla es fija: no se mueve al cambiar el filtro de fechas.

Rango fijo: interpretar fechas en la zona seleccionada y convertir a `[A, B)` UTC.
Exigir extremos alineados a la grilla destino; mostrar la alternativa alineada para
aceptación, sin redondear silenciosamente. Distintas resoluciones pueden exigir
distintos extremos, que se muestran por fila. Solo incluir periodos ya completos;
el fin fijo debe ser anterior o igual al último límite disponible de cada destino.

Rango móvil de longitud `L` segundos, retraso `lag`, ancla de origen `s` y referencia
inmutable `t`. Primero calcular hasta dónde hay intervalos originales cerrados;
después alinear el fin a la grilla de destino:

```text
fin_original_cerrado = s + floor((t - lag - s) / ds) * ds
fin_efectivo = a + floor((fin_original_cerrado - a) / dt) * dt
inicio_efectivo = fin_efectivo - L
```

Exigir `L > 0` y múltiplo de `dt` para cada destino. En manual `t = requested_at`;
en automático `t = due_at`, nunca el instante variable de un reintento. «Últimos
7 días» equivale aquí a 168 horas, no siete días civiles de duración variable.
Guardar y mostrar el rango efectivo de cada mapeo. Por ejemplo, a las 10:45 con
datos horarios por inicio, ancla 00:00, retraso cero y destino de 15 minutos, el fin
es 10:00: no usar la hora 10:00–11:00 todavía abierta. Si varias señales del mismo
set se actualizan juntas, usar el menor fin cerrado compatible del grupo y mostrar
ese rango común. Una primera extracción sin ancla de origen confirmada no se puede
programar; completar antes la detección/declaración y el preview manual.

Leer todos los intervalos de origen que solapen `[A, B)`, incluidos los que empiecen
antes de A o terminen después de B. Para inicio de periodo, el predicado temporal
equivale a `timestamp < B AND timestamp > A - ds`; para fin de periodo,
`timestamp > A AND timestamp < B + ds`. Adaptar los límites a los tipos/zona sin
perder precisión y confirmar el solapamiento tras normalizar. En timestamps sin
zona alrededor de DST, ampliar de manera conservadora la lectura por límites
locales y filtrar en UTC después; no perder filas por ordenar ingenuamente horas locales.
El límite de filas cuenta también los registros auxiliares de borde.

Un intervalo de origen usado debe haber terminado en o antes de `t - lag`; si todavía
está abierto, ese destino falla con `TS_DB_SOURCE_NOT_READY`, conservando sus datos.
Esto también aplica al subdividir una hora: no importar cuartos de hora estimados
desde una hora aún incompleta. El preview indica el último fin destino realmente
importable para ajustar el retraso o rango.

### 7.3 Significado del valor y fórmulas

El mapeo declara `value_semantics`: `interval_mean` o `interval_total`. Comprobar
su compatibilidad con tipo, unidad y agregación del destino. No deducir solo de la
unidad que un dato instantáneo representa un promedio. Contadores acumulativos
requieren una transformación previa explícita en el origen y quedan fuera del corte.

Sean `S_i` intervalos originales, `T_j` intervalos de destino, `x_i` sus valores y
`w_ij = duración(S_i ∩ T_j)` en segundos:

```text
interval_mean:  y_j = sum(x_i * w_ij) / duración(T_j)
interval_total: y_j = sum(x_i * w_ij / duración(S_i))
```

Exigir cobertura exactamente completa de cada `T_j` por intervalos válidos sin
solapes. Las fórmulas cubren agrupación, subdivisión y razones no enteras; implementarlas
con recorrido ordenado y acumuladores, no con un join de todos los pares.
Subdividir supone valor medio uniforme o distribución uniforme del total dentro
del intervalo original. No es interpolación lineal entre muestras.

| Ejemplo | Resultado obligatorio |
| --- | --- |
| MW cada 15 min: 10, 20, 30, 40 → 1 h | 25 MW. |
| MWh cada 15 min: 1, 2, 3, 4 → 1 h | 10 MWh. |
| Precio 80 USD/MWh de 1 h → 15 min | 80, 80, 80, 80; valores estimados. |
| Energía 12 MWh de 1 h → 15 min | 3, 3, 3, 3 MWh; suma conservada. |
| Medias 10, 20, 30 MW cada 20 min → 30 min | 40/3 y 80/3 MW; promedio ponderado. |
| Totales 2, 4, 6 MWh cada 20 min → 30 min | 4 y 8 MWh; total 12. |
| Misma resolución y fase | Valores originales, sin transformación numérica. |
| Un cuarto de hora ausente al agrupar una hora | Error; no dividir por 45 minutos ni inventar cero. |

Si cualquier intervalo original se divide entre destinos o se recorta para contribuir
a un destino, marcar sus resultados `quality_flag = estimated`; registrar método y
proporciones en la procedencia. Una agregación de periodos completos conserva la
clase de datos y registra que fue agregada. No cambiar una clase `real` a `forecast`
por el solo hecho de provenir de un conector. No asignar `measured` a una estimación.
Si el origen no aporta una flag con significado validado, conservar `null` para
puntos directos/agregaciones completas; no inventar una certificación de calidad.

La unidad origen debe coincidir con la del destino en este corte, tras normalización
de alias conocidos. No convertir MW↔MWh por cambiar resolución, ni introducir
conversiones monetarias. Si se necesitan otras unidades, exponerlas ya convertidas
en una vista o registrar una extensión explícita del conversor.

Añadir semánticas canónicas `interval_energy`/`interval_volume`, dimensiones
`energy`/`volume` y unidades `mwh`/`m3` si faltan, con agregación `sum`.
No concederles roles del optimizador que esperan MW o m³/s: podrán almacenarse en
catálogo, pero su vinculación exige compatibilidad real. Preservar los IDs existentes
y resolver nuevas semillas por clave. Las reglas de precios/potencia/caudal siguen
usando los tipos actuales con agregación `mean`.

Usar aritmética determinista, orden fijo, acumulación estable y validación de
finitud antes/después de transformar. Redondear solo al presentar. Al guardar,
respetar el float64 y el hash canónico existentes. La conservación se verifica
con tolerancia numérica documentada, por ejemplo `max(1e-9, 1e-12 * abs(esperado))`.

## 8. Actualización, revisión y atomicidad

La operación nueva se denomina `replace_range`. Para cada señal seleccionada:

```text
candidato = valores_base_fuera_de_[A,B) + valores_transformados_completos_en_[A,B)
```

No mutar filas de una revisión sellada. La nueva revisión del set incluye todos sus
periodos y señales; las señales no seleccionadas y la cobertura exterior se copian
sin cambios. Validar la continuidad y densidad del candidato completo. Si el nuevo
rango deja una brecha respecto de la cobertura existente, bloquear y solicitar un
rango que también cubra la brecha. Un origen sin filas o con un punto histórico
desaparecido es un error de cobertura; nunca una orden de borrar datos locales.

`replace_range` actualiza la zona consultada aunque antes hubiera una edición manual
en ella; el preview manual debe contar esos cambios. La activación de la programación
autoriza ese comportamiento en sus rangos futuros. No comparar con «última fecha
importada» para omitir correcciones históricas dentro de la ventana.

Unidad de atomicidad: un set destino. Un job puede terminar `partially_succeeded`
porque publicó sets independientes y bloqueó otros. No publicar nada de un set
incompleto. La extracción total y las cuotas globales deben resolverse antes de
empezar a publicar cualquier set; los errores de conexión/snapshot o exceso global
invalidan toda esa extracción. Tras validación, fallos locales de un set no revierten
commits de otros sets.

Transacción local por set:

1. Comprobar lease vigente, permiso actual, versión aprobada del plan, token,
   clasificación, alcance, definición/ETag y revisión base esperada.
2. Bloquear el set y detectar otra revisión publicada desde la preparación.
3. Crear identidad y definición, si era nueva, dentro de la misma unidad transaccional;
   guardar el destino resuelto del mapeo para que un reintento no cree otra identidad.
4. Registrar fuente `database`, construir revisión completa por lotes y verificar
   contrato, conteos, hash canónico y hash semántico de publicación.
5. Sellar, actualizar `current_revision_id`, proyección de catálogo cuando aplique,
   auditoría, resultado de idempotencia y recibo del grupo en la misma transacción.
6. Commit. Ante fallo, rollback completo del grupo; ninguna revisión parcial es utilizable.

La comparación de base debe implementarse dentro de la transacción del escritor;
un chequeo previo en la ruta no basta. Extender los servicios de publicación con
`expected_base_revision_id`/hash. Un conflicto no permite sobrescribir la revisión
nueva con una mezcla preparada sobre datos viejos: manual exige nuevo preview;
automático puede recomponer desde la nueva base hasta dos veces si los contratos
y el alcance aprobado siguen iguales. Después queda `conflict` y espera otra ejecución.

Un lote repetido con contenido y semántica iguales termina `unchanged`: no incrementa
revisión ni vuelve obsoletos bindings, pero sí registra ejecución y checksum remoto.
No usar hora de extracción, ID de job o ventana móvil como parte de esta igualdad.

**Extensión necesaria de deduplicación:** mantener `content_hash` canónico sin
recalcular historia, y añadir `publication_semantics_hash` para el canal database.
Este segundo digest recorre las flags efectivas de todos los puntos del candidato
y los contratos semánticos de procedencia por señal (identidad origen, significado,
resoluciones y versión de algoritmo). Conserva la procedencia de los tramos copiados;
excluye horarios de ejecución, contraseña, frecuencia del scheduler y fragmentación
incidental de rangos. Solo declarar `unchanged` si ambos hashes coinciden.
Su serialización canónica se ordena por señal/periodo y usa referencias al contrato
de procedencia de cada punto; dos segmentaciones del mismo contrato producen el
mismo digest. Incluir zona/convención/ancla de origen en ese contrato, sin IDs de job.
Una variación solo de calidad/procedencia crea una revisión con igual hash numérico.
Los escritores legacy conservan su política anterior salvo extensión explícita;
una revisión antigua sin este digest se compara reconstruyendo el contrato conocido,
o genera una primera revisión importada, nunca se modifica retroactivamente.

Los bindings y snapshots de corridas conservan sus IDs de revisión y hashes exactos.
La importación no selecciona la nueva revisión en variantes ni ejecuta el optimizador.
Las reglas existentes detectan revisión disponible/obsolescencia para que el usuario
elija el cambio posteriormente.

## 9. Ejecución automática

La definición de importación se guarda aunque esté en modo manual. La programación
admite `interval` (cada N minutos/horas), `daily` y `weekly` (hora y días), con zona
IANA. Mostrar siguientes tres ejecuciones y última ejecución. Valor mínimo inicial
de intervalo: 60 segundos, configurable por despliegue; una frecuencia menor que
la resolución de datos es válida, pero puede devolver `unchanged`.

Separar frecuencia, ventana móvil, resolución destino y retraso: son cuatro cosas
distintas. No deducir una de otra. Para diario/semanal, ante una hora inexistente
por DST disparar al primer instante válido posterior; ante una repetida, disparar
solo la primera ocurrencia. Registrar el ajuste y mostrarlo en la simulación de
próximas ejecuciones. Esta política de agenda no cambia el rechazo de timestamps
ambiguos en los datos.

Activar requiere conexión con secreto persistente, destinos resueltos, preview
válido de la versión exacta del plan y confirmación del impacto sobre fuentes
compartidas. La primera carga se publica manualmente; después se activa la política
automática. Cada tick valida por completo antes de publicar sin confirmación humana
adicional. Una edición de filtros, mapeos, rango, resolución, algoritmo, conexión
de origen o frecuencia pausa la aprobación anterior y requiere revisar/activar la
nueva versión. Rotar el secreto no cambia la versión funcional.

El worker actúa como el propietario de la programación, con permisos actuales.
La aprobación almacena las identidades, contratos, alcance y consumidores
compartidos revisados. Si un cambio de alcance o nuevos consumidores amplía el
impacto aprobado, pasar a `needs_review`; no simular una confirmación interactiva
con `confirm=true` en una ruta antigua. La autorización permanente de la programación
es un recurso explícito, revocable y auditado, no un token de preview de larga duración.

Scheduler durable:

- Guardar `next_run_at` UTC y reclamar ticks mediante transacción y restricción
  única `(schedule_id, schedule_version, due_at)`.
- Una ejecución activa por plan, tanto manual como automática. Si vence otra fecha,
  acumular como máximo un tick pendiente y señalar ejecuciones agrupadas.
- Tras reinicio, ejecutar una vez el vencimiento más reciente; registrar los
  omitidos, sin generar una tormenta de trabajos atrasados. El rango usa ese `due_at`.
- Si el tiempo sin éxito supera la ventana móvil y se produciría una brecha,
  bloquear los grupos afectados con `TS_DB_BACKFILL_REQUIRED`. Ofrecer una carga
  manual del hueco y luego reactivar; no ampliar silenciosamente la ventana.
- Reintentar errores transitorios hasta 3 intentos con espera 30/120 segundos y
  jitter. Mantener rangos efectivos e idempotencia. No reintentar automáticamente
  credenciales inválidas, esquema cambiado, calidad o permisos.
- Usar lease con heartbeat y fencing token; un proceso que perdió su lease no
  puede publicar aunque siga trabajando. Recuperar trabajos abandonados y consultar
  recibos comprometidos antes de decidir qué repetir.
- Tras caída durante extracción, descartar staging incompleto y reiniciar la
  lectura completa en otro snapshot. Tras extracción completa, reutilizar staging
  validado; nunca mezclar lotes de snapshots remotos distintos.

La programación funciona con el proceso worker/scheduler en ejecución y acceso
a ambas bases. Cerrar el navegador no afecta; apagar el servidor sí. Proporcionar
un comando supervisable para procesamiento continuo y una variante `--once` para
pruebas/operación. No depender de timers React, tareas en memoria de FastAPI ni de
que alguien invoque manualmente `/run-due`. No reutilizar la cola Julia del optimizador.

## 10. Arquitectura propuesta

```mermaid
flowchart LR
    UI[React: conexión y correspondencias] --> API[FastAPI: planes y trabajos]
    API --> Q[Cola durable local]
    SCH[Scheduler de importaciones] --> Q
    Q --> W[Worker con lease]
    W --> PG[PostgreSQL origen: lectura]
    PG --> N[Normalizar y validar]
    N --> R[Transformar resolución]
    R --> ST[Staging local transformado]
    ST --> V[Revisión completa candidata]
    V --> P[Publicación atómica por set]
    P --> C[Catálogo o serie de objeto]
    API --> ST
```

Módulos nuevos propuestos; nombres orientativos, responsabilidades obligatorias:

| Archivo | Responsabilidad |
| --- | --- |
| `app/database_imports/contracts.py` | Modelos tipados, códigos de error, límites y normalización de planes. |
| `app/database_imports/postgres.py` | Introspección, compilación de filtros y lectura remota por lotes. |
| `app/database_imports/secrets.py` | Secretos de sesión/persistentes, cifrado, rotación y redacción. |
| `app/database_imports/resampling.py` | Núcleo puro de intervalos y solapamiento; sin BBDD ni red. |
| `app/database_imports/service.py` | Preparación, snapshot, agrupación por set, merge y autorización. |
| `app/database_imports/repository.py` | Planes, versiones, jobs, staging, claims y recibos. |
| `app/database_imports/worker.py` | Extracción/transformación/publicación durable y recuperación. |
| `app/database_imports/scheduler.py` | Calendarios, ticks, aprobaciones y planificación de jobs. |
| `scripts/run_database_import_worker.py` | Entrada de proceso y modo `--once`. |
| `frontend/src/DatabaseSeriesImport.tsx` | Flujo compartido de importación. |
| `frontend/src/DatabaseConnectionPanel.tsx` | Panel plegable y perfiles privados. |
| `frontend/src/DatabaseImportMapping.tsx` | Matcheo y validación por fila. |
| `frontend/src/DatabaseImportHistory.tsx` | Estado, progreso, errores y programación. |

No ampliar indefinidamente `main.py`/`persistence.py`: registrar rutas/servicios
nuevos allí donde corresponda y extraer primitivas de publicación compartidas con
sus garantías actuales. La UI usa el mismo importador en ambos contextos.
La base local PostgreSQL es referencia de capacidad y concurrencia. SQLite mantiene
la semántica para pruebas/uso pequeño, con un solo escritor y límites anunciados.

## 11. Persistencia y migraciones

### 11.1 Recursos nuevos

Usar tablas operativas de aplicación separadas de los puntos canónicos. En la tabla
siguiente, `canonical.*` representa los nombres resueltos por los helpers existentes
(`ts_next.*` o `*_next`), no un esquema nuevo llamado `canonical`.
JSON se serializa de forma determinista; IDs internos conservan FKs reales.

| Tabla propuesta | Campos/relaciones mínimos |
| --- | --- |
| `database_connections` | `id`, `owner_user_id -> users`, nombre, host, puerto, base, usuario remoto, modo TLS, referencia CA administrada, `endpoint_version`, `resource_version`, estado, timestamps. Sin contraseña. |
| `database_connection_secrets` | FK conexión/propietario, modo sesión/persistente, FK sesión opcional, `key_id`, `secret_version`, nonce, ciphertext, expiración, fecha de rotación. Acceso restringido al servicio de secretos. |
| `database_import_plans` | ID, propietario, proyecto de contexto, nombre, FK conexión, versión vigente, estado, timestamps. |
| `database_import_plan_versions` | PK `(plan_id, version)`, configuración inmutable, `config_hash`, firma de esquema, versión del algoritmo, endpoint version, autor y fecha. No contiene secretos. |
| `database_import_mappings` | PK `(plan_id, version, mapping_id)`, identidad origen tipada, selección de origen, destino discriminado, FK señal existente opcional, definición nueva opcional, resoluciones, ancla y contrato semántico. |
| `database_import_target_resolutions` | PK `(plan_id, mapping_id)`, FK señal/set creados, referencia de creación y fecha. Se escribe en la transacción que crea la serie. No remapear por nombre. |
| `database_import_schedules` | FK plan, versión agenda, cadencia, zona IANA, siguiente fecha UTC, estado, aprobador, versión/hash de plan aprobados, fingerprint de impacto, referencia de validación. |
| `database_import_schedule_targets` | FK programación y señal, índice único de reserva activa por `signal_id`. Impide dos programaciones activas sobre el mismo destino, incluso con planes de usuarios distintos. |
| `database_import_ticks` | Programación, versión, `due_at`, estado, FK job, fechas omitidas/agrupadas. Unicidad `(schedule_id, schedule_version, due_at)`. |
| `database_import_jobs` | UUID público, plan/version, propietario, tick opcional, modo manual/automático, ventana congelada, estado, intento, lease/fencing, heartbeat, contadores, expiración, cancelación, idempotencia y error curado. |
| `database_import_job_groups` | Job y clave de grupo, FK set si existe o referencia de creación, revisión/hash base, contratos esperados, rango por mapeo, estado, hashes candidatos, token de validación, resultado y revisión publicada. |
| `database_import_stage_periods` | Grupo, `period_index`, inicio/fin UTC y duración. Solo periodos transformados/candidatos; únicos por grupo e inicio. |
| `database_import_stage_values` | Grupo, señal o referencia nueva, índice de periodo, float64, quality flag y procedencia de transformación. PK impide celdas duplicadas. |
| `database_import_events` | Evento append-only con plan/job/grupo, actor, estado, códigos y detalle curado. Nunca secretos ni valores completos. |

Todas las referencias de job/mapping/version deben comprobarse con FKs compuestas
o equivalentes, para impedir combinar IDs válidos de planes distintos. La relación
conexión/plan exige igual propietario. Un destino se resuelve siempre en el contexto
autorizado, pero su fuente y revisión se registran bajo el proyecto propietario real
del set; un objeto consumidor de otro proyecto no cambia esa propiedad.

Aplicar unicidad de fuente y destino en las versiones del plan. Una revisión de plan
no cambia el destino ya resuelto de un `mapping_id`: para redirigirlo se crea otro
mapeo y se revisa el impacto. Mantener las versiones antiguas usadas por jobs.

Índices mínimos: conexiones por propietario/estado; planes por propietario/proyecto;
agendas por estado/`next_run_at`; jobs por estado/disponibilidad y por plan/fecha;
jobs activos con unicidad parcial por plan; grupos por job/estado; staging por
grupo/señal/periodo; ticks por unicidad anterior. El claim de PostgreSQL puede usar
`FOR UPDATE SKIP LOCKED`; SQLite usa transacción de escritor único.

### 11.2 Fuente, calidad y trazabilidad

Ampliar `time_series_sources.kind` con `database` y la expectativa de fuente del
objeto con el mismo valor. Registrar la fuente solo junto con una publicación
válida. La metadata de una revisión publicada incluye un bloque versionado:

```json
{
  "database_import": {
    "schema_version": 1,
    "plan_id": 41,
    "plan_version": 3,
    "job_id": "6b1e4a82-7350-4f4a-821a-9a0f0834549b",
    "source_snapshot_checksum": "sha256:...",
    "extracted_at": "2026-09-21T15:10:00Z",
    "mapping_ids": ["m_101"],
    "source_resolution_seconds": 900,
    "target_resolution_seconds": 3600,
    "source_timestamp_convention": "period_end",
    "source_timezone": "America/Santiago",
    "value_semantics": "interval_mean",
    "algorithm": "interval_overlap_v1",
    "effective_range": {"start": "2026-09-14T15:00:00Z", "end": "2026-09-21T15:00:00Z"},
    "publication_semantics_hash": "sha256:..."
  }
}
```

El ejemplo es de una sola señal; en un set multiseñal, usar una lista por mapeo y
conservar las referencias de procedencia por tramo de la revisión base. La metadata
común no puede afirmar que toda la historia proviene de la última consulta.
El manifiesto privado conserva relación, columnas, IDs, filtros, firma de esquema,
endpoint version y configuración completa. La proyección del catálogo expone alias
curado, método, resoluciones y fechas, sin host, usuario remoto o parámetros privados.

Calcular checksum remoto incremental sobre registros tipados ordenados, sin
persistirlos como serie original. No inventar una revisión canónica de origen para
rellenar `time_series_revision_lineage`: sus FKs apuntan a revisiones locales reales.
La procedencia externa va en source/metadata/manifiesto. Los puntos de staging y del
catálogo ya están transformados; los únicos buffers originales son transitorios.

### 11.3 Retención y compatibilidad

Staging no publicado expira a las 24 horas, configurable. Purgar staging tras
publicación/cancelación y conservar recibos, estadísticas y manifiestos necesarios
para explicar una revisión. No caducar historia canónica ni borrar revisiones para
controlar tamaño. La eliminación de un plan es archivado: pausa agenda, revoca
reservas y conserva referencias históricas. Eliminar un perfil destruye sus secretos
y desactiva planes dependientes, manteniendo un identificador histórico sin secreto.

Extender la purga de proyecto TS7-024: pausar y cercar sus jobs antes de limpiar
dependencias; eliminar staging/planes/recibos en orden de FK junto con la purga
autorizada. Una conexión privada reutilizada por otros proyectos no se borra por
esa purga. Las conexiones a la misma base local no deben generar autoconsumo de
tablas internas de importación; excluir los esquemas/tablas operativos propios de
la selección cuando el origen sea esa misma base.

Migraciones aditivas e idempotentes para ambos motores. En SQLite, cualquier
reconstrucción de tabla necesaria para ampliar `CHECK` debe preservar FKs, triggers
de revisiones selladas, índices y hashes. Probar sobre una base previa con datos.
No revivir escritores legacy ni modificar los archivos de migraciones históricas
para aparentar que el canal ya estaba soportado.

## 12. Contrato HTTP propuesto

Las rutas de esta sección son nuevas, no endpoints existentes. Todas requieren
sesión interna, autorización por recurso y protección de mutaciones consistente
con la aplicación. Respuestas de conexiones, planes, jobs y previews:
`Cache-Control: no-store`. Los recursos ajenos privados se tratan como no encontrados.

### 12.1 Conexiones y descubrimiento

| Método y ruta | Función |
| --- | --- |
| `GET /api/database-connections` | Perfiles propios, paginados, sin secreto. |
| `POST /api/database-connections` | Crear perfil. Contraseña opcional de entrada, nunca de salida. |
| `GET /api/database-connections/{id}` | Detalle propio y booleano `has_saved_secret`. |
| `PATCH /api/database-connections/{id}` | Editar con `If-Match`; incrementar versiones pertinentes. |
| `DELETE /api/database-connections/{id}` | Desactivar, borrar secreto y suspender planes; conservar recibo histórico. |
| `PUT /api/database-connections/{id}/credentials` | Establecer/rotar secreto de sesión o persistente. |
| `DELETE /api/database-connections/{id}/credentials` | Revocar secreto y pausar agenda si corresponde. |
| `POST /api/database-connections/{id}/tests` | Probar autenticación/TLS/lectura, con timeout corto. |
| `GET /api/database-connections/{id}/schemas` | Esquemas accesibles. |
| `GET /api/database-connections/{id}/relations?schema=...` | Tablas/vistas accesibles, paginadas. |
| `POST /api/database-connections/{id}/relation-descriptions` | Columnas, tipos y firma de relación seleccionada. |
| `POST /api/database-connections/{id}/series-searches` | Búsqueda/paginación de IDs con filtros tipados. |
| `POST /api/database-connections/{id}/resolution-detections` | Muestra por ID, candidato y diagnóstico; no escribe series. |

Metadatos: páginas de 50, máximo 200; cursor opaco vinculado a propietario,
conexión/version y filtro. No incluir contraseña en parámetros de consultas HTTP.
Si la relación es inaccesible, no revelar sus columnas mediante mensajes de error.

### 12.2 Planes, trabajos y programación

| Método y ruta | Función |
| --- | --- |
| `GET/POST /api/projects/{project_id}/database-import-plans` | Listar propios/crear definición reusable. |
| `GET /api/database-import-plans/{id}` | Configuración, versión y destinos resueltos. |
| `PUT /api/database-import-plans/{id}` | Nueva versión inmutable con `If-Match`; pausa aprobación anterior. |
| `POST /api/database-import-plans/{id}/archive` | Archivar y detener programación. |
| `POST /api/database-import-plans/{id}/jobs` | Preparar extracción/validación; `202 Accepted`, nunca millones de puntos en la respuesta. |
| `GET /api/database-import-plans/{id}/jobs` | Historial paginado y agregado. |
| `GET /api/database-import-jobs/{job_id}` | Estado, fases, contadores y resultado por grupo. |
| `GET /api/database-import-jobs/{job_id}/preview?group_id=...` | Muestra transformada acotada e impacto, con token de snapshot. |
| `GET /api/database-import-jobs/{job_id}/errors?cursor=...` | Errores curados con conteo total y muestra paginada. |
| `POST /api/database-import-jobs/{job_id}/publications` | Publicar los grupos válidos seleccionados y revisados, `202`. |
| `POST /api/database-import-jobs/{job_id}/cancellations` | Cancelación cooperativa; devuelve grupos ya comprometidos. |
| `GET/PUT /api/database-import-plans/{id}/schedule` | Consultar/proponer agenda, inicialmente desactivada, con ETag. |
| `POST /api/database-import-plans/{id}/schedule/prevalidations` | Revisar plan, agenda, última carga válida, destinos, credenciales e impacto. |
| `POST /api/database-import-plans/{id}/schedule/activations` | Activar con token fresco, ETag, confirmación e idempotencia. |
| `POST /api/database-import-plans/{id}/schedule/pauses` | Pausar futuras ejecuciones; permitir cancelar la actual por separado. |

Crear trabajos, publicar y activar usan `Idempotency-Key`. Una misma clave/actor/
operación con otro payload devuelve 409. Guardar el recibo junto al commit;
repetir después de perder la respuesta devuelve el resultado original. Retener
claves de publicaciones referenciadas por revisiones mientras exista esa historia.
Los tokens incluyen versión de plan, snapshot, grupos, base, contratos e impacto;
no autorizan otros destinos y caducan con el staging. El ETag de validación no cambia
solo por un heartbeat o lectura de progreso.

### 12.3 Ejemplos mínimos

Crear plan con un origen y una correspondencia; todos los IDs son ilustrativos:

```http
POST /api/projects/7/database-import-plans
Content-Type: application/json
Idempotency-Key: crear-plan-ejemplo-01
```

```json
{
  "name": "Demanda PostgreSQL",
  "connection_id": 12,
  "selections": [{
    "selection_id": "s_medidas",
    "schema": "public",
    "relation": "medidas",
    "columns": {"series_id": "id_serie", "timestamp": "fecha_hora", "value": "valor"},
    "source_timezone": "America/Santiago",
    "timestamp_convention": "period_end",
    "filters": {"op": "and", "children": [
      {"column": "calidad", "operator": "eq", "value": "validado"}
    ]}
  }],
  "mappings": [{
    "mapping_id": "m_101",
    "selection_id": "s_medidas",
    "source_id": {"type": "int8", "value": "101"},
    "source_unit_key": "mw",
    "value_semantics": "interval_mean",
    "source_resolution": {"seconds": 900, "basis": "detected_confirmed"},
    "source_grid_anchor_utc": "1970-01-01T00:00:00Z",
    "target": {"kind": "existing_signal", "signal_id": 321},
    "target_resolution_seconds": 3600,
    "grid_anchor_utc": "1970-01-01T00:00:00Z"
  }],
  "window": {"mode": "rolling", "duration_seconds": 604800, "availability_lag_seconds": 600},
  "update_mode": "replace_range"
}
```

Para un destino existente, el backend contrasta resolución/ancla con su contrato;
no los toma como una orden de modificarlo. Devuelve `201`, `plan_id`, `version`,
ETag, clasificación resuelta y capacidades. Para crear, la unión `target` sería:

```json
{
  "kind": "new_object_signal",
  "linkable_object_id": 88,
  "series_key": "demanda_pg_101",
  "display_name": "Demanda de origen 101",
  "semantic_type_key": "load_demand",
  "data_class_key": "real",
  "unit_key": "mw",
  "binding_role_key": "load_demand",
  "display_timezone": "America/Santiago"
}
```

`load_demand` existe en el catálogo actual; el ejemplo presupone un objeto compatible.
La UI ofrece únicamente roles compatibles y el backend vuelve a comprobarlos.
`new_catalog_signal` omite objeto/rol, crea alcance `project` y permite promoción
posterior por el mecanismo administrativo existente.

Preparar trabajo manual:

```http
POST /api/database-import-plans/41/jobs
If-Match: "db-plan-41-v3"
Idempotency-Key: validar-ejemplo-01
Content-Type: application/json
```

```json
{"plan_version": 3, "mode": "manual"}
```

```json
{
  "job_id": "6b1e4a82-7350-4f4a-821a-9a0f0834549b",
  "state": "queued",
  "status_url": "/api/database-import-jobs/6b1e4a82-7350-4f4a-821a-9a0f0834549b",
  "poll_after_seconds": 2
}
```

Tras preparar: `ready_to_publish`, resumen por grupo, `validation_token`,
`validation_etag`, rango resuelto, hashes, errores e impacto. La publicación envía:

```json
{
  "validation_token": "token-opaco-del-snapshot",
  "group_ids": ["set:98"],
  "confirm": true
}
```

Usar `If-Match` del preview e `Idempotency-Key` nueva para esta operación. Si hay
grupos inválidos, mostrar claramente que solo se publicarán los válidos seleccionados.
Respuesta final por grupo: `published`, `unchanged`, `blocked`, `conflict` o `cancelled`,
con revisión previa/nueva, conteos y código de error cuando corresponda.

Agenda de ejemplo, propuesta tras primera carga:

```json
{
  "mode": "interval",
  "interval_seconds": 3600,
  "timezone": "America/Santiago",
  "starts_at": "2026-09-21T16:10:00Z"
}
```

Para `daily`: `local_time` y zona; para `weekly`: lo anterior y `weekdays` ISO 1–7.
El servidor responde agenda desactivada, ETag y siguientes fechas. Prevalidar y
activar son operaciones distintas del guardado de esta propuesta.

## 13. Estados y errores

Flujo principal del job:

```text
queued -> extracting -> transforming -> validating -> ready_to_publish
                                                    -> publishing -> succeeded
                                                                  -> partially_succeeded
```

Extracción y transformación pueden solaparse: las fases públicas reflejan progreso,
no obligan a materializar todas las filas originales antes de transformar. En automático,
un job validado avanza a publicación bajo la aprobación activa. Estados adicionales:
`retry_wait`, `needs_credentials`, `needs_review`, `conflict`, `failed`, `cancelling`,
`cancelled`, `expired`. `ready_to_publish` puede contener grupos bloqueados siempre
que exista al menos uno válido; si todos fallan, el job termina `failed`.

Contrato común de error:

```json
{
  "code": "TS_DB_DUPLICATE_TIMESTAMP",
  "message": "Hay dos registros del mismo ID para el mismo instante.",
  "request_id": "req-ejemplo",
  "retryable": false,
  "context": {
    "job_id": "6b1e4a82-7350-4f4a-821a-9a0f0834549b",
    "mapping_id": "m_101",
    "group_id": "set:98",
    "column": "fecha_hora",
    "source_id": {"type": "int8", "value": "101"},
    "timestamp_utc": "2026-09-20T15:00:00Z",
    "duplicate_count": 2
  }
}
```

En BBDD no existe número de fila estable como en CSV. Informar ID, instante y clave
de origen si existe; un ordinal de lectura se etiqueta como diagnóstico de ese
snapshot. Detectar duplicados antes de insertar staging con claves únicas, incluso
cuando sus valores coincidan; no resolverlos con «última fila gana» ni `DISTINCT`.

| Código | Tratamiento |
| --- | --- |
| `TS_DB_FORBIDDEN`, `TS_DB_RESOURCE_NOT_FOUND` | 403/404 sin filtrar recursos privados; reevaluar permisos. |
| `TS_DB_CONNECTION_FAILED`, `TS_DB_TIMEOUT` | Red/timeout; reintento acotado si es transitorio. |
| `TS_DB_AUTH_FAILED`, `TS_DB_CREDENTIALS_REQUIRED` | Pedir corregir credenciales; suspender agenda dependiente. |
| `TS_DB_TLS_FAILED`, `TS_DB_HOST_NOT_ALLOWED` | Error de conexión/configuración; no degradar validación. |
| `TS_DB_SCHEMA_CHANGED` | Remapear/reaprobar. |
| `TS_DB_MAPPING_NOT_ONE_TO_ONE` | Rechazar plan por identidad duplicada o destino repetido. |
| `TS_DB_FILTER_INVALID`, `TS_DB_COLUMN_TYPE_INVALID` | Corregir columna, tipo u operador. |
| `TS_DB_UNIT_MISMATCH`, `TS_DB_SEMANTICS_UNSUPPORTED` | No convertir ni cambiar significado automáticamente. |
| `TS_DB_RESOLUTION_UNDETERMINED`, `TS_DB_RESOLUTION_MISMATCH` | Declarar o corregir resolución; nunca forzar datos inconsistentes. |
| `TS_DB_TIMESTAMP_AMBIGUOUS`, `TS_DB_TIMESTAMP_NONEXISTENT` | Corregir representación de origen. |
| `TS_DB_DUPLICATE_TIMESTAMP`, `TS_DB_NULL_VALUE`, `TS_DB_NONFINITE_VALUE` | Bloquear grupo y conservar vigente. |
| `TS_DB_GAP`, `TS_DB_IRREGULAR_SOURCE`, `TS_DB_INCOMPLETE_COVERAGE` | Bloquear grupo; sin rellenado/descarte. |
| `TS_DB_RANGE_UNALIGNED`, `TS_DB_SOURCE_NOT_READY` | Ajustar rango, ancla o margen de disponibilidad. |
| `TS_DB_EMPTY_SOURCE` | No borrar ni crear revisión vacía. |
| `TS_DB_SET_INCOMPLETE` | Completar señales hermanas para la grilla resultante. |
| `TS_DB_BASE_CHANGED`, `TS_DB_PREVIEW_EXPIRED` | Nuevo preview/recomposición según modo; 409 para conflicto. |
| `TS_DB_AUTOMATION_TARGET_BUSY`, `TS_DB_PLAN_BUSY` | Otra programación reservó destino o existe ejecución activa; 409. |
| `TS_DB_BACKFILL_REQUIRED`, `TS_DB_APPROVAL_STALE` | Pausar grupo/agenda y pedir intervención contextual. |
| `TS_DB_LIMIT_EXCEEDED` | No truncar; dividir rango/lote o ajustar límites administrativamente. |
| `TS_DB_IDEMPOTENCY_CONFLICT` | 409 por reutilización de clave con otro contenido. |

Errores de payload usan 422, cuotas operativas 429 cuando proceda; los fallos de
datos de un trabajo asincrónico se reflejan en su estado, no como un `GET` HTTP 500.
Conservar también los códigos TS-7 de compatibilidad y concurrencia cuando sean
la causa autoritativa, traducidos a mensajes comprensibles en la UI.

## 14. Límites, procesamiento y observabilidad

«Punto» significa una celda numérica de una señal en un intervalo, no una fila que
pueda contener cien señales. Verificar límites por separado en lectura original,
salida transformada y revisión completa candidata, incluyendo señales/tramos
conservados. Una subdivisión puede superar la cuota aunque el origen sea pequeño.

| Parámetro inicial | Valor / condición |
| --- | --- |
| Mapeos por ejecución | 100. |
| Puntos originales leídos | 5.000.000, incluyendo bordes auxiliares. |
| Puntos transformados y candidatos completos | 5.000.000 en cada presupuesto, sumados entre grupos. |
| Periodos por set | 1.000.000 inicialmente, consistente con la ingesta grande existente. |
| Tamaño de lote remoto/local | 10.000 filas/celdas, ajustable por benchmark. |
| Muestra de resolución | Hasta 1.000 registros por ID; confirmar/validar todo después. |
| Preview transformado | 200 filas por grupo/página; nunca devolver serie completa por defecto. |
| Diagnóstico visible | Primeros 200 detalles por grupo y conteos totales por código. |
| Trabajos activos | 1 por plan, 3 por usuario; tope de workers por despliegue. |
| Conexión / exploración | 10 s / 30 s por operación. |
| Extracción | Límite de pared 15 min, configurable; timeout SQL acotado por operación. |
| Lease / heartbeat | 90 s / 20 s; renovar sin sostener locks de negocio. |
| Vida de staging sin publicar | 24 h. |
| Objetivo de respuesta de encolado/estado | p95 menor de 1 s en el entorno de referencia, sin extracción remota. |
| Objetivo memoria de worker | Consumo incremental menor de 256 MiB sobre baseline para la fixture, a verificar. |

Estos defaults se anuncian mediante capacidades del backend, no se duplican como
constantes independientes en React. La primera entrega debe superar una fixture
PostgreSQL de 100 series × 50.000 puntos; una segunda fixture comprueba expansión
de resolución, y otra revisiones con historia conservada. Documentar CPU, RAM, I/O,
red, tamaño de la base y tiempos por fase. No prometer latencia total independiente
del origen. SQLite valida corrección con fixture menor y anuncia límites propios.

Evitar `fetchall()`, listas de millones de diccionarios, JSON con todos los puntos,
joins cartesianos de intervalos y grandes `OFFSET`. Validar por streaming, insertar
staging/bulk por lotes y calcular hashes incrementalmente. Para publicar, leer staging
y base en orden y escribir por lotes sin exponer revisiones `building`.
Los normalizadores actuales que exigen listas deben adquirir una variante iterable
o un camino desde staging con las mismas validaciones, no un bypass de integridad.

Cancelar la consulta remota mediante el driver y cerrar la transacción. El chequeo
de cancelación/lease ocurre entre lotes y antes de cada commit. Si un commit ya
terminó, devolverlo en el recibo; no revertir historia publicada. En PostgreSQL,
separar conexión de heartbeat/claims y conexión de transacción de publicación para
no perder leases durante una escritura larga.

Métricas: jobs por estado, retraso del scheduler, filas/puntos procesados,
duración por fase, memoria, bytes de staging, errores por código, reintentos,
conflictos, revisiones publicadas y `unchanged`. Logs correlacionados por request,
job, plan/version y grupo, sin valores completos, credenciales ni SQL con valores
interpolados. El usuario consulta fallos y próxima ejecución en la interfaz;
notificaciones por correo/servicios externos quedan fuera de este alcance.

## 15. Criterios de aceptación y pruebas

La implementación debe automatizar pruebas del comportamiento, además de validar
el flujo visible. En esta etapa documental no se ejecutan ni se declaran aprobadas
pruebas de una funcionalidad aún inexistente.

| ID | Caso | Resultado verificable |
| --- | --- | --- |
| DBI-01 | Abrir importador desde catálogo y objeto | Mismo flujo, contexto/retorno correctos y distinción compartida/específica. |
| DBI-02 | Plegar/reabrir conexión | Conserva selección, accesible por teclado, sin mostrar secreto. |
| DBI-03 | Guardar perfil, reiniciar y luego cerrar sesión | Perfil y secreto persistente reutilizables; secreto de sesión inutilizable tras logout/caducidad. |
| DBI-04 | Otro usuario o `external` consulta IDs privados | Denegación sin metadata remota ni credenciales. |
| DBI-05 | Tabla/vista larga con varios IDs | Una fila de mapeo por ID tipado; dos tablas con mismo ID no se confunden. |
| DBI-06 | Entero ID mayor que 2^53 y UUID/texto | Ida y vuelta exacta sin coerción de JavaScript. |
| DBI-07 | Dos orígenes al mismo destino o un origen repetido | Rechazo por uno a uno antes de extracción masiva. |
| DBI-08 | Serie existente/nueva y reintento de creación | Existente se resuelve por ID; nueva se crea una sola vez, sin set huérfano tras rollback. |
| DBI-09 | Filtros anidados Y/O, nulos y nombres con comillas | Resultados correctos, parámetros seguros; O no amplía IDs/rango. |
| DBI-10 | Cambio de esquema o columna inaccesible | Detención y remapeo, sin importar otra columna por posición. |
| DBI-11 | Origen regular, solo un punto y manual incoherente | Detectar cuando sea posible; exigir declaración si no; bloquear incoherencia. |
| DBI-12 | Todos los ejemplos numéricos de la sección 7 | Resultados esperados, conservación y flags correctas. |
| DBI-13 | Razón no entera y ancla desplazada | Ponderación por solapamiento; ninguna muestra de borde omitida. |
| DBI-14 | Misma resolución/fase | Identidad numérica sin redondeo ni estimación añadida. |
| DBI-15 | Fin de periodo y timestamps con diferentes offsets | Mismos intervalos UTC físicos que la representación por inicio. |
| DBI-16 | Horas DST ambiguas/inexistentes sin offset | Rechazo; `timestamptz` desambiguado se procesa correctamente. |
| DBI-17 | Hueco, nulo, NaN, infinito, duplicado igual/diferente | Grupo bloqueado; no relleno, descarte ni «último gana». |
| DBI-18 | Último intervalo original aún abierto | Ventana móvil retrocede al último cierre compatible; rango fijo inválido da `SOURCE_NOT_READY`; nunca subdividir el intervalo abierto. |
| DBI-19 | Corrección en rango con historia fuera | Nueva revisión completa, exterior idéntico y anterior intacta. |
| DBI-20 | Consulta vacía o borrado remoto crea hueco | No borra los datos locales ni publica revisión vacía/parcial. |
| DBI-21 | Dos señales del mismo set, una inválida | Ninguna se actualiza; otro set independiente válido sí puede publicarse. |
| DBI-22 | Extender una señal dejando hermanas sin valores | Bloqueo del set, sin celdas inventadas. |
| DBI-23 | Repetición con mismos datos/semántica | `unchanged`, sin nueva revisión ni cambio de generación; ejecución auditada. |
| DBI-24 | Mismos números con distinta calidad/procedencia semántica | Nueva revisión pertinente; hash canónico histórico sin cambios. |
| DBI-25 | Fuente cambia después del preview | Commit del snapshot validado, sin segunda lectura remota oculta. |
| DBI-26 | Destino cambia antes del commit | Conflicto detectado bajo lock; nunca se pierden valores de la nueva base. |
| DBI-27 | Doble clic, dos workers y respuesta perdida tras commit | Un resultado por clave/tick y una creación/publicación efectiva. |
| DBI-28 | Proceso pierde lease y sigue trabajando | Fencing impide que publique; sucesor recupera correctamente. |
| DBI-29 | Caída durante extracción o publicación | Sin mezcla de snapshots ni revisión parcial; recuperación desde recibos. |
| DBI-30 | Frecuencia interval/daily/weekly y DST de agenda | Fechas deterministas, una ocurrencia repetida y política explícita de hora inexistente. |
| DBI-31 | Apagar servidor, reiniciar y superar ventana móvil | Coalescencia auditada y backfill requerido cuando corresponda. |
| DBI-32 | Revocar usuario/secreto o promover set a global | Programación se detiene según permisos/aprobación actual. |
| DBI-33 | Añadir consumidor que amplía impacto compartido | Agenda queda `needs_review`, sin aprobación simulada. |
| DBI-34 | Cancelar antes/después de un commit de grupo | Solo se detiene trabajo pendiente; recibo muestra qué sí quedó publicado. |
| DBI-35 | 100 series y 5 millones de puntos | Procesamiento por lotes dentro de memoria medida, interfaz disponible. |
| DBI-36 | Expansión o historia conservada excede cuota | Error explícito antes de publicación, sin truncamiento. |
| DBI-37 | Importar y abrir una corrida previa | Conserva binding y snapshot originales; nueva revisión seleccionable explícitamente. |
| DBI-38 | Migrar base previa PostgreSQL/SQLite | Fuentes `database` válidas, revisiones selladas protegidas y hashes previos iguales. |
| DBI-39 | Caducar staging/archivar plan/purgar proyecto | Limpieza consistente, sin referencias rotas ni borrar perfil de otro proyecto. |
| DBI-40 | Logs, API, URL y almacenamiento del navegador | Ausencia de secretos/DSN; certificado inválido no se acepta automáticamente. |

Pruebas unitarias propuestas: núcleo de intervalos, rango/grilla, filtros tipados,
zona horaria y agenda. Pruebas de integración con PostgreSQL real aislado: permisos
remotos, snapshots, cursores, constraints, locks, leases, idempotencia, migraciones
y límites. SQLite no sustituye esas pruebas de concurrencia.

Frontend: pruebas de estado y accesibilidad del panel, mapeos, contratos heredados,
errores por grupo, aprobaciones y polling; E2E contra la API para preview/publicación,
actualización programada, historial y uso posterior en una variante. Reutilizar
el estilo de [pruebas TS-7](../../../tests/test_ts7_011_object_specific_file_ingestion.py)
y los comandos de validación del [README](../../../README.md).

## 16. Secuencia de implementación

1. **Contratos y migraciones:** tablas operativas, fuente `database`, secretos,
   clasificación faltante y helpers de autorización. Probar upgrades y purga.
2. **Tramo vertical mínimo:** una conexión, tabla larga, un ID a nueva serie de
   catálogo, misma resolución, preview y publicación canónica. Incluir worker
   durable desde este tramo, para no fijar un flujo síncrono que deba rehacerse.
3. **Transformación temporal:** ambos sentidos, razón no entera, origen/destino,
   zonas, inicio/fin, bordes completos y pruebas de conservación.
4. **Destinos y actualización:** existentes, específicas de objeto, creación
   atómica, `replace_range`, señales hermanas, base esperada y hash semántico.
5. **Interfaz completa:** perfiles/panel, varias tablas e IDs, filtros, uno a uno,
   Aplicar a todas, preview, errores, progreso y cancelación.
6. **Automatización:** intervalos/agenda civil, ventanas, aprobaciones, reservas
   por destino, recuperación, backfill y cambios de permisos/impacto.
7. **Endurecimiento y entrega:** fixture de capacidad, E2E, claves/TLS,
   observabilidad, manual operativo y pruebas de rollback del despliegue.

Después de cambiar la API, regenerar contrato y tipos con `npm run api:generate`;
verificar `api:check`, `check`, pruebas relevantes y build desde `frontend`.
Ejecutar suites backend nuevas y regresiones de publicación canónica, objeto,
clasificación, catálogo, bindings y purga. No es necesario ejecutar Julia para
probar cada filtro, pero sí verificar el uso de una revisión importada en el flujo
existente de materialización de una corrida.

Despliegue: crear claves fuera del repo, aplicar migraciones, configurar destinos
de red/CA, iniciar worker supervisado, validar disponibilidad en salud y habilitar
entrada UI mediante flag de despliegue. No activar agendas por migración. Para
rollback funcional, detener/cercar worker y deshabilitar importación manteniendo
historia y esquema aditivo; un binario que desconozca `source.kind=database` no
debe desplegarse sobre datos nuevos sin una ruta de compatibilidad probada.

## 17. Condición de entrega

La integración está terminada cuando un usuario puede guardar una conexión,
seleccionar tablas/IDs, revisar cada correspondencia, fijar ambas resoluciones y
filtros, verificar una transformación real, publicar una revisión local y reutilizar
el plan manualmente o con frecuencia automática; los datos quedan disponibles por
los mecanismos de selección/vinculación existentes, con historia, trazabilidad y
garantías de atomicidad verificadas.

No quedan decisiones funcionales pendientes de la entrevista. La infraestructura
concreta del origen (host, credenciales, esquema y datos reales) se introduce al usar
la funcionalidad; este documento no contiene ni requiere credenciales de producción.
