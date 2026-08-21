---
id: 13
title: "Alcance de marca del portal cliente"
map: capa-de-configuracion
label: wayfinder:grilling
status: open
assignee:
blocked_by: [03, 08]
---

## Question

¿Que elementos de marca del informe ejecutivo son configurables y a que nivel
pertenecen cuando un proyecto puede ser visible para varios usuarios cliente?

La forma del portal ya esta fijada. Falta decidir si usa siempre la marca del
producto o si la configuracion por proyecto admite nombre visible, logo y
colores; si el nombre del cliente es solo informativo; y si dominio propio o
white-label quedan fuera de esta primera especificacion.

La respuesta debe evitar una configuracion distinta por persona y encajar con
el alcance por proyecto que defina **Modelo de datos de la configuracion por
proyecto**.

## Restriccion confirmada por el modelo de datos

**Modelo de datos de la configuracion por proyecto** ya cerro el envase: la
configuracion de portal es **un documento JSON `portal_config.v1`, uno por
proyecto**, validado contra un esquema en codigo con rechazo duro. Todo elemento
de marca que se decida aqui tiene que caber dentro de ese documento y sobrevivir
esa validacion; no hay tabla de marca aparte ni columnas tipadas donde alojarlo.

Dos consecuencias que acotan el alcance de este ticket:

- la marca **no se versiona**. El documento solo lleva un contador de revision,
  asi que no se puede reconstruir como se veia el portal en una publicacion
  pasada. Si la marca necesitara esa reconstruibilidad —por ejemplo para que un
  informe entregado a un cliente siga viendose igual—, eso redibuja el corte MVP
  del modelo de datos y hay que decirlo aqui explicitamente;
- editar la configuracion `active` la cambia **en vivo**, sin borrador. Un
  cambio de logo o de paleta aparece de inmediato en el portal de todos los
  clientes del proyecto.
