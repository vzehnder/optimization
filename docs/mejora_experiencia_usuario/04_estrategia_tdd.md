# Estrategia TDD para implementar la mejora

## Aplicación de la habilidad solicitada

La referencia es [`.agents/skills/tdd/SKILL.md`](../../.agents/skills/tdd/SKILL.md). Dos reglas condicionan la implementación:

> Test only at pre-agreed seams.

> Refactoring is not part of the loop. It belongs to the review stage.

Durante la planificación se propusieron fronteras y no se escribieron pruebas nuevas. Antes de la primera prueba de implementación, presentar las fronteras necesarias del ticket y registrar su confirmación por el usuario/responsable de la implementación. No es necesario volver a confirmar una frontera que ya haya sido aceptada para ese alcance; una frontera nueva sí requiere acuerdo. El acuerdo posterior de UX-001 se registra a continuación.

UX-000 preparó el [acuerdo concreto para UX-001 y su primer comportamiento](evidencia/ux-000/README.md#fronteras-propuestas-para-aprobación), junto con recorridos y regresiones existentes. El usuario confirmó F1/F2 y F3 condicional el 2026-09-12 para UX-001. [Ciclos de implementación](evidencia/ux-001/README.md). Este acuerdo no confirma automáticamente fronteras nuevas de otros tickets.

Para UX-005, el usuario respondió «confirmo» al acuerdo F1 (navegador con React y FastAPI aislado), F2 (interfaz React con respuestas HTTP controladas) y F3 (API pública para capacidades C6, validación y ejecución), antes de la primera prueba. El primer ciclo identificó una señal faltante, permitió ir a corregirla y mantuvo bloqueada la ejecución. [Registro de ciclos y resultados](evidencia/ux-005/README.md). No se incorporó F4.

## Fronteras propuestas

Una frontera es la interfaz pública desde la que se observa el comportamiento. No es un archivo interno elegido por conveniencia.

| Frontera | Observación permitida | Uso propuesto | Estado |
| --- | --- | --- | --- |
| F1: navegador → React → FastAPI aislado | Tarea visible, navegación, formularios, autenticación, persistencia tras recarga, descargas | Aceptación del recorrido de cada ticket | Confirmada para UX-001 y UX-005 |
| F2: React renderizado con Testing Library | Roles/nombres accesibles, mensajes, interacción y resultado mostrado; respuestas HTTP controladas | Variantes de estado/errores difíciles de reproducir; feedback rápido | Confirmada para UX-001 y UX-005 |
| F3: API pública FastAPI → almacén de prueba | Requests autenticados, códigos y payloads, lectura posterior por API, archivo descargado | Cambios de contrato, permisos, precondiciones o persistencia | Condicional para UX-001; confirmada para UX-005 |
| F4: API/CLI pública de Julia | Resultado del caso conocido y archivos de salida | Solo si se cambia generación, contrato matemático o materialización | Condicional, por confirmar |

El repositorio ya usa estas herramientas. No añadir otro runner, framework BDD o framework de mocks para este plan. Los helpers de fixtures pueden preparar datos, pero las aserciones de un comportamiento nuevo se hacen en la misma frontera pública: no verificar un guardado de API consultando tablas privadas.

## Un ciclo por comportamiento

1. Seleccionar una sola conducta del ticket y una frontera confirmada. Escribir su condición inicial, acción y resultado observable.
2. **RED:** agregar la mínima prueba de esa conducta y ejecutarla focalizada. Debe fallar por el comportamiento faltante, no por un import roto, un fixture inválido o el servidor apagado.
3. **GREEN:** implementar lo mínimo que hace pasar esa prueba. No anticipar el siguiente estado ni construir una abstracción genérica de toda la plataforma.
4. Ejecutar la prueba y la regresión directamente afectada. Registrar salida, comando y motivo del fallo previo.
5. Elegir el siguiente comportamiento a partir del resultado y repetir. No escribir todos los tests de todos los tickets antes de implementar.
6. En la revisión posterior, evaluar claridad, duplicación y separaciones de módulos. Si se refactoriza, mantener invariantes y volver a ejecutar pruebas pertinentes. Esta revisión es una etapa separada del ciclo RED → GREEN, conforme a la habilidad local.

## Ejemplo: ejecución bloqueada por una fuente desactualizada

Primer ciclo F1: abrir un escenario de prueba con una revisión desactualizada conocida, observar «Los datos cambiaron» y seguir la acción al origen afectado. La prueba falla mientras la pantalla no permita identificarlo. Implementar ese resumen y enlace.

Segundo ciclo, después del primero: revalidar explícitamente una selección compatible, recibir aceptación y observar que se permite ejecutar ese período. No activar el botón solo porque se ocultó el aviso localmente.

Tercer ciclo: después de revisar, otra sesión cambia una dependencia. Ejecutar debe mostrar el rechazo del servidor y conservar la selección. La lectura pública de corridas no debe mostrar una nueva corrida de este intento rechazado.

Cuarto ciclo, si hay cambio de contrato: verificar en F3 que la revisión exacta aceptada y el rango aparecen en el snapshot consultado por API. Esto no es una aserción sobre llamadas entre hooks.

Los ciclos son ilustrativos; ejecutar uno a la vez, adaptando el siguiente. No implementar una batería completa de casos imaginados como primer paso.

## Fixtures y resultados esperados

- Usar proyectos/usuarios únicos y una base aislada. Cubrir admin, analista, externo con cada capacidad y externo revocado.
- Un caso corto de dos períodos con timestamps con offset fijo, una batería y precio conocido sirve para interacción. Añadir renovable/demanda/hidro cuando el ticket toque sus necesidades.
- Preparar una pareja de fuentes con cobertura compatible y otra con un período faltante; el hueco esperado debe estar escrito literalmente en el fixture.
- Para unidades y resultados, usar ejemplos calculados independientemente o valores conocidos del fixture. No volver a calcular el esperado con la función bajo prueba.
- Preparar una revisión histórica y una posterior con un valor distinto; comprobar que abrir resultados antiguos sigue mostrando su dato y procedencia originales.
- Mantener casos C6 activo e inactivo y lectura canónica disponible/no disponible para los cambios de datos. El flag de lectura no sustituye la configuración efectiva del backend.
- Para consola, reutilizar el caso de 8760 filas y la cobertura de pegado, lease, conflicto y deshacer. No hacer una segunda tabla de pruebas que solo copie su implementación.

## Dobles y límites

Dobles permitidos en fronteras de sistema: HTTP, reloj, aleatoriedad, archivos cuando haga falta y proceso externo de Julia. Preferir base de prueba real a mocks del almacén. No mockear hooks, servicios internos o colaboradores propios para afirmar secuencias de llamadas.

`scripts/run_react_smoke_app.py` usa `SmokeValidationService` y `SmokeRunQueue`; Playwright verifica la integración de navegador y API con resultados deterministas, **no la corrección del optimizador Julia**. Si cambia la generación/materialización, añadir la regresión de integración con Julia real y ejecutar `test/runtests.jl` mediante su comando establecido.

Muchos tests de componentes actuales controlan HTTP y algunas suites de Python inspeccionan internals. No se exige reescribirlos en este plan; la nueva cobertura debe seguir las fronteras acordadas y observar el comportamiento público.

## Evitar pruebas frágiles

- Usar roles, etiquetas y contenido significativo; no selectores de clase CSS, profundidad del DOM, nombres de hooks ni snapshots gigantes.
- La prueba de paridad comprueba valores/capacidades después de guardar y reabrir, no que dos serializadores produzcan la misma cadena.
- Las pruebas de protección comprueban rechazo y ausencia de un efecto visible por API. Las de presentación no deben simular ser pruebas de autorización.
- No abrir un test nuevo para cada cambio de texto o espaciado reversible. Cubrirlos en el recorrido existente y en revisión visual cuando sea suficiente.
- Las comprobaciones de captura visual y tiempos son evidencia de UX; no sustituyen las pruebas de comportamiento ni deben introducir umbrales dependientes del equipo en Vitest.

## Comandos de referencia

Desde `frontend/` en PowerShell, usar `npm.cmd` para evitar depender de la política de ejecución de `npm.ps1`:

```powershell
npm.cmd test -- src/ApplicationRoots.test.tsx
npm.cmd test -- src/OperatorConsole.test.tsx -t "saves a scalar override"
npm.cmd run check
npm.cmd run build
$env:DATABASE_URL = 'sqlite:///:memory:'
npm.cmd run test:browser -- --grep "React analyst workspace"
```

Los dos filtros de ejemplo corresponden a pruebas existentes. Para cada ciclo, sustituir por el archivo/nombre de su prueba nueva. `test:browser` ya compila antes de lanzar Playwright: no duplicar el build en la misma verificación sin razón.

Desde la raíz, ejemplos de regresión específica:

```powershell
$env:DATABASE_URL = 'sqlite:///:memory:'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_ts3_case_variant_api.py' -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_configuration_layer_console_fail_closed.py' -v
```

Si cambia OpenAPI, regenerar y comprobar desde `frontend/`:

```powershell
$env:DATABASE_URL = 'sqlite:///:memory:'
npm.cmd run api:generate
npm.cmd run api:check
```

No editar `src/api/schema.ts` a mano. Si no cambia contrato, no regenerar por rutina. Registrar los comandos reales y restaurar variables de entorno de la sesión cuando corresponda.
