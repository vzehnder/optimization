# Formulacion del modelo MILP simple

## 1. Objetivo

Este documento define una primera formulacion matematica MILP simple para optimizar la operacion de una bateria BESS bajo arbitraje de precios.

El modelo decide cuanta potencia cargar, cuanta potencia descargar, cual es el estado de carga de la bateria y en que modo de operacion se encuentra en cada periodo del horizonte de optimizacion.

La primera version busca maximizar el margen economico por arbitraje:

```text
ingresos por descarga - costos por carga
```

No se consideran todavia degradacion, restricciones de red, reglas de mercado complejas, contratos, incertidumbre ni servicios complementarios.

---

## 2. Supuestos

1. Se optimiza una sola bateria.
2. El horizonte de optimizacion es discreto y conocido.
3. El precio de energia de cada periodo es un dato de entrada.
4. La bateria puede cargar desde la red y descargar hacia la red.
5. La potencia de carga y descarga esta limitada por parametros tecnicos.
6. El estado de carga debe mantenerse dentro de sus limites minimo y maximo.
7. Las eficiencias de carga y descarga son constantes.
8. El modelo base es mixto entero lineal, MILP.
9. La no simultaneidad entre carga y descarga se impone con una variable binaria.
10. En cada periodo la bateria puede cargar, descargar o permanecer inactiva.

---

## 3. Indices y conjuntos

### Conjunto de periodos

```text
T = {1, 2, ..., N}
```

Donde:

- `t` es un periodo de tiempo.
- `N` es el numero total de periodos del horizonte de optimizacion.

---

## 4. Parametros

### Datos temporales

| Parametro | Unidad | Descripcion |
| --- | --- | --- |
| `delta_t_h` | h | Duracion de cada periodo en horas. |
| `price_t` | USD/MWh | Precio de energia en el periodo `t`. |

### Parametros tecnicos de la bateria

| Parametro | Unidad | Descripcion |
| --- | --- | --- |
| `power_charge_max_mw` | MW | Potencia maxima de carga. |
| `power_discharge_max_mw` | MW | Potencia maxima de descarga. |
| `energy_capacity_mwh` | MWh | Capacidad nominal de energia. |
| `soc_min_mwh` | MWh | Estado de carga minimo permitido. |
| `soc_max_mwh` | MWh | Estado de carga maximo permitido. |
| `soc_initial_mwh` | MWh | Estado de carga inicial. |
| `charge_efficiency` | p.u. | Eficiencia de carga. |
| `discharge_efficiency` | p.u. | Eficiencia de descarga. |

### Parametro terminal opcional

| Parametro | Unidad | Descripcion |
| --- | --- | --- |
| `soc_final_target_mwh` | MWh | Estado de carga final requerido, si se desea cerrar el horizonte con una condicion terminal. |

---

## 5. Variables de decision

Para cada periodo `t` en `T`:

| Variable | Unidad | Dominio | Descripcion |
| --- | --- | --- | --- |
| `charge_mw_t` | MW | `>= 0` | Potencia cargada por la bateria en el periodo `t`. |
| `discharge_mw_t` | MW | `>= 0` | Potencia descargada por la bateria en el periodo `t`. |
| `soc_mwh_t` | MWh | `>= 0` | Estado de carga al final del periodo `t`. |
| `is_charging_t` | binaria | `{0, 1}` | Variable de modo. Toma valor 1 si la bateria puede cargar en el periodo `t`, y 0 si puede descargar o quedar inactiva. |

---

## 6. Funcion objetivo

El objetivo es maximizar el margen neto por arbitraje de energia.

```text
max sum_{t in T} price_t * discharge_mw_t * delta_t_h
    - sum_{t in T} price_t * charge_mw_t * delta_t_h
```

Equivalentemente:

```text
max sum_{t in T} price_t * (discharge_mw_t - charge_mw_t) * delta_t_h
```

Donde:

- `price_t * discharge_mw_t * delta_t_h` representa el ingreso por descargar energia.
- `price_t * charge_mw_t * delta_t_h` representa el costo por cargar energia.

---

## 7. Restricciones

### 7.1 Balance de estado de carga

Para el primer periodo:

```text
soc_mwh_1 =
    soc_initial_mwh
    + charge_mw_1 * delta_t_h * charge_efficiency
    - discharge_mw_1 * delta_t_h / discharge_efficiency
```

Para cada periodo `t > 1`:

```text
soc_mwh_t =
    soc_mwh_{t-1}
    + charge_mw_t * delta_t_h * charge_efficiency
    - discharge_mw_t * delta_t_h / discharge_efficiency
```

Esta restriccion actualiza el estado de carga considerando energia cargada, energia descargada y perdidas por eficiencia.

---

### 7.2 Limites de estado de carga

Para cada periodo `t`:

```text
soc_min_mwh <= soc_mwh_t <= soc_max_mwh
```

Adicionalmente, se debe cumplir:

```text
soc_max_mwh <= energy_capacity_mwh
```

---

### 7.3 Limite de potencia de carga y modo de operacion

Para cada periodo `t`:

```text
0 <= charge_mw_t <= power_charge_max_mw * is_charging_t
```

---

### 7.4 Limite de potencia de descarga y modo de operacion

Para cada periodo `t`:

```text
0 <= discharge_mw_t <= power_discharge_max_mw * (1 - is_charging_t)
```

Estas dos restricciones impiden que la bateria cargue y descargue simultaneamente.

Si `is_charging_t = 1`:

- `charge_mw_t` puede ser positivo.
- `discharge_mw_t` queda forzado a 0.

Si `is_charging_t = 0`:

- `discharge_mw_t` puede ser positivo.
- `charge_mw_t` queda forzado a 0.

La bateria puede quedar inactiva en cualquiera de los dos modos si carga y descarga son iguales a 0.

---

### 7.5 Estado inicial valido

Antes de resolver el modelo, los parametros deben cumplir:

```text
soc_min_mwh <= soc_initial_mwh <= soc_max_mwh
```

Esta validacion puede implementarse fuera del modelo como parte del modulo de validacion de datos.

---

### 7.6 Condicion terminal opcional

Para evitar que el modelo vacie la bateria al final del horizonte solo por efecto de borde, se puede exigir un estado de carga final.

Una opcion simple es cerrar el horizonte con el mismo estado de carga inicial:

```text
soc_mwh_N = soc_initial_mwh
```

Otra opcion es usar un parametro explicito:

```text
soc_mwh_N = soc_final_target_mwh
```

Esta restriccion es recomendable cuando se comparan escenarios o se optimizan ventanas cortas.

---

## 8. Naturaleza MILP del modelo

El modelo es MILP porque combina:

- Variables continuas: `charge_mw_t`, `discharge_mw_t`, `soc_mwh_t`.
- Variables binarias: `is_charging_t`.
- Funcion objetivo lineal.
- Restricciones lineales.

La variable binaria `is_charging_t` permite modelar la decision discreta de modo operativo. Esto evita simultaneidad entre carga y descarga sin introducir productos entre variables de decision.

El problema puede resolverse con solvers MILP como HiGHS, CBC, GLPK, Gurobi o CPLEX.

---

## 9. Variante con dos binarias de modo

Si mas adelante se quiere representar explicitamente tres estados, carga, descarga e inactividad, se puede usar una formulacion alternativa con dos variables binarias:

| Variable | Dominio | Descripcion |
| --- | --- | --- |
| `is_charging_t` | `{0, 1}` | Toma valor 1 si la bateria esta en modo carga. |
| `is_discharging_t` | `{0, 1}` | Toma valor 1 si la bateria esta en modo descarga. |

Restricciones:

```text
charge_mw_t <= power_charge_max_mw * is_charging_t
```

```text
discharge_mw_t <= power_discharge_max_mw * is_discharging_t
```

```text
is_charging_t + is_discharging_t <= 1
```

La formulacion de una sola binaria es suficiente para la primera version y usa menos variables enteras.

---

## 10. Entradas minimas requeridas

Para correr este modelo se requiere:

| Entrada | Fuente esperada |
| --- | --- |
| Serie de precios `price_t` | `data/processed/time_series/` |
| Duracion del periodo `delta_t_h` | Configuracion general o inferida desde timestamps. |
| Parametros tecnicos de bateria | `config/battery_params.yaml` |
| Configuracion de solver | `config/default_config.yaml` |
| Configuracion de escenario | `config/scenarios.yaml` |

---

## 11. Salidas esperadas

El modelo debe producir, al menos:

| Salida | Unidad | Descripcion |
| --- | --- | --- |
| `timestamp` | fecha/hora | Periodo de optimizacion. |
| `price_usd_mwh` | USD/MWh | Precio usado por el modelo. |
| `charge_mw` | MW | Potencia de carga optima. |
| `discharge_mw` | MW | Potencia de descarga optima. |
| `soc_mwh` | MWh | Estado de carga optimo. |
| `is_charging` | binaria | Modo operativo optimo. |
| `charge_cost_usd` | USD | Costo de carga por periodo. |
| `discharge_revenue_usd` | USD | Ingreso por descarga por periodo. |
| `net_revenue_usd` | USD | Margen neto por periodo. |

Tambien se debe guardar:

- Valor objetivo total.
- Estado del solver.
- Configuracion usada.
- Resumen de inputs.

---

## 12. Formulacion compacta

### Problema

```text
max sum_{t in T} price_t * (discharge_mw_t - charge_mw_t) * delta_t_h
```

Sujeto a:

```text
soc_mwh_t =
    soc_mwh_{t-1}
    + charge_mw_t * delta_t_h * charge_efficiency
    - discharge_mw_t * delta_t_h / discharge_efficiency
```

```text
soc_min_mwh <= soc_mwh_t <= soc_max_mwh
```

```text
0 <= charge_mw_t <= power_charge_max_mw * is_charging_t
```

```text
0 <= discharge_mw_t <= power_discharge_max_mw * (1 - is_charging_t)
```

```text
is_charging_t in {0, 1}
```

```text
soc_mwh_0 = soc_initial_mwh
```

Opcional:

```text
soc_mwh_N = soc_final_target_mwh
```

---

## 13. Comentarios de implementacion

Para una primera implementacion en Python, esta formulacion puede representarse con Pyomo usando:

- Un conjunto ordenado de periodos.
- Variables continuas no negativas para carga, descarga y estado de carga.
- Una variable binaria para el modo de operacion.
- Restricciones separadas en `constraints/generic.py`.
- Funcion objetivo en `models/objective.py`.
- Resolucion en `models/solver.py`.

La estructura recomendada es:

```text
1. Cargar precios y parametros.
2. Crear modelo y conjunto temporal.
3. Crear variables.
4. Agregar balance de estado de carga.
5. Agregar limites de energia.
6. Agregar restricciones MILP de modo operativo.
7. Agregar condicion terminal si corresponde.
8. Definir funcion objetivo.
9. Resolver.
10. Extraer y guardar resultados.
```
