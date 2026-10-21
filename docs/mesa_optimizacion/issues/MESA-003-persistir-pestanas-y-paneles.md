# MESA-003 · Guardar pestañas, paneles y distribución por caso

Status: Done
Type: AFK
Triage: ready-for-agent
Assignee: Codex
Source: [Plan de implementación](../plan_implementacion.md)
User stories covered: HU-02, HU-03, HU-10

## What to build

Permitir al analista configurar su mesa y recuperarla después: vista general, pestañas por componente, selección de series y modo de presentación por panel. Persistir solo configuración visual, con esquema y revisión propios, vinculada al usuario y al caso. Un guardado visual no cambia la preparación matemática.

## Acceptance criteria

- [x] Guardar y recargar título, componente, series, modo gráfico/tabla, orden y distribución por pestaña.
- [x] Ofrecer 1×1, 1×2, 2×2 y 2×3; al reducir la distribución conservar los paneles ocultos y restaurarlos al ampliarla.
- [x] Agregar y quitar una vista no crea ni elimina activos, muestras o bindings del caso.
- [x] Varios paneles pueden consultar el mismo componente; unidades diferentes se separan en ejes/subgráficos inequívocos.
- [x] Guardar con revisión obsoleta devuelve conflicto recuperable sin sobrescritura silenciosa; las preferencias no se filtran a otro usuario/caso.
- [x] Al eliminarse un componente, la vista queda identificada como no disponible y permite reconfiguración; no se reasigna por nombre.
- [x] La matriz 2×2 y controles principales caben a 1440×900; las pestañas, el diálogo y los modos son operables con teclado.
- [x] Configurar la vista no invalida snapshots ni resultados. La persistencia y la lectura posterior se comprueban por S2/S1.

## Blocked by

- [MESA-002 · Abrir un caso real y consultar demanda en la mesa](MESA-002-abrir-caso-y-demanda-real.md)

## Validación TDD

Interfaces acordadas: S1 + S2

Primer test: guardar cuatro vistas, pasar a una, recargar y restaurar cuatro sin perder las configuraciones. Añadir conflicto de revisión y viewport fijo como comportamientos separados.

Aplicar la [estrategia TDD](../validacion_tdd.md) y la definición de terminado del plan. Las interfaces S1/S2 y S3 condicional fueron confirmadas por el usuario el 2026-10-20; registrar en MESA-001 cualquier interfaz adicional antes de probarla. Cada ciclo implementa un solo comportamiento observable.

## Demostración de cierre

Personalizar dos pestañas distintas, recargar y recuperar cada disposición.

## Evidencia y seguimiento

- Inicio: 2026-10-20, por Codex. Dependencia MESA-002 Done; S1/S2 ya confirmadas. Primer ciclo S2: cuatro paneles → uno → recarga → cuatro, conservando sus configuraciones.
- Evidencia: [nueve ciclos rojo → verde, comandos y revisión AFK](../evidencia/MESA-003/validacion.md).
- Implementación: pestañas y vistas configurables, orden, cuatro distribuciones,
  guardado personal por caso, recuperación explícita de conflictos y componentes
  no disponibles. [Contrato HTTP y migración](../persistencia_vistas.md).
- Pruebas: cinco HTTP y siete de navegador nuevas. Suite MESA 10/10; Python
  42 OK y cinco PostgreSQL omitidas; 336 Vitest verificadas entre 334 iniciales
  y dos reintentos aislados; cuatro regresiones generales de navegador OK.
- TypeScript, ESLint, OpenAPI y formato modificado OK. El check global conserva
  16 avisos de formato en archivos preexistentes sin cambios, documentados en la evidencia.
- Capturas: [matriz 1440×900](../evidencia/MESA-003/mesa-paneles-1440.png),
  [diálogo](../evidencia/MESA-003/mesa-configurar-1440.png) y
  [móvil 390 px](../evidencia/MESA-003/mesa-paneles-390.png), revisadas con geometría,
  teclado y Axe. Referencias originales conservadas.
- Alcance: demanda real disponible; segunda unidad validada con fixture en la
  frontera HTTP. Las fuentes eléctricas/hidráulicas adicionales corresponden a
  MESA-004/005. No se alteran datos matemáticos, snapshots ni resultados.
- Cierre: **Done**, Codex, 2026-10-20, después de revisión técnica AFK y visual.
  No requiere conformidad HITL. Siguiente entrega recomendada: MESA-004.
