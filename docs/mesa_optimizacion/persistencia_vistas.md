# Persistencia visual de MESA-003

La mesa conserva una configuración por usuario autenticado y caso. Cambiar de
variante vuelve a consultar sus series y reutiliza la disposición del mismo caso.
El servidor deriva el usuario de la sesión y valida que el caso corresponda al
escenario; no acepta un usuario indicado por el cliente.

## Contrato HTTP

`GET /api/scenarios/{scenario_id}/mesa/preferences?case_id=…` devuelve `case_id`,
`revision` y `configuration`. Sin un guardado previo, la revisión es cero y la
configuración contiene una pestaña «Vista general» vacía. Al abrir por primera
vez, la interfaz propone una vista de la primera demanda disponible.

`PUT` en la misma ruta recibe `expected_revision` y `configuration`. Requiere
sesión interna y CSRF. Un guardado incrementa la revisión; una revisión obsoleta
devuelve 409. La comparación se ejecuta en el UPDATE SQL dentro de la transacción,
también durante el primer guardado, para cubrir escritores de distintos procesos.

La configuración v1 contiene pestaña activa, pestañas ordenadas y sus paneles
ordenados. Cada pestaña conserva título y distribución (`1x1`, `1x2`, `2x2`,
`2x3`); cada panel conserva ID, título, modo y referencias de componente y señales.
El límite es 24 pestañas y seis paneles por pestaña. Reducir la distribución no
trunca el arreglo de paneles. Quitar una vista solo cambia este documento.

## Migración y separación de datos

El arranque de `AnalystStore` aplica la migración aditiva e idempotente
`mesa_preferences_v1`, registrada en `schema_migrations`. Crea `mesa_preferences`
con clave primaria `(user_id, case_id)`, revisión, JSON de configuración y fecha
de actualización UTC. Las referencias a usuarios y casos usan `ON DELETE CASCADE`.
No requiere backfill: los usuarios existentes reciben el valor inicial al leer.
La misma sentencia DDL sirve para SQLite y PostgreSQL.

El documento no almacena muestras, resultados, bindings, parámetros ni snapshots.
Sus referencias de componente no tienen borrado en cascada: si desaparece el
objeto, el panel conserva su identidad y queda disponible para reconfiguración.
No se modifican tablas hidráulicas ni el checkpoint hidráulico. Revertir el código
puede dejar esta tabla sin uso, conservando las preferencias para reinstalarlo.

Las pruebas de esta entrega observan la persistencia a través de HTTP y navegador,
incluyendo reinicio de una base SQLite en disco. La ejecución PostgreSQL se informa
por separado según la disponibilidad del entorno de pruebas.
