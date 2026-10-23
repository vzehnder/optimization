# Usar la mesa de optimización

La mesa está disponible para analistas y administradores desde **Escenario →
Datos → Variante activa → Abrir mesa de optimización**. Conserva el caso y la
variante seleccionados. En una versión hidráulica promovida también puedes usar
**Preparar versión en la mesa**. Los recorridos de escenario, diagrama y detalle
de ejecución siguen disponibles.

Dentro de la mesa, **Cómo usar la mesa** abre una guía sin perder tus selecciones.

## Configurar y guardar cuatro vistas

1. Elige **2 × 2 · 4 vistas** y usa **Agregar vista** hasta completar los paneles.
2. En **Configurar**, elige título, componente y señales. Los nombres repetidos
   se distinguen por identidad; cada señal conserva su unidad.
3. Alterna **Gráfico** y **Tabla** en cada vista. Puedes repetir un componente
   para observar magnitudes distintas.
4. Usa **Guardar mesa** y recarga para recuperar tu configuración. Cada pestaña
   conserva sus vistas. Reducir la distribución oculta paneles sin borrarlos.

Guardar mesa conserva la disposición personal de ese caso. Para guardar valores
hay que entrar al editor de la serie; para cambiar activos, al editor hidráulico.

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
