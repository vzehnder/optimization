# MESA-002 · Evidencia de implementación

Fecha: 2026-10-20. Responsable: Codex. Interfaces confirmadas: S1 navegador y
S2 HTTP. No se modificó el motor ni se agregó una interfaz de prueba.
Estado: Done tras revisión técnica AFK y visual.

## Ciclos rojo → verde observados

Cada fila se ejecutó como un comportamiento independiente antes de implementar
su solución. Las expectativas usan los literales 10 y 12 MW de una fixture
persistida, con dos intervalos del 2026-10-20 en America/Santiago.

| Ciclo | Prueba / interfaz | Rojo observado | Verde |
| --- | --- | --- | --- |
| 1 | `test_demand_is_read_from_the_selected_canonical_revision_after_reload`, S2 | GET de mesa devolvía 404 en vez de 200. | Contexto, identidad, revisión, unidad, fechas y valores correctos en dos lecturas HTTP. |
| 2 | `demanda real en gráfico, tabla y recarga`, S1 | No existía el enlace «Abrir mesa de optimización». | Escenario → mesa → gráfico/tabla → recarga con la misma serie. |
| 3 | `test_uncovered_period_reports_no_coverage_without_inventing_zero`, S2 | Un rango de tres horas devolvía `available` con solo dos horas. | `no_coverage`, explicación y muestras vacías, sin ceros inventados. |
| 4 | `test_existing_legacy_variant_reads_its_own_demand_source`, S2 | Una variante anterior devolvía `[]` en lugar de `[7, 9]`. | Lee la fuente y revisión de esa variante mediante el contrato anterior existente. |
| 5 | `un período fuera de cobertura no muestra una curva parcial`, S1 | La pantalla ignoraba el rango de la URL y no mostraba el estado sin cobertura. | El rango forma parte de la consulta y de su clave de caché; no aparece una curva parcial. |
| 6 | Panel completo a 1440×900, S1 | El borde inferior estaba en 1156.6875 px, fuera de los 900 px disponibles. | Panel completo dentro del viewport, sin modificar estilos de otras pantallas. |

También se verificaron por HTTP identidades de otro caso/escenario/variante,
nombres iguales con objetos distintos, acceso anónimo y externo, ausencia de
fuente, caso vacío, rango exacto y rangos inválidos. Estas comprobaciones
reutilizan la autorización existente; no se presentan como fallos nuevos de TDD.

Las pruebas de navegador usan el servidor real aislado y autenticación habilitada.
Solo el test de carga/error/reintento/vacío sustituye respuestas en la frontera HTTP;
el recorrido principal y el de cobertura usan muestras persistidas reales de prueba.
La selección principal cambia desde Default a **Demanda alternativa** antes de abrir
la mesa, para detectar una sustitución accidental por la variante predeterminada.

## Comandos y resultados

Desde la raíz:

```powershell
.\.venv\Scripts\python.exe -m unittest -v tests.test_optimization_mesa tests.test_ts3_case_variant_api tests.test_ts7_009_run_materialization tests.test_react_auth tests.test_configuration_layer_access
```

Resultado: **42 descubiertas, 37 OK y 5 omitidas**, estas últimas requieren
`POSTGRES_TEST_DATABASE_URL`. Las siete pruebas nuevas de mesa pasaron.
Log: [API y regresiones](api-final.txt).

Desde `frontend`:

```powershell
npm.cmd test
npm.cmd run api:generate
npm.cmd run api:check
npm.cmd run test:browser -- --config=playwright.mesa.config.ts
npx.cmd playwright test e2e/react-foundation.spec.ts -g "React auth handles|React analyst workspace|UX-005|UX-006"
npm.cmd run check
```

- Vitest: **336 pruebas, 37 archivos, todos OK**. [Log](vitest-final.txt).
- OpenAPI y tipos generados sincronizados. [Log](api-schema-final.txt).
- Navegador: **3 pruebas MESA OK** y **4 regresiones OK**. Ver [ejecución de MESA](playwright-final.txt) y
  [regresiones de autenticación, navegación, preparación y resultados](playwright-regression.txt).
- TypeScript y ESLint pasan. El chequeo global de formato detecta archivos
  preexistentes (16) sin cambios en esta entrega. Se conserva ese resultado en
  [check global](check-final.txt); el formato de los archivos de implementación
  modificados pasa en [check de archivos cambiados](check-changed-files.txt).

## Incidencias de verificación resueltas

- El servidor general de smoke referenciaba variantes 1/2 inexistentes en su
  fixture de resultados. Ahora las crea y usa los IDs devueltos antes de crear
  los runs. No cambió el guard del producto.
- La primera fixture de mesa creaba un usuario en el servidor compartido e
  impedía probar el bootstrap inicial. Se trasladó a un servidor/base/configuración
  separados en el puerto 8141; la configuración general excluye esta suite.
  La regresión de bootstrap volvió a pasar.
- La clonación existente solo copia los bindings anteriores, no los canónicos.
  El test de selección se prepara con una variante canónica vinculada explícitamente;
  no presupone que clonar configure esa fuente. Ampliar la clonación queda fuera
  de MESA-002.
- Se reutiliza el arranque/cierre del runner existente con token de instancia y
  `windowsHide`; los resultados de MESA van a `.tmp/mesa-playwright-results`
  para no ser borrados por la limpieza de otra suite.

## Revisión técnica y visual

La ruta está bajo `AnalystRoot` y la API conserva la frontera interna existente.
El proyecto se deriva del escenario autorizado; caso y variante se comprueban en
servidor. El inventario parte de los requerimientos del modelo y resuelve objetos
por identidad técnica. La proyección no crea tablas ni copia muestras a otro almacén.
Las consultas se identifican por escenario/caso/variante/rango, reciben cancelación
y no conservan datos visibles de una consulta anterior durante la carga o un error.

Gráfico y tabla consumen el mismo arreglo de intervalos. Se muestran unidad, zona,
rol de entrada, fuente y número de revisión. No hay controles de edición ni
resultados inventados. Se verificaron teclado, Axe sin infracciones graves/críticas
en la mesa y ausencia de scroll horizontal global a 390 px.

Se mantiene la jerarquía de contexto, controles de vista y panel blanco de la
referencia A. La entrega muestra **un panel de demanda**; pestañas configurables,
matriz 2×2, edición, ejecución y comparación pertenecen a las entregas posteriores.
Se conserva la cabecera de la aplicación existente. Las capturas de implementación
no son baselines aprobadas ni sobrescriben los PNG originales.

Capturas revisadas: [demanda, 1440×900](mesa-demanda-1440.png) y
[tabla, 390×844](mesa-tabla-390.png). Chromium del Playwright 1.61.0 instalado,
DPR 1, idioma en-US, zona America/Santiago, tema claro y movimiento reducido.

Verificación documental: enlaces locales resueltos y hashes del HTML y los dos
PNG originales intactos; `git diff --check` sin errores. Los 16 archivos que
señala Prettier no tienen diferencias respecto de HEAD.
