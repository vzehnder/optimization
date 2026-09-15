# UX-009 · Administración comprensible

Base: `902662a`, árbol limpio al iniciar. Responsable: Codex.
Inicio y entrega para revisión: 2026-09-14. Estado: **In Review**.
Commit solicitado por el usuario el 2026-09-15:
`feat(ux): clarify administration and sensitive actions`, sobre `902662a`.
Sin PR; aceptación del resultado pendiente.

## Fronteras confirmadas

El usuario respondió **«Confirmo F1 y F2 para UX-009»** antes de escribir
la primera prueba nueva, aplicando la [skill TDD](../../../../.agents/skills/tdd/SKILL.md).

- F1: navegador → React → FastAPI/SQLite aislado para creación de usuarios,
  capacidades y acciones sensibles, persistencia y autorización reales.
- F2: React renderizado con HTTP controlado para errores, valores conservados
  y confirmaciones; aserciones sobre la interfaz pública.
- F3: regresiones existentes. No cambian contratos, roles ni permisos.
  F4 no aplica a este cambio de interfaz.

Se revisaron el paquete del plan, sus diez tickets, tracker, evidencias
históricas, scripts y resultados; 88 capturas históricas mediante cinco
hojas de contacto. El siguiente ticket sin implementar era UX-009.
La API vigente rechaza `client` al crear usuarios; la migración histórica
conserva `external + portal_view`, sin ampliar a operación. El formulario aún
ofrecía `client` aunque tampoco lo admitía su propia validación local.

Línea base: 8 pruebas de Admin/ExternalAccess/ApplicationRoots y 9 pruebas de
`test_configuration_layer_access` aprobadas. No se suman al resultado final.

## Resultado visible

- **Usuarios y accesos / Programación** dentro de `/react/admin/users`, con
  sección en la URL, recarga e historial. Ambos formularios conservan sus
  valores al alternar secciones; no se promete persistencia del borrador tras
  recargar la página.
- Roles **Administrador**, **Analista** y **Usuario externo**, con valores
  canónicos conservados. Error de email duplicado o inválido traducido,
  vinculado al campo y enfocado, sin vaciar los demás valores.
- En Accesos de cada proyecto, **Ver informes** y **Operar consolas** son
  decisiones independientes, inicialmente desmarcadas. Se revisan persona,
  proyecto y resultado antes de otorgar; al editar se muestran antes/después.
  Cancelar devuelve el foco y conserva la selección. Una respuesta fallida
  conserva la revisión y permite reintentar explícitamente.
- Revocar explica el alcance de ese proyecto y desactivar explica el alcance
  de toda la cuenta: efecto en la siguiente solicitud, sin afirmar que se
  cancelan ejecuciones iniciadas. Las confirmaciones y la autorización del
  servidor permanecen.
- Programación mantiene crear, listar, refrescar, ejecutar vencidos, rangos
  fijos/móviles, variante, frecuencia, estado e historial. Las fechas rechazadas
  por formato u offset se asocian a su campo y conservan los valores para corregir.
- El borrado contextual conserva nombre, advertencia completa, cancelación,
  confirmación y purga existente. Un fallo no se muestra como éxito.
- Correos largos y controles se ajustan al ancho de 320 píxeles.

## Ciclos TDD

Se implementó un comportamiento por ciclo. Los [extractos RED → GREEN](tdd-cycles.txt)
contienen comandos y resultados reales; las omisiones por `-t` son filtros,
no pruebas aprobadas. Ocho pruebas F2 evolucionaron mediante nueve ciclos;
una novena prueba de recuperación se añadió como regresión suplementaria.

| Ciclo | RED observado | GREEN |
| --- | --- | --- |
| 01 F2 | Cuatro roles técnicos, incluido `client`, frente a tres etiquetas canónicas | Crear/reabrir Usuario externo, tres opciones legibles |
| 02 F2 | No existe «Ver informes» ni revisión del acceso | Selección independiente, revisión del destinatario y persistencia |
| 03 F2 | Guardar no abre «Revisar cambios» | Comparación antes/después y confirmación sin perder el permiso existente |
| 04 F2 | Error crudo `email already exists` | Mensaje asociado al email, foco y corrección conservando formulario |
| 05 F2 | Ejecutar vencidos aparece junto a usuarios | Secciones separadas con los dos formularios conservados |
| 06 F2 | Falta Reintentar accesos tras fallo HTTP | Reconsulta y recuperación del formulario |
| 07 F2 | Error crudo de fecha sin offset | Mensaje de campo, foco, valores conservados y reintento |
| 08 F2 | El foco se pierde al abrir la revisión del alta | Encabezado enfocado, Tab a confirmar y retorno al selector |
| 09 F2 | El foco se pierde al revisar una edición de permisos | Encabezado enfocado y retorno a permisos al cancelar |
| 10 F1 | Desbordamiento horizontal en usuarios a 320 px | Correos y filas ajustados; recorrido y layout completos aprobados |
| 11 F1 | La lista se comprime junto al formulario al ampliar al 200 % | Cuadrícula adaptable; lista y formulario se apilan conservando ancho legible |

El [RED de layout](browser-layout-red.txt) falla en la aserción de ancho.
El [RED de ampliación](browser-zoom-red.txt) exige que lista y formulario se
apilen al 200 %. Después del último ajuste CSS se repitieron build y los tres
recorridos afectados: administración, UX-009 y accesibilidad. El GREEN final
aparece en [Playwright focalizado](playwright-affected-final.txt); sus tres
pruebas ya están incluidas en las 23 de la suite completa y no se suman otra vez.
La primera repetición del ciclo 09 pasó las ocho pruebas nuevas y falló un
selector ambiguo de la regresión antigua; se corrigió usando el nombre
accesible que identifica al usuario. La suite final completa pasa.

Otros ajustes del arnés no se cuentan como RED funcional: codificación del
pipe de PowerShell, consulta a una ruta de portal inexistente (corregida a
`/publications`), lectura del objeto de creación de proyecto (respuesta plana),
y opciones `exact` no soportadas por los tipos de `getByRole` de Testing Library.
El recorrido antiguo de administración pasó a timeout de 10 s tras medir
5,36 s con los pasos de revisión añadidos; sus aserciones se conservan.

## Validación final

**335 pruebas aprobadas**, sin duplicar líneas base ni repeticiones focalizadas.

| Comprobación | Resultado | Evidencia |
| --- | --- | --- |
| Vitest completo | 267 aprobadas, 22 archivos | [Salida](vitest-final.txt) |
| Playwright completo, incluye build | 23 aprobadas | [Salida](playwright-final.txt) |
| Repetición tras el último ajuste CSS | 3 recorridos afectados aprobados, build aprobado; no se suman al total | [Salida](playwright-affected-final.txt) |
| Seis módulos Python afectados | 45 aprobadas, 2 PostgreSQL omitidas; 47 ejecutadas | [Salida](python-final.txt) |
| TypeScript y ESLint | Aprobados; `check` alcanza Prettier | [Salida](check-final.txt) |
| Formato de los siete archivos frontend modificados | Aprobado | [Salida](format-final.txt) |
| Formato global | Falla en 21 archivos previos sin modificaciones | [Lista y salida](check-final.txt) |
| `git diff --check` | Aprobado | [Salida](diff-check.txt) |

Desde `frontend/`:

```powershell
npm.cmd test -- --maxWorkers=2
$env:DATABASE_URL = 'sqlite:///:memory:'
npm.cmd run test:browser
# Tras el último ajuste de layout, repetir los recorridos afectados:
npm.cmd run test:browser -- --grep "UX-009 administers|React admin users|representative React"
npm.cmd run check
npm.cmd exec prettier -- --check src/Admin.tsx src/Admin.test.tsx src/AdminExperience.test.tsx src/App.test.tsx e2e/react-foundation.spec.ts e2e/smoke-accessibility.spec.ts src/styles.css
```

Desde la raíz:

```powershell
$env:DATABASE_URL = 'sqlite:///:memory:'
.\.venv\Scripts\python.exe -m unittest tests.test_configuration_layer_access tests.test_react_auth tests.test_ts6_008_schedules tests.test_ts6_acceptance tests.test_ts7_024_project_purge tests.test_iter6_authorization_hardening -v
git diff --check
```

El recorrido F1 crea una identidad desde UI y comprueba persistencia tras
recarga; concede informes sin operación, agrega operación sin retirar informes,
revoca solo informes manteniendo operativa una sesión abierta, revoca todo y
desactiva la cuenta. La siguiente solicitud recibe el rechazo correspondiente.
Crea una programación futura fija, la reabre y evalúa vencidos sin lanzar una
ejecución anticipada; comprueba atrás/adelante. Finalmente cancela y confirma
el borrado de un proyecto desechable con escenario. Las regresiones Python
cubren rangos móviles, auditoría y purga; la prueba F2 existente de borrado se
amplió con un 503 y reintento. No se presentan esos comportamientos existentes
como funcionalidades nuevas.

## Conservación funcional

Filas afectadas de la [matriz](../../03_matriz_funcional.md):

| Capacidad | Acceso final | Evidencia |
| --- | --- | --- |
| Identidad, sesión y rechazo de acceso | Login y tres raíces vigentes | Auth F1 completo y `test_react_auth` |
| Usuarios, desactivación y capacidades | Administración → Usuarios y accesos; Proyecto → Accesos | AdminExperience, Admin, App; F1 UX-009; API de acceso |
| Portal, publicaciones y descargas | Portal autorizado existente | Recorrido de portal completo, revocación F1 y hardening API |
| Programación y horizonte móvil | Administración → Programación | App, F1 UX-009, `test_ts6_008_schedules` y `test_ts6_acceptance` |
| Eliminar proyecto y dependencias | Menú contextual de Proyectos | App con error/reintento, F1 UX-009 y `test_ts7_024_project_purge` |

No se modifica `Workspace.tsx`, la API, migraciones, roles, permisos ni purga.
Se preservan las denegaciones de analistas/externos y la ausencia de detalles
administrativos en superficies externas mediante las regresiones existentes.
La revisión estructural posterior conserva estados de revisión locales,
controles deshabilitados durante confirmación/envío y HTTP como frontera de
prueba; no requiere abstraer ni refactorizar otros módulos.

## Revisión visual y accesibilidad

14 capturas de datos sintéticos, conservadas localmente en `capturas/` y
excluidas de Git; Playwright las regenera en `frontend/test-results/`:

- `ux009-usuarios-{1440,1280,320,zoom200}.png`.
- `ux009-revision-acceso-{1440,1280,320,zoom200}.png`.
- `ux009-programacion-{1440,1280,320,zoom200}.png`.
- `ux009-desactivacion.png` y `ux009-eliminar-proyecto.png`.

Usuarios, revisión y programación se comprueban a 1440×900, 1280×720,
320×900 y ampliación CSS 200 %; sin desbordamiento de documento, con teclado
y foco, y axe sin impactos serious/critical en esas superficies. Las capturas
permiten revisar etiquetas, controles y consecuencias. No equivalen a pruebas
con participantes ni a una auditoría completa con lectores de pantalla.

## Límites y documentación

No se ejecutaron Julia real, PostgreSQL ni toda la suite Python. Las dos
regresiones PostgreSQL necesitan `POSTGRES_TEST_DATABASE_URL` dedicado; sus
omisiones no cuentan como aprobadas. El servidor smoke usa SQLite aislado y
resultados sintéticos; no valida resultados matemáticos. El build conserva la
advertencia existente de tamaño de chunk. No cambia el contrato generado.

Se actualizaron el [manual completo](../../../tutorials/manual_completo_uso_pagina_web.md),
la [guía del analista](../../../tutorials/guia_analista.md), el ticket, el tracker,
la estrategia TDD y la validación del plan. No quedan tickets por implementar
en este paquete; la aceptación de producto permanece en revisión.
