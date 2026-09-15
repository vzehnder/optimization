# Tutoriales de BESS Workspace

Revisados contra el código del repositorio el **2026-09-15**, con los cambios
de interfaz UX-001 a UX-009 y los recorridos TS-7. La disponibilidad de las
operaciones canónicas depende del estado de migración y de la cuenta.

| Necesito… | Tutorial |
| --- | --- |
| Entender la herramienta y hacer mi primera corrida | [Guía del analista](./guia_analista.md) |
| Seguir instrucciones pantalla por pantalla, incluidos portal, consola y administración | [Manual completo de uso](./manual_completo_uso_pagina_web.md) |
| Preparar archivos, importar series y asignar revisiones al modelo | [Carga y matcheo de series de tiempo](./carga_y_matcheo_series_tiempo.md) |

## Recorrido principal

1. Crear proyecto y escenario.
2. En **Modelo**, configurar componentes y guardar.
3. Importar o encontrar las fuentes necesarias.
4. En **Datos**, elegir la variante y confirmar sus fuentes: mediante
   **Confirmar fuentes** en compatibilidad, o mediante asociación y uso de
   revisión en el recorrido protegido.
5. Elegir el período y pulsar **Revisar preparación**.
6. Al ver **Preparado para ejecutar este período**, pulsar **Ejecutar variante**.
7. Revisar resultados y procedencia; comparar o preparar un informe si corresponde.

Importar, asociar, fijar una revisión, ejecutar y publicar un informe son
acciones separadas. Si el servidor dirige a una necesidad del modelo, sigue
ese enlace; el [manual explica los modos disponibles](./manual_completo_uso_pagina_web.md#19-variantes-de-entrada-y-bindings)
y los límites de la interfaz para series específicas.
