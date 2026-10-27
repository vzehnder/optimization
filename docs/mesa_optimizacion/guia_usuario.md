# Usar la mesa de optimización

La mesa está disponible para analistas y administradores desde **Escenario →
Datos → Variante activa → Abrir mesa de optimización**. Conserva el caso y la
variante seleccionados. En una versión hidráulica promovida también puedes usar
**Preparar versión en la mesa**. Los recorridos de escenario, diagrama y detalle
de ejecución siguen disponibles.

Dentro de la mesa, **Cómo usar la mesa** abre una guía sin perder tus selecciones.

## Configurar y guardar cuatro vistas

1. Elige **Filas: 2** y **Columnas: 2**. Cada pestaña admite entre 1 y 6 filas y
   columnas. Usa **Agregar vista** o **Agregar aquí** en una celda libre.
2. En **Configurar**, elige título, componente y señales. Los nombres repetidos
   se distinguen por identidad; cada señal conserva su unidad.
3. Pulsa **Elegir espacio**. Marca una celda o dos esquinas opuestas para formar
   un rectángulo y pulsa **Usar este espacio**, luego **Aplicar**. Las celdas
   ocupadas muestran el nombre de su vista. No se permite invadirlas, tampoco
   cuando están dentro de un rectángulo cuyas esquinas están libres.
4. Alterna **Gráfico** y **Tabla** en cada vista. Puedes repetir un componente
   para observar magnitudes distintas.
5. Usa **Guardar mesa** y recarga para recuperar tu configuración. Cada pestaña
   conserva su cuadrícula y posiciones. Para reducir filas o columnas, mueve o
   reduce primero las vistas que quedarían fuera. Una cuadrícula llena bloquea
   **Agregar vista** hasta liberar espacio o ampliar sus dimensiones.

El selector funciona con clics o con Tab, flechas y Enter. **Cancelar selección**
conserva el espacio anterior; **Cancelar** descarta toda la edición de la vista.
Las configuraciones anteriores se recuperan automáticamente. Si tenían vistas
ocultas, ampliar la cuadrícula vuelve a ubicarlas en celdas libres. En pantallas
pequeñas las vistas se apilan, conservando sus posiciones para escritorio.

Guardar mesa conserva la disposición personal de ese caso. Para guardar valores
hay que entrar al editor de la serie; para cambiar activos, al editor hidráulico.

## Ejes Y y altura de los gráficos

En **Configurar**, marca las series del componente y elige para cada una
**Primario · izquierda** o **Secundario · derecha**. Puedes agregar todas las
series disponibles a cualquiera de los dos ejes. Las series de cada eje comparten
su escala numérica; si mezclas unidades, la etiqueta indica **Múltiples unidades**
y las enumera. Los valores conservan sus unidades originales.

En centrales y unidades puedes marcar **Costo marginal · USD/MWh**; se asigna
inicialmente al eje secundario. Con una ejecución seleccionada se muestra el
precio de su snapshot, también en Antes, Comparar y Después. Sin ejecución se
consulta la fuente de precio de venta de la preparación. Si falta el precio,
la serie permanece seleccionable y muestra un estado sin datos.

Arrastra el control del borde derecho de una fila hacia abajo para agrandar los
gráficos que la ocupan. No hay un límite fijo de altura y la página se desplaza al llegar al
borde de la ventana. También puedes enfocar la barra y usar las flechas arriba y
abajo. La distribución sigue determinando el ancho. **Guardar mesa** conserva
los ejes y las alturas; **Detalle y procedencia de las series** muestra los
orígenes de las señales de un gráfico combinado.

Los gráficos agrupan automáticamente las muestras según el ancho disponible y
el período visible. Caudales, potencias, niveles, precios y estados almacenados
usan promedio ponderado por duración; las cantidades por intervalo, como energía
generada, volumen aportado o costos, usan suma. La barra del gráfico indica la
resolución y el método. La tabla conserva los valores originales y muestra inicio
y valor, sin columna de fecha fin.

Pasa el cursor sobre el gráfico para consultar valores, unidades e intervalos.
Arrastra sobre un período para ampliarlo; la agrupación se recalcula para mostrar
más detalle. **Restablecer zoom** recupera todo el período. Con el gráfico enfocado,
las flechas recorren los valores; **Mayús + flechas** selecciona y **Enter** amplía.
**Escape** restablece la vista. Este zoom es local al gráfico. Al cambiar el
inicio o fin de ejecución, todos los gráficos se ajustan al nuevo intervalo
`[inicio, fin)` y se restablece su zoom, sin validar ni ejecutar. Se respeta la
zona horaria de ejecución (UTC en la preparación hidráulica). Fechas incompletas
o inválidas conservan el último período válido; un período sin muestras muestra
un estado sin datos. Las tablas conservan los intervalos de la consulta.

## Editar, preparar y ejecutar

En una tabla con entrada editable, pulsa **Editar entrada**, modifica los valores,
escribe un motivo y confirma el alcance antes de **Guardar entrada**. Un conflicto
conserva el borrador y permite compararlo con la revisión actual. Los resultados
de una corrida son de solo lectura.

Abre **Preparar ejecución eléctrica**, elige inicio, fin exclusivo, zona y
resolución, y pulsa **Validar preparación**. Por ejemplo, desde las 00:00 hasta
las 02:00 de un mismo día cubre dos intervalos de una hora. La cobertura y la
resolución deben corresponder a las entradas. **Ejecutar caso eléctrico** se
habilita con una preparación válida; editar las entradas o el período exige
validar otra vez.

La red hidráulica usa **Preparar ejecución hidráulica**: selecciona una versión
fuente promovida, rango UTC, resolución, objetivo y opciones económicas requeridas.
Revisa cualquier remuestreo indicado antes de **Validar red hidráulica** y
**Ejecutar red hidráulica**. La red v3 se ejecuta por este camino; el hidro simple
v2 participa en el caso eléctrico.

El avance distingue cola, ejecución, guardado, éxito y fallo. Puedes recargar para
recuperar el mismo run. Si se pierde la conexión, usa **Reintentar conexión**;
una corrida fallida conserva las entradas y explica el error, sin ofrecer salidas.

## Comparar, recuperar y exportar

Tras completar la ejecución, usa **Ver resultados en la mesa** o su equivalente
hidráulico. **Antes**, **Comparar** y **Después** consultan el snapshot ejecutado:
editar hoy no altera esos valores históricos. **Preparación actual** vuelve a
las entradas del caso.

Para comparar salidas, selecciona una **Ejecución de referencia** compatible.
**Sin referencia previa** significa que no existe un antes ni una diferencia
para esa salida. La Δ es después menos antes, solo entre el mismo objeto,
magnitud, unidad e intervalos. El volumen inicial de un embalse es un parámetro;
no se presenta como una trayectoria histórica.

**Historial de ejecuciones → Consultar** recupera una corrida completada y su
procedencia. **Período de consulta** recorta el histórico en UTC, con fin exclusivo,
sin modificar el período preparado para ejecutar. **Todo el run** restaura el
rango completo. **Exportar CSV de vistas visibles** descarga las señales y el
rango consultados, con unidades, identidades, estados y orígenes. Una ausencia
se conserva como ausencia, sin convertirla en cero.

## Agregar activos y series manuales

En una red v3, **Editar activos hidráulicos** permite usar un activo existente o
crear un embalse/central. Completa límites, curvas, aportes, unidades y conexiones;
un borrador incompleto no se puede promover. Guarda el diagrama, genera el preview
y promueve una versión. **Preparar versión en la mesa** permite ejecutarla. Una
edición posterior necesita otra versión promovida para llegar a la simulación.

**Crear serie manual** publica una serie de apoyo asociada a un objeto. Agrégala
a una vista y usa **Gestionar serie manual** para editarla. El apoyo no participa
en el modelo. **Vincular revisión publicada** requiere un destino compatible,
motivo y confirmación; reemplaza esa entrada y exige revalidar. Este vínculo se
ofrece para variantes eléctricas e hidro simple v2. En red v3, usa el editor y
la versión promovida para cambiar entradas ejecutables.

## Teclado y pantalla estrecha

Tab recorre los controles. Flechas izquierda/derecha, Inicio y Fin cambian de
pestaña. Los diálogos devuelven el foco al cerrar; Escape respeta la confirmación
de cambios pendientes. A 390 px las vistas se apilan y las tablas conservan su
desplazamiento local, sin ensanchar toda la página.
