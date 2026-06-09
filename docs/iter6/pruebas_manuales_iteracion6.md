# Pruebas Manuales Iteracion 6

## Objetivo

Este archivo sirve como checklist manual para revisar el flujo web entregado en
Iteracion 6. El foco es comprobar que la aplicacion privada tiene autenticacion,
roles, gestion minima de usuarios, asignacion de clientes a proyectos,
templates de dashboard, publicaciones controladas sobre corridas exitosas, un
portal cliente read-only y descargas filtradas por allowlist.

Tambien cubre regresiones que no deben romperse:

- Iteracion 3: flujo web `Project -> Scenario -> ScenarioVersion -> Run`.
- Iteracion 4: editor estructurado, CSV/XLSX, precios separados y resultados.
- Iteracion 5: contrato `v2`, hidro simple, resultados y charts hidro.
- Iteracion 6: auth, roles, publicaciones, portal cliente y revocacion.

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

Ejecutar desde la raiz del repositorio.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:DATABASE_URL = "sqlite:///.tmp/manual_iter6.sqlite3"
$env:ARTIFACT_ROOT = ".tmp/manual-artifacts"
$env:INPUT_SOURCE_ROOT = ".tmp/manual-input-sources"
$env:JULIA = "julia"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Abrir:

```text
http://127.0.0.1:8000/
```

Si el puerto `8000` esta ocupado, usar otro puerto con `--port 8001` y ajustar
la URL de revision.

## Datos De Prueba

Usar o crear al menos:

| Tipo | Valor sugerido |
| --- | --- |
| Admin | `admin@example.local` |
| Analyst | `analyst@example.local` |
| Client | `client@example.local` |
| Project | `Iter6 Manual Publication` |
| Scenario | `Client Portal Scenario` |
| Dashboard template | `Client Summary Template` |
| Publication title | `January Hybrid Dispatch Results` |

Para obtener una corrida `succeeded`, se puede usar una version creada desde el
editor estructurado de Iteracion 5 o el flujo legacy paste/upload existente.

## Flujo Feliz

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Abrir la app sin sesion. | La app redirige a login o muestra estado no autenticado; no permite entrar a `/projects`. | Pendiente |
| 2 | Crear/bootstrappear el primer admin segun la documentacion de la iteracion. | Existe un usuario `admin` activo con password hasheada. | Pendiente |
| 3 | Iniciar sesion como admin. | Redirige al area interna; se ven controles administrativos. | Pendiente |
| 4 | Crear usuario `analyst`. | El usuario aparece activo con rol `analyst`. | Pendiente |
| 5 | Crear usuario `client`. | El usuario aparece activo con rol `client`. | Pendiente |
| 6 | Crear o seleccionar proyecto `Iter6 Manual Publication`. | El proyecto existe en la app interna. | Pendiente |
| 7 | Asignar `client` al proyecto. | El cliente queda listado como asignado al proyecto. | Pendiente |
| 8 | Crear o seleccionar una corrida `succeeded` dentro del proyecto. | La corrida tiene artefactos registrados y pagina interna de resultados. | Pendiente |
| 9 | Crear dashboard template `Client Summary Template`. | El template permite activar/desactivar summary, charts y previews. | Pendiente |
| 10 | Crear publicacion desde la corrida `succeeded`. | La publicacion queda en estado draft/unpublished y referencia proyecto, scenario, version y run. | Pendiente |
| 11 | Configurar titulo, notas, template y downloads. | `summary_json`, `dispatch_csv` y `asset_dispatch_csv` quedan habilitados o seleccionables. | Pendiente |
| 12 | Abrir preview como cliente. | La vista muestra exactamente el dashboard curado, sin controles internos. | Pendiente |
| 13 | Publicar. | La publicacion pasa a `published`. | Pendiente |
| 14 | Cerrar sesion interna. | La sesion termina. | Pendiente |
| 15 | Iniciar sesion como cliente. | Redirige al portal cliente. | Pendiente |
| 16 | Abrir lista de proyectos cliente. | Solo aparece el proyecto asignado. | Pendiente |
| 17 | Abrir detalle del proyecto. | Aparece la publicacion activa. | Pendiente |
| 18 | Abrir la publicacion. | Se ven titulo, notas, metadatos, summary, charts y previews permitidos. | Pendiente |
| 19 | Descargar artefactos permitidos. | Downloads habilitados responden correctamente. | Pendiente |
| 20 | Intentar acceder a una ruta interna como cliente. | La app rechaza o redirige; no muestra controles de analista. | Pendiente |

## Revocacion

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Como admin/analyst, despublicar la publicacion. | Cliente deja de verla inmediatamente. | Pendiente |
| 2 | Intentar abrir la URL de la publicacion como cliente. | Responde `403`, `404` o redireccion controlada; no muestra resultados. | Pendiente |
| 3 | Republicar y luego remover asignacion cliente-proyecto. | El proyecto desaparece del portal cliente. | Pendiente |
| 4 | Intentar descargar un artefacto antes habilitado. | La descarga queda bloqueada por falta de acceso. | Pendiente |
| 5 | Desactivar el usuario cliente. | El cliente no puede iniciar sesion ni seguir usando rutas protegidas. | Pendiente |

## Errores Manuales A Revisar

| Caso | Como provocarlo | Resultado esperado | Estado |
| --- | --- | --- | --- |
| Login invalido | Password incorrecta. | No se crea sesion; mensaje claro. | Pendiente |
| Usuario desactivado | Desactivar cliente y tratar de entrar. | Login rechazado o sesion invalidada. | Pendiente |
| Run fallido | Intentar crear publicacion desde run `failed`. | La app rechaza la publicacion. | Pendiente |
| Sin template | Intentar publicar sin template cuando el flujo lo requiera. | Error claro o template default controlado. | Pendiente |
| Artifact no habilitado | Adivinar URL de `stdout_log` o `input_snapshot`. | Acceso denegado para cliente. | Pendiente |
| Proyecto no asignado | Adivinar URL de otro proyecto. | Acceso denegado para cliente. | Pendiente |
| Publicacion draft | Adivinar URL de una publicacion no publicada. | Acceso denegado para cliente. | Pendiente |
| Cliente en API interna | Llamar endpoint de draft, upload, validation, promotion o launch run. | Acceso denegado. | Pendiente |

## Revision Visual

| Componente | Verificacion | Estado |
| --- | --- | --- |
| Login | Formulario claro, errores legibles, sin controles internos visibles. | Pendiente |
| Admin users | Lista usuarios, roles y estado activo/desactivado sin superposicion. | Pendiente |
| Project access | Asignacion y remocion de clientes es entendible. | Pendiente |
| Dashboard templates | Controles de secciones son claros y no parecen builder avanzado. | Pendiente |
| Publication editor | Titulo, notas, template, allowlist y estado son visibles. | Pendiente |
| Preview cliente | No muestra botones internos ni artefactos deshabilitados. | Pendiente |
| Portal cliente | Navegacion simple: proyectos, publicaciones, cuenta/logout. | Pendiente |
| Publication detail | Summary, charts y previews caben en desktop y movil. | Pendiente |
| Downloads | Nombres, tipos y disponibilidad son claros. | Pendiente |
| Revoked state | Paginas revocadas no filtran informacion sensible. | Pendiente |

## Verificacion Automatizada Complementaria

Estas pruebas no reemplazan la revision manual, pero sirven como referencia de
aceptacion de Iteracion 6.

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_iter6_acceptance -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Si alguna implementacion de Iteracion 6 toca contratos Julia, formatos de
artefactos o comportamiento del optimizador, tambien ejecutar:

```powershell
julia --project=. -e "import Pkg; Pkg.test()"
```

## Cierre

| Area | Resultado | Evidencia / notas |
| --- | --- | --- |
| Auth y roles | Pendiente | |
| Gestion de usuarios | Pendiente | |
| Asignacion cliente-proyecto | Pendiente | |
| Dashboard templates | Pendiente | |
| Publicacion y preview | Pendiente | |
| Portal cliente read-only | Pendiente | |
| Descargas allowlisted | Pendiente | |
| Revocacion inmediata | Pendiente | |
| Regresion analyst app | Pendiente | |
| Revision visual/responsive | Pendiente | |

Decision final:

```text
Aceptado / Rechazado / Aceptado con observaciones
```
