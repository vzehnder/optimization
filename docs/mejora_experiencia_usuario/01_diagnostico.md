# Diagnóstico del repositorio

## Arquitectura y dominio observados

La aplicación activa es React, servida bajo `/react`, con FastAPI para autenticación, persistencia, archivos y orquestación; Julia resuelve los modelos. La raíz interna concentra la mayor parte de las tareas en `Workspace.tsx` y `DraftEditor.tsx`. Consola, portal, catálogo global y recorrido protegido cuentan con componentes específicos.

Referencias principales:

- [Rutas y raíces](../../frontend/src/App.tsx): `AuthenticatedRoutes`, `AnalystRoot`, `ConsoleRoot`, `PortalRoot`, `LandingRedirect`.
- [Workspace](../../frontend/src/Workspace.tsx): proyectos, escenarios, variantes, hidráulica, catálogos por proyecto, resultados y publicaciones.
- [Editor estructurado](../../frontend/src/DraftEditor.tsx): modelo, ingestión y generación/validación/promoción.
- [API](../../app/main.py) y [cliente tipado](../../frontend/src/api/client.ts).
- [Semántica de jerarquía](../series_tiempo/iter1/decision_record_ts1_hierarchy.md) y [variantes](../series_tiempo/iter3/decision_record_ts3_variant_semantics.md).
- [Arquitectura de configuración y superficies externas](../capa_configuracion/architecture_configuration_layer_final.md).
- [Especificación TS-7](../wayfinder/catalogo-global-series-genericas/10-especificacion-consolidada.md) y [excepción de borrado de proyecto](../series_tiempo/iter7/decision_record_ts7_project_purge.md).

No se encontró `AGENTS.md` ni `CONTEXT.md` en la búsqueda del repositorio. Se leyó la [habilidad TDD solicitada](../../.agents/skills/tdd/SKILL.md), junto con sus referencias `tests.md` y `mocking.md`.

## Fricciones y evidencia

Los impactos de la columna «Hipótesis» deben comprobarse con usuarios. No se han medido abandonos, tiempos ni tasas de error.

| Hecho observable en código | Evidencia localizable | Hipótesis de impacto | Cambio propuesto |
| --- | --- | --- | --- |
| La navegación principal se denomina «Analista», «Catalogo», «Admin», «Sistema» | `App.tsx`, `AnalystRoot` | No anticipa la tarea ni el contenido de «Analista» | Etiquetar «Proyectos», conservar catálogo y agrupar utilidades; UX-001 |
| Un proyecto muestra escenarios, creación, series, accesos, portal y templates en una pila | `Workspace.tsx`, `ProjectDetailView` | Configuración ocasional compite con trabajo diario | Secciones por tarea con URL y retorno; UX-001/007/009 |
| El escenario presenta variantes, consolas, versiones, JSON experto e historial en la misma vista | `Workspace.tsx`, `ScenarioDetailView` | Cuesta identificar el siguiente paso y distinguir caminos | Resumen de avance y accesos a modelo, datos, ejecución, resultados y avanzado; UX-001/005 |
| El editor expone `Draft schema`, IDs, solver y «Graph, grid y solver» junto a campos habituales | `DraftEditor.tsx`, `DraftEditor` | El usuario necesita aprender detalles técnicos antes de modelar | Mostrar primero parámetros del dominio; detalles técnicos desplegables; UX-002 |
| Conviven «Guardar draft», «Generar preview», «Validar con Julia», «Promover version» y ejecución por variante | `DraftEditor.tsx`, acciones de caso generado; `Workspace.tsx`, `CaseInputVariantBindingEditor` | Se interpreta la promoción manual como requisito de toda corrida | Señalar dos caminos y recomendar variante cuando aplica; UX-005 |
| El botón «Vincular y correr variante» guarda asociaciones en un bucle y luego ejecuta | `Workspace.tsx`, `CaseInputVariantBindingEditor.runMutation` | Un error intermedio es difícil de interpretar; cambiar datos y ejecutar se perciben como una sola decisión | Separar confirmación de datos de revisión/ejecución y explicitar estados parciales; UX-005 |
| Los selectores de señales de la variante enumeran `timeSeriesSets`; el rango usa campos de texto ISO y se reinicia al cambiar una serie | `Workspace.tsx`, `CaseInputVariantBindingEditor` | Se eligen fuentes incompatibles y se pierde el rango que se estaba preparando | Selección contextual y rango visible con zona y cobertura; UX-004/005 |
| Subida, mapeo, edición, importación al catálogo y extracción legacy son secciones distintas del editor | `DraftEditor.tsx`, `SourceSummary`, `TimeSeriesMappingPanel`, `TimeSeriesCatalogImportPanel` | Es difícil saber cuándo un archivo ya está disponible para ejecutar | Pasos guiados y confirmación del destino; UX-003 |
| El catálogo global ya tiene búsqueda, filtros por tipo/clase/unidad/alcance/estado, orden, inspector y paginación por cursor; mantiene filtros en estado local | `GlobalCatalog.tsx`, `GlobalCatalogView` | Hay carga inicial alta y el contexto puede perderse al desmontar la vista | Filtros principales y adicionales, URL reproducible y retorno al origen; UX-004 |
| El recorrido canónico muestra «Recorrido protegido», «Toda mutacion...» y «Datos o revision ejecutable» | `ProtectedMutationJourney.tsx`, `JourneyShell`, `STEPS` | Explica la implementación más que la tarea que la persona está haciendo | Título según intención y resumen de cambios, conservando cuatro pasos; UX-004 |
| Estado, lineage, procedencia, series y snapshot aparecen antes de resultados | `Workspace.tsx`, `RunDetailView` | Hay que recorrer auditoría para saber qué ocurrió | Estado + resultado primero; auditoría accesible bajo demanda; UX-006 |
| La configuración de consola requiere JSON para parámetros y resultados | `OperatorConsole.tsx`, `ConsoleDocumentForm` | El ingeniero necesita conocer el esquema incluso para cambios habituales | Formulario sobre el mismo contrato y JSON experto reversible; UX-008 |
| La consola ya impide ejecutar cambios sin guardar y distingue bloqueos; hay tabla virtualizada, pegado, historial y deshacer | `OperatorConsole.tsx`, `ConsoleShellView`, `ConsoleGroupEditor` y sus pruebas | La mejora es orientar y conservar contexto, no volver a construir la tabla | Resumen de preparación y recuperación coherente; UX-008 |
| Existen etiquetas mezcladas: `Run state`, `Failure context`, `Publication Drafts`, `Password` | `Workspace.tsx`, `App.tsx`, `Admin.tsx` | Mayor esfuerzo de lectura y vocabulario inconsistente | Español consistente en textos; identificadores API sin cambios |
| Administración incluye opciones `external` y `client`, aunque el modelo de roles actual declara `external` | `Admin.tsx`, `CreateUserForm`, `userRoles`; `auth.py` | Dos opciones parecen representar personas distintas | Presentar la identidad vigente y verificar compatibilidad del alias; UX-009 |

## Capacidades que ya resuelven parte del problema

No deben plantearse como desarrollos desde cero:

- El editor estructurado ya tiene estado de guardado, errores asociados al campo, aviso al cerrar y confirmación al navegar por enlaces con cambios pendientes. Extender y verificar atrás/adelante y nuevas pestañas, sin afirmar que no hay protección actual.
- Hay breadcrumbs, estados vacíos, reintentos y manejo de errores. Conviene unificar su experiencia en los recorridos tocados.
- La ejecución ya tiene polling y recuperación de fallas temporales. No hace falta migrarla a WebSockets.
- Resultados ya tiene Plotly, tablas acotadas y descarga de artefactos. La consola ya virtualiza horizontes de 8760 filas en una prueba de componente.
- El catálogo TS-7 ya separa consulta de mutación y usa un único recorrido protegido. Sus pruebas cubren filtros, cursores, rechazos y precondiciones.
- El portal ya tiene configuración visual, selección de KPIs/gráficos/tablas/descargas y render compartido con el preview. No proponer un portal nuevo.
- Ya existen Vitest, Testing Library, Playwright y axe. El trabajo es añadir cobertura de comportamientos nuevos en esas fronteras.

## Riesgos que condicionan el plan

1. **Convivencia de versiones.** `ts_next_canonical_read` habilita lectura para la identidad; no demuestra por sí solo que C6 esté activo. `app/main.py` adapta el endpoint legacy de bindings según el estado C6. No inferir el escritor permitido desde un flag de lectura.
2. **Validación múltiple.** Guardar un modelo, validar un caso generado, validar una variante y ejecutar son operaciones distintas. El frontend no debe inventar un estado «listo» a partir de un único booleano local.
3. **Transacciones parciales.** La composición frontend de varios requests no garantiza atomicidad. Antes de añadir «Continuar» o «Ejecutar», definir qué quedó guardado y qué se puede reintentar.
4. **Información externa.** Las superficies externas dependen de allowlists del backend. Reutilizar un componente interno que imprime JSON puede filtrar información aunque se oculten campos visualmente.
5. **Formularios extensos.** Desmontar pestañas puede perder valores o sobrescribir campos ocultos. Debe probarse la persistencia del documento completo mediante UI/API pública.
6. **Hidráulica.** Layout, topología física y parámetros tienen reglas de desactualización diferentes; cambiar la organización visual no debe invalidar un modelo físico.

Las prioridades propuestas reducen estas fricciones sin cambiar el modelo matemático. Los tamaños de archivo son una consideración de mantenimiento, no evidencia de mala usabilidad ni motivo para una refactorización masiva previa.
