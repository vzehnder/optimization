# UX-001 · Orientación y navegación por tareas

Fecha: 2026-09-12. Responsable: Codex. Estado: In Review.
Base: `aeeb22e`; árbol limpio al comenzar.
Ticket: [UX-001](../../issues/UX-001-orientacion-y-navegacion.md).
Entrega: `feat(ux): implement task-oriented workspace navigation`, sobre esa base; sin PR creada.
Las capturas se conservan localmente y se excluyen de Git por solicitud del usuario.
El recorrido de Playwright descrito abajo permite regenerarlas.

## Fronteras confirmadas

El usuario respondió «confirmo» en esta conversación a la propuesta concreta
de F1 (navegador → React → FastAPI aislado), F2 (React renderizado mediante
Testing Library, con HTTP controlado) y F3 condicional (API autenticada si
cambia contrato, permisos o persistencia). El acuerdo cubre UX-001. F4 no
aplica: no se modifica Julia ni la materialización.

Se acepta con este acuerdo la preparación de UX-000. Las 62 pruebas existentes
de `App.test.tsx` y `ApplicationRoots.test.tsx` se ejecutaron nuevamente antes
de implementar: 62 passed, 36,85 s.

## Comportamiento implementado

La navegación interna muestra Proyectos, Catálogo de series cuando el servidor
habilita su lectura y Administración solo para admin. Estado del sistema está
en Utilidades. Las raíces de consola y portal conservan sus entradas y permisos.

El proyecto separa Escenarios, Datos, Informes, Consolas y Accesos; esta última
sección solo existe para admin. Informes contiene configuración del portal y
templates. Consolas permite llegar a las de cada escenario.

El escenario muestra Resumen, Modelo, Datos, Ejecuciones y Avanzado. El resumen
consulta el modelo por la API existente: un 404 ofrece Crear modelo; un modelo
guardado ofrece Continuar preparación. Carga y error mantienen el estado
desconocido y permiten reintentar. No se afirma que un modelo guardado esté listo
para ejecutar. Las consultas de versiones/corridas tienen errores locales para
que un fallo del historial no bloquee el acceso al modelo.

Datos conserva variantes, asociaciones y período. Avanzado conserva JSON experto,
versiones inmutables, diagrama hidráulico y consolas. Las secciones se ocultan sin
desmontar formularios, para conservar valores pendientes dentro de la pantalla.
Los parámetros de sección se validan contra destinos fijos; los cambios de sección
y retornos desde modelo, comparación, versión y corrida conservan las consultas
que reciben. Las URLs existentes siguen funcionando. El foco pasa al título del
destino, incluso cuando la consulta de identidad tarda en responder.

## Ciclos RED → GREEN

Se ejecutó cada ciclo antes de pasar al siguiente. Las aserciones nuevas observan
la interfaz renderizada o el navegador; no inspeccionan hooks ni tablas privadas.
Los fallos de preparación se corrigieron antes de contar una ejecución como RED.

| Frontera y comportamiento | RED observado | GREEN implementado |
| --- | --- | --- |
| F2: escenario sin modelo → editor del mismo escenario | No existe el enlace Crear modelo | Consulta del modelo, estado vacío y enlace contextual |
| F2: ejecuciones → comparación → escenario | No existe el enlace Ejecuciones | Sección por URL y retorno con escenario y consultas conservados |
| F2: descubrir herramientas expertas y conservar JSON pendiente | El JSON experto está visible en la entrada del escenario | Resumen y secciones; Avanzado descubre versiones, JSON, hidráulica y consolas |
| F2: separar tareas del proyecto conservando formulario pendiente | Dashboard templates sigue visible en la entrada del proyecto | Secciones y enlaces a consolas por escenario, sin desmontar el formulario |
| F2: foco al entrar al editor y regresar | El foco permanece en BODY | Foco al título del destino tras navegación y carga |
| F1: guardar modelo y volver a la sección de origen | El retorno pierde `?origin=review&section=advanced` | Breadcrumb del editor conserva la consulta de origen |
| F2: abrir el modelo aunque falle el historial | El error de corridas sustituye toda la pantalla; no aparece Invierno | Errores y reintentos locales de versiones y corridas |

La prueba adicional de error y reintento pendiente del modelo pasó desde su primera
ejecución: amplía la cobertura del comportamiento existente en ese punto, no se
presenta como un ciclo RED nuevo. El fixture inicial de consolas se corrigió para
devolver `operator_consoles`. Una opción `exact` de Playwright introducida por
error en aserciones de Testing Library se retiró antes del RED de navegador.

Pruebas focalizadas reproducibles desde `frontend/`:

```powershell
npm.cmd test -- src/WorkspaceNavigation.test.tsx
$env:DATABASE_URL = 'sqlite:///:memory:'
npm.cmd run test:browser -- --grep 'UX-001'
```

Los siete casos de componentes están en
[`WorkspaceNavigation.test.tsx`](../../../../frontend/src/WorkspaceNavigation.test.tsx).
El recorrido real está en
[`react-foundation.spec.ts`](../../../../frontend/e2e/react-foundation.spec.ts),
caso «UX-001 keeps task context and pending model edits through navigation and reload».
Los casos existentes de roles, versiones, consola, informes y catálogo se adaptaron
a los nuevos enlaces/secciones conservando sus aserciones funcionales.

## Validación final

| Comando | Resultado |
| --- | --- |
| `npm.cmd test` desde `frontend/` | 15 archivos, **166 pruebas aprobadas**, 43,53 s. [Salida](vitest-final.txt) |
| `npm.cmd run test:browser` con SQLite en memoria | Compilación TypeScript/Vite y **13 pruebas aprobadas**, 1,1 min. [Salida](playwright-final.txt) |
| `python -m unittest discover -s tests -p 'test_react_foundation.py' -v` | **4 aprobadas**, 2,632 s |
| `python -m unittest discover -s tests -p 'test_configuration_layer_access.py' -v` | **9 aprobadas**, 10,203 s |
| `python -m unittest discover -s tests -p 'test_ts7_019_layered_catalog_surface.py' -v` | **5 aprobadas**, 4,770 s |
| `npm.cmd run check` | TypeScript y ESLint pasan; Prettier falla por 25 archivos preexistentes sin cambios respecto a `aeeb22e` |
| Prettier sobre los 13 archivos de código modificados/nuevos | Aprobado |
| `git diff --check` | Aprobado |

Total: **197 pruebas funcionales aprobadas**. Las pruebas Python usan
`.\.venv\Scripts\python.exe` desde la raíz con `DATABASE_URL=sqlite:///:memory:`.
No se modifican API, permisos ni persistencia; F3 se usa como regresión existente.

El primer intento de `check` coincidió con la limpieza de `test-results` de
Playwright y ESLint encontró un archivo desaparecido. Se repitió secuencialmente:
el único fallo restante es el formato previo. Los 25 archivos son:

```text
e2e/global-setup.ts
eslint.config.js
index.html
package-lock.json
package.json
playwright.config.ts
scripts/check-generated.mjs
scripts/export-openapi.mjs
src/api/client.test.ts
src/api/client.ts
src/ErrorBoundary.test.tsx
src/ErrorBoundary.tsx
src/hydro/HydraulicInflowPanel.test.tsx
src/hydro/inflowImport.test.ts
src/hydro/inflowImport.ts
src/main.tsx
src/ProtectedMutationJourney.test.tsx
src/ProtectedMutationJourney.tsx
src/RunResults.tsx
src/test/setup.ts
src/timeSeriesCatalogMapping.ts
tsconfig.app.json
tsconfig.json
tsconfig.node.json
vite.config.ts
```

Se comprobó con `git diff --quiet HEAD -- frontend/<archivo>` que ninguno de esos
25 archivos está modificado. No se incluyen reformateos ajenos al ticket. Vite
advierte sobre un bundle mayor a 500 kB; la compilación final termina con código 0.
PowerShell presenta ese stderr como `NativeCommandError` en el log redirigido,
pero no es un fallo de las 13 pruebas.

## Paridad de capacidades afectadas

Filas de la [matriz funcional](../../03_matriz_funcional.md), con destino y evidencia:

| Capacidad | Acceso después del cambio | Evidencia ejecutada |
| --- | --- | --- |
| Identidad, login/logout, raíces, acceso y C6/lectura canónica | Entradas del backend; navegación interna condicionada por rol y capacidad | ApplicationRoots, GlobalCatalog, Admin, ExternalAccess; E2E de autenticación, permisos y revocación; 9 + 5 pruebas API |
| Crear/listar proyectos y escenarios, enlaces directos y borrado de proyecto | Proyectos → Escenarios; borrado contextual de la lista | App; E2E de creación/recarga; 4 pruebas API de foundation |
| Modelo incompleto y cambios pendientes | Modelo / Crear modelo / Continuar preparación | WorkspaceNavigation; App; E2E UX-001 y editor estructurado con error de guardado |
| Hidráulica v3 | Avanzado → Diagrama hidráulico y ruta directa existente | Enlace en WorkspaceNavigation; E2E de persistencia de parámetros, curvas y nodos |
| Catálogo por proyecto y herramientas de datos | Proyecto → Datos → catálogo; escenario → Datos → catálogo | App y GlobalCatalog, incluyendo importación, revisiones y restricciones de lectura |
| Variantes, asociaciones y rango | Escenario → Datos | App y recorrido protegido existente; E2E UX-001 conserva el rango al usar atrás/adelante entre secciones |
| Validar/promover, JSON experto y versiones inmutables | Modelo y Avanzado; promoción abre Avanzado | App; E2E de validación y versionado generado/experto |
| Corridas, logs, resultados y comparación | Ejecuciones → corrida/comparación; retornos a Ejecuciones | WorkspaceNavigation; App; E2E de ciclo de corrida, resultados y descargas |
| Templates, portal, publicaciones y accesos | Proyecto → Informes / Accesos; publicación desde corrida | PortalConfiguration, PortalResults, ExternalAccess; E2E de templates, publicación y portal |
| Crear/configurar/probar consolas | Proyecto → Consolas → escenario; escenario → Avanzado | WorkspaceNavigation, OperatorConsole y suite existente de raíces |

Esta tabla registra la cobertura ejecutada, no afirma una nueva aceptación de
todos los contratos de cada fila. El backend y las rutas protegidas no cambian.

## Navegador, presentación y accesibilidad

Chromium de Playwright sobre el servidor smoke FastAPI aislado en el puerto 8123,
con proyecto y escenario ficticios creados por API. El nuevo recorrido comprueba
guardado/recarga real del modelo, cancelar la salida por Proyectos con cambios
pendientes, retorno a Avanzado, sección en URL, atrás/adelante y consulta inválida.

Se revisaron las capturas de proyecto y escenario sin solapamientos ni recortes
en las pantallas mostradas. El proyecto además tiene una aserción de ausencia de
desbordamiento horizontal en los tres anchos. La navegación utiliza enlaces
semánticos con `aria-current`, y el recorrido comprueba foco en títulos. Axe no
detectó impactos serious/critical en las nuevas vistas a 320 px; también pasó
el smoke existente de accesibilidad y teclado.

| Tamaño | Proyecto | Escenario |
| --- | --- | --- |
| 1440 × 900 | [Captura](capturas/proyecto-1440.png) | [Captura](capturas/escenario-1440.png) |
| 1280 × 720 | [Captura](capturas/proyecto-1280.png) | [Captura](capturas/escenario-1280.png) |
| 320 × 900 | [Captura](capturas/proyecto-320.png) | [Captura](capturas/escenario-320.png) |

[Proyecto ampliado al 200 % mediante CSS zoom](capturas/proyecto-zoom-200.png):
el enlace Consolas se activa con Enter y el título recibe foco. Esta comprobación
de reflujo no equivale a probar el zoom nativo de todos los navegadores ni lectores
de pantalla.

## Revisión y límites

Se revisaron el diff, los destinos y la preservación de formularios después de los
ciclos. No se necesitó una extracción general de `Workspace.tsx`. Se actualizaron
la guía del analista, el manual completo y el tracker. UX-000 queda Done por el
acuerdo del usuario; UX-001 queda In Review, con implementación y evidencia
disponibles, pendiente de aceptación del resultado.

La protección de cambios pendientes comprobada es la salida por los enlaces del
editor y la conservación local al cambiar de sección. No se amplía en este ticket
la protección histórica de un modelo sin guardar ante todas las acciones de
historial/cierre del navegador. Tampoco se guardan automáticamente formularios
pendientes al recargar. La edición progresiva corresponde a UX-002.

La preparación completa para ejecutar, los resultados simplificados y el flujo
guiado de datos siguen en UX-005/006/004. No hubo participantes de una prueba de
usabilidad, ejecución real de Julia, suite completa Python ni PostgreSQL; este
cambio de navegación no modifica contratos matemáticos ni transacciones. El
servidor smoke simula el solver. El fallo previo de formato impide afirmar que la
puerta global `npm.cmd run check` esté verde.
