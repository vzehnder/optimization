# UX-007 · Configurar y publicar informes

Base: `cf64106`, árbol limpio al iniciar. Responsable: Codex.
Inicio y entrega para revisión: 2026-09-14. Estado: **In Review**.
Commit solicitado por el usuario: `feat(ux): guide report configuration and explicit publication`,
sobre `cf64106`. Sin PR. Aceptación de producto pendiente.

## Resultado implementado

Desde una ejecución exitosa, **Preparar informe** conduce a contenido,
borrador, vista previa y publicación explícita. La ejecución del enlace se
conserva al configurar y volver. La vista previa muestra título, comentario,
período, contenido y descargas del payload externo real; el contexto técnico
queda en un desplegable interno. Publicar/despublicar actualiza la vista y
ofrece el enlace para una cuenta externa autorizada.

En **Informes** del proyecto, los controles se abren por Identidad y logo,
Indicadores, Gráficos, Tablas y Descargas. Se conserva el documento completo,
incluidos parámetros de secciones cerradas. Subir un logo ya no descarta la
edición del nombre. La revisión de guardado es la aceptada por el editor; una
consulta de fondo no autoriza sobrescribir cambios de otra sesión. Ante 409 se
mantiene el trabajo y se ofrece descartar explícitamente y cargar lo vigente.

Los cambios pendientes sobreviven a secciones del proyecto y errores de
consulta; salir pide guardar o descartar. El diálogo sigue visible aunque
Informes esté cerrado y retiene el foco. Guardar con un campo nativo inválido
abre su sección y lo enfoca. Los borradores en edición requieren guardar o
cancelar antes de previsualizar/publicar. Se conservaron todas las opciones de
plantillas y se actualizaron los tutoriales.

Se mantiene la semántica del servidor: la configuración activa afecta también
a informes publicados; una configuración en borrador no expone sus secciones.
El enlace de activación lleva al campo Estado. Título, comentario y artefactos
solo se editan en borradores: para cambiarlos después de publicar se prepara un
nuevo borrador de la misma ejecución. El logo se guarda por separado. La
interfaz explica estas reglas; no cambia contratos, permisos ni persistencia.

## Fronteras confirmadas

El usuario respondió «confirmo» antes de escribir pruebas nuevas:

- F1: navegador → React → FastAPI/SQLite aislado para guardar borradores,
  previsualizar, publicar/despublicar y comprobar el portal autorizado.
- F2: React con HTTP controlado para conservar configuración, manejar
  errores/conflictos y verificar estados y foco.
- F3: regresiones existentes; cualquier cambio de contrato o permisos
  requiere ampliar el acuerdo. F4 no aplica al alcance de presentación.

Se usó la [skill TDD local](../../../../.agents/skills/tdd/SKILL.md),
un comportamiento RED → GREEN por ciclo. Los dobles nuevos están en HTTP;
las aserciones observan React renderizado, navegación y respuestas visibles.
No se mockean hooks ni servicios internos.

## Ciclos RED → GREEN

Los [extractos de ejecución](tdd-cycles.txt) conservan comando, diagnóstico y
resultado; omiten los grandes volcados DOM. Los filtros omiten pruebas ajenas
al ciclo, que después se ejecutan en la suite completa.

| Ciclo F2 | RED observado | GREEN comprobado |
| --- | --- | --- |
| 1. Borrador de la ejecución elegida | No existe el campo Título del informe del recorrido | Guardar borrador, abrir su título y KPI 1250.5, volver a ejecución 99 |
| 2. Configuración por secciones | No existe la acción Gráficos | Cambiar branding, gráficos, tablas y descargas; guardar y reabrir conservando opciones |
| 3. Logo y edición pendiente | Subir logo borra Marca pendiente | Conservar el nombre y guardar usando la revisión aceptada del logo |
| 4. Conflicto de revisión | Un refetch adopta la revisión ajena y no aparece el conflicto | Rechazo 409 conserva trabajo; cargar lo vigente exige descarte explícito |
| 5. Publicación desde preview | No existe Publicar informe | Publicar, ofrecer enlace autorizado y despublicar |
| 6. Configuración inactiva | No existe el enlace de activación | Enlazar al campo Estado con foco y volver al resultado elegido |
| 7. Error de consulta de fondo | Desaparece Nombre publico al fallar GET | Conservar la edición y recuperarse con Reintentar configuración |
| 8. Salida con cambios pendientes | No aparece diálogo de salida | Cancelar salida conserva campos; cambiar sección del proyecto sigue permitido |
| 9. Respuesta normalizada | El campo conserva espacios que el servidor eliminó | Adoptar el documento guardado si no hubo edición posterior al envío |
| 10. Borrador en edición | Publicar sigue habilitado con cambios sin guardar | Guardar/cancelar antes de publicar o abrir preview |
| 11. Diálogo desde otra sección | La confirmación está dentro del panel oculto | Diálogo visible, foco inicial y Escape aun fuera de Informes |
| 12. Campo inválido cerrado | El campo inválido no se abre ni recibe foco | Abrir Tablas, explicar Filas visibles y enfocar la corrección |

F1 integra los ciclos con React y FastAPI/SQLite real aislado: configuración y
plantilla persistidas tras recarga, borrador ausente del listado externo,
preview del resultado elegido, publicación con teclado, mismo KPI y título
para el cliente, descarga, cambio de configuración compartida, despublicación
y revocación durante la sesión. Se amplió el recorrido con validación nativa
y diálogo a 320 px después del ciclo 12.

La primera ejecución F1 tuvo una expectativa incorrecta del fixture: un
proyecto asignado puede existir en el listado aunque no tenga publicaciones.
Se corrigió para entrar al proyecto y comprobar «No hay publicaciones
activas». No se cuenta ese fallo de expectativa como RED de producto.

## Verificación ejecutada

**323 pruebas aprobadas**, sin duplicar línea base ni repeticiones focalizadas:

| Comprobación | Resultado | Salida |
| --- | --- | --- |
| Vitest completo, 20 archivos | 246 aprobadas, 88.89 s | [vitest-final.txt](vitest-final.txt) |
| Playwright completo | 21 aprobadas, 2.1 min | [playwright-final.txt](playwright-final.txt) |
| Python: publicaciones, resultados, branding, autorización y acceso | 56 aprobadas, 44.305 s | [python-final.txt](python-final.txt) |
| Playwright UX-007 tras el último ajuste de foco | 1 aprobada, 21.7 s; incluida en las 21 anteriores | [playwright-focused.txt](playwright-focused.txt) |
| Contrato OpenAPI generado | Sin diferencias | [api-check.txt](api-check.txt) |
| Chequeo global | TypeScript y ESLint pasan; Prettier falla en 21 archivos previos | [check-final.txt](check-final.txt) |

La suite completa de navegador se ejecutó antes del último ajuste de validación
nativa; después se repitieron la suite completa de Vitest, build y el recorrido
F1 afectado, que además comprueba el error cerrado y el diálogo. ESLint y
Prettier focalizados pasan para todos los archivos frontend modificados.
`git diff --check` pasa. Build conserva el aviso previo de bundle mayor a
500 kB; ese aviso no es un fallo de compilación.

Línea base: [23 pruebas React](vitest-baseline.txt) y
[47 pruebas Python](python-baseline.txt) aprobadas antes de implementar.

Desde `frontend/`, comandos ejecutados:

```powershell
npm.cmd test -- src/PortalConfiguration.test.tsx src/PortalResults.test.tsx
npm.cmd test -- --maxWorkers=2
npm.cmd run test:browser
npm.cmd run test:browser -- --grep "UX-007"
npm.cmd run check
$env:DATABASE_URL = 'sqlite:///:memory:'
npm.cmd run api:check
npx.cmd eslint src/Workspace.tsx src/PortalConfiguration.test.tsx src/ReportExperience.test.tsx src/WorkspaceNavigation.test.tsx e2e/react-foundation.spec.ts
npx.cmd prettier --check src/Workspace.tsx src/PortalConfiguration.test.tsx src/ReportExperience.test.tsx src/WorkspaceNavigation.test.tsx e2e/react-foundation.spec.ts src/styles.css
```

Desde la raíz, con SQLite de prueba:

```powershell
$env:DATABASE_URL = 'sqlite:///:memory:'
.\.venv\Scripts\python.exe -m unittest tests.test_iter6_publications tests.test_configuration_layer_portal_results tests.test_configuration_layer_portal_branding tests.test_iter6_authorization_hardening tests.test_configuration_layer_access -v
git diff --check
```

Las variables se establecieron en procesos de herramientas; no se modificó
configuración persistente ni la base local de trabajo. Playwright usa su
servidor y directorio temporal propios.

Los 21 archivos previos que impiden aprobar `check` son: `e2e/global-setup.ts`,
`eslint.config.js`, `index.html`, `package-lock.json`, `package.json`,
`playwright.config.ts`, `scripts/check-generated.mjs`,
`scripts/export-openapi.mjs`, `src/api/client.test.ts`,
`src/ErrorBoundary.test.tsx`, `src/ErrorBoundary.tsx`,
`src/hydro/HydraulicInflowPanel.test.tsx`, `src/hydro/inflowImport.test.ts`,
`src/hydro/inflowImport.ts`, `src/main.tsx`, `src/test/setup.ts`,
`src/timeSeriesCatalogMapping.ts`, `tsconfig.app.json`, `tsconfig.json`,
`tsconfig.node.json` y `vite.config.ts`. Ninguno cambia en UX-007.

## Conservación funcional

Filas afectadas de la [matriz](../../03_matriz_funcional.md):

| Capacidad | Evidencia de conservación |
| --- | --- |
| Templates, branding, KPIs, gráficos, tablas y descargas configurables | F2 guarda/reabre documento completo, logo, revisión, etiquetas, series, columnas, unidades y límites; regresión de catálogos. F1 crea y conserva plantilla; recorrido previo también la edita |
| Crear/editar borrador, preview, publicar/despublicar | F2 del recorrido y F1 nuevo + anterior; conserva selección de artefactos, historial y ejecución explícita |
| Portal externo, publicaciones y descargas permitidas | Preview y portal mantienen el constructor externo y componentes compartidos; F1 comprueba título/KPI, download, retirada por despublicación y acceso revocado. Regresión API comprueba autorización en cada request |

`app/main.py`, `app/portal_configuration.py`, `app/surface_payloads.py`,
`ClientPortal.tsx`, `PortalResults.tsx` y el contrato generado no cambian.
No se sustituye el filtrado del servidor por ocultamiento CSS. La configuración
cerrada en el editor es estado interno de edición, no contenido del portal.

## Revisión visual y accesibilidad

Se inspeccionaron las **14 capturas** del último F1. Configuración, preview y
portal a 1440×900, 1280×720, 320×900 y ampliación CSS 200 %; además error y
confirmación de salida a 320 px. Las comprobaciones de layout pasan sin
desbordamiento horizontal en las tres superficies. Axe no detectó infracciones
serious/critical en configuración, preview, portal ni diálogo. Se verificaron
Tab, Shift+Tab, Escape, foco del campo inválido y publicación con Enter.

Las capturas son locales, regenerables y excluidas de Git como en los tickets
anteriores. Se generan en `frontend/test-results/react-foundation-UX-007-*/`;
se conservan aquí en `capturas/`:

- Configuración: [1440](capturas/informe-configuracion-1440.png), [1280](capturas/informe-configuracion-1280.png), [320](capturas/informe-configuracion-320.png), [200 %](capturas/informe-configuracion-zoom200.png).
- Vista previa: [1440](capturas/informe-preview-1440.png), [1280](capturas/informe-preview-1280.png), [320](capturas/informe-preview-320.png), [200 %](capturas/informe-preview-zoom200.png).
- Portal: [1440](capturas/informe-portal-1440.png), [1280](capturas/informe-portal-1280.png), [320](capturas/informe-portal-320.png), [200 %](capturas/informe-portal-zoom200.png).
- [Error con campo enfocado](capturas/informe-error-320.png) y [confirmación de salida](capturas/informe-cambios-320.png).

Los estados de carga, vacío, ausencia de resultados, error, conflicto y edición
pendiente se cubren por componentes/regresiones; las capturas nuevas registran
el recorrido disponible, error de campo y cambios pendientes. No se afirma
captura nueva de cada variante de error ni auditoría completa con lectores de
pantalla o participantes.

## Límites y revisión posterior

No se ejecutaron Julia real, PostgreSQL ni toda la suite Python. El smoke usa
resultados sintéticos; no demuestra corrección matemática. No cambian TS-7,
versiones, cálculos ni materialización. No se añadió envío por correo, generador
libre de dashboards o edición de publicaciones que el backend no permite.

La revisión posterior conservó los controles existentes y pequeñas funciones
locales para contexto, pasos y protección de salida. No se hizo una extracción
general de `Workspace.tsx`: no es necesaria para este recorrido. Tutoriales y
tracker actualizados; revisión y aceptación de producto aún pendientes.
