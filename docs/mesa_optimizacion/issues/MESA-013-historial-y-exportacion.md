# MESA-013 · Recuperar ejecuciones y exportar la comparación

Status: Todo
Type: AFK
Triage: ready-for-agent
Assignee: —
Source: [Plan de implementación](../plan_implementacion.md)
User stories covered: HU-09, HU-06, HU-11

## What to build

Completar el recorrido desde la mesa hacia su historial persistido, recuperar un resultado pasado o elegirlo como referencia y exportar las series comparadas. Reutilizar los runs y resultados existentes, incluyendo la política de lectura indexada/fallback, sin crear otro archivo histórico paralelo.

## Acceptance criteria

- [ ] El historial muestra únicamente ejecuciones autorizadas del contexto, con estado, rango y procedencia identificables después de recargar.
- [ ] Consultar un run antiguo no reemplaza la preparación actual ni modifica la versión matemática que corrió.
- [ ] Una referencia incompatible se explica y no se empareja silenciosamente; ejecuciones fallidas no ofrecen outputs aparentes.
- [ ] Exportar CSV con componente, serie, unidad, período, origen antes/después y diferencia cuando sea válida.
- [ ] La exportación corresponde a las vistas/series y rango elegidos; incluye todos los intervalos solicitados aunque la tabla esté paginada.
- [ ] Exportar por la misma selección y autorización que la vista; escapar delimitadores y valores peligrosos para apertura en planillas.
- [ ] Índices faltantes o retención de resultados producen el fallback/estado permitido por el sistema, sin confundir ausencia con cero.
- [ ] Una prueba recupera una comparación histórica y valida su CSV contra valores literales conocidos.

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

- Inicio: pendiente.
- Evidencia rojo → verde / revisión HITL: pendiente.
- Pruebas y comandos ejecutados: pendiente.
- Capturas de implementación y diferencias revisadas: pendiente, cuando aplique.
- Decisiones o desviaciones respecto del plan: pendiente.
- Cierre y responsable: pendiente.
