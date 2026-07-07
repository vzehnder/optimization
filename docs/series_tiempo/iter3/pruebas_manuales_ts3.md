# Pruebas Manuales TS-3

## Objetivo

Este archivo sirve como checklist manual para revisar el flujo central de
variantes de series por caso entregado en TS-3. El foco es comprobar que un
caso expone una variante default, que los bindings requeridos se descubren
desde la topologia activa, que el rango elegido exige cobertura exacta sin
resampling implicito, que cambios en series dejan la variante desactualizada
hasta revalidar, y que dos variantes del mismo caso generan runs con lineage
distinto sin romper la ruta legacy de `ScenarioVersion -> Run`.

Tambien cubre regresiones que no deben romperse:

- TS-1: hashes de topologia/parametros y stale por cambios del caso.
- TS-2: sets versionados, revisiones y hashes de series en BBDD.
- Iteracion 3 a 6: flujo React, runs, resultados, publicaciones y portal
  cliente sobre corridas existentes.

## Registro De Prueba

| Campo | Valor |
| --- | --- |
| Fecha | |
| Tester | |
| Rama/commit | |
| Navegador | |
| URL local | |
| Resultado general | Pendiente |

## Preparacion Local

Ejecutar desde la raiz del repositorio. Editar `DB_PASSWORD` en `.env` para
que coincida con el rol local de PostgreSQL.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Abrir:

```text
http://127.0.0.1:8000/
```

Si el puerto `8000` esta ocupado, usar otro puerto con `--port 8001` y ajustar
la URL de revision.

## Datos De Prueba

| Tipo | Valor sugerido |
| --- | --- |
| Project | `TS-3 Manual Check` |
| Scenario | `Variant workflow` |
| Case shape | `grid + battery + load + renewable` |
| Variant A | `Default` |
| Variant B | `Stress prices` |
| Set price base | `Spot A` |
| Set price stress | `Spot B` |
| Set load | `Load base` |
| Set renewable hourly | `Solar hourly` |
| Set renewable mismatch | `Solar 2h` |

## Flujo Feliz: Default Variant Y Bindings Requeridos

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Crear o abrir un caso con grid, bateria, carga y renovable. | El panel de variantes muestra `Default` aunque el caso no haya tenido variantes previas. | Pendiente |
| 2 | Revisar la lista de `required_signals`. | Aparecen `price_usd_per_mwh`, `load_demand_mw` (`load_1`) y `renewable_available_power_mw` (`solar_1`). | Pendiente |
| 3 | Vincular solo el set `Spot A` al precio. | La variante sigue incompleta y el panel deja visibles las familias faltantes. | Pendiente |
| 4 | Intentar correr con solo el binding de precio. | El backend responde `400` nombrando `load_demand_mw` y `renewable_available_power_mw` como faltantes. | Pendiente |
| 5 | Vincular `Load base` a `load_1`. | El panel sigue marcando solo el renovable como faltante. | Pendiente |
| 6 | Vincular `Solar hourly` a `solar_1`. | La variante queda completa y lista para validar o correr. | Pendiente |

## Errores Manuales A Revisar

| Caso | Como provocarlo | Resultado esperado | Estado |
| --- | --- | --- | --- |
| Cobertura incompleta | Elegir un `range_end` una hora mas alla del horizonte de los sets. | Error `missing coverage` nombrando binding, set y tramo faltante; no se crea run. | Pendiente |
| Horizonte incompatible | Reemplazar `Solar hourly` por `Solar 2h` y correr el mismo rango. | Error `horizon incompatible ... no implicit resampling`; no se crea run. | Pendiente |
| Variante stale por series | Validar o correr la variante y luego editar un valor del set `Spot A`. | La variante queda `desactualizada`, el dropdown/banner explican motivo y el run queda bloqueado. | Pendiente |
| Revalidacion requerida | Intentar correr la variante stale sin revalidar. | Error `stale` o banner equivalente; no se crea run nuevo. | Pendiente |

## Flujo Feliz: Stale Y Revalidacion

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Con la variante completa, presionar `Revalidar variante` o validar el rango. | Estado `valid` y sin marker de stale. | Pendiente |
| 2 | Editar un valor del set de precio ya vinculado. | La variante pasa a `desactualizada` sin recargar la pagina. | Pendiente |
| 3 | Presionar `Revalidar variante`. | El marker stale desaparece y el boton de correr vuelve a habilitarse. | Pendiente |

## Flujo Feliz: Clonar Y Correr Dos Variantes

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Clonar `Default` como `Stress prices`. | El dropdown muestra ambas variantes y `Default` sigue marcado como default. | Pendiente |
| 2 | En `Stress prices`, rebind solo el precio al set `Spot B`. | `Default` conserva `Spot A`; el clone cambia solo su binding de precio. | Pendiente |
| 3 | Correr `Default` sobre un rango valido. | Se crea un run exitoso con snapshot tecnico y lineage de `Default`. | Pendiente |
| 4 | Correr `Stress prices` sobre el mismo rango. | Se crea otro run exitoso con snapshot distinto, distinto hash de precio y mismo hash de carga/renovable. | Pendiente |
| 5 | Abrir ambos run details. | Se ve `Variante`, `Rango de fechas`, `Series de entrada` y `Ver snapshot tecnico` colapsado por defecto. | Pendiente |
| 6 | Revisar la lista de runs del caso. | Ambos runs aparecen diferenciados por variante; no se mezclan como solo `Version N`. | Pendiente |

## Compatibilidad Legacy

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Crear una `ScenarioVersion` via JSON crudo por la ruta legacy. | La version se guarda y puede lanzar un run sin tocar variantes. | Pendiente |
| 2 | Abrir el run/detail de esa version legacy. | La UI no falla; simplemente no muestra lineage TS-3 de variante. | Pendiente |
| 3 | Ver legacy run y variant runs coexistiendo en el mismo sistema. | Ambos flujos funcionan en paralelo sin regression. | Pendiente |

## Revision Visual

| Componente | Verificacion | Estado |
| --- | --- | --- |
| Dropdown de variantes | Marca clara de default y estado stale visible cuando aplica. | Pendiente |
| Editor de bindings | Lista legible de `required_signals`, sets vinculados y CTA de revalidacion/correr. | Pendiente |
| Alertas de validacion | Mensajes de faltantes, cobertura y horizonte compatibles con soporte. | Pendiente |
| Run detail | Secciones `Variante`, `Rango de fechas`, `Series de entrada` y snapshot tecnico legibles. | Pendiente |
| Lista de runs | Distingue runs por variante sin romper runs legacy. | Pendiente |

## Verificacion Automatizada Complementaria

Estas pruebas no reemplazan la revision manual, pero sirven como referencia de
aceptacion de TS-3.

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ts3_acceptance -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Desde `frontend/`:

```powershell
npm test -- --run
npx tsc -b
npx eslint .
npm run api:check
npm run build
```

TS-3 reutiliza el contrato Julia actual. Ejecutar Julia solo si un cambio
posterior toca `system_case_json`, comportamiento del optimizador o formatos
de artefactos:

```powershell
julia --project=. -e "import Pkg; Pkg.test()"
```

## Cierre TS-3

Antes de aceptar la iteracion, ejecutar la suite automatizada enfocada, la
suite Python completa y la verificacion frontend:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ts3_acceptance -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

```powershell
cd frontend
npm test -- --run
npx tsc -b
npx eslint .
npm run api:check
npm run build
```

No se requiere Julia para este cierre salvo que el cambio haya tocado
contratos Julia, formatos de artefactos o comportamiento del optimizador.

| Area | Resultado | Evidencia / notas |
| --- | --- | --- |
| Variant default y required signals | Pendiente | |
| Missing binding errors claros | Pendiente | |
| Coverage exacta | Pendiente | |
| Horizon compatibility sin resampling | Pendiente | |
| Stale + revalidacion | Pendiente | |
| Clone y dos variantes | Pendiente | |
| Run lineage y snapshot tecnico | Pendiente | |
| Compatibilidad legacy | Pendiente | |
| Regresion TS-1, TS-2 e iter3-iter6 | Pendiente | |
| Revision visual/responsive | Pendiente | |

Decision final:

```text
Aceptado / Rechazado / Aceptado con observaciones
```
