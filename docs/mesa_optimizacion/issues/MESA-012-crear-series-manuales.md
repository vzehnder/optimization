# MESA-012 · Crear series manuales de apoyo y vincular entradas admitidas

Status: Done
Type: AFK
Triage: ready-for-agent
Assignee: Codex
Source: [Plan de implementación](../plan_implementacion.md)
User stories covered: HU-08, HU-04

## What to build

Ofrecer desde la mesa un recorrido para crear una serie manual con nombre, unidad, datos y período, conservada en el catálogo canónico asociado al objeto/contexto admitido. Puede organizarse como componente de referencia en la vista. Para influir en la optimización necesita una asociación/binding compatible explícito; no se crea un tipo físico arbitrario.

## Acceptance criteria

- [x] Crear y publicar la serie mediante el mecanismo canónico, con identidad, unidad, rol, períodos, revisión y procedencia manual.
- [x] Agregar una pestaña/grupo y paneles que referencien esa serie sin duplicar sus valores en la configuración visual.
- [x] Editar datos y recuperar la misma revisión después de recargar, con validaciones y permisos equivalentes a las demás entradas.
- [x] Una serie sin binding se etiqueta como apoyo y no participa en la simulación; no recibe un resultado ficticio.
- [x] Solo ofrecer destinos/señales compatibles con el tipo de objeto; una asociación inválida se rechaza en servidor.
- [x] Vincular a una entrada admitida activa la revalidación y hace que la próxima preparación use la revisión publicada.
- [x] Las ediciones y vinculaciones no alteran snapshots o runs existentes.
- [x] Demostrar por API/UI la diferencia entre una serie de apoyo persistida y una entrada realmente vinculada.

## Blocked by

- [MESA-003 · Guardar pestañas, paneles y distribución por caso](MESA-003-persistir-pestanas-y-paneles.md)
- [MESA-006 · Editar entradas en tablas y guardar revisiones auditables](MESA-006-editar-entradas-versionadas.md)

## Validación TDD

Interfaces acordadas: S1 + S2

Primer test: crear una serie de apoyo y recuperarla sin que cambie el payload ejecutable. Segundo ciclo: vincular una señal admitida y observar la revisión en la preparación pública.

Aplicar la [estrategia TDD](../validacion_tdd.md) y la definición de terminado del plan. Las interfaces S1/S2 y S3 condicional fueron confirmadas por el usuario el 2026-10-20; registrar en MESA-001 cualquier interfaz adicional antes de probarla. Cada ciclo implementa un solo comportamiento observable.

## Demostración de cierre

Crear un aporte manual, mostrarlo en la mesa y vincularlo conscientemente a un objeto compatible.

## Evidencia y seguimiento

- Inicio: 2026-10-21, por instrucción del usuario. S1 navegador y S2 HTTP ya confirmadas; dependencias MESA-003 y MESA-006 Done. Cambios locales previos preservados.
- Evidencia rojo → verde: trece ciclos completos en S1/S2; [detalle](../evidencia/MESA-012/validacion.md). Revisión técnica y visual AFK completadas.
- Pruebas y comandos ejecutados: once pruebas HTTP y cinco de navegador nuevas. 129 Python distintas aprobadas, 336 Vitest verificadas entre suite/reintento, cinco regresiones generales y 51/52 MESA; una prueba hidráulica existente agota 120 s. Última revisión de matrices y recorridos manuales: 9/9. TypeScript, ESLint, OpenAPI, build y formato de archivos modificados OK; formato global mantiene 16 archivos ajenos pendientes.
- Capturas de implementación: escritorio, móvil, editor y matriz hidráulica inspeccionados; enlaces en la evidencia. No sustituyen la aceptación HITL de MESA-014.
- Decisiones: catálogo TS-7 sin migraciones, publicación y vínculo separados. Destinos ejecutables de variantes v1/v2, incluido hidro simple; red v3 conserva su versión promovida y admite apoyo sin fingir que un binding cambia esa fuente. Comparación/CSV del apoyo sin resultados ni Δ ficticios.
- Cierre y responsable: Codex, 2026-10-21. Criterios del ticket satisfechos; limitaciones de PostgreSQL y timeout hidráulico registradas. El recorrido hidráulico pasó en una copia temporal con espera ampliada, sin cambiar la prueba original. Siguiente: MESA-014, con dependencias satisfechas y aceptación humana pendiente.
