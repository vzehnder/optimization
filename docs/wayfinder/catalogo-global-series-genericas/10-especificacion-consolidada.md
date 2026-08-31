---
id: 10
title: "Especificacion consolidada del catalogo global y series especificas"
map: catalogo-global-series-genericas
label: wayfinder:task
status: closed
assignee: claude
blocked_by: [01, 02, 03, 04, 05, 06, 07, 08, 09, 11, 12]
---

## Question

Nada que decidir: consolidar las resoluciones del mapa en el documento que es
su destino.

El spec final debe incluir modelo relacional y diagrama, catalogos y reglas de
compatibilidad, contratos de API, permisos, auditoria y ciclo de vida,
comportamiento de las superficies aceptadas en el prototipo, estrategia de
migracion/coexistencia, rendimiento e indices, criterios de aceptacion y fuera
de alcance. Debe enlazar las resoluciones en vez de inventar decisiones nuevas.

Debe presentar por separado, pero bajo las mismas garantias de revision y
auditoria, el camino de series genericas reutilizables y el de series
especificas creadas desde un objeto. El segundo debe incluir el orden de alta,
persistencia object-scoped, API, archivos, actualizacion, lectura, binding y
retiro sin depender del catalogo global.

Al cerrar este ticket, el paso siguiente deja de ser Wayfinder: convertir el
spec aceptado en tickets de implementacion.

## Activo entregado

- [TS-7: Catalogo global de series genericas y series especificas por objeto](../../series_tiempo/iter7/spec_ts7_catalogo_global_y_series_especificas.md)

Se ubica en `docs/series_tiempo/iter7/` siguiendo la convencion de iteraciones
del repositorio (iter1 a iter6), para que quede junto al material que los
tickets de implementacion consultan. El mapa y sus tickets siguen viviendo en
`docs/wayfinder/` y el spec los enlaza uno por uno.

## Resolucion

Resuelto el 2026-08-30. Tarea de consolidacion: no se tomo ninguna decision
nueva.

### Que consolida

El spec tiene catorce capitulos mas un indice de trazabilidad que enlaza las
once resoluciones cerradas del mapa y el activo del prototipo:

1. vocabulario y separacion de dimensiones;
2. modelo relacional canonico, con diagrama y DDL consolidado;
3. contrato de compatibilidad, matriz inicial, evaluador y codigos;
4. ciclo de vida de asociaciones y bindings, staleness y materializacion;
5. alcance, permisos, promocion y despromocion;
6. camino A, la API del catalogo global de series genericas;
7. camino B, las series especificas por objeto con su API y carga de archivos;
8. experiencia aceptada del prototipo;
9. rendimiento, indices e integridad;
10. migracion y coexistencia C0 a C7;
11. corte de entrega y la matriz completa de aceptacion;
12. fuera de alcance;
13. precisiones y sustituciones entre resoluciones;
14. agrupacion sugerida de los tickets `TS7-0NN`.

Los dos caminos se presentan por separado, con su propia superficie e
identidad, pero bajo las mismas garantias de revision inmutable, compatibilidad
fail-closed y auditoria. El camino especifico incluye el orden completo objeto
existente, definicion local, ingesta por API o archivo, publicacion sellada,
lectura, binding directo y archivado, sin depender del catalogo global.

### Regla de precedencia declarada

El spec fija que la fuente autoritativa siempre es la resolucion enlazada, que
su capitulo 13 dice cual gana cuando dos se solapan, y que el spec no puede
ampliar ni relajar ninguna de las dos.

### DDL consolidado en lugar de cadenas de ALTER

El capitulo 2 presenta el punto fijo de todos los `ALTER` de 02, 03, 04, 07, 08,
11 y 12 sobre el DDL base de 01. Los `ALTER` originales quedan en cada ticket
como historia. Esto evita que un ticket de implementacion tenga que reconstruir
el esquema leyendo siete resoluciones en orden.

### Precisiones y sustituciones registradas

Se registran trece precisiones entre resoluciones (P-01 a P-13), cada una con la
resolucion que precisa y la que resulta precisada. Las mas relevantes:

- `time_series_binding_roles.semantic_type_id` se retira; el rol se desacopla
  del tipo semantico y la relacion vive en la matriz positiva.
- La asociacion incorpora `binding_role_id`, cambiando su unicidad activa.
- `content_hash` es nulo mientras la revision esta `building`.
- El invariante de una sola senal por set `object_specific` se implementa con
  indice parcial unico y FK diferible, no con un constraint trigger de conteo.
- El estado `legacy_unmaterialized` limita, solo para historia heredada sin
  datos y nunca ejecutable, la afirmacion de que toda fila de revisiones es una
  fotografia completa.
- El rol legacy `client` ya no existe: todo requisito historico se aplica a
  `external`.

Se declaran ademas dos puntos que ninguna resolucion fijo literalmente y que la
implementacion resuelve sin reabrir una decision: la forma exacta del `CHECK` de
`content_hash` para `legacy_unmaterialized`, y el nombre fisico final de las
tablas `ts_next` tras la contraccion, que 07 ya declaro fuera del contrato de
API.

### Consecuencias

Este ticket cierra el mapa. El paso siguiente deja de ser Wayfinder: es
convertir el spec en tickets de implementacion `TS7-0NN`, en el orden que impone
la migracion. El capitulo 14 propone trece agrupaciones. Ningun ticket de
implementacion puede reabrir una decision del spec sin volver al mapa y
registrar la sustitucion.
