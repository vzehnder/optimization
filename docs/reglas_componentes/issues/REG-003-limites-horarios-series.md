# REG-003: Calcular mínimos y máximos horarios desde series versionadas

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: [Plan](../plan.md), secciones 5, 6 y 7.
User stories covered: HU-03, HU-09.

## What to build

Permitir seleccionar entradas del catálogo o del objeto para una regla y escribir
límites horarios calculados. El analista vincula afluente/disponibilidad, define
parámetros y compara las curvas calculadas antes de aplicarlas a una corrida.
La selección usa revisiones canónicas exactas y conserva sus reglas de propiedad,
compatibilidad y obsolescencia. Esta entrega completa el MVP de límites horarios.

## Acceptance criteria

- [ ] Cada puerto declara alias, dimensión/semántica y contexto de objeto; la selección persiste identidad, revisión sellada y hash mediante el contrato canónico.
- [ ] La UI ofrece solo entradas autorizadas/compatibles y distingue series genéricas de específicas. La API vuelve a verificar pertenencia, revisión y hash.
- [ ] Python combina entradas y parámetros por período; la preview muestra mínimos, máximos y salidas numéricas en tabla/gráfico con unidades, sin publicar series todavía.
- [ ] Se comprueba toda la grilla: faltantes, duplicados, duración incompatible, cobertura insuficiente, valores no finitos y unidades incompatibles bloquean con período/alias. No hay resampling o relleno implícito.
- [ ] Un mínimo mayor que un máximo conocido para la misma variable/período se identifica antes del solve, incluyendo la intersección con límites físicos conocidos; no se promete detectar toda infactibilidad.
- [ ] Una publicación nueva de una entrada vuelve obsoleta la validación; no mueve el pin. Revalidar la revisión antigua con motivo o seleccionar otra produce nueva evidencia antes de ejecutar.
- [ ] Las restricciones horarias llegan a Julia y el snapshot conserva entradas, cálculos, parámetros y lineage; cambios posteriores no alteran una corrida guardada.
- [ ] La clasificación añade únicamente las unidades/tipos necesarios que falten, de forma aditiva y compatible con TS-7.
- [ ] Un horizonte anual dentro de cuotas y otro que las exceda tienen comportamiento medido y acotado; preview paginada y cancelación no truncan la validación real.

## Demonstration and validation

Calcular máximo como capacidad por disponibilidad y mínimo como fracción de un
afluente permitido por el puerto. Resolver y comprobar ambos límites por período.
Introducir un hueco, una revisión nueva y un cruce mínimo/máximo; verificar los
tres bloqueos en UI/API. Probar persistencia en ambos motores, resultados Julia,
concurrencia durante compilación y mediciones del runtime real.

## Blocked by

- [REG-002](REG-002-aplicar-limite-caudal.md).
