# UX-007 · Configurar y publicar informes con claridad

Estado: In Review. Prioridad: P1. Dependencias: UX-006. Tamaño: M.

Responsable: Codex. Inicio: 2026-09-14, sobre `cf64106`.
El usuario confirmó «confirmo» para F1/F2 antes de las pruebas nuevas.
[Acuerdo y evidencia](../evidencia/ux-007/README.md).

## Problema y resultado

Configuración del portal, templates y publicaciones están en puntos distintos del flujo. El ingeniero debe poder preparar una entrega y comprobar exactamente lo que verá el cliente antes de publicarla.

## Código y contratos

- `frontend/src/Workspace.tsx`: `PortalConfigurationSection`, `DashboardTemplatesSection`, `PublicationSection`, `PublicationPreviewView`.
- `frontend/src/ClientPortal.tsx`, `PortalResults.tsx`.
- `app/portal_configuration.py`, `app/surface_payloads.py` y endpoints existentes de templates/configuración/publicaciones.
- Regresión: `PortalConfiguration.test.tsx`, `PortalResults.test.tsx`, `tests/test_iter6_publications.py`, `tests/test_configuration_layer_portal_results.py`, `tests/test_configuration_layer_portal_branding.py` y Playwright de publicaciones.

## Pasos de implementación

1. Colocar configuración y templates en Informes del proyecto, con enlaces desde una corrida exitosa. Mostrar configuración vigente y qué publicación se está preparando.
2. Conservar controles estructurados existentes de branding, KPI, gráficos, tablas y descargas. Agrupar por sección y abrir solo la sección editada; no reconstruir el sistema de configuración.
3. Mantener estado de edición y revisión al cambiar secciones. Guardar un campo de branding no debe eliminar selecciones de gráficos ni parámetros ocultos.
4. Mostrar pasos Resultado → Contenido → Vista previa → Publicación, reutilizando recursos existentes. Crear/guardar borrador no publica. Si el proyecto carece de configuración válida, enlazar al campo correspondiente.
5. Reusar el mismo constructor de payload externo en preview y portal. Refrescar el preview tras guardar configuración/publicación; si hay conflicto de revisión, explicar y conservar el trabajo sin sobrescribir.
6. Publicar mediante acción explícita y mostrar vínculo permitido para comprobar el resultado. Conservar edición posterior, despublicación y las reglas vigentes sobre el efecto de cambiar configuración de proyecto.
7. En portal, priorizar título, fecha y contenido autorizado. Mantener listados, navegación y descargas aprobadas, sin mostrar variantes, logs, IDs internos innecesarios o configuración técnica.

## Secuencia TDD sugerida

F1/F2; F3 para permisos/contrato si se modifican:

1. RED: desde una corrida exitosa, guardar un borrador y abrir un preview con título y KPI conocidos; la publicación aún no aparece al externo. GREEN: primer flujo conectado.
2. RED: cambiar branding conserva gráficos/tablas/descargas configurados al guardar y reabrir. GREEN: organización sin pérdida.
3. RED: publicar explícitamente hace visible al externo autorizado el mismo contenido permitido; despublicar lo retira. GREEN: confirmación y retorno.
4. RED si el cambio lo afecta: revocar acceso durante una sesión impide seguir consultando/descargando y elimina contenido protegido de la UI. GREEN: mantener manejo de autorización/caché.

## Aceptación

- «Guardar borrador», «Vista previa» y «Publicar» se distinguen; no se publica automáticamente.
- Se conservan todas las opciones del portal y templates existentes, incluido branding/logo y selección de artefactos.
- El preview usa la superficie externa real y no una copia de datos internos filtrada solo por CSS.
- Una publicación usa resultados de la corrida elegida, no de «la última» por inferencia.
- La despublicación y revocación siguen aplicando en cada request.
- Teclado, estados vacíos, ausencia de resultados y pantallas estrechas tienen revisión visual.

Este ticket no agrega un generador libre de dashboards ni nuevas reglas de entrega por correo. Evaluar separaciones internas pequeñas solo en revisión posterior.

## Resolución

- Responsable: Codex. Inicio y entrega para revisión: 2026-09-14.
- Estado final: **In Review**, pendiente de aceptación de producto.
- PR o commits: `feat(ux): guide report configuration and explicit publication`,
  sobre `cf64106`, solicitado por el usuario. Sin PR.
- Comportamiento implementado: configuración por sección que conserva el
  documento y su revisión, logo sin pérdida de edición, recuperación de
  errores/conflictos, salida protegida y corrección con foco. Flujo Resultado →
  Contenido → Vista previa → Publicación, con retorno a la ejecución elegida,
  activación de configuración y acciones explícitas desde preview.
- Fronteras: el usuario respondió «confirmo» para F1/F2 antes de las pruebas.
  F3 ejecutó regresiones existentes; no hubo cambio de contrato o permisos.
- TDD: [12 ciclos RED → GREEN](../evidencia/ux-007/README.md#ciclos-red--green).
- Verificación: 246 pruebas frontend, 21 navegador y 56 Python aprobadas;
  323 en total sin duplicar repeticiones. Tras el último ajuste de foco se
  repitieron Vitest completo, build y F1 afectado. Contrato generado,
  TypeScript, ESLint y formato del código modificado pasan.
- Revisión visual: 14 capturas, 1440/1280/320 px y ampliación CSS 200 %;
  teclado/foco y axe sin serious/critical en las superficies comprobadas.
- Conservación: las tres filas de informes/portal de la matriz están
  [contrastadas con pruebas](../evidencia/ux-007/README.md#conservación-funcional).
  Preview y portal siguen usando la superficie externa compartida; no cambian
  autorización, persistencia, TS-7 ni resultados matemáticos.
- Limitaciones: `check` falla por Prettier en 21 archivos previos sin cambios.
  No se ejecutaron Julia real, PostgreSQL, toda la suite Python ni evaluación
  con participantes/lectores de pantalla. El smoke tiene solver sintético.
- Tutoriales actualizados. Persona que revisó/aceptó: pendiente.

### Criterios comprobados

- [x] Guardar borrador, vista previa y publicar son acciones distintas; el
  borrador no aparece como publicación activa para el externo.
- [x] Branding/logo, KPI, gráficos, tablas, descargas, plantillas y artefactos
  conservan sus controles y persistencia.
- [x] Preview reutiliza el payload externo y sus componentes de informe.
- [x] El informe muestra los resultados de la ejecución elegida y permite
  volver a ella después de configurar.
- [x] Despublicar y revocar acceso retiran el contenido; regresiones API
  conservan la protección de consultas y descargas por request.
- [x] Teclado y foco comprobados, revisión visual en tamaños estrechos;
  estados vacíos y ausencia de resultados cubiertos por las regresiones.

Comandos, resultados reales y límites de capturas en la
[evidencia completa](../evidencia/ux-007/README.md).
