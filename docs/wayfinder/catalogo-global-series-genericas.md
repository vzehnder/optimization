---
label: wayfinder:map
slug: catalogo-global-series-genericas
title: "Catalogo global y series especificas vinculadas a objetos"
created: 2026-08-30
---

# Catalogo global y series especificas vinculadas a objetos

## Destination

Una **especificacion funcional y tecnica lista para implementar** de dos
caminos complementarios: un catalogo global autorizado para descubrir,
clasificar y reutilizar series genericas, y series especificas que nacen desde
un objeto ya creado, quedan vinculadas solamente a ese objeto y no necesitan
una serie generica como antecedente.

El mapa cierra cuando existe un spec consolidado con modelo relacional,
contratos de API y carga de archivos, experiencia de catalogo y gestion desde
el objeto, compatibilidad y migracion, permisos, auditoria, rendimiento y
criterios de aceptacion. Debe quedar definido el orden objeto -> definicion de
serie especifica -> carga o actualizacion de valores, tanto por API como por
archivo. Ese spec queda listo para convertirse en tickets de implementacion;
este mapa no implementa codigo de producto.

## Notes

**Dominio**: aplicacion privada de optimizacion de despacho (FastAPI + React +
motor Julia) con catalogo generico de entradas, variantes por caso, resultados
indexados y un camino hidraulico legacy. Referencias principales:
`docs/series_tiempo/iter2/decision_record_ts2_catalog_semantics.md`,
`docs/series_tiempo/iter3/decision_record_ts3_variant_semantics.md`,
`docs/series_tiempo/iter5/architecture_ts5_final.md` y
`docs/db/propuesta_bbdd_componentes_timeseries.md`.

**Tracker**: markdown local. Convenciones en `docs/wayfinder/README.md`.

**Este mapa planifica; no implementa.** Cada ticket resuelve una decision o
produce el activo de especificacion que depende de esas decisiones.

Las resoluciones cerradas del 01 al 05 describen principalmente el camino de
series genericas reutilizables. La ampliacion de alcance se resolvera en
tickets nuevos y trazables; si una decision nueva limita o sustituye una
anterior, debe declararlo expresamente sin reescribir su historia.

**Skills a consultar**: `/grilling` para decisiones HITL y `/prototype` para
la interfaz desechable. La skill `/domain-modeling` recomendada por Wayfinder
no esta instalada; el modelado se apoya directamente en el esquema, codigo y
documentos de arquitectura del repositorio.

### Decisiones de encuadre confirmadas en el charting (2026-08-30)

Fijan la direccion del mapa; no son tickets cerrados.

- La superficie principal de series **genericas y reutilizables** es global
  para `analyst` y `admin`, pero cada serie conserva propietario, alcance y
  permisos.
- Hay dos alcances: `project` por defecto y `global` solo mediante promocion
  explicita de un administrador.
- Una señal generica individual es la unidad buscable y vinculable en el
  catalogo; el set conserva la frontera atomica de importacion, revision y
  auditoria.
- Tipo semantico (precio, demanda, afluente, etc.) y clase de datos (`real`,
  `forecast`, `programmed`, etc.) son dimensiones distintas.
- Los tipos semanticos viven en un catalogo de BBDD: tipos canonicos protegidos
  y tipos personalizados administrables con contrato completo.
- Las series genericas y los objetos se relacionan muchos-a-muchos mediante
  tablas de vinculos separadas; una serie generica no incorpora su objeto como
  propietario.
- Tambien se admite una serie **especifica de objeto**: el objeto debe existir
  primero, la definicion queda ligada obligatoriamente a ese objeto y no exige
  crear ni enlazar una entrada generica del catalogo.
- Una serie especifica se descubre y administra desde el contexto del objeto,
  queda en su alcance de proyecto y no aparece como candidata reutilizable en
  el catalogo global. Su definicion y sus valores deben poder crearse y
  actualizarse por API o mediante carga de archivos.
- Desde un objeto se deben poder cargar o actualizar valores de cualquiera de
  sus series asociadas. Si la serie es generica y compartida, el flujo debe
  hacer explicitos el permiso y el impacto sobre todos sus consumidores, y
  ofrecer el camino especifico cuando no se quiera modificar la fuente comun.
- Para series genericas hay dos capas distintas: asociacion de catalogo con
  objetos base y binding de ejecucion con una entidad activa de caso/variante.
  El nuevo modelo debe decidir como una serie especifica satisface el binding
  de su propio objeto sin fabricar una asociacion generica.
- Los objetos vinculables iniciales son señales globales, componentes
  (`grid`, carga, renovable, bateria e hidro) y entidades hidraulicas (sistema,
  nodo, tramo, planta y unidad). Proyecto, usuario, corrida, publicacion y
  consola no son destinos.
- Los objetos heterogeneos se representan mediante un registro padre comun
  con identidad estable y FK real desde los vinculos.
- La compatibilidad de tipo, unidad, objeto y alcance se rechaza de forma
  estricta tanto en UI como en backend.
- Una asociacion de catalogo sigue la identidad vigente de la serie; un binding
  ejecutable registra revision/hash y queda stale ante un cambio.
- Un objeto puede tener varias asociaciones del mismo tipo, pero solo un
  binding efectivo por variante, objeto y rol, salvo transformaciones
  multi-entrada declaradas.
- La interfaz permite iniciar el vinculo desde el catalogo o desde el objeto,
  y admite operaciones masivas con prevalidacion y guardado atomico.
- Reemplazar un binding requiere comparacion y confirmacion; el anterior queda
  en historial. Series y tipos usados se archivan, no se borran fisicamente.
- La navegacion separa entradas genericas, series especificas dentro de cada
  objeto, resultados read-only y legacy. Un resultado no se reutiliza como
  entrada sin una transformacion explicita.
- Las series hidraulicas legacy siguen visibles por adaptador y se migran bajo
  demanda; todo vinculo nuevo usa el modelo generico.
- La lista usa filtros y paginacion de servidor y nunca carga todos los puntos.
- Los filtros base cubren texto, tipo semantico, clase, proyecto/alcance,
  objeto vinculado, estado/origen, unidad, cobertura/resolucion y estado de
  vinculo o staleness.
- `analyst` vincula dentro de proyectos autorizados; `admin` administra tipos y
  promocion global; `external` (el reemplazo del rol legacy `client`) no accede
  al catalogo. Toda mutacion se audita.

### Hallazgos de codigo verificados en el charting

- `time_series_sets` ya es un catalogo generico **por proyecto** y guarda
  `data_kind`, timezone, estado, hash y version; sus revisiones son atomicas por
  set (`app/persistence.py`).
- `time_series_signals` guarda señales individuales dentro del set, pero el
  tipo canonico se expresa como `signal_key` y el alcance de entidad como texto.
- `TIME_SERIES_SIGNAL_CATALOG` es hoy un registro Python de ocho claves, no una
  tabla administrable (`app/time_series_catalog.py`).
- `case_time_series_bindings` referencia una variante, `time_series_set_id`,
  `signal_key` y un par textual `entity_type`/`entity_id`; no referencia
  directamente `time_series_signal_id`.
- La vista React actual lista sets de un solo proyecto. El editor de variantes
  ofrece todos los sets del proyecto en cada selector sin filtrar previamente
  por compatibilidad (`frontend/src/Workspace.tsx`).
- Las series hidraulicas legacy ya tienen adaptador y migracion bajo demanda.
  Los resultados viven en indices separados y reconstruibles; no deben
  fundirse fisicamente con las entradas.

## Decisiones tomadas

<!-- una linea por ticket cerrado: gist + link -->

- [Modelo relacional canonico para series, tipos y objetos vinculables](catalogo-global-series-genericas/01-modelo-relacional-canonico.md) — senales con identidad estable, revisiones completas e inmutables, catalogos persistentes, objetos mediante una union de FK tipadas y bindings que fijan revision/hash.

- [Contrato de compatibilidad entre tipos de serie y objetos](catalogo-global-series-genericas/02-compatibilidad-tipos-y-objetos.md) - roles desacoplados y matriz positiva tipo-rol-objeto, con unidad exacta, objetos normalizados, transformaciones materializadas y errores estables compartidos por UI y backend.

- [Ciclo de vida de asociaciones y bindings versionados](catalogo-global-series-genericas/03-ciclo-de-vida-asociaciones-y-bindings.md) - asociaciones que siguen la identidad vigente, bindings append-only a revision exacta, staleness fail-closed con pin explicito, auditoria, concurrencia y materializacion transaccional de snapshots inmutables.

- [Alcance global, permisos y promocion entre proyectos](catalogo-global-series-genericas/04-alcance-global-permisos-y-promocion.md) - propietario e identidad estables, uso `project` aislado por destino, publicacion global administrada, `external` sin acceso y despromocion fail-closed con historia intacta.

- [Contrato de consulta y API del catalogo global](catalogo-global-series-genericas/05-contrato-consulta-y-api-catalogo-global.md) - recursos separados para entradas, resultados y legacy, listas signal-first con cursores estables, previews acotados y mutaciones atomicas mediante prevalidacion, ETags e idempotencia.

- [Modelo y ciclo de vida de series especificas por objeto](catalogo-global-series-genericas/11-modelo-series-especificas-por-objeto.md) - raiz canonica compartida con propiedad inmutable del objeto, un set por serie, binding directo a revision/hash y separacion estructural del catalogo global.

- [API y carga de archivos desde series asociadas a objetos](catalogo-global-series-genericas/12-api-y-archivos-series-especificas.md) - rutas object-scoped tipadas, definicion local, ingesta JSON/CSV/XLSX en dos fases, impacto y confirmacion para fuentes compartidas, revisionado atomico y errores comunes.

- [Prototipo del catalogo global y la vinculacion contextual](catalogo-global-series-genericas/06-prototipo-catalogo-y-vinculacion.md) - C queda como patron unico de mutacion protegida, con exploracion densa de A, contexto objeto-necesidad-fuente de B y confirmacion reforzada para impacto compartido.

- [Migracion y coexistencia con el modelo actual](catalogo-global-series-genericas/07-migracion-y-coexistencia.md) - migracion expand/backfill/verificar/cutover sin dual-write prolongado, snapshots verificables, anomalias fail-closed, aliases temporales y rollback no destructivo por checkpoint.

- [Rendimiento, indices e integridad transaccional](catalogo-global-series-genericas/08-rendimiento-indices-e-integridad.md) - PostgreSQL productivo y SQLite de compatibilidad, proyeccion global transaccional, keyset e indices por consulta, publicacion staged copy-on-write y FK/triggers que impiden huerfanos o fugas object-scoped.

- [Corte de entrega y criterios de aceptacion](catalogo-global-series-genericas/09-corte-y-criterios-de-aceptacion.md) - una sola entrega visible hasta el cutover C6, con regla explicita de MVP, extensiones declaradas, matriz de 76 criterios observables en seis niveles de evidencia y disparadores de rollback con plazos.

- [Especificacion consolidada del catalogo global y series especificas](catalogo-global-series-genericas/10-especificacion-consolidada.md) - spec TS-7 en catorce capitulos con DDL consolidado, ambos caminos separados bajo las mismas garantias, trece precisiones declaradas entre resoluciones y la agrupacion sugerida de tickets `TS7-0NN`.

## Destino alcanzado

El mapa esta cerrado: no quedan tickets abiertos ni niebla. El destino es
[TS-7: Catalogo global de series genericas y series especificas por objeto](../series_tiempo/iter7/spec_ts7_catalogo_global_y_series_especificas.md),
que enlaza las once resoluciones sin reescribirlas.

El paso siguiente ya no es Wayfinder: convertir ese spec en tickets de
implementacion con prefijo `TS7-0NN`.

## Not yet specified

- Ninguno.

## Out of scope

- Implementar el frontend, backend o migraciones durante este mapa.
- Cambiar la matematica del optimizador o agregar señales que exijan un nuevo
  contrato Julia.
- Permitir acceso de usuarios `external` al catalogo o a bindings internos.
- Usar directamente resultados de corridas como inputs sin una transformacion
  versionada y auditable.
- Eliminar automaticamente tablas legacy o reescribir snapshots historicos.
- Convertir proyectos, usuarios, corridas, publicaciones o consolas en objetos
  vinculables en la primera entrega.
- Constructor libre de taxonomias sin validacion, formulas ejecutables o tipos
  de objeto definidos solo por texto.
- Vistas guardadas, dashboards analiticos del catalogo y exportaciones masivas;
  son mejoras posteriores al flujo base de buscar y vincular.
