# REG-006: Limitar agua y energía por horizonte o día civil

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: [Plan](../plan.md), secciones 5 y 7.
User stories covered: HU-06.

## What to build

Permitir que una regla imponga un presupuesto sobre integrales de caudal o
potencia en el horizonte completo o en días civiles de una zona horaria elegida.
El analista ve ventanas, unidades y presupuesto efectivo antes de aplicar;
el solver recibe la suma afín ponderada por duración.

## Acceptance criteria

- [ ] El SDK ofrece ventanas reproducibles sobre la grilla y sumas afines; la configuración guarda zona IANA y política de ventanas parciales.
- [ ] La integración de MW por horas produce MWh; m³/s por segundos produce m³ y admite conversión explícita a hm³. No se suma potencia/caudal sin duración como si fuera energía/volumen.
- [ ] Días de 23/25 horas usan sus intervalos reales; la zona local sirve para agrupar, manteniendo identidades UTC en el snapshot.
- [ ] Bordes de ventana desalineados con intervalos bloquean en esta versión. Días parciales requieren aceptación explícita de la ventana parcial y no prorratean el presupuesto.
- [ ] Preview muestra inicio/fin, duración, términos incluidos, unidad y presupuesto de cada fila; ausencia de períodos o unidades incorrectas produce error localizado.
- [ ] La regla puede agregar uno o varios componentes ya soportados; se conserva la atribución de términos y la política temporal en lineage.
- [ ] Julia aplica las sumas y la solución satisface el presupuesto dentro de tolerancias, sin alterar balances ni el objetivo.

## Demonstration and validation

Limitar un volumen diario de turbinado y una energía total; comparar contra un
caso sin esas reglas. Cubrir duración variable, cambio horario, ventana parcial
y límites de día que corten un intervalo. Comprobar conversiones con valores
calculables a mano, además del recorrido real desde UI hasta solver.

## Blocked by

- [REG-004](REG-004-relacionar-componentes-hidraulicos.md).
