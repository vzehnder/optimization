# REG-013: Relacionar generación renovable e intercambio con la red

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: [Plan](../plan.md), secciones 5 y 6.
User stories covered: HU-04, HU-11.

## What to build

Completar una relación eléctrica personalizada dentro de un mismo caso: usar
generación renovable utilizada/recortada e importación/exportación de red en
expresiones afines. Un ejemplo demostrable limita la exportación a una fracción
conocida de la generación renovable utilizada.

## Acceptance criteria

- [ ] El editor ofrece las cuatro capacidades con unidades MW y convención de magnitudes no negativas; cualquier expresión neta declara su signo.
- [ ] La disponibilidad renovable se expone como dato conocido, no se confunde con generación elegida por el solver. La demanda fija tampoco se presenta como decisión libre.
- [ ] El analista selecciona alias de red y renovable, parámetros/series, prueba la relación y la aplica a una variante mediante el flujo común.
- [ ] Julia agrega la relación sobre variables reales y conserva balance eléctrico, disponibilidad, límites base de red y exclusión de simultaneidad cuando esté configurada.
- [ ] Solo se combinan componentes del mismo snapshot; no se inventa acoplamiento eléctrico entre el sistema v3 separado y un despacho v1/v2.
- [ ] Unidades, referencias, pins y cambios de contexto usan los mismos validadores y lineage; una relación no lineal se rechaza como en hidráulica.
- [ ] Los resultados muestran el efecto conjunto sobre exportación, generación y recorte, y los casos sin reglas siguen iguales.

## Demonstration and validation

Aplicar un límite de exportación igual a una fracción de la generación utilizada
en un caso con excedentes; comprobar la ecuación y el balance, no solo la curva
de exportación. Probar orientación de signos, referencias cruzadas inválidas
y el flujo web a solve con las mismas garantías de contrato.

## Blocked by

- [REG-011](REG-011-hidro-simple.md).
