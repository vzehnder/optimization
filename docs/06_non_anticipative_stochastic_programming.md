# Formulacion MILP estocastica no anticipativa para programacion

## 1. Objetivo

Este documento define la formulacion recomendada para operar una bateria BESS bajo incertidumbre de CMg cuando se necesita obtener una trayectoria programable unica.

La idea central es separar:

- Decisiones programadas, que deben ser iguales para todos los escenarios porque se toman antes de saber que CMg ocurrira.
- Decisiones de recourse, que pueden depender del escenario y representan la capacidad de reoptimizar en el futuro.

En operacion real, esta formulacion se usa normalmente con rolling horizon:

```text
1. Resolver el modelo con escenarios de CMg.
2. Programar solo la primera decision o el primer bloque comprometido.
3. Observar nueva informacion.
4. Actualizar escenarios.
5. Reoptimizar.
```

Asi se evita el problema de obtener una trayectoria distinta por escenario para el periodo que realmente debe programarse.

---

## 2. Diferencia con el modelo wait-and-see

El modelo wait-and-see entrega variables por escenario:

```text
charge_mw_{s,t}
discharge_mw_{s,t}
soc_mwh_{s,t}
```

Eso es util para analisis, pero no entrega una sola trayectoria operable.

La formulacion recomendada impone decisiones comunes para el bloque programado:

```text
charge_mw_t
discharge_mw_t
soc_mwh_t
```

Luego permite variables por escenario solo para el futuro no comprometido:

```text
charge_mw_{s,t}
discharge_mw_{s,t}
soc_mwh_{s,t}
```

---

## 3. Conjuntos

### Escenarios

```text
S = {1, 2, ..., M}
```

Cada escenario `s` tiene un vector de CMg y una probabilidad `prob_s`.

### Periodos

```text
T = {1, 2, ..., N}
```

### Periodos programados

```text
P subset T
```

Estos son los periodos para los cuales se necesita una trayectoria unica. Por ejemplo:

- `P = {1}` si solo se ejecuta la primera decision.
- `P = {1, ..., 24}` si se debe programar un bloque diario.

### Periodos de recourse

```text
R = T \ P
```

Estos periodos se usan para valorar el futuro bajo distintos escenarios. Sus decisiones no se programan inmediatamente.

---

## 4. Parametros

### Incertidumbre

| Parametro | Unidad | Descripcion |
| --- | --- | --- |
| `prob_s` | p.u. | Probabilidad de ocurrencia del escenario `s`. |
| `cmg_{s,t}` | USD/MWh | CMg del escenario `s` en el periodo `t`. |

Las probabilidades deben cumplir:

```text
sum_{s in S} prob_s = 1
```

```text
prob_s >= 0
```

### Tiempo

| Parametro | Unidad | Descripcion |
| --- | --- | --- |
| `delta_t_h` | h | Duracion de cada periodo. |

### Bateria

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

### Terminal opcional

| Parametro | Unidad | Descripcion |
| --- | --- | --- |
| `soc_final_target_mwh` | MWh | Estado de carga final deseado al final del horizonte. |

---

## 5. Variables de decision

## 5.1 Variables programadas

Para cada periodo `t` en `P`:

| Variable | Unidad | Dominio | Descripcion |
| --- | --- | --- | --- |
| `charge_mw_t` | MW | `>= 0` | Potencia de carga programada. |
| `discharge_mw_t` | MW | `>= 0` | Potencia de descarga programada. |
| `soc_mwh_t` | MWh | `>= 0` | Estado de carga programado. |
| `is_charging_t` | binaria | `{0, 1}` | Modo operativo programado. |

Estas variables no tienen indice de escenario. Por construccion, son no anticipativas.

## 5.2 Variables de recourse

Para cada escenario `s` en `S` y periodo `t` en `R`:

| Variable | Unidad | Dominio | Descripcion |
| --- | --- | --- | --- |
| `charge_mw_{s,t}` | MW | `>= 0` | Potencia de carga futura si ocurre el escenario `s`. |
| `discharge_mw_{s,t}` | MW | `>= 0` | Potencia de descarga futura si ocurre el escenario `s`. |
| `soc_mwh_{s,t}` | MWh | `>= 0` | Estado de carga futuro si ocurre el escenario `s`. |
| `is_charging_{s,t}` | binaria | `{0, 1}` | Modo operativo futuro si ocurre el escenario `s`. |

Estas variables no se programan inmediatamente. Sirven para estimar el valor esperado de quedar en cierto estado de carga al final del bloque programado.

---

## 6. Funcion objetivo

El objetivo maximiza el valor esperado del margen economico total:

```text
max
sum_{s in S} prob_s *
[
  sum_{t in P} cmg_{s,t} * (discharge_mw_t - charge_mw_t) * delta_t_h
  +
  sum_{t in R} cmg_{s,t} * (discharge_mw_{s,t} - charge_mw_{s,t}) * delta_t_h
]
```

El primer termino valora la trayectoria unica programada bajo todos los escenarios posibles de CMg.

El segundo termino valora la operacion futura adaptable a cada escenario.

---

## 7. Restricciones programadas

### 7.1 Balance de estado de carga

Para el primer periodo programado:

```text
soc_mwh_1 =
    soc_initial_mwh
    + charge_mw_1 * delta_t_h * charge_efficiency
    - discharge_mw_1 * delta_t_h / discharge_efficiency
```

Para cada periodo programado `t > 1`:

```text
soc_mwh_t =
    soc_mwh_{t-1}
    + charge_mw_t * delta_t_h * charge_efficiency
    - discharge_mw_t * delta_t_h / discharge_efficiency
```

### 7.2 Limites de estado de carga

Para cada `t` en `P`:

```text
soc_min_mwh <= soc_mwh_t <= soc_max_mwh
```

### 7.3 Limite de potencia de carga

Para cada `t` en `P`:

```text
0 <= charge_mw_t <= power_charge_max_mw * is_charging_t
```

### 7.4 Limite de potencia de descarga

Para cada `t` en `P`:

```text
0 <= discharge_mw_t <= power_discharge_max_mw * (1 - is_charging_t)
```

Estas dos restricciones impiden carga y descarga simultanea en la trayectoria programada.

---

## 8. Restricciones de recourse

Sea `r0` el primer periodo de `R` y `p_end` el ultimo periodo de `P`.

### 8.1 Enlace entre programacion y recourse

Para cada escenario `s`, el estado de carga inicial del recourse debe ser el estado final del bloque programado:

```text
soc_mwh_{s,r0} =
    soc_mwh_{p_end}
    + charge_mw_{s,r0} * delta_t_h * charge_efficiency
    - discharge_mw_{s,r0} * delta_t_h / discharge_efficiency
```

### 8.2 Balance de estado de carga futuro

Para cada escenario `s` y periodo `t` en `R`, con `t > r0`:

```text
soc_mwh_{s,t} =
    soc_mwh_{s,t-1}
    + charge_mw_{s,t} * delta_t_h * charge_efficiency
    - discharge_mw_{s,t} * delta_t_h / discharge_efficiency
```

### 8.3 Limites de estado de carga

Para cada escenario `s` y periodo `t` en `R`:

```text
soc_min_mwh <= soc_mwh_{s,t} <= soc_max_mwh
```

### 8.4 Limite de potencia de carga

Para cada escenario `s` y periodo `t` en `R`:

```text
0 <= charge_mw_{s,t} <= power_charge_max_mw * is_charging_{s,t}
```

### 8.5 Limite de potencia de descarga

Para cada escenario `s` y periodo `t` en `R`:

```text
0 <= discharge_mw_{s,t} <= power_discharge_max_mw * (1 - is_charging_{s,t})
```

---

## 9. Condicion terminal opcional

Para reducir efectos de borde, se puede imponer una condicion terminal por escenario:

```text
soc_mwh_{s,N} = soc_final_target_mwh
```

Una opcion simple es:

```text
soc_final_target_mwh = soc_initial_mwh
```

Si el horizonte se resuelve en rolling horizon, esta condicion puede reemplazarse por un valor terminal aproximado o por un horizonte suficientemente largo.

---

## 10. Formulacion equivalente con no anticipatividad explicita

Otra forma de escribir el mismo concepto es usar variables por escenario para todo el horizonte y agregar igualdades en los periodos programados.

Para todo par de escenarios `s` y `s'`, y para todo `t` en `P`:

```text
charge_mw_{s,t} = charge_mw_{s',t}
```

```text
discharge_mw_{s,t} = discharge_mw_{s',t}
```

```text
soc_mwh_{s,t} = soc_mwh_{s',t}
```

```text
is_charging_{s,t} = is_charging_{s',t}
```

La formulacion con variables programadas sin indice `s` es mas limpia y evita crear igualdades redundantes.

---

## 11. Que trayectoria se programa

La trayectoria que se programa en la bateria es solo:

```text
charge_mw_t
discharge_mw_t
soc_mwh_t
is_charging_t
```

para `t` en `P`.

Las trayectorias:

```text
charge_mw_{s,t}
discharge_mw_{s,t}
soc_mwh_{s,t}
```

para `t` en `R` no se programan directamente. Representan planes futuros condicionados a cada escenario.

En rolling horizon, despues de ejecutar el primer periodo o bloque:

```text
1. Se actualiza `soc_initial_mwh` con el estado real de la bateria.
2. Se actualizan los escenarios de CMg.
3. Se vuelve a resolver el modelo.
4. Se programa el siguiente periodo o bloque.
```

---

## 12. Relacion con usar CMg esperado

Si todas las decisiones deben ser iguales para todos los escenarios durante todo el horizonte:

```text
P = T
```

y el unico parametro incierto es el CMg en una funcion objetivo lineal, entonces el modelo es equivalente a optimizar con:

```text
expected_cmg_t = sum_{s in S} prob_s * cmg_{s,t}
```

En ese caso, usar CMg esperado es suficiente.

La formulacion estocastica aporta valor cuando:

- Solo una parte del horizonte esta comprometida y el futuro puede adaptarse.
- Se usa rolling horizon.
- Se agregan metricas de riesgo.
- Hay restricciones que dependen del escenario.
- Se quiere estimar el valor esperado de conservar energia para escenarios futuros.

---

## 13. Entradas minimas requeridas

| Entrada | Fuente esperada |
| --- | --- |
| Escenarios de CMg `cmg_{s,t}` | `data/processed/time_series/` |
| Probabilidades `prob_s` | `config/scenarios.yaml` |
| Largo del bloque programado `P` | `config/scenarios.yaml` |
| Horizonte total `T` | `config/scenarios.yaml` |
| Parametros de bateria | `config/battery_params.yaml` |
| Configuracion de solver MILP | `config/default_config.yaml` |

Ejemplo conceptual:

```yaml
stochastic_programming:
  commitment_periods: 1
  horizon_periods: 24
  scenarios:
    - name: low_cmg
      probability: 0.25
      cmg_file: cmg_low.csv
    - name: base_cmg
      probability: 0.50
      cmg_file: cmg_base.csv
    - name: high_cmg
      probability: 0.25
      cmg_file: cmg_high.csv
```

---

## 14. Salidas esperadas

### Salida programable

Esta es la salida que se usa para operar la bateria:

| Salida | Unidad | Descripcion |
| --- | --- | --- |
| `timestamp` | fecha/hora | Periodo programado. |
| `charge_mw` | MW | Potencia de carga programada. |
| `discharge_mw` | MW | Potencia de descarga programada. |
| `soc_mwh` | MWh | Estado de carga esperado despues del periodo. |
| `is_charging` | binaria | Modo operativo programado. |

### Salida analitica por escenario

Esta salida sirve para evaluar el valor futuro y la sensibilidad:

| Salida | Unidad | Descripcion |
| --- | --- | --- |
| `scenario` | texto | Escenario de CMg. |
| `probability` | p.u. | Probabilidad del escenario. |
| `timestamp` | fecha/hora | Periodo futuro. |
| `cmg_usd_mwh` | USD/MWh | CMg del escenario. |
| `charge_mw` | MW | Potencia de carga futura condicionada al escenario. |
| `discharge_mw` | MW | Potencia de descarga futura condicionada al escenario. |
| `soc_mwh` | MWh | Estado de carga futuro condicionado al escenario. |
| `net_revenue_usd` | USD | Margen por escenario. |

---

## 15. Recomendacion practica

Para una primera implementacion operativa, usar:

```text
P = {1}
```

Es decir:

- Resolver un horizonte de varias horas con escenarios.
- Ejecutar solo la primera decision.
- Reoptimizar en el siguiente periodo.

Esto evita comprometer una trayectoria larga basada en informacion incierta y aprovecha los escenarios para asignar valor al estado de carga futuro.

Si el proceso operativo exige programar un bloque completo, por ejemplo 24 horas, usar:

```text
P = {1, ..., 24}
```

En ese caso la trayectoria diaria sera unica. Si no hay recourse ni penalizaciones de riesgo, el resultado tendera a comportarse como una optimizacion contra el CMg esperado.
