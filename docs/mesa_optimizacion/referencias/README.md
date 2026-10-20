# Referencia visual de la mesa

Capturas realizadas el 2026-10-20 a partir del HTML que el usuario aprobó como
prueba de concepto. No son capturas de una implementación conectada al backend.

| Archivo | Estado documentado |
| --- | --- |
| [01-mesa-general-antes.png](01-mesa-general-antes.png) | Variante A, pestaña Vista general, distribución 2×2, cuatro gráficos, sin ejecutar. |
| [02-mesa-comparacion-graficos-tabla.png](02-mesa-comparacion-graficos-tabla.png) | Mismo contexto tras una simulación ficticia; Comparar activo, tres gráficos y tabla del embalse. |
| [prototipo-validado.html](prototipo-validado.html?variant=A) | Copia autónoma del código usado para estas capturas. |
| [manifest.json](manifest.json) | Estado, entorno, dimensiones y hashes de los archivos. |

## Entorno de referencia

- Ventana: 1440×900 píxeles CSS.
- Device pixel ratio emulado: 1.
- Chromium/Chrome en Windows, tema claro, movimiento reducido.
- Idioma observado del navegador: en-US. Por eso el control nativo de fecha se
  ve en formato mes/día/año, aunque los textos de la aplicación están en español.
- Zona horaria observada: America/Santiago.
- Datos: ficticios, 2026-10-20, 24 intervalos horarios.
- Fuente: tipografía local del prototipo; registrar fuentes/versiones propias al
  establecer baselines de la aplicación React.

## Reproducir la primera captura

1. Abrir la copia del HTML con ?variant=A y recargar para limpiar el estado en memoria.
2. Fijar viewport 1440×900, DPR 1, tema claro y movimiento reducido.
3. Mantener Vista general, distribución 2×2 y el rango inicial del 2026-10-20.
4. Esperar fuentes y dibujo. Mantener el scroll en el inicio y el puntero fuera
   de los gráficos para evitar tooltip.
5. Capturar el viewport completo.

## Reproducir la segunda captura

1. Partir del estado anterior.
2. Pulsar Simular escenario y esperar Simulación 01 · completada.
3. Comprobar Comparar activo y esperar que desaparezca la notificación temporal.
4. Cambiar únicamente Reserva de agua / Embalse El Alto a tabla.
5. Mantener scroll de página y tabla en el inicio y el puntero fuera de gráficos.
6. Capturar el viewport completo.

## Uso durante la implementación

Consultar [validacion_tdd.md](../validacion_tdd.md). Estos archivos no se
sobrescriben para hacer pasar una prueba. La futura aplicación tendrá sus
baselines de regresión después de revisar y aceptar las diferencias.

Las fórmulas del HTML no tienen valor de especificación matemática. Los
resultados ficticios, el límite de siete días, la pérdida de estado al recargar
y las salidas inventadas antes del primer run no se trasladan al producto.
