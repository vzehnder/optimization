# MESA-004 · Consultar BESS, demanda y renovables por componente

Status: Done
Type: AFK
Triage: ready-for-agent
Assignee: Codex
Source: [Plan de implementación](../plan_implementacion.md)
User stories covered: HU-01, HU-03, HU-11

## What to build

Ampliar el recorrido de consulta a las familias eléctricas del caso. Usar los descriptores canónicos para distinguir disponibilidad renovable, demanda, parámetros BESS y salidas del optimizador. Incorporar esas series a pestañas y selectores, incluyendo resultados de una ejecución existente cuando corresponda.

## Acceptance criteria

- [x] Descubrir todas las instancias BESS, carga y generación renovable activas del contexto sin confundir nombres repetidos.
- [x] Consultar las entradas y parámetros existentes con unidades y procedencia, sin convertir escalares en series horarias ficticias.
- [x] Exponer carga/descarga, energía o SOC y generación usada/vertida solo cuando exista el resultado correspondiente.
- [x] Sin run o sin columna compatible, mostrar estado no disponible; no fabricar el perfil que dibuja el prototipo.
- [x] Los selectores de panel ofrecen solo series compatibles con el componente; gráficos y tablas conservan identidad y unidad.
- [x] Se preserva el comportamiento de casos v1/v2 existentes y se identifica el contrato soportado.
- [x] Una prueba real de consulta verifica al menos un BESS y un renovable con datos disponibles y salidas todavía ausentes.

## Blocked by

- [MESA-002 · Abrir un caso real y consultar demanda en la mesa](MESA-002-abrir-caso-y-demanda-real.md)

## Validación TDD

Interfaces acordadas: S1 + S2

Primer test: abrir un caso sin runs, ver disponibilidad renovable y comprobar que potencia de descarga BESS figura sin resultado; luego consultar un run existente por la interfaz pública.

Aplicar la [estrategia TDD](../validacion_tdd.md) y la definición de terminado del plan. Las interfaces S1/S2 y S3 condicional fueron confirmadas por el usuario el 2026-10-20; registrar en MESA-001 cualquier interfaz adicional antes de probarla. Cada ciclo implementa un solo comportamiento observable.

## Demostración de cierre

Cambiar entre BESS, demanda y renovables sin salir de la mesa, con datos reales y estados vacíos honestos.

## Evidencia y seguimiento

- Inicio: 2026-10-20. Siguiente entrega del tracker, solicitada por el usuario.
- Interfaces bajo prueba: S1 navegador y S2 HTTP, ya confirmadas en MESA-001.
- Evidencia: [doce ciclos rojo → verde, contrato, comandos y revisión AFK](../evidencia/MESA-004/validacion.md).
- Implementación: inventario eléctrico, entradas canónicas/legacy, parámetros
  escalares y resultados por activo con run/snapshot. Selección de run en la URL,
  estados no disponibles y conservación de vistas locales al cambiar ejecución.
- Validación: diez pruebas HTTP y tres de navegador nuevas. 93 Python OK y cinco
  PostgreSQL omitidas; 13 MESA, cuatro regresiones de navegador y 336 Vitest OK.
  Build, TypeScript, ESLint, OpenAPI y formato modificado OK. El check global
  conserva los 16 avisos de formato preexistentes documentados.
- Capturas revisadas: [eléctricas 1440×900](../evidencia/MESA-004/mesa-electricas-1440.png),
  [390 px](../evidencia/MESA-004/mesa-electricas-390.png) y
  [resultados](../evidencia/MESA-004/mesa-resultados-1440.png).
- Alcance: consulta de artefactos/índices persistidos, sin modificar el motor ni
  crear almacenamiento paralelo. Ejecución nueva y comparación siguen en sus tickets.
  Se reparó una fixture TS-4 que referenciaba una variante inexistente.
- Cierre: **Done**, Codex, 2026-10-20, tras revisión técnica AFK y visual.
  Siguiente entrega recomendada: MESA-005.
