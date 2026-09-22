# REG-002: Aplicar un máximo de caudal Python en una corrida hidráulica

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: [Plan](../plan.md), secciones 4, 5, 6 y 9.
User stories covered: HU-01, HU-02, HU-09.

## What to build

Completar el primer recorrido hasta el optimizador: el analista escribe una
restricción afín que limita el caudal turbinado de una unidad v3 con un parámetro
escalar, publica una revisión, la aplica a una variante y ejecuta el caso.
La corrida demuestra que el límite personalizado modifica el resultado y deja
trazabilidad. El camino usa un contrato genérico de filas afines aunque esta
entrega solo exponga el caudal de una unidad.

## Acceptance criteria

- [ ] El SDK produce restricciones simbólicas mediante `<=`, `>=` y `==`, con nombres y referencias de origen; nunca las evalúa como booleanos Python.
- [ ] Publicar crea una revisión inmutable; aplicar fija esa revisión, parámetros, objeto y variante. Desactivar registra actor/motivo y no borra historia.
- [ ] Preview muestra filas, unidades y alcance temporal; una regla sin filas requiere aceptación explícita antes de aplicarse como restricción.
- [ ] Servidor y Julia validan IR, coeficientes finitos, unidades y referencias a la unidad/grilla del snapshot. Un producto de decisiones o condición simbólica se rechaza.
- [ ] Materializar congela código, contexto, runtime e IR con hashes, comprueba concurrencia al confirmar y es atómico/idempotente; Python no se ejecuta dentro de Julia ni durante un reintento del mismo snapshot.
- [ ] JuMP agrega el límite junto a los límites y balances base. No se sustituye la capacidad física ni se omite una regla contradictoria.
- [ ] Una capacidad/versión desconocida, motor sin soporte, aplicación inválida u obsoleta bloquea antes de resolver. Los cambios de topología/parámetros/código publicado no actualizan pins automáticamente.
- [ ] Todos los productores de corridas preservan las reglas o bloquean con motivo; consolas/programaciones con reglas activas aún no soportadas bloquean. Desactivar la funcionalidad tampoco permite omitirlas.
- [ ] La pantalla de corrida permite identificar revisión de regla y parámetros usados; modelos sin reglas conservan su ejecución anterior.

## Demonstration and validation

En un caso de cuatro períodos con solución base por encima del límite elegido,
aplicar un máximo de 5 m³/s y comprobar caudales/resultado. Desactivar y recuperar
el comportamiento base. Verificar en Julia el efecto real, snapshots históricos,
roundtrip de IR, cambio concurrente y negativa de un motor viejo; completar la
prueba desde UI hasta resultados usando el runtime aislado.

## Blocked by

- [REG-001](REG-001-probar-regla-python.md).
