# Formulacion MILP bajo incertidumbre de CMg

## 1. Objetivo

Este documento define una formulacion MILP simple para optimizar la operacion de una bateria BESS cuando el costo marginal, `CMg`, es incierto.

La incertidumbre se representa mediante un conjunto finito de escenarios. Cada escenario contiene un vector temporal de CMg y una probabilidad de ocurrencia.

El modelo maximiza el valor esperado del margen economico por arbitraje:

```text
valor esperado de ingresos por descarga - costos por carga
```

Esta formulacion corresponde al equivalente deterministico de un problema estocastico basado en escenarios.

---

## 2. Enfoque de incertidumbre

Se supone que existen varios vectores posibles de CMg:

```text
cmg_{s,t}
```

Donde:

- `s` representa un escenario de CMg.
- `t` representa un periodo de tiempo.
- Cada escenario `s` tiene una probabilidad `prob_s`.

Ejemplo conceptual:

| Escenario | Probabilidad | Vector de CMg |
| --- | ---: | --- |
| `low_cmg` | 0.25 | `[30, 28, 35, 45, ...]` |
| `base_cmg` | 0.50 | `[40, 38, 42, 55, ...]` |
| `high_cmg` | 0.25 | `[55, 50, 60, 85, ...]` |

Las probabilidades deben cumplir:

```text
sum_{s in S} prob_s = 1
```

```text
prob_s >= 0
```

---

## 3. Interpretacion del modelo

La formulacion base permite que la operacion de la bateria se adapte a cada escenario de CMg.

Esto significa que las variables de carga, descarga, estado de carga y modo operativo dependen del escenario:

```text
charge_mw_{s,t}
discharge_mw_{s,t}
soc_mwh_{s,t}
is_charging_{s,t}
```

Esta es una formulacion tipo wait-and-see: calcula la operacion optima para cada trayectoria posible de CMg y maximiza el valor esperado.

Si se requiere modelar decisiones antes de conocer el CMg realizado, se deben agregar restricciones de no anticipatividad. Esa extension se describe mas adelante.

---

## 4. Indices y conjuntos

### Conjunto de escenarios

```text
S = {1, 2, ..., M}
```

Donde:

- `s` es un escenario de CMg.
- `M` es el numero total de escenarios.

### Conjunto de periodos

```text
T = {1, 2, ..., N}
```

Donde:

- `t` es un periodo de tiempo.
- `N` es el numero total de periodos del horizonte de optimizacion.

---

## 5. Parametros

### Parametros de incertidumbre

| Parametro | Unidad | Descripcion |
| --- | --- | --- |
| `prob_s` | p.u. | Probabilidad de ocurrencia del escenario `s`. |
| `cmg_{s,t}` | USD/MWh | Costo marginal en el escenario `s` y periodo `t`. |

### Datos temporales

| Parametro | Unidad | Descripcion |
| --- | --- | --- |
| `delta_t_h` | h | Duracion de cada periodo en horas. |

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
| `soc_final_target_mwh` | MWh | Estado de carga final requerido para cada escenario. |

---

## 6. Variables de decision

Para cada escenario `s` en `S` y periodo `t` en `T`:

| Variable | Unidad | Dominio | Descripcion |
| --- | --- | --- | --- |
| `charge_mw_{s,t}` | MW | `>= 0` | Potencia cargada por la bateria en escenario `s`, periodo `t`. |
| `discharge_mw_{s,t}` | MW | `>= 0` | Potencia descargada por la bateria en escenario `s`, periodo `t`. |
| `soc_mwh_{s,t}` | MWh | `>= 0` | Estado de carga al final del periodo `t` en escenario `s`. |
| `is_charging_{s,t}` | binaria | `{0, 1}` | Variable de modo operativo en escenario `s`, periodo `t`. |

---

## 7. Funcion objetivo

El objetivo es maximizar el valor esperado del margen neto.

```text
max sum_{s in S} prob_s *
    sum_{t in T} cmg_{s,t} * (discharge_mw_{s,t} - charge_mw_{s,t}) * delta_t_h
```

Donde:

- `cmg_{s,t} * discharge_mw_{s,t} * delta_t_h` representa el ingreso por descarga en escenario `s`, periodo `t`.
- `cmg_{s,t} * charge_mw_{s,t} * delta_t_h` representa el costo por carga en escenario `s`, periodo `t`.
- `prob_s` pondera el resultado de cada escenario por su probabilidad de ocurrencia.

---

## 8. Restricciones

### 8.1 Normalizacion de probabilidades

Antes de resolver el modelo, los escenarios deben cumplir:

```text
sum_{s in S} prob_s = 1
```

```text
prob_s >= 0
```

Esta validacion puede implementarse fuera del modelo.

---

### 8.2 Balance de estado de carga

Para cada escenario `s` y primer periodo:

```text
soc_mwh_{s,1} =
    soc_initial_mwh
    + charge_mw_{s,1} * delta_t_h * charge_efficiency
    - discharge_mw_{s,1} * delta_t_h / discharge_efficiency
```

Para cada escenario `s` y periodo `t > 1`:

```text
soc_mwh_{s,t} =
    soc_mwh_{s,t-1}
    + charge_mw_{s,t} * delta_t_h * charge_efficiency
    - discharge_mw_{s,t} * delta_t_h / discharge_efficiency
```

---

### 8.3 Limites de estado de carga

Para cada escenario `s` y periodo `t`:

```text
soc_min_mwh <= soc_mwh_{s,t} <= soc_max_mwh
```

Adicionalmente:

```text
soc_max_mwh <= energy_capacity_mwh
```

---

### 8.4 Limite de potencia de carga y modo de operacion

Para cada escenario `s` y periodo `t`:

```text
0 <= charge_mw_{s,t} <= power_charge_max_mw * is_charging_{s,t}
```

---

### 8.5 Limite de potencia de descarga y modo de operacion

Para cada escenario `s` y periodo `t`:

```text
0 <= discharge_mw_{s,t} <= power_discharge_max_mw * (1 - is_charging_{s,t})
```

Estas restricciones impiden carga y descarga simultanea dentro de cada escenario.

---

### 8.6 Estado inicial valido

Antes de resolver el modelo:

```text
soc_min_mwh <= soc_initial_mwh <= soc_max_mwh
```

---

### 8.7 Condicion terminal opcional

Para evitar efectos de borde en cada escenario, se puede exigir:

```text
soc_mwh_{s,N} = soc_initial_mwh
```

O bien:

```text
soc_mwh_{s,N} = soc_final_target_mwh
```

Para todo escenario `s`.

---

## 9. Extension: no anticipatividad

La formulacion anterior permite que la bateria conozca desde el inicio la trayectoria completa de CMg de cada escenario.

Si se quiere representar incertidumbre real en la que algunas decisiones deben tomarse antes de observar el escenario, se deben agregar restricciones de no anticipatividad.

### Caso simple: primera decision comun

Si la decision del primer periodo debe ser la misma para todos los escenarios:

```text
charge_mw_{s,1} = charge_mw_{s',1}
```

```text
discharge_mw_{s,1} = discharge_mw_{s',1}
```

```text
is_charging_{s,1} = is_charging_{s',1}
```

Para todo par de escenarios `s` y `s'`.

### Caso general: arbol de escenarios

Si los escenarios comparten informacion hasta cierto periodo, las decisiones deben ser iguales mientras las trayectorias de CMg observadas sean indistinguibles.

Para periodos `t` donde dos escenarios `s` y `s'` comparten la misma historia de informacion:

```text
charge_mw_{s,t} = charge_mw_{s',t}
```

```text
discharge_mw_{s,t} = discharge_mw_{s',t}
```

```text
is_charging_{s,t} = is_charging_{s',t}
```

Estas restricciones convierten la formulacion en un modelo estocastico no anticipativo.

---

## 10. Variante: politica robusta unica

Si se necesita una politica unica de operacion que no dependa del escenario, se pueden usar variables sin indice `s`:

```text
charge_mw_t
discharge_mw_t
soc_mwh_t
is_charging_t
```

La funcion objetivo sigue ponderando los CMg por probabilidad:

```text
max sum_{s in S} prob_s *
    sum_{t in T} cmg_{s,t} * (discharge_mw_t - charge_mw_t) * delta_t_h
```

Esto es equivalente a optimizar contra el CMg esperado:

```text
expected_cmg_t = sum_{s in S} prob_s * cmg_{s,t}
```

```text
max sum_{t in T} expected_cmg_t * (discharge_mw_t - charge_mw_t) * delta_t_h
```

Esta variante es mas simple, pero pierde la capacidad de adaptar la operacion a distintos escenarios.

---

## 11. Entradas minimas requeridas

Para correr este modelo se requiere:

| Entrada | Fuente esperada |
| --- | --- |
| Matriz de CMg `cmg_{s,t}` | `data/processed/time_series/` |
| Probabilidad de cada escenario `prob_s` | `config/scenarios.yaml` o archivo dedicado de escenarios. |
| Duracion del periodo `delta_t_h` | Configuracion general o inferida desde timestamps. |
| Parametros tecnicos de bateria | `config/battery_params.yaml` |
| Configuracion de solver MILP | `config/default_config.yaml` |

La matriz de CMg puede representarse en formato ancho:

```text
timestamp,cmg_low,cmg_base,cmg_high
2026-01-01 00:00:00,30,40,55
2026-01-01 01:00:00,28,38,50
```

O en formato largo:

```text
scenario,timestamp,cmg_usd_mwh,probability
low,2026-01-01 00:00:00,30,0.25
base,2026-01-01 00:00:00,40,0.50
high,2026-01-01 00:00:00,55,0.25
```

El formato largo suele ser mas flexible para agregar escenarios.

---

## 12. Salidas esperadas

El modelo debe producir resultados por escenario y periodo:

| Salida | Unidad | Descripcion |
| --- | --- | --- |
| `scenario` | texto | Nombre del escenario. |
| `probability` | p.u. | Probabilidad del escenario. |
| `timestamp` | fecha/hora | Periodo de optimizacion. |
| `cmg_usd_mwh` | USD/MWh | CMg usado en el escenario y periodo. |
| `charge_mw` | MW | Potencia de carga optima. |
| `discharge_mw` | MW | Potencia de descarga optima. |
| `soc_mwh` | MWh | Estado de carga optimo. |
| `is_charging` | binaria | Modo operativo optimo. |
| `charge_cost_usd` | USD | Costo de carga por periodo. |
| `discharge_revenue_usd` | USD | Ingreso por descarga por periodo. |
| `net_revenue_usd` | USD | Margen neto por periodo. |
| `expected_net_revenue_usd` | USD | Margen neto ponderado por probabilidad. |

Tambien se debe guardar:

- Valor esperado del objetivo.
- Resultado economico por escenario.
- Probabilidades usadas.
- Estado del solver.
- Configuracion usada.

---

## 13. Formulacion compacta

### Problema

```text
max sum_{s in S} prob_s *
    sum_{t in T} cmg_{s,t} * (discharge_mw_{s,t} - charge_mw_{s,t}) * delta_t_h
```

Sujeto a, para todo `s` y `t`:

```text
soc_mwh_{s,t} =
    soc_mwh_{s,t-1}
    + charge_mw_{s,t} * delta_t_h * charge_efficiency
    - discharge_mw_{s,t} * delta_t_h / discharge_efficiency
```

```text
soc_min_mwh <= soc_mwh_{s,t} <= soc_max_mwh
```

```text
0 <= charge_mw_{s,t} <= power_charge_max_mw * is_charging_{s,t}
```

```text
0 <= discharge_mw_{s,t} <= power_discharge_max_mw * (1 - is_charging_{s,t})
```

```text
is_charging_{s,t} in {0, 1}
```

```text
soc_mwh_{s,0} = soc_initial_mwh
```

Opcional:

```text
soc_mwh_{s,N} = soc_final_target_mwh
```

Con:

```text
sum_{s in S} prob_s = 1
```

```text
prob_s >= 0
```

---

## 14. Comentarios de implementacion

Para implementar esta formulacion en Pyomo:

- Crear un conjunto `SCENARIOS`.
- Crear un conjunto `TIME`.
- Cargar `cmg[s, t]` como parametro indexado por escenario y tiempo.
- Cargar `prob[s]` como parametro indexado por escenario.
- Crear variables indexadas por `(s, t)`.
- Agregar restricciones de bateria por cada `(s, t)`.
- Definir la funcion objetivo como suma ponderada por probabilidades.

La estructura recomendada es:

```text
1. Cargar escenarios de CMg y probabilidades.
2. Validar que las probabilidades sumen 1.
3. Validar que todos los escenarios tengan el mismo horizonte temporal.
4. Crear modelo, conjunto de escenarios y conjunto temporal.
5. Crear variables por escenario y periodo.
6. Agregar restricciones de balance, energia y modo operativo.
7. Agregar restricciones de no anticipatividad si corresponde.
8. Definir funcion objetivo esperada.
9. Resolver el MILP.
10. Extraer resultados por escenario.
11. Calcular resultados esperados y comparacion entre escenarios.
```

---

## 15. Comentario practico

El numero de variables y restricciones crece aproximadamente en proporcion a:

```text
numero de escenarios * numero de periodos
```

Por eso conviene partir con pocos escenarios representativos, por ejemplo:

- CMg bajo.
- CMg base.
- CMg alto.

Luego se pueden agregar mas escenarios, arboles de incertidumbre o tecnicas de reduccion de escenarios si el problema crece demasiado.
