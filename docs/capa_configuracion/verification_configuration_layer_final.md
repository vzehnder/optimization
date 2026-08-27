# Verificacion final de la capa de configuracion

Fecha: 2026-08-27

Este informe cierra BESS-CONFIG-017 contra la arquitectura aceptada. La prueba
combina contratos HTTP y persistencia reales, cobertura React, Playwright sobre
el bundle de produccion y una narrativa visible en Chrome. Los datos del
recorrido son ficticios y el fixture no agrega endpoints privilegiados.

## Evidencia automatizada

| Contrato | Evidencia principal |
| --- | --- |
| Migracion sin ampliacion | `ConfigurationLayerMigrationAcceptanceTests` abre un SQLite legado, ejecuta la migracion real y comprueba publicacion conservada, `external + portal_view`, lista de consolas vacia y detalle 404. |
| Capacidades y aterrizaje | `ConfigurationLayerCapabilityAcceptanceTests` cubre portal, operacion, ambas, ninguna, `safe next`, precedencia, revocacion en el siguiente request y 404 externos. |
| Configuracion y portal | `ConfigurationLayerPortalAcceptanceTests` prueba rechazo sin escritura, revisiones, auditoria, preview fiel, marca actual, descarga allowlisted, contenido ajeno 404 e inyecciones que no cruzan la frontera. |
| Parametros y corridas | `ConfigurationLayerOperatorEditingAcceptanceTests` prueba aislamiento del draft/hash base, valores efectivos inmutables, actor real, pipeline comun, resultados configurados, fallos seguros y comparacion. |
| Series y concurrencia | La misma narrativa prueba cambio de fuente, primera copia, aislamiento canonico, guardado multi-set atomico, lease, heartbeat, contencion, ETag stale, historia, undo y restore append-only. Los tests React de `OperatorConsole` cubren ademas parser ambiguo, truncamiento, errores por celda, pegado y estados de shell. |
| Staleness y recuperacion | `ConfigurationLayerRecoveryAcceptanceTests` distingue cambios propios, origen canonico viejo y cambios externos; conserva review requests y exige el gesto correcto para cada bloqueo. |
| Catalogo declarativo | `ConfigurationLayerSignalCatalogAcceptanceTests` inyecta una nueva senal y demuestra que aparece solo en el catalogo interno, sin tocar payload externo. |
| Raices y UI | Los tests React cubren las tres raices, guards, marca, resultados, edicion, recuperacion y autorizacion. Playwright recorre 12 historias sobre el build. |

## Comandos y resultados

Ejecutados desde la raiz salvo que se indique `frontend/`:

| Comando | Resultado |
| --- | --- |
| `.\.venv\Scripts\python.exe -m unittest tests.test_configuration_layer_acceptance` | 9 tests passed. |
| `.\.venv\Scripts\python.exe -m unittest discover -s tests` | 834 tests passed; 7 PostgreSQL tests skipped porque no habia URL de entorno. |
| `npm test` | 11 archivos y 133 tests passed. |
| `npm run api:check` | OpenAPI generado sin drift. |
| `npx eslint .` | Passed. |
| `npm run build` | TypeScript y bundle Vite passed; queda el warning informativo existente de chunk mayor a 500 kB. |
| `npm run test:browser` | Build y 12 Playwright tests passed. |
| `julia --project=. -e "import Pkg; Pkg.test()"` | 532 tests passed. Julia aviso que el manifest se resolvio con 1.11.7 y se ejecuto con 1.12.6. |

La suite Python tambien muestra el warning de deprecacion conocido de
`fastapi.testclient`/`httpx`; no produjo fallos. No se modificaron contratos de
persistencia PostgreSQL en este issue y sus siete pruebas dependientes de una
base externa quedaron reportadas como skips, no simuladas.

## Narrativa Chrome

El fixture se inicio con:

```powershell
.\.venv\Scripts\python.exe scripts\run_configuration_acceptance_app.py
```

Browser no estaba disponible en la sesion, por lo que se uso Chrome, tambien
autorizado por el solicitante. El recorrido se hizo sobre
`http://127.0.0.1:8124/react`, mediante labels, roles y acciones visibles:

1. `operator login` llevo a `Plan diario Planta Norte`, sin calcular otra raiz
   en React.
2. La operadora adquirio el lease, pego cuatro celdas en Demanda/Precio, reviso
   las cuatro diferencias y guardo atomically; el historial mostro a Olga
   Operadora y cuatro celdas.
3. Ejecuto una corrida, vio `Beneficio total`, guardo un override de 6.5 MW,
   ejecuto otra corrida y abrio la comparacion de ambas.
4. Un cambio normal del draft produjo `dependencia_movida`; la corrida quedo
   deshabilitada, la operadora solicito revision y el timestamp aparecio.
5. Tras login de ingenieria, `Revalidar variante` cambio la consola a
   `Ninguno` y `Sin espera`.
6. `client login` aterrizo en el portal; Vera Cliente abrio `Energia Cliente
   Norte`, vio el logo, la publicacion, el KPI configurado y la descarga
   `summary.json` autorizada.

La descarga produjo un evento real del navegador y permanecio en la URL de la
publicacion. La revision final de consola de Chrome devolvio cero warnings y
cero errores.

## Fuera de alcance confirmado

Se comparo el diff con la lista normativa. Permanecen fuera de la
implementacion:

- Simplificar o fusionar Draft, Caso, Variante, Rango y Version inmutable.
- Exponer o editar topologia hidraulica desde la consola, o unificar los
  editores hidraulico y one-bus.
- Limites de potencia por unidad variables en el tiempo o cambios al contrato
  Julia.
- Unificar los mecanismos one-bus e hidraulico de senales requeridas.
- Carga CSV/XLSX por el operador; la superficie sigue siendo tabla y pegado.
- Edicion de modelos por el cliente read-only.
- Colores, tipografia, tema, favicon, dominio propio o white-label.
- Marca propia en la consola de operador.
- i18n o negociacion de idioma.
- Historial/reversion de configuraciones o marca historica.
- Linter semantico al guardar.
- Nueva paginacion de resultados/historial, limites menores de payload u
  optimizaciones fisicas sin medicion.
- Inbox, email, push, caducidad o escalamiento automatico de bloqueos.
- Registrar quien movio una dependencia.
- Regenerar automaticamente copias operativas desde su origen.
- Onboarding o manual de producto del ingeniero configurador.

El lanzador local y las actualizaciones de tests son infraestructura de
aceptacion; no agregan ninguna de esas capacidades al producto.
