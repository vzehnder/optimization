# UX-006 · Resultados y comparación

Fecha: 2026-09-12. Responsable: Codex. Base: `61dc87a`.
Estado: **In Review**, aceptación de producto pendiente.
Commit de esta entrega: `feat(ux): prioritize results and contextual run comparison`,
solicitado por el usuario; sin PR. [Ticket](../../issues/UX-006-resultados-y-comparacion.md).

Se leyeron los 20 Markdown, scripts y registros de evidencia del paquete y se
inspeccionaron sus 29 capturas antes de implementar. El árbol estaba limpio.
UX-006 era el siguiente ticket recomendado tras UX-001 y UX-005.

## Fronteras confirmadas

La [skill local TDD](../../../../.agents/skills/tdd/SKILL.md) exige:

> Before writing any test, write down the seams under test and confirm them with the user.

El usuario confirmó con «confirmo» el 2026-09-12, antes de la primera prueba:

| Frontera | Alcance confirmado |
| --- | --- |
| F1: navegador → React → FastAPI aislado | Resultado/período, auditoría, comparación desde origen, retorno a ambas ejecuciones, descargas, teclado y presentación mediante Playwright. |
| F2: React renderizado con HTTP controlado | KPIs/unidades, estados, polling, consulta fallida/reintento, ausencias y comparación contextual; aserciones por interfaz pública, sin mocks de hooks. |

F3 solo ejecuta regresiones existentes; no cambian contratos, permisos ni
persistencia de producción. F4 no aplica: Julia, generación y materialización
permanecen intactos. Se consultó el ADR TS-4 de resultados e indexación.

## Resultado implementado

- Identidad, estado en español y período con offset del snapshot preceden al
  resumen. KPIs con unidades y formato local, distinguiendo ausencia y cero.
  El resumen completo conserva escalares, anidados, hidro, activos y arrays.
- «Detalle técnico y auditoría» agrupa estado técnico, tiempos, origen,
  procedencia, hashes, entradas, snapshot, logs y artefactos. La explicación
  de fallo aparece arriba; «Ver diagnóstico» abre y enfoca su detalle.
- Comparación e informe junto al resumen. Tablas de 25 filas con navegación y
  conservación de página al contraerlas. Gráficos y lifecycle de Plotly conservados.
- Reintentos de resultados, contexto y archivos sin reenviar ejecuciones.
  El refresco fallido conserva datos aceptados; 401/403/404 retiran los datos
  de esa consulta.
- Comparación con `baseline`/`candidate` validados entre las corridas exitosas
  del escenario, selección en URL y retorno a ambas. La API decide compatibilidad,
  indexación y series disponibles. Caso, variante, período y unidades visibles.
- La API admite rangos distintos: se advierte que los totales cubren intervalos
  diferentes y las diferencias solo existen en timestamps coincidentes.
  Fuera del solapamiento se conserva la ausencia, sin inventar cero.
- Portal y consola siguen usando `PortalResults.tsx`, sin auditoría interna.
  Crear borrador, preview y publicar siguen siendo acciones explícitas.

## Ciclos RED → GREEN

Cada fila empezó con un fallo antes de implementar su conducta. Los
[extractos originales](tdd-cycles.txt) contienen error, aserción y resultado
focalizado; los registros completos permanecen en `.tmp/`. La posición sobre
el pliegue se revisó visualmente, sin contar nodos DOM.
Los registros versionados están normalizados a UTF-8, sin códigos de color ni
espacios al final de línea; se conserva su contenido y resultado.

| Registro | RED observado | GREEN |
| --- | --- | --- |
| 1 · F2 | No aparece «Finalizada» ni el resumen solicitado. | Contexto, KPI conocido 1.250,5 USD y acceso al snapshot. |
| 2 · F2 | La explicación del fallo queda oculta dentro de auditoría. | Fallo resumido, logs bajo auditoría y foco al abrir. |
| 3 · F2 | No existe reintento tras finalizar y fallar la consulta. | Polling, recuperación y cero mutaciones. |
| 4 · F2 | Se pierde el KPI tras un refresco 503. | Mantener resultado y permitir reintentar. |
| 5 · F2 | Falta comparación desde el resultado. | Origen preseleccionado, diferencia conocida de 500 USD y retornos. |
| 6 · F2 | La ausencia no se distingue del valor cero. | «No disponible», 0 USD y 5 MWh, datos legacy y descarga. |
| 7 · F2 | Filas posteriores a la 25 inaccesibles. | Páginas y conservación al contraer. |
| 8 · F2 | Rangos distintos sin advertencia. | Contexto y ausencias fuera del solapamiento. |
| 9 · F2 | Base inválida del enlace sin petición de corregir. | Mensaje y selección explícita. |
| 10 · F2 | Comparación rechazada con 409 sin reintento. | Recuperación con la misma pareja. |
| 11 · F2 | Contexto fallido sin recuperación. | Reintento conservando KPI, sin inventar origen manual. |
| 12 · F2 | Inventario de artefactos fallido sin reintento. | Recuperar descarga desde auditoría. |
| 13 · F2 | Resultado visible después de un 403. | Retirarlo ante rechazo de acceso. |
| 14 · F2 | Tras volver desde candidata, nueva comparación elige la misma corrida dos veces. | Quitar candidata si coincide con la nueva base. |
| Layout · F1 | Selectores desbordan el documento a 320 px. | Selectores adaptables; [RED](layout-red.txt) y [GREEN](layout-green.txt). |
| 16 · F2 | Resultado sin secciones elimina también la acción de comparar. | Vacío explícito con acciones y archivos accesibles. |

El recorrido F1 completo se añadió como aceptación y pasó inicialmente; no se
presenta ese primer pase como RED. Su ampliación a 320 px sí reprodujo el fallo
de layout antes del ajuste CSS.

La prueba adicional de cambiar a una pareja con otras señales pasó con el
fallback real del servidor: [regresión](series-regression.txt). Su primer
fixture asumía erróneamente un rechazo 422 por señal ausente; se corrigió al
leer `app/result_comparison.py`. Ese intento (`.tmp/ux006-cycle15-red.txt`) no
cuenta como RED funcional. También se corrigieron esperas asíncronas y la
antigüedad de caché necesaria para provocar el refresco; los fallos de
preparación no cuentan como defectos de producto.

## Validación final

| Comando | Resultado |
| --- | --- |
| Desde `frontend/`: `npm.cmd test` | **195 aprobadas**, 17 archivos, 47,46 s. [Salida](vitest-final.txt). |
| Desde `frontend/`: `npm.cmd test -- --run src/RunExperience.test.tsx` | **16 aprobadas** al completar los ciclos; incluidas en las 195. [Salida](vitest-focused.txt). |
| Desde `frontend/`: `npm.cmd run test:browser` | Build TypeScript/Vite y **15 aprobadas**, 1,4 min. [Salida](playwright-final.txt). |
| Desde raíz: `.venv/Scripts/python.exe -m unittest tests.test_results_review tests.test_manual_runs tests.test_ts4_run_comparison tests.test_ts4_result_indexing -v` | **63 aprobadas**, 10,350 s. [Salida](python-final.txt). |
| Desde `frontend/`: `npm.cmd run check` | TypeScript y ESLint pasan; **falla Prettier** en 23 archivos previos no modificados. [Lista completa](check-final.txt). |
| Formato del frontend modificado y `git diff --check` | Aprobados; 95 enlaces relativos de la documentación modificada comprobados, sin destinos faltantes. |

Total final sin duplicar repeticiones ni línea base: **273 pruebas funcionales
aprobadas**. Los archivos frontend modificados se formatearon con Prettier;
`RunResults.tsx` deja de formar parte de los 24 fallos previos de UX-005.
Se conserva el aviso de Vite por bundle mayor de 500 kB.

Python y navegador usaron `DATABASE_URL=sqlite:///:memory:` limitada al proceso
PowerShell. El navegador usa el servidor smoke aislado y su doble de Julia.
Se añadieron dos resultados indexados conocidos (1000 y 1500 USD) y un fallo
sintético al servidor, reutilizando el fixture TS-4. Las aserciones leen UI y
API pública, sin consultar la BBDD. El fixture de una fila sirve para
presentación/indexación, no para comprobar balance energético, cobertura
matemática ni el cálculo del solver.

## Capturas y accesibilidad

Capturas conservadas localmente en `capturas/`, excluidas de Git como en las
entregas previas. Se regeneran con:

```powershell
cd frontend
$env:DATABASE_URL = 'sqlite:///:memory:'
npm.cmd run test:browser -- --grep UX-006
```

Playwright las escribe en `test-results/react-foundation-UX-006-*`.

| Captura local | Comprobación |
| --- | --- |
| `resultado-1280.png` | 1280×720: estado, caso, variante, período, KPI y acciones visibles sin abrir auditoría. |
| `resultado-1440.png` | Resultado, gráficos, tablas, publicaciones y auditoría a 1440×900. |
| `resultado-320.png` | Flujo estrecho, tablas/gráficos en su propio espacio, sin desbordamiento del documento. |
| `resultado-zoom200.png` | Ampliación CSS al 200 %, sin desbordamiento del documento. |
| `comparacion-1280.png`, `comparacion-320.png` | Pareja, rangos, unidades, diferencia y controles adaptables. |
| `fallo-1280.png` | Explicación y acción de diagnóstico antes de auditoría. |

Se inspeccionaron las capturas. F1 comprueba recarga, retorno a ambas
ejecuciones, descarga JSON real, teclado/foco del diagnóstico y axe sin
serious/critical en resultado, comparación y diagnóstico abierto. La regresión
completa comprueba también Plotly, legacy, publicación, portal allowlisted,
descarga autorizada y revocación. No es una auditoría con lector de pantalla,
zoom nativo del navegador ni un estudio con participantes.

## Conservación funcional

| Fila de la matriz | Acceso y evidencia |
| --- | --- |
| Cola, polling, recuperación y fallo con logs | Estado, reintentos, «Ver diagnóstico» y auditoría; F2 y lifecycle F1. |
| KPIs, gráficos, tablas de sistema/activos/hidro y artefactos | Resumen completo, gráficos, tablas paginadas y archivos; App/F1/Python. |
| Comparar dos corridas | Acción contextual o entrada de escenario; F2, pareja conocida F1 y TS-4 Python. |
| Snapshot y linaje exactos | Auditoría conserva hashes, series, procedencia y snapshot bajo demanda; App y F1. |
| Borrador, preview, publicación y portal externo | Acceso a informe y componentes externos conservados; suite F1 y PortalResults. |

Se actualizaron la guía del analista y el manual completo en sus secciones de
estados, resultados, diagnóstico, descargas y comparación.

## Línea base previa y límites

Antes de los cambios: **130 pruebas existentes aprobadas** (64 App/navegación,
63 Python y 3 navegador). [Python](python-baseline.txt),
[navegador](browser-baseline.txt). No se suman al total final. La primera salida
Python truncada se repitió a archivo para conservar evidencia.

No se ejecutaron Julia real, PostgreSQL ni toda la suite Python, porque el
cambio de producto es de presentación. No se modificaron APIs, OpenAPI, runner,
compatibilidad, datos históricos ni permisos de producción.
