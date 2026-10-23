# MESA-013 · Recuperar ejecuciones y exportar la comparación

Status: Done
Type: AFK
Triage: ready-for-agent
Assignee: Codex
Source: [Plan de implementación](../plan_implementacion.md)
User stories covered: HU-09, HU-06, HU-11

## What to build

Completar el recorrido desde la mesa hacia su historial persistido, recuperar un resultado pasado o elegirlo como referencia y exportar las series comparadas. Reutilizar los runs y resultados existentes, incluyendo la política de lectura indexada/fallback, sin crear otro archivo histórico paralelo.

## Acceptance criteria

- [x] El historial muestra únicamente ejecuciones autorizadas del contexto, con estado, rango y procedencia identificables después de recargar.
- [x] Consultar un run antiguo no reemplaza la preparación actual ni modifica la versión matemática que corrió.
- [x] Una referencia incompatible se explica y no se empareja silenciosamente; ejecuciones fallidas no ofrecen outputs aparentes.
- [x] Exportar CSV con componente, serie, unidad, período, origen antes/después y diferencia cuando sea válida.
- [x] La exportación corresponde a las vistas/series y rango elegidos; incluye todos los intervalos solicitados aunque la tabla esté paginada.
- [x] Exportar por la misma selección y autorización que la vista; escapar delimitadores y valores peligrosos para apertura en planillas.
- [x] Índices faltantes o retención de resultados producen el fallback/estado permitido por el sistema, sin confundir ausencia con cero.
- [x] Una prueba recupera una comparación histórica y valida su CSV contra valores literales conocidos.

## Blocked by

- [MESA-009 · Comparar entradas y resultados eléctricos con procedencia](MESA-009-comparar-series-electricas.md)
- [MESA-010 · Comparar resultados hidráulicos sin mezclar objetos o unidades](MESA-010-comparar-series-hidraulicas.md)

## Validación TDD

Interfaces acordadas: S1 + S2

Primer test: seleccionar un run histórico tras editar el caso y recuperar los valores originales; en otro ciclo, descargar su CSV y comprobar identidad, valores y Δ.

Aplicar la [estrategia TDD](../validacion_tdd.md) y la definición de terminado del plan. Las interfaces S1/S2 y S3 condicional fueron confirmadas por el usuario el 2026-10-20; registrar en MESA-001 cualquier interfaz adicional antes de probarla. Cada ciclo implementa un solo comportamiento observable.

## Demostración de cierre

Volver a una ejecución previa y descargar la misma comparación que se ve en los paneles.

## Evidencia y seguimiento

- Inicio: 2026-10-21, por instrucción del usuario; dependencias MESA-009/010 Done.
- TDD: once ciclos rojo → verde en S1/S2, diez pruebas HTTP y seis de navegador nuevas. [Evidencia y comandos](../evidencia/MESA-013/validacion.md).
- Historial persistido existente, selección recuperable, rangos de consulta y CSV autorizado con procedencia. Incluye 256 intervalos, retención/fallback y recuperación de objetos eléctricos archivados.
- Capturas a 1440/390 px, teclado y Axe; referencias originales conservadas.
- Sin cambios de motor ni persistencia; no se crea otro catálogo histórico. El período de consulta usa UTC explícito; los snapshots mantienen su zona original.
- Verificación: 135 pruebas Python distintas, 47/47 MESA, 5/5 regresiones generales y 336/336 Vitest. Build, TypeScript, ESLint, OpenAPI y formato modificado OK; quedan 16 avisos de formato global previos.
- Cierre AFK: 2026-10-21 por Codex, tras revisión técnica, pruebas y capturas. Siguiente entrega: MESA-012; MESA-014 continúa dependiendo de ella.
