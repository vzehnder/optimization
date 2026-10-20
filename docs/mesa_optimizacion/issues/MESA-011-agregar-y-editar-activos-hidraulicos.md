# MESA-011 · Agregar y editar centrales y embalses ejecutables

Status: Todo
Type: AFK
Triage: ready-for-agent
Assignee: —
Source: [Plan de implementación](../plan_implementacion.md)
User stories covered: HU-07, HU-05, HU-06

## What to build

Permitir agregar a la mesa un activo hidráulico existente o crear uno nuevo en el caso mediante los servicios y editores del dominio. El recorrido incluye parámetros, unidades/conexiones necesarias, entradas y validación hasta que el nuevo componente pueda participar en una ejecución admitida y mostrar resultados.

## Acceptance criteria

- [ ] Distinguir «usar activo existente» de «crear activo», evitando duplicar objetos físicos por agregar una pestaña.
- [ ] Una central/embalse nuevo se persiste y aparece al recargar con identidad estable en mesa y diagrama.
- [ ] Editar nombre y parámetros expuestos mediante el recorrido del dominio, incluyendo curvas, límites y unidades cuando sean requeridos.
- [ ] Completar conexiones y entradas desde un panel de la mesa que reutiliza la edición hidráulica; un objeto incompleto permanece borrador.
- [ ] Indicar qué impide ejecutar y qué componente debe completarse. Crear una pestaña no convierte automáticamente un activo en modelado.
- [ ] Validar, congelar y ejecutar un caso admitido que incluya el componente nuevo; sus resultados se consultan en la mesa.
- [ ] Crear/modificar el componente invalida la preparación correspondiente y conserva versiones/runs históricos.
- [ ] Probar creación → recarga → validación → ejecución → resultados sin verificaciones ocultas por consultas directas a BBDD.

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

- Inicio: pendiente.
- Evidencia rojo → verde / revisión HITL: pendiente.
- Pruebas y comandos ejecutados: pendiente.
- Capturas de implementación y diferencias revisadas: pendiente, cuando aplique.
- Decisiones o desviaciones respecto del plan: pendiente.
- Cierre y responsable: pendiente.
