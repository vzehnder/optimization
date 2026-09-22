# REG-009: Comparar revisiones y resolver aplicaciones obsoletas

Status: Todo
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

- [ ] La lista contextual distingue borrador, publicada, archivada y estado de cada aplicación; muestra causas concretas de obsolescencia/invalidación calculadas en servidor.
- [ ] La comparación incluye código/SDK, parámetros, revisiones de fuentes, unidades, horizonte y referencias de objeto relevantes; no se limita a un diff textual.
- [ ] Mantener un pin antiguo requiere revalidar contra el contexto actual y dejar motivo; una incompatibilidad real no se resuelve solo aceptando un aviso.
- [ ] Reemplazar una revisión y sus mapeos es atómico, usa concurrencia optimista, y mantiene el evento/aplicación anterior como historia consultable.
- [ ] Un cambio entre preview y confirmación se rechaza con conflicto. Publicar o editar un borrador no modifica silenciosamente las aplicaciones existentes.
- [ ] Archivar evita aplicaciones nuevas, conserva referencias y presenta acciones explícitas a consumidores vigentes; no se elimina contenido usado por corridas.
- [ ] La recuperación histórica crea una nueva aplicación/evento o revisión, y no altera datos de snapshots anteriores ni presupone que su contexto sigue siendo válido.
- [ ] El historial permite ir desde una corrida a las revisiones y hashes exactos consumidos, incluso cuando las definiciones actuales cambiaron.

## Demonstration and validation

Con dos instancias de una plantilla, publicar nueva revisión; mantener una antigua
con motivo y actualizar la otra. Introducir un cambio incompatible de objeto y
comprobar que no admite aceptación ciega. Probar carreras de edición, archivo,
reintento idempotente y consulta de corrida histórica en ambos motores de BBDD.

## Blocked by

- [REG-003](REG-003-limites-horarios-series.md).
- [REG-008](REG-008-reutilizar-reglas.md).
