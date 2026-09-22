# REG-004: Relacionar unidades, plantas y embalses del mismo modelo

Status: Done
Type: AFK
Triage: ready-for-agent
Source: [Plan](../plan.md), secciones 2, 5 y 6.
User stories covered: HU-04.

## What to build

Un analista agrega alias hacia otros objetos presentes en el mismo snapshot
hidráulico y formula relaciones afines entre caudal/potencia de unidades y
almacenamiento/vertimiento de embalses. Puede limitar la suma de generación de
dos unidades o usar la generación agregada de una planta. Una relación dentro
de un único componente usa los mismos operadores y validación.

## Acceptance criteria

- [x] El editor descubre variables y unidades por tipo de objeto y capacidad real del motor; no muestra caudal genérico de tramo ni cota v3 como variable de decisión.
- [x] Se guardan alias de objetos con identidades estables, y se verifica que todos pertenecen al mismo snapshot/modelo, no solamente al mismo proyecto.
- [x] Las expresiones admiten suma/resta, coeficientes conocidos y relaciones afines; la preview identifica todos los objetos que afecta una fila.
- [x] La potencia de planta se expande a la suma de las unidades de su snapshot sin crear otra variable física; cambios de membresía invalidan la aplicación validada.
- [x] Parámetros y puertos de entrada asociados a un objeto referenciado respetan su contexto de propiedad, permisos y compatibilidad TS-7.
- [x] Todas las reglas activas se intersectan sin prioridad de reemplazo. Identificadores de fila incluyen la instancia para evitar colisiones entre reglas.
- [x] Referencias eliminadas, otro proyecto, otro caso incompatible y operaciones no afines bloquean con alias y línea cuando esté disponible.
- [x] Julia aplica las filas a las variables reales y la corrida conserva mapa de alias y objetos para su interpretación histórica.

## Demonstration and validation

Fronteras TDD: se reutilizan las interfaces confirmadas en REG-002/003 — HTTP
autenticado con SQLite/PostgreSQL, editor React, runtime OCI real y carga/solve
públicos de Julia. Los casos nuevos comprueban referencias dentro del modelo,
potencia conjunta, expansión de planta, almacenamiento y snapshots históricos.

Dos unidades capaces de producir más de 10 MW en conjunto reciben un límite
compartido de 10 MW; verificar la suma y no un límite independiente por unidad.
Repetir con el alias de planta. Probar una relación lineal con almacenamiento,
una referencia externa y un cambio de membresía, desde selección hasta solve.

## Evidencia de implementación (2026-09-22)

Implementado con ciclos rojo → verde en las fronteras anteriores. El editor
conserva alias por ID, descubre variables con sus unidades y permite asociar
parámetros y entradas al objeto referenciado. La API valida pertenencia activa
al caso y propiedad TS-7; el SDK `reg-004.1` emite `affine_hydraulic.v1` para
relaciones ampliadas y conserva `affine_flow.v1` para reglas locales de caudal.
Julia enlaza cada término con las variables físicas existentes. Se preservan
alias, miembros de planta, entradas y código en los snapshots históricos.

- REG-004: **19 pruebas Python** entre HTTP SQLite/PostgreSQL y contenedor OCI
  real. Comprueban selección, IDs estables, otro caso/proyecto, propiedad de
  series específicas, parámetros `hm3`, capacidad física de almacenamiento,
  capacidad declarada del motor y obsolescencia sin alterar el historial.
- Regresión Python: **121 pruebas distintas aprobadas sin omisiones**, contando
  REG-001 a REG-004 y el catálogo TS7-001. La tanda de 112 detectó dos expectativas
  del contrato anterior de parámetros; se actualizaron para el campo opcional
  `object_id` y ambas pasaron junto a las nueve pruebas restantes. La compilación
  anual completa de 8784 períodos pasó en **4.423 s**; 8785 se rechazaron en
  **3.780 s**, tiempos locales de pared del ejecutor OCI.
- Julia 1.11.7/HiGHS: **29 comprobaciones** en `test/component_rules.jl`.
  Dos unidades comparten **10 MW** por período; otra aplicación con los mismos
  nombres intersecta el resultado a **8 MW**. La relación
  `1.5 × almacenamiento >= 14.925 hm³` conserva **9.95 hm³** y limita la suma
  de caudales turbinados a **13.8888888889 m³/s** en los cuatro períodos del
  fixture. Exigir además vertimiento de 2 m³/s reduce esa suma a
  **5.8888888889 m³/s**. Membresía inválida y cotas imposibles se rechazan.
- React: **69 pruebas** de `ComponentRules`, `HourlyRules`, `RelatedRules`,
  `RunExperience` y `ProtectedMutationJourney`. Incluyen selección sin escritura
  anticipada, retorno contextual, preview con ambos objetos y MW, y error con
  alias/línea. Build, ESLint y contrato OpenAPI regenerado/`api:check` aprobados.
- Chromium: `component-rules-related.spec.ts` aprobado con API, OCI y Julia
  reales en datos temporales. La suma explícita de dos unidades y el alias de
  planta producen **10 MW en cada uno de cuatro períodos**. Cambiar membresía
  bloquea nuevas corridas e identifica el alias, conservando el snapshot previo.
  También pasaron el guardado/reapertura de REG-001 y el recorrido horario
  completo de REG-003. El recorrido real detectó una lectura concurrente sin
  bloqueo de conexión; se corrigió y se repitió satisfactoriamente.

Workflow y [operación/reproducción](../runtime.md) actualizados. Para adoptar
el SDK se reconstruye la imagen, se fija su digest y se reinicia el worker.
Publicaciones de SDK anteriores requieren publicar/probar/aplicar nuevamente.
No se ejecutó CI remoto ni las suites globales de Julia/frontend, y no hubo
despliegue ni cambios en bases de proyectos. La siguiente issue por orden es
REG-005; relaciones entre períodos y presupuestos permanecen fuera de REG-004.

## Blocked by

- [REG-003](REG-003-limites-horarios-series.md).
