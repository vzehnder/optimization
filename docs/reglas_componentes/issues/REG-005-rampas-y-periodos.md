# REG-005: Expresar rampas y relaciones con períodos anteriores

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: [Plan](../plan.md), secciones 5 y 7.
User stories covered: HU-05.

## What to build

El analista escribe restricciones entre períodos, empezando por rampas de subida
y bajada de generación o caudal. Declara la política del primer período y
previsualiza cuáles están cubiertos. Las referencias temporales se compilan a
filas afines del mismo contrato y producen resultados observables en la corrida.

## Acceptance criteria

- [ ] El SDK permite referencias anteriores y diferencias con índices/instantes verificables; nunca interpreta un índice negativo como el último período.
- [ ] Las rampas declaran unidades como MW/h o m³/s por hora, verificadas contra variable y tiempo; las dos direcciones se expresan con restricciones afines separadas.
- [ ] El cálculo usa la distancia entre inicios de intervalos definida en el plan, también con duraciones variables; no asume siempre una hora.
- [ ] La política inicial es explícita: omitir visiblemente la primera comparación o proporcionar valor inicial con unidad e instante. No se inventa generación/caudal previo.
- [ ] Al cambiar horizonte se regeneran referencias y validación; el snapshot conserva política, valor inicial y grilla exactos.
- [ ] Preview y errores indican períodos afectados, referencias fuera del horizonte y dimensión incompatible; un solo período se resuelve según la política elegida.
- [ ] Julia respeta ambas rampas junto a las restricciones existentes, y la solución permite comprobar sus diferencias temporales.

## Demonstration and validation

Resolver tres intervalos con duraciones distintas y límites de subida/bajada
que modifiquen el despacho. Comparar omisión inicial frente a condición inicial
declarada. Probar horizonte de un período, índice inválido, cambio de rango y
roundtrip de las referencias temporales mediante API, UI y pruebas Julia.

## Blocked by

- [REG-004](REG-004-relacionar-componentes-hidraulicos.md).
