# UX-004 · Catálogo desde la necesidad del modelo

Implementación sobre `91bb561`, 2026-09-14. Estado: **In Review**. Responsable: Codex.
Commit solicitado por el usuario: `feat(ux): connect catalog sources to model needs`.
La aceptación de producto queda pendiente; no se creó PR.

## Acuerdo y alcance

Se leyó el paquete completo `docs/mejora_experiencia_usuario`, incluidos tickets,
tracker y evidencia anterior. Se aplicó la habilidad local
[TDD](../../../../.agents/skills/tdd/SKILL.md). Antes de las pruebas nuevas, el
usuario confirmó: **«Confirmo F1 y F2 para UX-004»**.

- **F1:** navegador → React → FastAPI/SQLite aislado. Modelo, resumen del objeto,
  fuente candidata, asociación, reemplazo de revisión, regreso y ejecución.
- **F2:** interfaz React con HTTP controlado. Compatibilidad, paginación, URL,
  errores, prevalidación, conservación de contexto y rechazo de destinos inválidos.
- **F3:** solo regresiones existentes de las APIs. No se amplió el contrato del
  backend; el cliente tipa campos que ya devuelve la preparación y los bindings.
- **F4:** no se incorporó. No cambian materialización ni lógica matemática.

Las nuevas pruebas observan interfaces públicas. La fixture del servidor de humo
prepara dos precios y una variante con usos canónicos; las aserciones de F1
comprueban el resultado en el navegador, incluida persistencia tras recarga.

## Comportamiento entregado

Las necesidades muestran nombre funcional, componente, fuente/revisión y estado.
Los accesos a fuentes conservan objeto, escenario y variante; la URL de regreso
prevalece sobre una preferencia de variante guardada y la clonación actualiza esa
URL. Con lectura canónica deshabilitada se conserva el camino compatible.

El catálogo deja Buscar, Tipo y Unidad a la vista y agrupa clase, alcance,
estado y orden en Más filtros. Los filtros aplicados, el inspector y la cadena de
cursores viajan en una URL con parámetros permitidos. El resumen del objeto
conserva búsqueda, origen y regreso, y ofrece entrada al catálogo general. Los
cursores rechazados permiten iniciar de nuevo conservando filtros.

El recorrido mantiene cuatro pasos, contexto lateral y título de la tarea.
Busca y pagina candidatas en el servidor, muestra las incompatibilidades y
descarta la selección al cambiar de necesidad. La asociación desde el catálogo
permite seleccionar objetos de varias páginas y nombra los afectados al confirmar.
El reemplazo identifica objeto y necesidad juntos; al cambiar de fuente no
reutiliza la asociación de la fuente anterior.

El paso final muestra objeto, fuente/revisión, alcance, consumidores y cambio.
Asociar y fijar una revisión en una variante conservan acciones y mensajes
distintos. Un conflicto bloquea la confirmación hasta Revisar de nuevo, conserva
el borrador y actualiza las precondiciones. Ningún mensaje promete preparación
para ejecutar sin revisar antes la variante y el período. Las lecturas afectadas
se invalidan tras la asociación o el uso para mostrar el cambio al regresar.

## Ciclos RED → GREEN

Cada fila enlaza las salidas del comportamiento antes y después de implementarlo.
No se escribieron todos los tests primero. Los ajustes encontrados en revisión
se resolvieron con ciclos adicionales y el formato se aplicó al código modificado.

| Comportamiento | RED | GREEN |
| --- | --- | --- |
| Necesidad y variante al abrir candidatas | [context](context-red.txt) | [context](context-green.txt) |
| Acceso desde una necesidad del modelo | [need](need-red.txt) | [need](need-green.txt) |
| Filtros e inspector tras recarga | [url](url-red.txt) | [url](url-green.txt) |
| Regreso al catálogo con página e inspector | [return](return-red.txt) | [return](return-green.txt) |
| Recuperación del cursor del catálogo | [cursor](cursor-red.txt) | [cursor](cursor-green.txt) |
| Conflicto exige nueva revisión | [conflict](conflict-red.txt) | [conflict](conflict-green.txt) |
| Asociación no anuncia uso en variante | [impact](impact-red.txt) | [impact](impact-green.txt) |
| Título y hechos de la confirmación | [review](review-red.txt) | [review](review-green.txt) |
| Filtros y retorno del objeto | [object](object-red.txt) | [object](object-green.txt) |
| Búsqueda y páginas de candidatas en servidor | [candidates](candidates-red.txt) | [candidates](candidates-green.txt) |
| Consulta rechazada recuperable | [query](query-red.txt) | [query](query-green.txt) |
| Cambio de necesidad descarta candidata/cursor | [change-need](change-need-red.txt) | [change-need](change-need-green.txt) |
| Reintento de prevalidación fallida | [prevalidation](prevalidation-red.txt) | [prevalidation](prevalidation-green.txt) |
| Variante del regreso sobre preferencia local | [variant](variant-red.txt) | [variant](variant-green.txt) |
| Fuente/revisión visible en la necesidad | [source-need](source-need-red.txt) | [source-need](source-need-green.txt) |
| Regreso conserva solo contexto público | [public-return](public-return-red.txt) | [public-return](public-return-green.txt) |
| Entrada al catálogo desde el objeto | [general-entry](general-entry-red.txt) | [general-entry](general-entry-green.txt) |
| Cursor del objeto recuperable | [object-cursor](object-cursor-red.txt) | [object-cursor](object-cursor-green.txt) |
| Lote de objetos desde varias páginas | [bulk](bulk-red.txt) | [bulk](bulk-green.txt) |
| Reemplazo en el objeto correcto | [exact-object](exact-object-red.txt) | [exact-object](exact-object-green.txt) |
| Cambio de fuente no arrastra otra asociación | [source-association](source-association-red.txt) | [source-association](source-association-green.txt) |
| IDs inválidos no abren una acción incompleta | [destination](destination-red.txt) | [destination](destination-green.txt) |
| Clonar desde una URL con variante activa | [clone](clone-red.txt) | [clone](clone-green.txt) |
| Modelo → asociación → uso → ejecución | [browser](browser-red.txt) | [browser](browser-green.txt) |
| Tablas accesibles, tamaño móvil y foco del paso | [visual](visual-red.txt) | [visual](visual-green.txt) |

Las cuatro regresiones de destinos externos/no permitidos ya pasaron sobre la
allowlist existente cuando se añadieron: no se cuentan como RED ficticios.
La [comprobación visual ampliada](revision-visual-suplementaria.txt) de
confirmación por teclado y objeto con fuente también pasó sin cambios nuevos.
Se corrigieron errores de preparación de fixture y tipado durante el trabajo;
esos errores de herramientas no se presentan como fallos funcionales RED.

## Validación final

**491 pruebas aprobadas**, sin sumar la línea base ni repeticiones focalizadas.

| Comprobación | Resultado |
| --- | --- |
| Frontend completo | 19 archivos, **234 aprobadas**; [salida](vitest-final.txt) |
| Python afectado | **237 aprobadas**, 82 PostgreSQL omitidas, 319 ejecutadas; [salida](python.txt) |
| Navegador completo | **20 aprobadas**; [salida final](playwright-final.txt) |
| Recorrido tras ajuste visual final | **1 aprobado**, sin sumarlo otra vez al total; [salida](playwright-focused.txt) |
| Contrato generado | [api:check](api-check.txt) aprobado |
| TypeScript, ESLint y formato | TypeScript y ESLint pasan. `check` falla solo por los mismos **21 archivos previos** sin formato; [lista exacta](check-final.txt). No se cuenta como aprobado. |

Desde `frontend/`:

```powershell
npm.cmd test -- --maxWorkers=2
$env:DATABASE_URL = 'sqlite:///:memory:'
npm.cmd run test:browser
npm.cmd run api:check
npm.cmd run check
```

Ejecutar `check` separado de Playwright para que no recorra sus archivos mientras
se recrean. Build conserva el aviso previo de bundle mayor que 500 kB.

La regresión Python cubre TS-7 006–014, 019–022, catálogo TS-2, adaptador
hidráulico TS-5, transformaciones TS-6 y conectores. Cada
caso se identifica en `python.txt`; las omisiones PostgreSQL no cuentan como
aprobadas. Se conserva creación específica, ingesta de archivo, archivo de
específicas, revisión compartida, derivación local y cambios de alcance, además
de los caminos legacy, C6, hidráulica, ejecución, consola y portal.

## Presentación y límites

La prueba F1 genera 19 capturas de objeto, candidatas, confirmación y objeto con
fuente a 1440×900, 1280×720, 320×900 y zoom CSS 200 %. También captura el catálogo
con inspector a 1440, 1280 y 320 px. Se inspeccionan las imágenes; las tablas
conservan su desplazamiento horizontal propio y son alcanzables con teclado.
El foco pasa al encabezado de cada paso; la confirmación es alcanzable y visible
con Tab a 320 px. Axe comprueba impactos serious/critical en las vistas ejercitadas.
La inspección final amplió la columna de descripciones de la confirmación en
pantallas estrechas y normalizó el campo de búsqueda; se repitió F1 tras ese ajuste.
Las capturas regenerables se guardan localmente en `capturas/`, excluidas de Git
conforme al criterio de las entregas anteriores.

El servidor de humo usa Chromium, FastAPI y SQLite aislados. La variante cambia
el precio de compra 70/72 por 55/60 y ejecuta dos horas; el solver es sintético, por
lo que F1 no valida el resultado matemático. No se ejecutaron Julia real,
PostgreSQL, toda la suite Python, participantes ni una auditoría completa con
lectores de pantalla. No se cambiaron transacciones, migraciones, C6 de producción
ni el escritor canónico. La revisión de producto sigue pendiente.
