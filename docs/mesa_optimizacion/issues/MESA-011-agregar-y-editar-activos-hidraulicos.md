# MESA-011 · Agregar y editar centrales y embalses ejecutables

Status: Done
Type: AFK
Triage: ready-for-agent
Assignee: Codex
Source: [Plan de implementación](../plan_implementacion.md)
User stories covered: HU-07, HU-05, HU-06

## What to build

Permitir agregar a la mesa un activo hidráulico existente o crear uno nuevo en el caso mediante los servicios y editores del dominio. El recorrido incluye parámetros, unidades/conexiones necesarias, entradas y validación hasta que el nuevo componente pueda participar en una ejecución admitida y mostrar resultados.

## Acceptance criteria

- [x] Distinguir «usar activo existente» de «crear activo», evitando duplicar objetos físicos por agregar una pestaña.
- [x] Una central/embalse nuevo se persiste y aparece al recargar con identidad estable en mesa y diagrama.
- [x] Editar nombre y parámetros expuestos mediante el recorrido del dominio, incluyendo curvas, límites y unidades cuando sean requeridos.
- [x] Completar conexiones y entradas desde un panel de la mesa que reutiliza la edición hidráulica; un objeto incompleto permanece borrador.
- [x] Indicar qué impide ejecutar y qué componente debe completarse. Crear una pestaña no convierte automáticamente un activo en modelado.
- [x] Validar, congelar y ejecutar un caso admitido que incluya el componente nuevo; sus resultados se consultan en la mesa.
- [x] Crear/modificar el componente invalida la preparación correspondiente y conserva versiones/runs históricos.
- [x] Probar creación → recarga → validación → ejecución → resultados sin verificaciones ocultas por consultas directas a BBDD.

## Blocked by

- [MESA-008 · Ejecutar una red hidráulica desde la misma mesa](MESA-008-ejecutar-red-hidraulica.md)
- [MESA-010 · Comparar resultados hidráulicos sin mezclar objetos o unidades](MESA-010-comparar-series-hidraulicas.md)

## Validación TDD

Interfaces acordadas: S1 + S2; S3 si cambia el contrato ejecutable.

Primer test: crear y recuperar un embalse por UI/API. Progresar en ciclos separados hasta rechazar el incompleto y ejecutar uno válido con una red fixture compatible.

Aplicar la [estrategia TDD](../validacion_tdd.md) y la definición de terminado del plan. Las interfaces S1/S2 y S3 condicional fueron confirmadas por el usuario el 2026-10-20; registrar en MESA-001 cualquier interfaz adicional antes de probarla. Cada ciclo implementa un solo comportamiento observable.

## Demostración de cierre

Agregar un embalse y una central, completar sus datos y verlos participar en una simulación real de prueba.

## Evidencia y seguimiento

- Inicio: 2026-10-21, Codex. Dependencias MESA-008/010 completas. S1 navegador y S2 HTTP ya confirmadas; se reutilizan el editor y la persistencia hidráulicos, sin cambiar el contrato del motor.
- Implementación: editor del dominio integrado en la mesa v3, selección de objetos existentes, creación de embalses/centrales, curvas, afluentes, unidades y conexiones. Borradores y guardados pendientes protegidos; conflicto recuperable con inventario actualizado.
- TDD: diez ciclos rojo → verde en S1/S2, una prueba HTTP y nueve de navegador nuevas. [Evidencia, comandos e incidencias](../evidencia/MESA-011/validacion.md). La prueba decimal pasó desde el inicio y se registra como regresión.
- Demostración: embalse y central creados por UI, recargados, validados/promovidos y ejecutados con worker/Julia reales; potencia de 10 MW y volumen final de 4,9352 hm³ por balance independiente.
- Revisión técnica: sin cambios del motor, esquema ni contrato ejecutable. La revisión guardada del diagrama participa en la huella de preparación; rechaza nuevas solicitudes obsoletas y conserva snapshots/reintentos aceptados. No se requiere migración ni S3.
- Revisión visual: editor a [1440 px](../evidencia/MESA-011/mesa-activos-editor-1440.png) y [390 px](../evidencia/MESA-011/mesa-activos-editor-390.png), [resultados reales](../evidencia/MESA-011/mesa-activos-resultados-1440.png) y [matriz 2×2](../evidencia/MESA-011/mesa-hidraulica-matriz-1440.png). Accesibilidad Axe y retorno de foco comprobados. Referencias originales conservadas.
- Alcance: «Usar activo existente» opera sobre objetos del caso actual. Una edición requiere promover otra versión para incluirla en la ejecución; las fuentes históricas siguen siendo explícitas. No se importan activos de otros casos.
- Verificación: 188 Python, 41 navegador MESA y cinco regresiones generales de navegador OK; TypeScript, ESLint, build, OpenAPI y formato modificado OK. Vitest 335/336 por fallo de foco previo; formato global pendiente en los mismos 16 archivos ajenos. [Auditoría documental final](../evidencia/MESA-011/docs-final.txt).
- Cierre y responsable: In Progress → In Review → Done, revisión técnica y visual AFK completada por Codex el 2026-10-21. Siguiente entrega recomendada: MESA-013; MESA-012 también está habilitada por dependencias.
