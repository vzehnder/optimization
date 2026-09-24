# REG-009: Comparar revisiones y resolver aplicaciones obsoletas

Status: Done
Type: AFK
Triage: ready-for-agent
Source: [Plan](../plan.md), secciones 4, 6 y 9.
User stories covered: HU-09.

## What to build

Completar la recuperación guiada de reglas que ya bloquean correctamente desde
las primeras entregas. El analista compara código, parámetros, entradas y objetos,
elige mantener una revisión antigua o adoptar otra, prueba el resultado y aplica
el cambio con motivo. Puede consultar el historial y recuperar una revisión
anterior sin sobrescribir ninguna corrida.

## Acceptance criteria

- [x] La lista contextual distingue borrador, publicada, archivada y estado de cada aplicación; muestra causas concretas de obsolescencia/invalidación calculadas en servidor.
- [x] La comparación incluye código/SDK, parámetros, revisiones de fuentes, unidades, horizonte y referencias de objeto relevantes; no se limita a un diff textual.
- [x] Mantener un pin antiguo requiere revalidar contra el contexto actual y dejar motivo; una incompatibilidad real no se resuelve solo aceptando un aviso.
- [x] Reemplazar una revisión y sus mapeos es atómico, usa concurrencia optimista, y mantiene el evento/aplicación anterior como historia consultable.
- [x] Un cambio entre preview y confirmación se rechaza con conflicto. Publicar o editar un borrador no modifica silenciosamente las aplicaciones existentes.
- [x] Archivar evita aplicaciones nuevas, conserva referencias y presenta acciones explícitas a consumidores vigentes; no se elimina contenido usado por corridas.
- [x] La recuperación histórica crea una nueva aplicación/evento o revisión, y no altera datos de snapshots anteriores ni presupone que su contexto sigue siendo válido.
- [x] El historial permite ir desde una corrida a las revisiones y hashes exactos consumidos, incluso cuando las definiciones actuales cambiaron.

## Demonstration and validation

Con dos instancias de una plantilla, publicar nueva revisión; mantener una antigua
con motivo y actualizar la otra. Introducir un cambio incompatible de objeto y
comprobar que no admite aceptación ciega. Probar carreras de edición, archivo,
reintento idempotente y consulta de corrida histórica en ambos motores de BBDD.

## Blocked by

- [REG-003](REG-003-limites-horarios-series.md).
- [REG-008](REG-008-reutilizar-reglas.md).

## Fronteras TDD y entrega

Se reutilizan las fronteras confirmadas por el usuario en REG-008: HTTP sobre
SQLite/PostgreSQL, runtime OCI real, React/navegador y snapshot consumido por
Julia. Los ciclos rojo → verde cubren archivo, conservación y sustitución de pins,
reintento idempotente, comparación estructurada, incompatibilidades, mapeos,
historial y detalle de la revisión consumida por una corrida.

El recorrido «Comparar y recuperar revisiones» mantiene la aplicación vigente
hasta confirmar una prueba nueva. La confirmación verifica definición,
publicación, aplicación, fuentes, objetos, horizonte y runtime; actualiza los mapeos y
la revisión local en la misma transacción que conserva la aplicación anterior y
crea la nueva. Los eventos incluyen actor, motivo y aplicación de origen.
Archivar conserva revisiones y enlaces a consumidores, y exige resolución explícita.

## Evidencia de verificación (2026-09-24)

- **30 pruebas HTTP con OCI real**: conservación del pin, adopción con valores locales,
  restauración histórica, archivo, consumidor incompatible, concurrencia,
  idempotencia, fuentes e imagen del runtime que cambian durante la prueba,
  bloqueo de clones tras archivo y límites de proyecto/rol.
  Cada caso se ejecuta sobre SQLite y PostgreSQL en bases exclusivas de pruebas.
- **75 pruebas distintas de regresión de REG-001 a REG-008** comprobadas.
  La tanda inicial pasó 73 y omitió los 75 duplicados PostgreSQL. Se actualizó
  la expectativa de la lista contextual al nuevo contrato y se verificó de nuevo.
  Ante una respuesta 404 transitoria en la prueba concurrente, se protegieron
  también las lecturas iniciales de aplicación bajo el bloqueo de conexión;
  cinco repeticiones posteriores de esa prueba pasaron.
- **144 pruebas React** aprobadas en once archivos. Los cinco casos del nuevo
  panel se volvieron a comprobar al completar unidades, alias y expresiones.
- **50 comprobaciones Julia** aprobadas en `test/component_rules.jl`.
- **Chromium con API, OCI y Julia reales**: dos instancias parten en 17 m³/s;
  Norte conserva su pin, Sur adopta la nueva revisión y ambas resuelven 11 m³/s;
  recuperar la aplicación histórica de Sur devuelve 17 m³/s. La corrida
  inicial y sus hashes permanecen intactos. El archivo bloquea nuevas corridas
  y presenta acciones explícitas. Capturas de comparación e historial revisadas.
- Build, TypeScript, ESLint, contrato OpenAPI regenerado/`api:check`, compilación
  Python y `git diff --check` aprobados. Prettier de archivos modificados aprobado;
  `npm run check` completo sigue detectando formato preexistente en 17 archivos
  ajenos a la entrega, como en REG-007/008.

El SDK sigue en `reg-006.1`; no se cambió la matemática ni la imagen OCI fijada
por digest. No se ejecutó CI remoto ni se modificaron bases de proyectos reales.
La siguiente entrega por orden es REG-010.
