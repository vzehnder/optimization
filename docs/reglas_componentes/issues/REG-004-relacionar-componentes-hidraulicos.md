# REG-004: Relacionar unidades, plantas y embalses del mismo modelo

Status: Todo
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

- [ ] El editor descubre variables y unidades por tipo de objeto y capacidad real del motor; no muestra caudal genérico de tramo ni cota v3 como variable de decisión.
- [ ] Se guardan alias de objetos con identidades estables, y se verifica que todos pertenecen al mismo snapshot/modelo, no solamente al mismo proyecto.
- [ ] Las expresiones admiten suma/resta, coeficientes conocidos y relaciones afines; la preview identifica todos los objetos que afecta una fila.
- [ ] La potencia de planta se expande a la suma de las unidades de su snapshot sin crear otra variable física; cambios de membresía invalidan la aplicación validada.
- [ ] Parámetros y puertos de entrada asociados a un objeto referenciado respetan su contexto de propiedad, permisos y compatibilidad TS-7.
- [ ] Todas las reglas activas se intersectan sin prioridad de reemplazo. Identificadores de fila incluyen la instancia para evitar colisiones entre reglas.
- [ ] Referencias eliminadas, otro proyecto, otro caso incompatible y operaciones no afines bloquean con alias y línea cuando esté disponible.
- [ ] Julia aplica las filas a las variables reales y la corrida conserva mapa de alias y objetos para su interpretación histórica.

## Demonstration and validation

Dos unidades capaces de producir más de 10 MW en conjunto reciben un límite
compartido de 10 MW; verificar la suma y no un límite independiente por unidad.
Repetir con el alias de planta. Probar una relación lineal con almacenamiento,
una referencia externa y un cambio de membresía, desde selección hasta solve.

## Blocked by

- [REG-003](REG-003-limites-horarios-series.md).
