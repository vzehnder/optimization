---
id: 04
title: "Rol y permisos del operador"
map: capa-de-configuracion
label: wayfinder:grilling
status: open
assignee:
blocked_by: []
---

## Question

¿Quien es el operador para el sistema de autenticacion: un rol nuevo, o un
`client` con permisos ampliados?

Hoy hay tres roles (`admin`, `analyst`, `client`) y un unico gate compartido,
`require_authenticated_app_boundary` en `app/main.py`, que TS-5 dejo como punto
de control por construccion. Cualquier respuesta debe pasar por ahi.

Lo que hay que decidir:

- **Cuarto rol `operator` vs. capacidad sobre `client`**: un rol nuevo es mas
  limpio semanticamente pero toca la matriz de permisos entera, el bootstrap,
  la gestion de usuarios y los tests de frontera. Ampliar `client` es mas
  barato pero rompe la promesa actual de que `client` es read-only, que esta
  escrita en `docs/final/objetivo_final.md` y verificada en el acceptance de
  la iteracion 6.
- **Alcance del permiso**: ¿un operador se asigna a un proyecto (como el
  cliente hoy), a un escenario, o a una configuracion concreta? Un operador con
  acceso a todo el proyecto puede correr cualquier caso del proyecto.
- **¿Puede un mismo usuario ser operador y cliente?** Es decir, ejecutar en un
  proyecto y solo leer en otro. Eso empuja hacia permisos por asignacion en vez
  de rol global.
- **Escritura sobre el catalogo**: el operador va a editar series, es decir a
  escribir en datos del proyecto. La matriz de permisos aceptada en TS-5 dice
  que los clientes nunca ven series de entrada. Esto hay que reconciliarlo
  explicitamente, no por omision.
- **Auditoria**: `created_by` en las revisiones de series y en las corridas
  debe distinguir al operador. ¿Que se registra y donde se ve?

**Insumo de** [Inventario de la superficie configurable existente](01-inventario-superficie-configurable.md):
la atribucion de corridas manuales esta rota hoy —toda corrida disparada a mano
queda estampada `triggered_by = "internal_analyst"`—, mientras que la edicion de
series si atribuye al usuario real. Ver el detalle en la seccion D de ese
ticket. La decision de auditoria de aqui debe partir de ese hecho, no de la
suposicion de que las corridas ya identifican a quien las lanzo.

Este ticket decide el sujeto; **Donde aterriza la edicion de series del
operador** decide el objeto. Son independientes y pueden trabajarse en
paralelo, pero el spec final debe cuadrarlos.
