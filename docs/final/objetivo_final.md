# Objetivo Final: Interfaz Web De Optimizacion One-Bus Para Sistemas Hibridos

## 1. Vision

Construir una aplicacion web privada para que un analista pueda crear, editar,
versionar, ejecutar y publicar modelos de optimizacion de sistemas electricos
hibridos conectados a un unico nodo electrico.

El producto debe usar el motor de optimizacion Julia existente como nucleo
matematico. La aplicacion web no reemplaza ese motor: lo envuelve con una
interfaz de modelacion, persistencia, ejecucion automatica, visualizacion de
resultados y publicacion controlada para clientes.

El alcance electrico sigue siendo intencionalmente acotado:

- Un solo nodo, bus o punto de conexion comun.
- Sin flujo de red.
- Sin multiples barras fisicas.
- Sin lineas, impedancias, perdidas de red ni restricciones de transmision.

El objetivo no es construir un simulador electrico general. Es construir una
herramienta practica para optimizar recursos energeticos co-ubicados en un
mismo nodo.

## 2. Contexto Actual

El repositorio ya cuenta con dos iteraciones base:

- Iteracion 1: modelo Julia de arbitraje para un BESS individual, con carga,
  descarga, SOC, eficiencias, degradacion lineal, condicion terminal,
  anti-simultaneidad, outputs y reporte Plotly.
- Iteracion 2: modelo Julia one-bus para sistema hibrido, con contrato
  `system_case.json`, grafo logico validado, normalizacion, renovables, BESS,
  red, carga local, curtailment, limites de importacion/exportacion, CLI
  estable y outputs `dispatch.csv` y `asset_dispatch.csv`.

El objetivo final parte desde ese contrato tecnico, no desde cero.

## 3. Usuarios Objetivo

### Analista

El usuario principal inicial sera el analista. El analista debe poder:

- Crear y editar modelos.
- Cargar series de tiempo.
- Versionar escenarios.
- Ejecutar optimizaciones manuales.
- Programar corridas automaticas.
- Inspeccionar resultados.
- Crear dashboards y graficos internos.
- Publicar resultados seleccionados para clientes.

Inicialmente el analista puede ser el propio desarrollador del sistema.

### Cliente

El cliente sera inicialmente un usuario de solo lectura. Debe poder:

- Entrar a una vista web.
- Ver resultados publicados por el analista.
- Revisar dashboards y KPIs.
- Descargar archivos o reportes habilitados.

El cliente no debe editar modelos ni disparar corridas en la primera version.
La edicion por parte del cliente queda como extension futura.

## 4. Flujo Principal Del Producto

La aplicacion debe ordenar el trabajo alrededor del flujo:

```text
Proyecto
-> Escenario o modelo versionado
-> Caso de optimizacion one-bus
-> Corrida manual o programada
-> Artefactos de resultado
-> Dashboard interno
-> Publicacion read-only para cliente
```

Los archivos `system_case.json`, `dispatch.csv`, `asset_dispatch.csv`,
`summary.json`, `model_metadata.json` y artefactos equivalentes deben seguir
existiendo como salidas reproducibles y auditables, aunque la aplicacion agregue
una capa de base de datos y gestion web encima.

## 5. Componentes Del Modelo

La primera version completa del editor debe soportar los siguientes componentes
en un unico nodo:

- Punto de conexion comun, red o PCC.
- BESS.
- Solar.
- Eolica.
- Hidraulica con regulacion simple.
- Demanda local opcional.

El editor debe permitir agregar multiples activos de un mismo tipo cuando el
modelo Julia lo soporte o cuando el contrato pueda representarlo de manera
estable.

### BESS

Debe preservar la fisica ya implementada:

- Potencia maxima de carga y descarga.
- Energia minima y maxima.
- Energia inicial.
- Eficiencia de carga y descarga.
- Condicion terminal.
- Degradacion lineal por movimiento de SOC.
- Anti-simultaneidad opcional de carga y descarga.

### Renovables Solar Y Eolica

Solar y eolica deben modelarse como generacion renovable con disponibilidad
exogena por periodo:

- Potencia disponible.
- Potencia usada.
- Potencia vertida o curtailed.
- Penalizacion opcional por curtailment.

No se requiere modelar fisica interna de los generadores en la primera version.

### Hidraulica Con Regulacion

La hidraulica debe modelarse como un activo despachable con stock intertemporal,
similar en espiritu a una bateria, pero con entradas naturales.

Alcance inicial recomendado:

- Potencia maxima de generacion.
- Energia o volumen almacenado equivalente.
- Minimo y maximo de almacenamiento.
- Estado inicial.
- Afluentes por periodo.
- Vertimiento opcional.
- Costo o valor de agua opcional.
- Condicion terminal opcional.

Quedan fuera del primer alcance:

- Cascadas hidraulicas.
- Multiples embalses acoplados.
- Cotas.
- Curvas no lineales.
- Hidraulica de pasada detallada.
- Red hidraulica fisica.

### Red / PCC

La red debe representar la interaccion con el sistema externo:

- Importacion de energia.
- Exportacion de energia.
- Limite de importacion.
- Limite de exportacion.
- Anti-simultaneidad importacion/exportacion opcional.

La primera version interna puede seguir usando precio unico si eso acelera el
prototipo. Sin embargo, antes de considerar la version como lista para clientes,
debe soportar precios separados:

- Precio de compra/importacion.
- Precio de venta/exportacion.

Esto es necesario para casos tipo pyme, netmetering o esquemas regulados donde
comprar energia y vender excedentes no tienen el mismo valor economico.

## 6. Editor Web

El frontend inicial debe ser un editor estructurado, no un canvas libre.

La fuente de verdad debe estar en formularios, tablas y validaciones que generen
un caso compatible con el contrato del optimizador. Puede existir una vista
visual simple del nodo con sus componentes conectados, pero no debe ser la unica
forma de editar el modelo.

Secciones esperadas del editor:

- Datos generales del proyecto.
- Definicion del PCC.
- Lista de activos.
- Parametros por activo.
- Series temporales.
- Restricciones.
- Configuracion de solver.
- Validacion del caso.
- Vista previa del `system_case`.
- Historial de versiones del modelo.

## 7. Datos De Entrada

La primera version debe priorizar carga desde archivos:

- CSV.
- Excel.

Debe incluir:

- Previsualizacion tabular.
- Validacion de columnas.
- Validacion de timestamps.
- Validacion de duracion de periodos.
- Validacion de valores negativos o faltantes segun tipo de serie.
- Mapeo de columnas hacia activos.
- Edicion tabular basica.

Conectores automaticos a APIs de precios, mediciones, forecasts o bases de
datos externas quedan como extension futura.

## 8. Backend Y Ejecucion

El backend objetivo inicial debe ser Python/FastAPI, con workers que llamen al
CLI estable de Julia como proceso externo.

Responsabilidades del backend:

- Autenticacion.
- Roles y permisos.
- Gestion de proyectos.
- Persistencia de modelos y versiones.
- Almacenamiento de archivos de entrada.
- Generacion de `system_case.json`.
- Validacion previa.
- Encolamiento de corridas.
- Ejecucion del CLI Julia.
- Captura de stdout, stderr, logs y estados.
- Persistencia de artefactos de salida.
- Exposicion de resultados al frontend.
- Publicacion read-only para clientes.

El backend no debe reimplementar la formulacion de optimizacion. La logica
matematica debe permanecer en Julia.

## 9. Programacion Automatica

La primera version debe soportar programacion simple de corridas:

- Manual.
- Diaria.
- Semanal.
- Mensual.

Cada corrida debe tener estado observable:

- `queued`.
- `running`.
- `succeeded`.
- `failed`.

Tambien debe registrar:

- Fecha de creacion.
- Fecha de inicio.
- Fecha de termino.
- Modelo/version usada.
- Usuario o agenda que disparo la corrida.
- Ruta de artefactos.
- Logs.
- Error estructurado si falla.

Quedan fuera del primer alcance:

- Optimizacion en tiempo real.
- Streaming de resultados.
- Integracion SCADA.
- Control automatico de activos fisicos.
- Reoptimizacion continua.

## 10. Resultados Y Dashboards

La aplicacion debe incluir una herramienta interna para crear graficos y
dashboards por corrida.

La herramienta debe partir desde los outputs existentes:

- `dispatch.csv`.
- `asset_dispatch.csv`.
- `summary.json`.
- `model_metadata.json`.

Graficos base esperados:

- Precio de compra y precio de venta cuando existan.
- Importacion y exportacion de red.
- Generacion renovable usada y vertida.
- Carga y descarga BESS.
- SOC de baterias.
- Generacion hidraulica.
- Estado de embalse o energia hidraulica almacenada.
- Demanda local.
- Profit por periodo.
- Costos e ingresos acumulados.
- KPIs economicos por corrida.

El analista debe poder guardar configuraciones de dashboards como plantillas por
proyecto o por tipo de modelo. Una plantilla debe poder reutilizarse en nuevas
corridas y luego publicarse al cliente en modo lectura.

## 11. Vista Cliente

La vista cliente inicial debe ser read-only.

Debe permitir:

- Ver proyectos asignados.
- Ver corridas publicadas.
- Revisar dashboards publicados.
- Descargar reportes o archivos habilitados.
- Ver fecha, version y estado de cada corrida.

No debe permitir:

- Editar modelos.
- Cambiar parametros.
- Cargar archivos.
- Ejecutar optimizaciones.
- Modificar dashboards fuente.

## 12. Autenticacion Y Roles

La primera version debe incluir autenticacion simple y roles claros:

- `admin` o `analyst`: crea, edita, ejecuta, programa, revisa y publica.
- `client`: ve solo resultados publicados y descargas permitidas.

No se requiere un sistema complejo de permisos granulares en la primera version.

## 13. Arquitectura Objetivo Inicial

Arquitectura recomendada:

```text
Frontend web
-> FastAPI backend
-> Base de datos PostgreSQL
-> Worker de ejecucion
-> CLI Julia existente
-> Almacenamiento de artefactos
-> Dashboards y resultados publicados
```

Despliegue inicial recomendado:

- Privado.
- Simple.
- Dockerizado.
- En VPS, servidor o maquina controlada.
- Con PostgreSQL.
- Con carpeta persistente o bucket para artefactos.

Quedan fuera del primer despliegue:

- Alta disponibilidad.
- Kubernetes.
- Multi-tenant avanzado.
- Escalamiento horizontal.
- Operacion cloud compleja.

## 14. Fuera De Alcance De La Primera Version

La primera version no debe intentar resolver:

- Multiples nodos electricos.
- Flujo AC o DC.
- Lineas electricas.
- Perdidas de red.
- Restricciones de transmision.
- Unit commitment termico.
- Servicios complementarios.
- Modelos hidraulicos en cascada.
- Forecasting automatico.
- Integracion SCADA.
- Control automatico de activos reales.
- Edicion de modelos por clientes.
- APIs externas de datos.
- Alta disponibilidad.
- Escalamiento multiusuario avanzado.

## 15. Criterios De Aceptacion Del Objetivo Final

El objetivo se considera logrado cuando:

- Un analista puede crear un proyecto desde la web.
- Un analista puede crear y versionar un modelo one-bus.
- El modelo puede incluir PCC, BESS, solar, eolica, hidraulica simple y carga
  local.
- El analista puede cargar series temporales desde CSV o Excel.
- El sistema valida el caso antes de ejecutar.
- El backend genera un `system_case` compatible con el motor Julia.
- El backend ejecuta Julia mediante el CLI estable.
- La corrida produce artefactos reproducibles y trazables.
- El sistema guarda modelos, corridas, estados, logs y resultados.
- El analista puede ejecutar corridas manuales.
- El analista puede programar corridas diarias, semanales o mensuales.
- El sistema soporta precio de compra y precio de venta separados antes de la
  version cliente-ready.
- El analista puede crear dashboards internos desde los resultados.
- El analista puede guardar plantillas de graficos por proyecto.
- El analista puede publicar resultados seleccionados.
- Un cliente puede entrar a una vista read-only y ver resultados publicados.
- Un cliente puede descargar reportes o archivos habilitados.
- Los clientes no pueden editar modelos ni ejecutar optimizaciones.
- La aplicacion puede desplegarse de forma privada y reproducible con Docker.

## 16. Principio Rector

La prioridad es cerrar un flujo completo y confiable para el analista antes de
ampliar ambiciones de producto.

El orden estrategico es:

1. Mantener estable el motor Julia.
2. Construir el editor web estructurado.
3. Persistir proyectos, modelos y corridas.
4. Ejecutar optimizaciones desde backend.
5. Crear dashboards internos.
6. Publicar resultados read-only para clientes.
7. Agregar precios separados de compra y venta antes de la version cliente-ready.
8. Evaluar edicion por clientes y automatizaciones mas avanzadas como fases
   futuras.
