# REG-008: Reutilizar una regla parametrizada en varios componentes

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: [Plan](../plan.md), secciones 4 y 5.
User stories covered: HU-08.

## What to build

Un analista convierte una definición en plantilla reutilizable dentro del
proyecto y la aplica a varios componentes compatibles. El código y contrato de
puertos se comparten por revisión; cada instancia conserva sus propios parámetros,
alias, entradas, variante y activación. La biblioteca ofrece ejemplos editables
de las capacidades ya implementadas, no una segunda representación del modelo.

## Acceptance criteria

- [ ] La biblioteca del proyecto permite descubrir una regla por nombre, revisión, capacidades requeridas y tipos compatibles, sin exponer contenido a externos.
- [ ] Aplicar a otro componente crea una instancia independiente de la misma revisión; no copia referencias al componente original silenciosamente.
- [ ] El formulario solicita los puertos/alias y parámetros tipados obligatorios; las opciones se filtran por capacidades del motor y contexto del nuevo objeto.
- [ ] La previsualización muestra diferencias entre instancias y sus filas efectivas; cambiar un parámetro local no modifica código ni otras aplicaciones.
- [ ] Varias instancias de la misma regla coexisten con identificadores de restricción únicos, lineage y activación independientes.
- [ ] Publicar otra revisión conserva todas las asignaciones fijadas y marca las afectadas para resolución; no actualiza código ejecutado por todas las centrales de forma automática.
- [ ] Copiar o clonar una variante conserva pins, exige remapear objetos inexistentes y deja constancia de origen; no hereda una validación válida si cambió el contexto.
- [ ] Aplicaciones a tipos incompatibles, otro proyecto o alias faltantes se rechazan también por API.

## Demonstration and validation

Aplicar la misma regla de caudal a dos unidades con capacidades distintas.
Modificar parámetros de una y comprobar resultados independientes. Publicar
una revisión nueva y comprobar pins/obsolescencia. Verificar el flujo de biblioteca,
concurrencia al aplicar y la ausencia de colisiones en la IR y en JuMP.

## Blocked by

- [REG-004](REG-004-relacionar-componentes-hidraulicos.md).
