# Estructura inicial del repositorio: Optimización de baterías BESS utility-scale

## 1. Objetivo del repositorio

Este repositorio tiene como objetivo desarrollar un programa en Python para optimizar la operación de baterías BESS de gran escala.

La primera versión debe ser simple, modular y fácil de extender. La idea es separar claramente:

- La extracción y preparación de datos.
- La definición de parámetros de la batería.
- La construcción del modelo de optimización.
- Las restricciones genéricas aplicables a cualquier batería.
- Las restricciones específicas del caso de estudio, mercado o proyecto.
- La ejecución de escenarios.
- El almacenamiento y análisis de resultados.

La lógica general esperada es:

```text
1. Cargar datos y parámetros
2. Crear el modelo base
3. Agregar variables
4. Agregar restricciones genéricas
5. Agregar restricciones específicas
6. Definir función objetivo
7. Resolver modelo
8. Guardar resultados
9. Analizar resultados
```

---

## 2. Principios de diseño

El repositorio debe partir simple, pero evitando una estructura monolítica difícil de mantener.

Principios recomendados:

1. **Separación entre datos, modelo y resultados**  
   Los datos no deben mezclarse con la lógica de optimización.

2. **Modelo genérico primero**  
   El modelo debe poder construirse con restricciones básicas de una batería, independientemente del caso de uso.

3. **Restricciones específicas como módulos separados**  
   Las reglas particulares de un mercado, contrato, planta o caso de estudio deben agregarse después del modelo base.

4. **Escalabilidad**  
   La estructura debe permitir agregar nuevos escenarios, nuevas funciones objetivo, nuevas restricciones y nuevas fuentes de datos sin reescribir todo.

5. **Reproducibilidad**  
   Cada corrida debe poder guardar sus inputs, configuración y resultados.

---

## 3. Estructura propuesta del repositorio

```text
battery-optimization/
│
├── README.md
├── pyproject.toml
├── requirements.txt
├── .gitignore
├── .env.example
│
├── docs/
│   ├── 00_repo_structure.md
│   ├── 01_model_formulation.md
│   ├── 02_data_requirements.md
│   ├── 03_running_scenarios.md
│   └── 04_results_interpretation.md
│
├── config/
│   ├── default_config.yaml
│   ├── battery_params.yaml
│   └── scenarios.yaml
│
├── data/
│   ├── raw/
│   │   ├── prices/
│   │   ├── demand/
│   │   ├── generation/
│   │   └── battery/
│   │
│   ├── processed/
│   │   ├── time_series/
│   │   └── parameters/
│   │
│   └── external/
│
├── src/
│   └── battery_optimization/
│       │
│       ├── __init__.py
│       │
│       ├── data/
│       │   ├── __init__.py
│       │   ├── loaders.py
│       │   ├── validators.py
│       │   ├── preprocessing.py
│       │   └── schemas.py
│       │
│       ├── parameters/
│       │   ├── __init__.py
│       │   ├── battery.py
│       │   ├── market.py
│       │   └── scenario.py
│       │
│       ├── models/
│       │   ├── __init__.py
│       │   ├── base_model.py
│       │   ├── variables.py
│       │   ├── objective.py
│       │   └── solver.py
│       │
│       ├── constraints/
│       │   ├── __init__.py
│       │   ├── generic.py
│       │   └── specific/
│       │       ├── __init__.py
│       │       ├── market_rules.py
│       │       ├── grid_limits.py
│       │       ├── contract_rules.py
│       │       └── degradation.py
│       │
│       ├── results/
│       │   ├── __init__.py
│       │   ├── extractor.py
│       │   ├── exporter.py
│       │   └── plots.py
│       │
│       └── utils/
│           ├── __init__.py
│           ├── logging.py
│           └── paths.py
│
├── scripts/
│   ├── run_single_scenario.py
│   ├── run_multiple_scenarios.py
│   └── prepare_data.py
│
├── notebooks/
│   ├── 00_data_exploration.ipynb
│   └── 01_results_analysis.ipynb
│
├── models/
│   ├── saved/
│   └── debug/
│
├── results/
│   ├── runs/
│   ├── summaries/
│   ├── figures/
│   └── exports/
│
└── tests/
    ├── test_data_loaders.py
    ├── test_generic_constraints.py
    ├── test_specific_constraints.py
    └── test_model_solve.py
```

---

## 4. Descripción de carpetas principales

### `docs/`

Carpeta para documentación del proyecto.

Debe contener este archivo y otros documentos explicativos del modelo, datos, supuestos, casos de uso y resultados.

Archivos sugeridos:

```text
docs/
├── 00_repo_structure.md
├── 01_model_formulation.md
├── 02_data_requirements.md
├── 03_running_scenarios.md
└── 04_results_interpretation.md
```

#### `00_repo_structure.md`

Documento que explica la estructura inicial del repositorio.

#### `01_model_formulation.md`

Documento con la formulación matemática del problema de optimización.

Debe incluir, al menos:

- Conjuntos.
- Parámetros.
- Variables.
- Función objetivo.
- Restricciones genéricas.
- Restricciones específicas.

#### `02_data_requirements.md`

Documento con los datos requeridos para correr el modelo.

Ejemplos:

- Precios horarios.
- Potencia máxima de carga.
- Potencia máxima de descarga.
- Capacidad energética.
- Estado de carga inicial.
- Eficiencia de carga.
- Eficiencia de descarga.
- Restricciones de conexión.
- Señales de mercado.
- Disponibilidad de la batería.

#### `03_running_scenarios.md`

Documento que explica cómo correr escenarios.

Debe describir:

- Cómo configurar un escenario.
- Cómo seleccionar el horizonte de optimización.
- Cómo cambiar parámetros de la batería.
- Cómo ejecutar una corrida.
- Dónde se guardan los resultados.

#### `04_results_interpretation.md`

Documento que explica cómo interpretar los resultados.

Debe incluir:

- Energía cargada.
- Energía descargada.
- Estado de carga.
- Ingresos.
- Costos.
- Utilidad neta.
- Restricciones activas.
- Comparación entre escenarios.

---

## 5. Configuración

### `config/`

Carpeta para archivos de configuración.

```text
config/
├── default_config.yaml
├── battery_params.yaml
└── scenarios.yaml
```

### `default_config.yaml`

Configuración general del proyecto.

Ejemplo:

```yaml
project:
  name: battery_optimization
  timezone: America/Santiago

solver:
  name: highs
  time_limit_seconds: 300
  mip_gap: 0.001

paths:
  raw_data: data/raw
  processed_data: data/processed
  results: results/runs
```

### `battery_params.yaml`

Parámetros técnicos de la batería.

Ejemplo:

```yaml
battery:
  name: bess_base
  power_charge_max_mw: 100
  power_discharge_max_mw: 100
  energy_capacity_mwh: 400
  soc_min_mwh: 0
  soc_max_mwh: 400
  soc_initial_mwh: 200
  charge_efficiency: 0.95
  discharge_efficiency: 0.95
```

### `scenarios.yaml`

Definición de escenarios.

Ejemplo:

```yaml
scenarios:
  - name: base_case
    price_series: prices_base.csv
    battery_params: battery_params.yaml
    start_date: 2026-01-01
    end_date: 2026-01-07
    specific_constraints:
      - none

  - name: grid_limited_case
    price_series: prices_base.csv
    battery_params: battery_params.yaml
    start_date: 2026-01-01
    end_date: 2026-01-07
    specific_constraints:
      - grid_limits
```

---

## 6. Datos

### `data/`

Carpeta para datos de entrada y datos procesados.

```text
data/
├── raw/
├── processed/
└── external/
```

### `data/raw/`

Datos originales, sin modificar.

Ejemplos:

```text
data/raw/
├── prices/
├── demand/
├── generation/
└── battery/
```

Posibles archivos:

```text
data/raw/prices/price_series.csv
data/raw/battery/battery_characteristics.csv
data/raw/generation/generation_forecast.csv
data/raw/demand/demand_forecast.csv
```

### `data/processed/`

Datos limpios y listos para ser usados por el modelo.

Ejemplos:

```text
data/processed/time_series/optimization_timeseries.csv
data/processed/parameters/battery_params_processed.csv
```

### `data/external/`

Datos externos o de referencia que no son generados por el proyecto.

Ejemplos:

- Información pública del Coordinador.
- Datos de mercado.
- Datos meteorológicos.
- Datos de disponibilidad de red.

---

## 7. Código fuente

### `src/battery_optimization/`

Carpeta principal del código Python.

---

## 8. Módulo de datos

### `src/battery_optimization/data/`

Responsable de cargar, validar y preparar datos.

```text
data/
├── loaders.py
├── validators.py
├── preprocessing.py
└── schemas.py
```

### `loaders.py`

Funciones para cargar datos desde CSV, Excel, bases de datos o APIs.

Ejemplo de responsabilidades:

- Leer precios.
- Leer parámetros de batería.
- Leer series de tiempo.
- Leer escenarios.

### `validators.py`

Validaciones básicas antes de correr el modelo.

Ejemplos:

- Verificar que no falten timestamps.
- Verificar que los precios sean numéricos.
- Verificar que la capacidad de la batería sea positiva.
- Verificar que el estado inicial de carga esté dentro de los límites.

### `preprocessing.py`

Transformaciones previas a la optimización.

Ejemplos:

- Filtrar horizonte de tiempo.
- Reindexar series horarias.
- Completar datos faltantes.
- Unificar unidades.

### `schemas.py`

Definición esperada de columnas y tipos de datos.

Ejemplo:

```python
REQUIRED_TIME_SERIES_COLUMNS = [
    "timestamp",
    "price_usd_mwh"
]
```

---

## 9. Módulo de parámetros

### `src/battery_optimization/parameters/`

Responsable de representar los parámetros del modelo.

```text
parameters/
├── battery.py
├── market.py
└── scenario.py
```

### `battery.py`

Define una estructura para los parámetros técnicos de la batería.

Parámetros mínimos:

- Potencia máxima de carga.
- Potencia máxima de descarga.
- Capacidad energética.
- Estado de carga mínimo.
- Estado de carga máximo.
- Estado de carga inicial.
- Eficiencia de carga.
- Eficiencia de descarga.

### `market.py`

Define parámetros del mercado o sistema.

Ejemplos:

- Precios.
- Costos variables.
- Penalizaciones.
- Tarifas.
- Restricciones de inyección o retiro.

### `scenario.py`

Define los parámetros de cada escenario.

Ejemplos:

- Nombre del escenario.
- Fechas de inicio y término.
- Archivos de entrada.
- Restricciones específicas activas.
- Solver utilizado.

---

## 10. Módulo de modelos

### `src/battery_optimization/models/`

Responsable de crear y resolver el modelo de optimización.

```text
models/
├── base_model.py
├── variables.py
├── objective.py
└── solver.py
```

### `base_model.py`

Crea el modelo base.

Responsabilidades:

- Inicializar el objeto del modelo.
- Definir el horizonte temporal.
- Llamar a la creación de variables.
- Llamar a restricciones genéricas.
- Permitir agregar restricciones específicas.
- Definir la función objetivo.

Flujo conceptual:

```python
model = create_base_model(data, battery_params)
add_variables(model, data, battery_params)
add_generic_constraints(model, data, battery_params)
add_specific_constraints(model, data, battery_params, scenario)
set_objective(model, data, battery_params)
solve_model(model, solver_config)
```

### `variables.py`

Define las variables de decisión.

Variables mínimas recomendadas:

- Energía cargada en cada período.
- Energía descargada en cada período.
- Estado de carga.
- Variable binaria opcional para evitar carga y descarga simultánea.

Ejemplo conceptual:

```text
charge[t] >= 0
discharge[t] >= 0
soc[t] >= 0
```

### `objective.py`

Define la función objetivo.

Primera versión recomendada:

```text
Maximizar ingresos por arbitraje = ingresos por descarga - costos por carga
```

Ejemplo conceptual:

```text
max sum_t price[t] * discharge[t] - price[t] * charge[t]
```

Más adelante se pueden agregar:

- Costos de degradación.
- Penalizaciones por desviación.
- Pagos por potencia.
- Servicios complementarios.
- Restricciones contractuales.
- Costos de operación.

### `solver.py`

Módulo encargado de resolver el modelo.

Responsabilidades:

- Seleccionar solver.
- Configurar límites de tiempo.
- Configurar gap.
- Ejecutar optimización.
- Capturar estado de solución.
- Manejar errores.

---

## 11. Restricciones

### `src/battery_optimization/constraints/`

Carpeta central para restricciones del modelo.

```text
constraints/
├── generic.py
└── specific/
    ├── market_rules.py
    ├── grid_limits.py
    ├── contract_rules.py
    └── degradation.py
```

---

## 12. Restricciones genéricas

### `constraints/generic.py`

Estas restricciones aplican a cualquier batería BESS.

Restricciones mínimas recomendadas:

### 12.1 Balance de estado de carga

```text
soc[t] = soc[t-1] + charge[t] * efficiency_charge - discharge[t] / efficiency_discharge
```

### 12.2 Límite mínimo y máximo de estado de carga

```text
soc_min <= soc[t] <= soc_max
```

### 12.3 Límite de potencia de carga

```text
0 <= charge[t] <= power_charge_max
```

### 12.4 Límite de potencia de descarga

```text
0 <= discharge[t] <= power_discharge_max
```

### 12.5 Estado inicial de carga

```text
soc[0] = soc_initial
```

### 12.6 No cargar y descargar simultáneamente

En una primera versión simple, esta restricción podría omitirse si el modelo no genera simultaneidad por efecto económico.

Si se quiere evitar explícitamente, se puede agregar una variable binaria:

```text
charge[t] <= power_charge_max * is_charging[t]
discharge[t] <= power_discharge_max * (1 - is_charging[t])
```

Esto transforma el problema en un modelo mixto entero si antes era lineal continuo.

---

## 13. Restricciones específicas

### `constraints/specific/`

Estas restricciones dependen del caso de uso.

Ejemplos:

### `market_rules.py`

Restricciones propias de reglas de mercado.

Ejemplos:

- Bloques horarios.
- Límites de participación.
- Reglas de liquidación.
- Reglas de ofertas.
- Mínimos técnicos comerciales.

### `grid_limits.py`

Restricciones asociadas a la red o punto de conexión.

Ejemplos:

- Límite máximo de inyección.
- Límite máximo de retiro.
- Restricciones por congestión.
- Restricciones dinámicas por horario.

### `contract_rules.py`

Restricciones contractuales.

Ejemplos:

- Energía mínima comprometida.
- Energía máxima comprometida.
- Perfil de entrega.
- Penalizaciones por incumplimiento.

### `degradation.py`

Restricciones o costos asociados a degradación.

Ejemplos:

- Costo por energía ciclada.
- Límite de ciclos diarios.
- Límite de throughput.
- Penalización por profundidad de descarga.

---

## 14. Orden recomendado de construcción del modelo

La construcción del modelo debe seguir un orden claro:

```text
1. Crear modelo vacío
2. Crear variables
3. Agregar restricciones genéricas
4. Agregar restricciones específicas
5. Agregar función objetivo
6. Resolver
7. Extraer resultados
```

En código, esto podría verse así:

```python
from battery_optimization.models.base_model import create_model
from battery_optimization.constraints.generic import add_generic_constraints
from battery_optimization.constraints.specific.grid_limits import add_grid_limit_constraints
from battery_optimization.models.objective import set_arbitrage_objective
from battery_optimization.models.solver import solve_model

model = create_model(time_index, battery_params)

add_generic_constraints(model, time_index, battery_params)

if "grid_limits" in scenario.specific_constraints:
    add_grid_limit_constraints(model, time_index, grid_params)

set_arbitrage_objective(model, time_index, prices)

solution = solve_model(model, solver_config)
```

---

## 15. Resultados

### `src/battery_optimization/results/`

Responsable de extraer, guardar y visualizar resultados.

```text
results/
├── extractor.py
├── exporter.py
└── plots.py
```

### `extractor.py`

Extrae resultados desde el modelo resuelto.

Variables típicas:

- `charge_mw`
- `discharge_mw`
- `soc_mwh`
- `price`
- `revenue`
- `cost`
- `net_revenue`

### `exporter.py`

Guarda resultados en archivos.

Formatos recomendados:

- CSV para resultados tabulares.
- JSON o YAML para configuración de la corrida.
- HTML o PNG para gráficos.
- Parquet si los resultados crecen mucho.

### `plots.py`

Funciones de visualización.

Gráficos mínimos recomendados:

- Precio horario.
- Carga y descarga de la batería.
- Estado de carga.
- Ingresos por período.
- Comparación entre escenarios.

---

## 16. Carpeta `models/`

Esta carpeta puede usarse para guardar modelos exportados o información de depuración.

```text
models/
├── saved/
└── debug/
```

Ejemplos:

```text
models/debug/base_case_model.lp
models/debug/base_case_model.mps
models/saved/base_case_solution.pkl
```

No debe confundirse con `src/battery_optimization/models/`, que contiene el código fuente para construir modelos.

---

## 17. Carpeta `results/`

Carpeta para resultados de corridas.

```text
results/
├── runs/
├── summaries/
├── figures/
└── exports/
```

### `results/runs/`

Cada corrida debería guardarse en una carpeta independiente.

Ejemplo:

```text
results/runs/2026-05-19_120000_base_case/
├── config_used.yaml
├── input_summary.csv
├── solution.csv
├── objective_value.txt
├── solver_status.json
└── figures/
    ├── soc.png
    ├── charge_discharge.png
    └── price.png
```

### `results/summaries/`

Resultados agregados para comparar escenarios.

Ejemplo:

```text
results/summaries/scenario_comparison.csv
```

### `results/figures/`

Figuras consolidadas.

### `results/exports/`

Archivos preparados para compartir con terceros.

---

## 18. Scripts

### `scripts/`

Scripts ejecutables para tareas comunes.

```text
scripts/
├── run_single_scenario.py
├── run_multiple_scenarios.py
└── prepare_data.py
```

### `run_single_scenario.py`

Ejecuta un escenario específico.

Ejemplo de uso:

```bash
python scripts/run_single_scenario.py --scenario base_case
```

### `run_multiple_scenarios.py`

Ejecuta varios escenarios definidos en `scenarios.yaml`.

Ejemplo:

```bash
python scripts/run_multiple_scenarios.py
```

### `prepare_data.py`

Procesa datos crudos y genera archivos listos para optimización.

Ejemplo:

```bash
python scripts/prepare_data.py
```

---

## 19. Tests

### `tests/`

Tests mínimos recomendados:

```text
tests/
├── test_data_loaders.py
├── test_generic_constraints.py
├── test_specific_constraints.py
└── test_model_solve.py
```

### Tests iniciales sugeridos

1. El modelo corre con una serie de precios simple.
2. El estado de carga nunca supera el máximo.
3. El estado de carga nunca baja del mínimo.
4. La potencia de carga nunca supera el límite.
5. La potencia de descarga nunca supera el límite.
6. El balance de energía se cumple.
7. El resultado se guarda correctamente.
8. El modelo detecta errores si faltan datos requeridos.

---

## 20. Librerías recomendadas

Para una primera versión simple:

```text
pandas
numpy
pyyaml
matplotlib
plotly
pyomo
highspy
```

Opciones de modelación:

### Opción recomendada inicial: Pyomo

Ventajas:

- Flexible.
- Buena separación entre variables, restricciones y función objetivo.
- Compatible con varios solvers.
- Escalable para problemas más complejos.

### Solver recomendado inicial: HiGHS

Ventajas:

- Open source.
- Fácil de instalar.
- Adecuado para modelos lineales y mixtos enteros.
- Buena opción para partir sin licencias comerciales.

---

## 21. Primera versión mínima viable

La primera versión del repositorio debería permitir:

1. Leer una serie horaria de precios.
2. Leer parámetros básicos de una batería.
3. Crear un modelo de arbitraje simple.
4. Agregar restricciones genéricas de batería.
5. Resolver el modelo.
6. Guardar resultados.
7. Graficar carga, descarga y estado de carga.

### Alcance mínimo del primer modelo

#### Inputs

- Precio horario.
- Potencia máxima de carga.
- Potencia máxima de descarga.
- Capacidad de energía.
- Estado de carga inicial.
- Eficiencia de carga.
- Eficiencia de descarga.

#### Variables

- Carga.
- Descarga.
- Estado de carga.

#### Función objetivo

Maximizar utilidad por arbitraje.

#### Restricciones

- Balance de estado de carga.
- Límite de carga.
- Límite de descarga.
- Límite de estado de carga.
- Estado inicial.

#### Outputs

- Serie horaria de carga.
- Serie horaria de descarga.
- Serie horaria de estado de carga.
- Ingresos por descarga.
- Costos por carga.
- Resultado neto.
- Estado del solver.

---

## 22. Futuras extensiones

Una vez que el modelo base funcione, se pueden agregar módulos más avanzados.

Extensiones posibles:

1. Restricciones de conexión a la red.
2. Degradación de batería.
3. Ciclos máximos diarios.
4. Optimización co-localizada con solar o eólica.
5. Participación en servicios complementarios.
6. Restricciones de potencia firme o suficiencia.
7. Optimización bajo incertidumbre.
8. Optimización rolling horizon.
9. Escenarios estocásticos.
10. Integración con bases de datos.
11. API para ejecutar optimizaciones.
12. Dashboard de resultados.
13. Comparación automática de escenarios.
14. Calibración de parámetros técnicos.
15. Modelo económico de ingresos y costos.

---

## 23. Recomendación de implementación inicial

Para partir, se recomienda implementar en este orden:

### Etapa 1: Setup del repositorio

- Crear estructura de carpetas.
- Crear ambiente Python.
- Crear archivos de configuración.
- Crear datos de ejemplo.

### Etapa 2: Modelo mínimo

- Crear variables.
- Agregar restricciones genéricas.
- Definir función objetivo de arbitraje.
- Resolver con HiGHS.

### Etapa 3: Resultados

- Extraer variables.
- Guardar resultados.
- Crear gráficos simples.

### Etapa 4: Escenarios

- Leer escenarios desde YAML.
- Ejecutar más de un escenario.
- Comparar resultados.

### Etapa 5: Restricciones específicas

- Agregar restricciones de red.
- Agregar restricciones contractuales.
- Agregar degradación simple.

---

## 24. Convención recomendada para nombres

### Variables de energía y potencia

Usar unidades explícitas:

```text
charge_mw
discharge_mw
soc_mwh
price_usd_mwh
energy_capacity_mwh
power_charge_max_mw
power_discharge_max_mw
```

### Fechas

Usar siempre:

```text
timestamp
```

### Escenarios

Usar nombres simples:

```text
base_case
high_price_volatility
grid_limited
degradation_cost
```

---

## 25. Comentario final

La clave del diseño inicial es que el modelo no quede amarrado a un caso específico.

El primer modelo debe representar una batería genérica optimizando arbitraje contra una serie de precios. Luego, sobre esa base, se deben ir agregando restricciones específicas según el caso de uso.

La estructura propuesta permite que el repositorio parta simple, pero pueda crecer hacia casos más complejos como BESS con restricciones de red, degradación, contratos, servicios complementarios o integración con modelos de mercado.
