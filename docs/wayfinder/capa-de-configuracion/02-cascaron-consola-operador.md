---
id: 02
title: "Forma del cascaron de la consola de operador"
map: capa-de-configuracion
label: wayfinder:prototype
status: closed
assignee: vzehnder
blocked_by: []
---

## Question

¿Que secciones fijas tiene la consola de operador, en que orden, y que ve el
operador al entrar?

El destino fija que la forma es la misma siempre y que el ingeniero solo
parametriza su contenido. Entonces esa forma hay que dibujarla una vez y
defenderla. La pregunta se responde haciendo un prototipo desechable con el que
reaccionar, no discutiendola en abstracto.

Preguntas que el prototipo debe forzar a contestar:

- ¿La consola es una sola pantalla con todo a la vista, o un flujo por pasos?
  El operador hace pocas cosas pero necesita entender que va a correr.
- ¿Que ve primero: los parametros, la tabla editable, o el resultado de la
  ultima corrida?
- ¿Como se presenta "que caso estoy corriendo" sin exponer el vocabulario
  interno (escenario, caso, variante, version)? ¿Que nombre le pone el
  ingeniero a eso?
- ¿Como elige el operador el rango de fechas, y como se le muestra que rango
  tiene datos disponibles?
- ¿Donde vive el boton de correr y que pasa mientras la corrida esta `queued` /
  `running`? El operador no deberia quedarse mirando una pantalla muerta.
- ¿Que ve el operador cuando la corrida falla, dado que el error real viene de
  Julia o de una validacion de cobertura?
- ¿Ve el historial de sus corridas anteriores? ¿Puede comparar dos?

Enlazar el prototipo desde este ticket como activo. No tocar `frontend/src`:
el prototipo es material de conversacion, no una primera version.

## Activos

- [Prototipo desechable de la consola de operador](../prototypes/consola-operador/README.md)
  — tres variantes navegables para la sesion de reaccion; no contiene una
  decision ni codigo de produccion.

## Resolucion

Decision aprobada en sesion de reaccion el 2026-08-11, a partir de la variante
**Mesa de trabajo** y una segunda iteracion del prototipo.

### Forma fija de la consola

La consola es **una sola pantalla de trabajo**, no un asistente por pasos ni
una portada centrada en la ultima corrida. Su orden fijo es:

1. Identidad publica del plan que se ejecutara.
2. Periodo y parametros expuestos.
3. Datos de entrada agrupados.
4. Revision y accion de ejecutar, siempre visibles en un panel lateral.
5. Historial de ejecuciones al final de la pantalla.

El operador entra directamente a esa mesa. No ve escenario, caso, variante,
binding, revision ni version inmutable. Ve un nombre y una descripcion publicos
definidos por el analista, junto con el periodo disponible, la ultima
actualizacion y quien preparo la configuracion.

### Periodo, parametros y datos

- El periodo se elige con fechas de inicio y termino sobre una visualizacion
  del rango que tiene datos disponibles; la consola confirma si la seleccion
  cabe dentro de ese rango.
- Los parametros habilitados aparecen antes de los datos y usan las etiquetas,
  unidades, defaults y rangos definidos por el analista.
- Las series se organizan en **grupos con pestañas**. El analista define los
  grupos, sus nombres, el orden y las series que contiene cada uno; el operador
  solo navega entre ellos.
- Cada grupo alterna entre **Tabla** y **Grafico**. Tabla es la vista editable y
  admite pegado desde Excel; Grafico es una lectura alternativa de las mismas
  series y el mismo periodo, sin edicion.
- La consola muestra cobertura del periodo y cantidad de series/grupos antes
  de permitir la ejecucion.

### Ejecucion, error e historial

- Un resumen lateral persistente muestra periodo, cobertura y parametros, y
  contiene la accion primaria de ejecutar.
- `queued` informa la posicion o espera y permite abandonar la pantalla;
  `running` muestra progreso y tiempo aproximado. El operador no necesita
  permanecer mirando una pantalla estatica.
- Un fallo se traduce primero a una explicacion accionable —por ejemplo, rango
  y serie con datos faltantes— con acceso directo a corregirlos. El detalle
  tecnico queda como accion secundaria.
- El historial reciente es parte de la pantalla y permite abrir resultados y
  seleccionar dos corridas para compararlas.

### Limites de esta decision

Esta resolucion fija la experiencia y la jerarquia, no los contratos internos.
El detalle del pegado y validacion pertenece a **Contrato de la tabla editable
y del pegado desde Excel**; la persistencia de grupos, etiquetas y orden a
**Modelo de datos de la configuracion por proyecto**; y su representacion para
el frontend a **Contrato del payload de las superficies configuradas**. No se
necesita un ticket nuevo: esas preguntas ya existen en el mapa.

## Adenda de cierre

La mesa de trabajo fue aprobada nuevamente por el usuario el 2026-08-11 a
nivel de estructura general. Se incorporan estas decisiones al cierre:

- los valores se leen desde la base de datos SQL y las ediciones se guardan en
  ella mediante una revision auditable;
- mientras existan cambios sin guardar o un guardado en curso, la ejecucion
  permanece deshabilitada;
- el operador puede elegir la **version nombrada del set de series** usada por
  cada señal y trabaja sobre su revision mas reciente. Esa eleccion no expone
  la version inmutable de la corrida ni permite ejecutar una revision historica
  arbitraria.

Los ajustes finos y los contratos de persistencia quedan en los tickets
**Donde aterriza la edicion de series del operador**, **Contrato de la tabla
editable y del pegado desde Excel**, **Modelo de datos de la configuracion por
proyecto** y **Contrato del payload de las superficies configuradas**.
