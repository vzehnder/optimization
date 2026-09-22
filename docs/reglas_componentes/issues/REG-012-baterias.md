# REG-012: Restringir carga, descarga y energía de baterías

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: [Plan](../plan.md), secciones 5, 6 y 7.
User stories covered: HU-03, HU-11.

## What to build

Exponer carga, descarga y energía almacenada de baterías como capacidades del
SDK. Un analista define una reserva horaria de energía o limita carga/descarga
con entradas conocidas, aplica la regla a una variante y observa su efecto en
el despacho. No necesita una API Python distinta a la de hidráulica.

## Acceptance criteria

- [ ] El editor y API exponen potencia de carga/descarga en MW y energía al final del período en MWh, con signos y convención temporal explícitos.
- [ ] Parámetros y series de energía se validan mediante clasificación canónica; las semillas faltantes se incorporan aditivamente sin eludir compatibilidad.
- [ ] Se puede imponer una reserva horaria de energía y límites afines de carga/descarga desde un código versionado con preview y aplicación trazable.
- [ ] La integración mapea a variables existentes y conserva eficiencias, balances, degradación, restricciones de simultaneidad y condición terminal del modelo base.
- [ ] No se habilitan variables binarias de usuario ni un producto entre variables por soportar baterías; se mantiene el rechazo matemático común.
- [ ] Las reglas pueden relacionar la batería con otro componente ya soportado del mismo snapshot; objetos de otros modelos se rechazan.
- [ ] Cambios de capacidad, objeto o entradas invalidan validación según el contrato común; los resultados históricos mantienen su interpretación.

## Demonstration and validation

En un caso de arbitraje, aplicar una reserva de MWh variable por hora que cambie
la descarga. Comprobar el balance con eficiencias y la condición terminal;
introducir una reserva superior a capacidad y comprobar diagnóstico/bloqueo
cuando sea deducible. Verificar el flujo completo y la regresión del caso sin reglas.

## Blocked by

- [REG-011](REG-011-hidro-simple.md).
