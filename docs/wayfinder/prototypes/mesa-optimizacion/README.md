# Prototipo: mesa de optimización

Pregunta a validar: ¿es cómoda una pantalla única con pestañas por componente,
vistas configurables y comparación de series antes y después de una simulación?

Estado: **concepto validado por el usuario el 2026-10-20** para avanzar a la
planificación. Es un prototipo desechable, no una implementación del producto.
El [plan y tracker de implementación](../../../mesa_optimizacion/README.md)
conserva capturas y una copia del HTML como referencia. El desglose y las interfaces
de prueba fueron confirmados; las decisiones técnicas restantes están en el tracker.

## Abrir

Abrir `index.html` directamente en el navegador. Es un único archivo autónomo:
no requiere instalar dependencias, conexión a internet ni iniciar el backend.

Desde la raíz del repositorio, en PowerShell:

```powershell
Start-Process docs/wayfinder/prototypes/mesa-optimizacion/index.html
```

También se puede servir por HTTP:

```powershell
.\.venv\Scripts\python.exe -m http.server 4174 --bind 127.0.0.1 --directory docs/wayfinder/prototypes/mesa-optimizacion
```

Abrir <http://localhost:4174/?variant=A>.

## Qué se puede probar

- Una vista general y pestañas para BESS, demanda, renovables, central hidráulica
  y embalse. Los componentes agregados reciben su propia pestaña.
- Distribución independiente por pestaña: 1×1, 1×2, 2×2 y 2×3. Al reducirla,
  las vistas sobrantes se ocultan y se recuperan al ampliarla.
- Configurar cada vista: título, componente, una o varias series, gráfico o tabla.
  Las unidades diferentes se separan en gráficos con sus propios ejes.
- Agregar o quitar vistas. Agregar componentes hidráulicos, eléctricos o manuales.
  Los manuales permiten definir nombre de serie, unidad y valor base.
- Editar los valores «Antes» en tablas. Los resultados «Después» son de solo lectura.
- Seleccionar de 1 a 7 días, incluyendo ambas fechas, con resolución de una hora.
- Ejecutar una simulación ilustrativa y comparar antes, después y diferencias.
  Cambiar fechas, valores o agregar componentes invalida los resultados actuales.
- Consultar el registro de ejecuciones de la sesión y exportar las series de las
  vistas visibles a CSV. El registro no almacena copias recuperables de resultados.
- Consultar valores de gráficos al pasar el puntero. Para revisar o editar con
  teclado, usar las tablas.

## Alternativas de organización

La barra inferior cambia el parámetro de URL y conserva los datos de la sesión:

- `?variant=A`: **Paneles**, pestañas horizontales y matriz configurable. Es la
  propuesta principal para la pantalla solicitada.
- `?variant=B`: **Explorador**, componentes en una columna lateral y vistas a la derecha.
- `?variant=C`: **Series en filas**, metadatos a la izquierda y gráficos anchos a la
  derecha. La distribución seleccionada establece cuántas vistas se muestran;
  esta alternativa siempre las dispone en filas.

Las flechas izquierda y derecha cambian de diseño cuando el foco no está en un
campo o una pestaña. Dentro de las pestañas, las flechas cambian de componente.

## Alcance

Todos los nombres, perfiles y resultados son inventados. La simulación aplica
variaciones deterministas a las series editadas: no ejecuta un optimizador ni
verifica balances hidráulicos, eléctricos o económicos. Las fechas representan
intervalos horarios de ejemplo, sin tratamiento de cambios de hora.

Todo el estado vive en memoria y se pierde al recargar. No lee componentes de
la base de datos, no llama APIs y no modifica la aplicación existente.

La validación debe decidir si la matriz y las pestañas resultan cómodas, qué
series conviene mostrar por defecto y cómo deberían editarse los componentes.
Las conexiones y la implementación funcional corresponden a una etapa posterior.
