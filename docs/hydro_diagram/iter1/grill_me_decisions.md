# Hydro Diagram Iteration 1 Grill-Me Decisions

Fecha: 2026-06-26

Este documento registra las decisiones cerradas durante la entrevista
`grill-me` para la primera iteracion del editor de diagrama hidraulico.

## Decisiones Aceptadas

1. El diagrama editara la topologia activa del caso de optimizacion y
   reutilizara objetos fisicos desde una red hidraulica base del proyecto.
2. La primera iteracion sera end-to-end con solver limitado: diagrama, BBDD,
   validacion, `system_case_json` y ejecucion para una red dirigida simple sin
   tiempo de viaje ni generacion dependiente de cota.
3. Las centrales seran nodos visibles del diagrama principal. Las unidades se
   editaran dentro del panel de la central, con subvista si hace falta.
4. Los tramos seran `hydraulic_reaches` tipados: rios, canales, tuneles,
   compuertas, vertederos, bypasses, restituciones y otros.
5. El panel permitira crear o editar curvas como tablas de puntos y tambien
   seleccionar curvas versionadas existentes.
6. El MVP exigira dos curvas: `storage_elevation` para embalses y
   `flow_power` por unidad. Curvas 2D, area, perdidas, evaporacion, head neto y
   eficiencia quedan preparadas para extensiones futuras.
7. El editor permitira dibujar un grafo dirigido general, pero la validacion
   del MVP aceptara solo redes compatibles con el solver activo.
8. El layout visual se persistira por caso, separado de la fisica, con
   autolayout inicial si no existe layout guardado.
9. La creacion de conexiones usara drag-and-drop como flujo principal y un
   formulario de respaldo para origen y destino.
10. Cada `case_hydraulic_unit` tendra una sola curva `flow_power` activa en el
    MVP.
11. `natural_inflow_m3s` se podra asociar a cualquier `hydraulic_node`, no solo
    a embalses.
12. El MVP incluira `minimum_flow_m3s` opcional por tramo, como escalar o serie
    vinculada.
13. La iteracion creara una extension en `docs/hydro_diagram/iter1/` y no
    modificara directamente `docs/db/propuesta_bbdd_componentes_timeseries.md`
    en esta pasada.
14. La UI principal del diagrama sera React. El editor server-rendered legado
    no recibira una superficie equivalente.
15. El MVP no incluira importacion masiva de topologia desde CSV/XLSX. Si
    incluira seleccion/edicion de curvas versionadas e importacion de series.
16. Las issues incluiran cambios minimos al modelo Julia para una ejecucion
    end-to-end.
17. El contrato ejecutable nuevo sera `bess_system_dispatch.v3`.
18. Cualquier edicion del diagrama invalida la validacion vigente y bloquea la
    promocion hasta revalidar. Las `scenario_versions` promovidas siguen siendo
    inmutables.
19. La version promovida guardara un snapshot liviano del layout como metadata
    no ejecutable.
20. El modelo usara claves tecnicas estables y nombres visibles editables:
    `node_key`, `reach_key`, `plant_key`, `unit_key`, `display_name` y
    `case_label`.
21. La persistencia de cambios sera explicita, con estado dirty visible y
    validacion en vivo.
22. El MVP no soportara edicion concurrente en tiempo real. Usara control
    simple con `updated_at` o revision para evitar sobrescrituras silenciosas.
23. Se mantendra un checkpoint vivo de BBDD en
    `docs/db/hydro_diagram_db_checkpoint.md` con estado objetivo, estado
    implementado, pendientes y ultima issue que toco BBDD.
24. Las issues se publicaran como archivos locales en
    `docs/hydro_diagram/iter1/issues/`, con tracker Markdown local y triage
    `ready-for-agent`.

