# Pruebas Manuales TS-1

## Objetivo

Este archivo sirve como checklist manual para revisar la jerarquia de
topologia y parametros entregada en TS-1. El foco es comprobar que los
snapshots ejecutables generados (drafts estructurados y diagramas hidraulicos
v3) registran procedencia de topologia/parametros, que ediciones de topologia
y de parametros invalidan la validacion vigente de forma independiente, y que
versiones anteriores a TS-1 (sin metadata de jerarquia) siguen funcionando sin
cambios.

Tambien cubre regresiones que no deben romperse:

- Iteracion 3 a 5: flujo web draft/hidro -> `ScenarioVersion` -> `Run`.
- Iteracion 6: publicaciones y portal cliente sobre corridas existentes.

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
| Project | `TS-1 Manual Check` |
| Scenario (hidro) | `Hydraulic Provenance` |
| Scenario (draft) | `Structured Provenance` |

## Flujo Feliz: Diagrama Hidraulico

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Crear un diagrama hidraulico con embalse, junctions, central y unidad. | El diagrama valida y genera preview v3 con Julia real. | Pendiente |
| 2 | Promover el diagrama. | La version creada muestra seccion "Procedencia" con `Modelo: Diagrama hidraulico v3` y hashes distintos de topologia/parametros. | Pendiente |
| 3 | Editar solo conectividad (ej. reconectar `intake_node_key` de una unidad). | El diagrama queda "stale" y muestra el badge ambar "Topologia desactualizada" sin badge de parametros. | Pendiente |
| 4 | Intentar promover sin revalidar. | La promocion es rechazada mencionando "topology". | Pendiente |
| 5 | Revalidar y promover. | Nueva version con hash de topologia distinto y hash de parametros igual al anterior. | Pendiente |
| 6 | Editar solo un parametro (ej. `storage_max_hm3` del embalse). | El diagrama queda "stale" y muestra el badge morado "Parametros desactualizados" sin badge de topologia. | Pendiente |
| 7 | Intentar promover sin revalidar. | La promocion es rechazada mencionando "parameters" y no "topology". | Pendiente |
| 8 | Revalidar y promover. | Nueva version con hash de parametros distinto y hash de topologia igual al anterior. | Pendiente |
| 9 | Mover un nodo sin cambiar conectividad (solo layout). | El diagrama no queda stale y sigue promovible; hashes de topologia y parametros no cambian. | Pendiente |
| 10 | Lanzar una corrida manual sobre la ultima version. | La corrida resuelve `OPTIMAL` con HiGHS y muestra resultados/charts. | Pendiente |

## Flujo Feliz: Draft Estructurado

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Crear un draft estructurado (BESS + carga) con una fuente CSV mapeada. | El panel "Caso generado" muestra hashes de topologia/parametros tras validar. | Pendiente |
| 2 | Editar solo un parametro de un activo (ej. potencia maxima de carga de la bateria). | La promocion es rechazada mencionando "parameters" y no "topology". | Pendiente |
| 3 | Eliminar un activo (cambio estructural). | La promocion es rechazada mencionando "topology". | Pendiente |
| 4 | Revalidar y promover. | La version generada muestra `Modelo: ...structured_draft` con procedencia coherente. | Pendiente |

## Compatibilidad Legacy

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Abrir una version creada por paste/upload de JSON crudo (sin `kind`). | La seccion "Procedencia" muestra hashes de topologia/parametros pero sin fila "Modelo". | Pendiente |
| 2 | Abrir una version sembrada antes de TS-1 (sin `generation_metadata`), si hay una disponible. | La pagina carga sin error mostrando "Sin datos de procedencia" en vez de fallar. | Pendiente |
| 3 | Lanzar una corrida manual sobre una version legacy. | La corrida se comporta igual que sobre una version con procedencia (resuelve, registra artefactos). | Pendiente |
| 4 | Publicar y luego intentar eliminar una version legacy referenciada por una corrida. | La eliminacion es rechazada `409` mencionando referencias por corridas. | Pendiente |

## Errores Manuales A Revisar

| Caso | Como provocarlo | Resultado esperado | Estado |
| --- | --- | --- | --- |
| Promocion bloqueada por topologia | Cambiar conectividad y promover sin revalidar. | Mensaje explicito de "topology", no generico. | Pendiente |
| Promocion bloqueada por parametros | Cambiar un parametro y promover sin revalidar. | Mensaje explicito de "parameters", no generico. | Pendiente |
| Ambos cambian a la vez | Cambiar conectividad y un parametro en la misma edicion. | Ambos badges visibles; mensaje menciona "topology and parameters". | Pendiente |
| Layout no genera stale | Solo mover un nodo. | No hay badge de stale; promocion sigue habilitada. | Pendiente |

## Revision Visual

| Componente | Verificacion | Estado |
| --- | --- | --- |
| Version detail | Seccion "Procedencia" legible con hashes truncados y fila "Modelo" condicional. | Pendiente |
| Run detail | Hereda la misma "Procedencia" de su scenario version. | Pendiente |
| Editor hidraulico | Badges de stale distinguibles visualmente (ambar vs morado) y combinables. | Pendiente |
| Draft estructurado | Panel "Caso generado" muestra procedencia sin romper el resto del panel. | Pendiente |

## Verificacion Automatizada Complementaria

Estas pruebas no reemplazan la revision manual, pero sirven como referencia de
aceptacion de TS-1.

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ts1_acceptance -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

TS-1 no cambia contratos Julia, formatos de artefactos ni comportamiento del
optimizador. Ejecutar Julia solo si un cambio posterior los toca:

```powershell
julia --project=. -e "import Pkg; Pkg.test()"
```

## Cierre TS-1

Antes de aceptar la iteracion, ejecutar la suite automatizada enfocada y luego
la suite Python completa:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ts1_acceptance -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

No se requiere Julia para este cierre salvo que el cambio haya tocado
contratos Julia, formatos de artefactos o comportamiento del optimizador.

| Area | Resultado | Evidencia / notas |
| --- | --- | --- |
| Procedencia topologia/parametros | Pendiente | |
| Stale por topologia | Pendiente | |
| Stale por parametros | Pendiente | |
| Layout no genera stale | Pendiente | |
| Compatibilidad legacy | Pendiente | |
| Regresion iter3-iter6 | Pendiente | |
| Revision visual/responsive | Pendiente | |

Decision final:

```text
Aceptado / Rechazado / Aceptado con observaciones
```
