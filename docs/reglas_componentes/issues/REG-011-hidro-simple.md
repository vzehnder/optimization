# REG-011: Usar reglas Python en componentes hidro del modelo v2

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: [Plan](../plan.md), secciones 2, 5 y 6.
User stories covered: HU-11.

## What to build

Llevar el mismo recorrido de reglas al componente `hydro` del modelo de despacho
v2: caudal turbinado, vertimiento, potencia y volumen almacenado. El analista
reutiliza operadores y plantillas compatibles sin conocer la diferencia entre
adaptadores Julia. La integración respeta el balance eléctrico y las relaciones
hidráulicas que ese modelo ya impone.

## Acceptance criteria

- [ ] La superficie contextual ofrece únicamente variables/unidades reales del componente v2; el contrato excluye altura/cota de la API inicial aunque el motor tenga detalles internos adicionales.
- [ ] Los mismos puertos, parámetros, operadores, revisiones y permisos atraviesan editor, API, materialización, carga/normalización y solve v2.
- [ ] Un pin registra tipo/esquema de objeto y capacidades requeridas; no se interpreta una identidad v3 como si fuera un componente v2.
- [ ] Restricciones afines se agregan sobre variables existentes conservando curvas/modos y balances base; no amplían el soporte de curvas ni suprimen binarias internas.
- [ ] Plantillas compatibles pueden aplicarse mediante remapeo explícito; una capacidad no soportada se rechaza antes del solve con explicación visible.
- [ ] El snapshot y resultados identifican el adaptador/contrato usado; un motor antiguo no puede ignorar el bloque de reglas.
- [ ] Casos v1/v2 sin reglas y casos hidráulicos v3 conservan su comportamiento; las pruebas cubren ambos caminos y sus lectores de contrato.

## Demonstration and validation

Aplicar una regla de caudal horario a un hidro v2 y comprobar potencia, volumen
y balance eléctrico de la solución. Reutilizar la intención de una plantilla
v3 con selección explícita del objeto v2; rechazar mezcla de referencias de
dos snapshots. Probar roundtrip/solve Julia y el recorrido contextual real.

## Blocked by

- [REG-004](REG-004-relacionar-componentes-hidraulicos.md).
