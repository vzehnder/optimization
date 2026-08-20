---
id: 04
title: "Rol y permisos del operador"
map: capa-de-configuracion
label: wayfinder:grilling
status: closed
assignee: vzehnder
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

## Resolucion

### Identidad y asignacion

- Los roles globales pasan a ser `admin`, `analyst` y `external`. No se crea un
  rol global `operator`: la capacidad de operar depende del proyecto.
- Los usuarios `client` existentes migran a `external` y conservan su acceso
  actual mediante la capacidad `portal_view` en cada proyecto ya asignado. La
  migracion no amplia permisos.
- Cada asignacion de un usuario `external` a un proyecto contiene dos
  capacidades independientes: `portal_view` y `operate`. Una cuenta puede
  tener una, ambas o ninguna, y puede tener capacidades distintas en proyectos
  distintos.
- Las capacidades pertenecen al proyecto, no a una configuracion concreta. Si
  cambia la configuracion activa, las asignaciones sobreviven y pasan a la
  nueva superficie; cada accion registra que version uso.
- Solo `admin` puede otorgar o revocar capacidades. `analyst` configura las
  superficies, pero no administra identidades ni accesos.

### Matriz de autorizacion

| Sujeto | Facultades |
| --- | --- |
| `admin` | Administra usuarios y capacidades; configura; prueba la consola; ve la auditoria completa. |
| `analyst` | Configura y prueba la consola; ve la auditoria completa; no administra accesos. |
| `external` + `portal_view` | Ve exclusivamente publicaciones y descargas aprobadas del proyecto. |
| `external` + `operate` | Usa la configuracion operativa activa, modifica solo los inputs expuestos, ejecuta y ve el historial operativo compartido. |

`admin` y `analyst` pueden entrar a la consola para probarla en los proyectos a
los que ya tienen acceso interno. Actuan con su identidad real; no requieren
una asignacion `external` ni impersonan a un operador.

`operate` no concede acceso general al proyecto ni al catalogo. Solo autoriza
endpoints propios de la consola para:

- leer las senales y versiones nombradas habilitadas por la configuracion
  activa;
- guardar valores de los inputs expuestos;
- validar y ejecutar mediante el flujo operativo;
- consultar resultados e historial de esa configuracion.

Un usuario `external` nunca obtiene por `operate` acceso a drafts, catalogo,
escenarios, variantes, bindings, versiones inmutables ni endpoints internos.
La garantia anterior se reformula explicitamente: `portal_view` nunca ve
inputs; `operate` ve y modifica unicamente los inputs expuestos por la
configuracion. **Donde aterriza la edicion de series del operador** decide el
objeto interno sobre el que se materializa esa escritura.

Las capacidades se comprueban en cada request, despues del gate compartido
`require_authenticated_app_boundary`; no se confia en el estado de la sesion
al iniciar. Revocar una capacidad bloquea de inmediato nuevas lecturas,
ediciones y ejecuciones. Una corrida ya iniciada no se cancela: conserva al
actor original y sigue visible para `admin`/`analyst`, mientras que el usuario
revocado deja de verla.

### Auditoria y visibilidad

Toda mutacion operativa debe registrar de forma estructurada:

- `actor_user_id` como identidad estable;
- correo o nombre como snapshot legible;
- origen `operator_console`;
- proyecto y version de configuracion activa;
- timestamp;
- para una corrida, la revision exacta de inputs materializada.

La atribucion hardcodeada `triggered_by = "internal_analyst"` deja de ser
valida: ninguna corrida autenticada puede perder quien la inicio.

Quienes tengan `operate` ven el historial compartido de corridas de la
configuracion, incluido autor, fecha y estado, pero no rutas internas,
`stdout`, `stderr` ni detalles tecnicos sensibles. `admin` y `analyst` ven la
auditoria completa. `portal_view` no concede acceso a informacion de
auditoria.
