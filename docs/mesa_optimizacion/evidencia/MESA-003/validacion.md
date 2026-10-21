# MESA-003 · Evidencia de implementación

Fecha: 2026-10-20. Responsable: Codex. Interfaces S1 (navegador) y S2 (HTTP),
confirmadas previamente por el usuario. No cambia el motor ni se añade otra
interfaz de prueba. Estado: Done tras revisión técnica AFK y visual.

## Recorrido entregado

Desde la mesa se agregan, renombran, ordenan y quitan pestañas y vistas. Cada
pestaña conserva su distribución y cada panel conserva título, componente por
identidad, señales y modo. **Guardar mesa** persiste la configuración personal
del caso. Reducir la distribución oculta paneles y ampliarla los recupera.

El [contrato y la migración](../../persistencia_vistas.md) documentan GET/PUT,
la tabla `mesa_preferences`, versión de esquema y revisión esperada. Un conflicto
409 conserva la edición visible; **Cargar mesa guardada** permite reemplazarla
explícitamente y continuar. Los errores de red permiten reintentar.

## Ciclos rojo → verde observados

Se avanzó por comportamiento, ejecutando cada prueba antes de implementar su
solución. Los errores de preparación de fixtures no se cuentan como rojos.

| Ciclo | Interfaz y comportamiento | Rojo observado | Verde observado |
| --- | --- | --- | --- |
| 1 | S2, cuatro paneles → uno → reiniciar aplicación/base → cuatro | PUT devolvía 404. | Configuraciones y paneles ocultos recuperados desde SQLite en disco. |
| 2 | S2, escritor con revisión obsoleta | 200 con sobrescritura. | 409, lectura intacta y guardado con revisión vigente. |
| 3 | S1, configurar y recuperar cuatro vistas | No existía «Agregar vista». | Guardado, recarga y restauración con títulos, tabla y gráficos. |
| 4 | S1, dos pestañas con orden y distribución propios | No existía «Agregar pestaña». | Persistencia independiente, reordenación/quitar vista y navegación con flechas/Home. |
| 5 | S1, conflicto entre dos páginas | No existía «Cargar mesa guardada». | La edición local sigue visible; recuperar la guardada permite continuar. |
| 6 | S1, matriz 2×2 a 1440×900 | Un panel terminaba en 971.8125 px. | Cuatro paneles completos, sin solapamiento, dentro del viewport. |
| 7 | S1, varias series y unidades | El selector no ofrecía la segunda serie. | MW y USD/MWh en subgráficos/tablas separados; selección persistida. |
| 8 | S2, documento visual consistente | Se aceptaba una pestaña activa inexistente con 200. | 422 para referencias ambiguas, señales repetidas/vacías, muestras embebidas o esquema no admitido; documento anterior intacto. |
| 9 | S1, foco después de quitar una vista | «Agregar vista» no recibía el foco al desaparecer el botón original. | Foco en una acción disponible; Escape conserva el retorno al botón original. |

También se comprobaron aislamiento por usuario/caso, acceso anónimo y externo,
CSRF e invariancia de entradas, bindings, snapshot y resultados indexados existentes.
Las observaciones pasan por HTTP; la base solo prepara fixtures. No se consulta
una tabla privada para demostrar un guardado.

El componente retirado se prueba editando el borrador por la API real. Existe otro
objeto con el mismo nombre; el panel conserva el ID anterior, queda «No disponible»
y solo cambia al reconfigurarlo explícitamente.

La consulta productiva sigue ofreciendo la demanda de MESA-002. La presentación
multiserie usa `additional_series`, con una fixture en la frontera HTTP para la
segunda unidad; no añade precios ficticios al producto. El inventario de otras
familias corresponde a MESA-004/005. Persistencia, conflictos, pestañas y retirada
de componentes se prueban contra el servidor real autenticado.

## Comandos y resultados

Desde la raíz:

```powershell
.\.venv\Scripts\python.exe -m unittest -v tests.test_mesa_preferences tests.test_optimization_mesa tests.test_ts3_case_variant_api tests.test_ts7_009_run_materialization tests.test_react_auth tests.test_configuration_layer_access
```

**47 descubiertas: 42 OK y 5 omitidas** por ausencia de
`POSTGRES_TEST_DATABASE_URL`. Incluye las cinco pruebas HTTP nuevas.
[Log de API y regresiones](api-final.txt). La migración usa SQL compatible con
ambos motores; la ejecución comprobada en esta entrega es SQLite.

Desde `frontend`:

```powershell
npm.cmd run api:generate
npm.cmd run api:check
npm.cmd run test:browser -- --config=playwright.mesa.config.ts -g "dos pestañas"
npx.cmd playwright test --config=playwright.mesa.config.ts
npm.cmd test
npm.cmd test -- src/App.test.tsx src/ComponentRules.test.tsx -t "lets analysts create, edit, save, recover, remove, and reopen a structured draft|publishes, previews and applies a flow restriction to the selected variant" --maxWorkers=1
npm.cmd run check
npx.cmd prettier --check src/OptimizationMesa.tsx src/MesaPreferences.tsx src/optimizationMesa.css e2e/optimization-mesa.spec.ts src/api/schema.ts openapi.json
npx.cmd playwright test e2e/react-foundation.spec.ts -g "React auth handles|React analyst workspace|UX-005|UX-006"
```

- API/tipos sincronizados: [log](api-schema-final.txt).
- Navegador MESA: **10/10 OK**, siete nuevas y tres de regresión. [Log](playwright-final.txt).
  El build usado por la suite completa se produjo en `test:browser` después del
  último cambio de producto.
- Vitest: primera ejecución **334 OK y dos fallos por espera/timeout** en editor
  de borrador y carga del editor de reglas. Reintento aislado, sin modificar esos
  tests ni sus límites: **2/2 OK**. Quedan verificadas las 336 entre ambas
  ejecuciones; la primera suite completa no fue verde.
  [Primera ejecución](vitest-final.txt), [reintento](vitest-retry.txt).
- TypeScript y ESLint OK. El check global llega a Prettier y falla por los mismos
  **16 archivos preexistentes** de MESA-002, sin diferencias respecto de HEAD.
  El formato de archivos cambiados pasa.
  [Check global](check-final.txt), [archivos modificados](check-changed-files.txt).
- Regresión general de navegador: **4/4 OK**, autenticación, escenario,
  preparación y resultados. [Log](playwright-regression.txt).

## Revisión técnica y visual

La revisión se compara en un UPDATE SQL condicional dentro de una transacción,
incluido el primer guardado. No depende solo del bloqueo local del proceso.
El usuario procede de la sesión y el caso se valida contra el escenario. El
documento tiene límites estructurales, rechaza campos ajenos y no copia muestras.

La identidad usa registro, tipo e ID técnico; los nombres son etiquetas. Cada
serie muestra sus propias unidades y procedencia. Reducir la distribución no
modifica el arreglo de paneles. La migración es aditiva e idempotente y no toca
tablas hidráulicas, snapshots ni resultados.

Capturas revisadas con Chromium de Playwright 1.61.0, DPR 1, idioma en-US, zona
America/Santiago, tema claro y movimiento reducido:

- [Matriz 2×2, 1440×900](mesa-paneles-1440.png).
- [Diálogo de configuración, 1440×900](mesa-configurar-1440.png).
- [Cuatro paneles apilados, 390 px](mesa-paneles-390.png).

Se conservan cabecera y navegación de la aplicación. La jerarquía sigue la
referencia A; los cuatro paneles del fixture consultan demanda real de prueba,
sin inventar BESS, resultados hidráulicos ni simulación. Son evidencias de esta
entrega, no una baseline de aceptación final de MESA-014. Los PNG/HTML originales
se conservan intactos.

Geometría, teclado, foco y Axe pasan, sin infracciones graves/críticas en mesa y
diálogo. Las tablas tienen scroll local; a 390 px no hay desborde horizontal global.

## Incidencias de verificación

- Un contexto de `TestClient` cerraba el almacén compartido antes de preparar
  otro usuario. Se corrigió el ciclo de vida del test.
- El rol antiguo `client` no se puede crear; se comprueba el rol vigente
  `external` y se conserva la regresión del rechazo del rol anterior.
- El borrador devuelve `{draft: …}`. Se corrigió la preparación del test y se
  utilizó el rol accesible `combobox` para seleccionar el componente.
- Los dos fallos temporales de Vitest se resolvieron con ejecución aislada;
  ambos resultados permanecen documentados. No se ampliaron timeouts.

Revisión AFK completada por Codex el 2026-10-20. Los ocho criterios de MESA-003
están satisfechos; siguiente entrega recomendada: MESA-004.

Verificación documental final: 23 Markdown, 171 enlaces locales resueltos,
14 estados de tickets coherentes con el tracker (3 Done y 11 Todo), hashes y
dimensiones de las referencias originales intactos. `git diff --check` sin
errores de whitespace. Los cambios locales previos de MESA-001/002 se conservaron.
