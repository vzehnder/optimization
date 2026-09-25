# REG-012: Restringir carga, descarga y energía de baterías

Status: Done
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

- [x] El editor y API exponen potencia de carga/descarga en MW y energía al final del período en MWh, con signos y convención temporal explícitos.
- [x] Parámetros y series de energía se validan mediante clasificación canónica; las semillas faltantes se incorporan aditivamente sin eludir compatibilidad.
- [x] Se puede imponer una reserva horaria de energía y límites afines de carga/descarga desde un código versionado con preview y aplicación trazable.
- [x] La integración mapea a variables existentes y conserva eficiencias, balances, degradación, restricciones de simultaneidad y condición terminal del modelo base.
- [x] No se habilitan variables binarias de usuario ni un producto entre variables por soportar baterías; se mantiene el rechazo matemático común.
- [x] Las reglas pueden relacionar la batería con otro componente ya soportado del mismo snapshot; objetos de otros modelos se rechazan.
- [x] Cambios de capacidad, objeto o entradas invalidan validación según el contrato común; los resultados históricos mantienen su interpretación.

## Demonstration and validation

En un caso de arbitraje, aplicar una reserva de MWh variable por hora que cambie
la descarga. Comprobar el balance con eficiencias y la condición terminal;
introducir una reserva superior a capacidad y comprobar diagnóstico/bloqueo
cuando sea deducible. Verificar el flujo completo y la regresión del caso sin reglas.

## Blocked by

- [REG-011](REG-011-hidro-simple.md).

## Fronteras TDD confirmadas (2026-09-24)

El usuario confirmó pruebas de comportamiento en las tres interfaces: API HTTP
autenticada con persistencia y OCI real, entrada/salida pública de Julia, y UI
React con un recorrido real de navegador. La implementación siguió ciclos
rojo → verde de una capacidad a la vez.

## Implementación

El acceso contextual de la batería guardada ofrece `carga`, `descarga` y
`energia`, más `energia_inicial` como dato conocido tipado. El editor incluye
ejemplos de reserva, rampas y presupuestos; los selectores muestran MWh y fijan
la revisión canónica. La semántica `battery_energy_reserve` y el rol
`rule_energy_reserve` se incorporan por clave, conservando clasificaciones existentes.

El adaptador `battery_system.v1` soporta baterías de sistemas v1/v2 y relaciones
con hidros del mismo snapshot v2. Julia agrega restricciones sobre las variables
existentes y conserva el modelo físico. Los pins registran esquema, identidad,
capacidades y hashes; se verifica soporte del motor antes de resolver. Biblioteca,
clonación, obsolescencia y cumplimiento usan los contratos comunes.

El SDK pasa a `reg-012.1`; requiere reconstruir la imagen OCI y reiniciar el
worker con su digest. Las aplicaciones anteriores requieren publicar, probar y
aplicar de nuevo; los resultados históricos siguen usando sus snapshots.
Las transiciones de energía usan cierres de intervalo: desde el inicio del
horizonte, intervalos de 0,5 y 1,5 horas producen esas mismas distancias.
Las rampas de potencia siguen midiendo distancias entre inicios.

## Evidencia de entrega

- **26 pruebas nuevas HTTP aprobadas**, 13 por motor SQLite/PostgreSQL, con OCI
  real y sin omisiones. La pasada final con la imagen reconstruida tomó 183 s.
  Cubren clasificación, reservas, parámetros, límites físicos, errores matemáticos,
  alias, pins, historial, obsolescencia, biblioteca, clonación y referencias temporales.
- **635 comprobaciones Julia aprobadas**: 25 nuevas, 50 de reglas hidráulicas,
  24 de hidro simple, 4 de resultados primales y 532 generales. Se verifican
  intervalos desiguales, presupuestos, relaciones batería/hidro, roundtrip y caso base.
- **38 pruebas React aprobadas** en los módulos afectados, además de build,
  TypeScript y ESLint. La prueba nueva se repitió tras la aclaración temporal.
- **Chromium real aprobado** con API, OCI y Julia sobre una base temporal, en
  2,6 minutos. Reserva `[0; 4; 1; 2]` MWh y límite conjunto de 3 MW producen
  energía `[4,4; 4; 1; 2]` MWh y descarga `[0; 0,36; 2,7; 0]` MW. El objetivo
  de 208,95 USD incluye degradación; conserva eficiencias y 2 MWh terminales.
  El informe muestra ocho restricciones evaluadas y cumplidas. Capturas
  `frontend/test-results/reg012-applied.png` y `reg012-compliance.png` inspeccionadas.
- **26 pruebas de regresión REG-011 aprobadas** en SQLite/PostgreSQL con OCI.
  La regresión adicional de runtime, reutilización, revisiones, cumplimiento y
  catálogo ejecutó 125 casos: 77 aprobados, 47 duplicados PostgreSQL omitidos y
  una expectativa antigua del catálogo corregida. La repetición del catálogo y
  de la instalación aditiva aprobó sus 20 pruebas, incluyendo PostgreSQL.
  OCI procesó 8784 períodos y 17568 filas/salidas en 4,557 s y rechazó 8785 períodos.
- OpenAPI regenerado, `api:check`, compilación Python, `git diff --check` y
  Prettier de archivos modificados aprobados. El chequeo global de formato
  señala los mismos 17 archivos preexistentes documentados en REG-011.

CI incluye HTTP, React, Julia y navegador de esta entrega; no se ejecutó CI remoto.
[Operación y reproducción](../runtime.md). La siguiente issue por orden es
**REG-013: red y renovables**.
