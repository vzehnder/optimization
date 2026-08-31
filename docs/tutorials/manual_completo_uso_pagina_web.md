# Manual completo de uso de BESS Workspace

> Tutorial operativo extremadamente detallado para una sesión guiada con un
> experto. Este documento describe la interfaz React vigente, sus rutas, roles,
> campos, decisiones y mecanismos de seguridad. Última revisión contra el código
> de la aplicación: 2026-08-30.

## 1. Propósito de este manual

Este manual permite que una persona experta en optimización, operación de
sistemas eléctricos o análisis energético pueda guiar a otra persona en el uso
de toda la aplicación web, aun si ninguna de las dos conoce previamente la
estructura interna de BESS Workspace.

Al terminar el recorrido principal se debería poder:

1. iniciar la aplicación y entrar con el rol correcto;
2. crear un proyecto y un escenario;
3. describir un sistema one-bus con red, BESS, demanda, renovables o hidro;
4. cargar, revisar, normalizar y versionar series de tiempo;
5. asociar cada señal requerida con un set del catálogo;
6. elegir un rango temporal compatible y ejecutar una optimización;
7. verificar el snapshot, la procedencia y los resultados de la corrida;
8. comparar dos corridas;
9. configurar y publicar resultados para un usuario externo;
10. preparar una consola operacional limitada;
11. construir, validar y promover un diagrama hidráulico v3;
12. reconocer bloqueos, datos desactualizados y errores comunes sin forzar el
    sistema.

El objetivo no es solamente aprender dónde hacer clic. La persona guiada debe
entender qué objeto modifica cada acción, qué queda inmutable y cómo comprobar
que una corrida utilizó exactamente los datos esperados.

## 2. Cómo usar este documento durante una sesión guiada

Se recomienda trabajar con dos personas:

- **persona guiada**: comparte pantalla y ejecuta las acciones;
- **experto guía**: explica el modelo, revisa unidades, cuestiona supuestos y
  comprueba la evidencia antes de autorizar el paso siguiente.

Para una primera sesión, usar un proyecto de prueba y datos no productivos. No
eliminar proyectos, versiones, usuarios ni accesos durante el recorrido. Las
acciones de borrado o revocación se explican, pero deben practicarse después en
un entorno desechable.

En cada hito, el experto debería pedir tres respuestas:

1. **Qué estoy modificando**: draft, set, variante, versión, corrida,
   publicación o consola.
2. **Qué evidencia veo**: estado, revisión, hash, rango, mensaje de validación
   o lineage.
3. **Qué podría invalidarse**: una variante, un derivado, una consola o la
   validación hidráulica.

### 2.1 Recorrido mínimo recomendado

Para conocer la aplicación sin abarcar todas las funciones avanzadas, seguir
este orden:

```text
Login
  -> Proyecto
    -> Escenario
      -> Draft
        -> Assets
        -> Fuente temporal
          -> Set del catálogo
      -> Variante de entrada
        -> Bindings
        -> Rango
          -> Corrida
            -> Resultados
            -> Publicación
```

Después del recorrido mínimo, practicar por separado:

- transformaciones y combinación de series;
- consola de operador;
- diagrama hidráulico v3;
- portal externo;
- schedules administrados.

## 3. Qué es BESS Workspace y qué no es

BESS Workspace es una aplicación privada para configurar y ejecutar modelos de
despacho económico de sistemas híbridos. La interfaz prepara un contrato
`system_case.json`, el backend lo valida y el motor Julia lo resuelve.

El modelo eléctrico base es **one-bus**:

- todos los recursos se conectan a un PCC común;
- no se modelan líneas eléctricas, impedancias, pérdidas ni flujo AC/DC entre
  buses;
- los edges del caso expresan conectividad lógica, no una red eléctrica
  detallada;
- el optimizador sí representa límites de red, importación/exportación, BESS,
  demanda, renovables, almacenamiento hidráulico y restricciones
  intertemporales dentro de los contratos soportados.

La aplicación no debe interpretarse como un simulador eléctrico general ni
como un SCADA. La consola operacional permite entradas controladas y corridas,
pero conserva límites, auditoría y validaciones de la plataforma.

### 3.1 Principio rector: fail-closed

Si la aplicación no puede demostrar que topología, parámetros, series y rango
son compatibles, bloquea la ejecución. No completa datos silenciosamente, no
reutiliza validaciones vencidas y no hace resampling implícito durante una
corrida.

Un botón deshabilitado suele ser una protección deliberada, no un error visual.
El procedimiento correcto es leer el mensaje o banner asociado y resolver su
causa.

## 4. Modelo mental de los objetos

```text
Proyecto
├── Escenario
│   ├── Draft estructurado mutable
│   ├── Diagrama hidráulico mutable, si corresponde
│   ├── Variante de entrada
│   │   └── Bindings a sets del catálogo
│   ├── Consola de operador
│   │   └── Variante propia clonada
│   ├── Versión inmutable
│   │   └── Corrida
│   │       ├── Resultados indexados
│   │       ├── Artefactos auditables
│   │       └── Publicación
│   └── Comparación de corridas
├── Catálogo de series de tiempo
│   ├── Set
│   ├── Revisión
│   └── Set derivado con lineage
├── Configuración del portal
├── Templates de dashboard
└── Capacidades de usuarios externos
```

| Objeto       | Función                                                     | ¿Se modifica?          | Identificador que conviene registrar        |
| ------------ | ----------------------------------------------------------- | ---------------------- | ------------------------------------------- |
| Proyecto     | Contenedor de escenarios, datos, portal y accesos.          | Sí.                    | Project ID y nombre.                        |
| Escenario    | Caso lógico que agrupa modelo, variantes, versiones y runs. | Sí.                    | Scenario ID y nombre.                       |
| Draft        | Documento de trabajo del editor estructurado.               | Sí.                    | Fecha de último guardado.                   |
| Set temporal | Horizonte y señales versionadas de un proyecto.             | Mediante revisiones.   | Set ID, versión, revisión y `content_hash`. |
| Variante     | Selección nombrada de sets para las señales de un caso.     | Sí.                    | Variant ID y nombre.                        |
| Versión      | Snapshot ejecutable congelado.                              | No.                    | Version ID y número.                        |
| Corrida      | Ejecución de una versión.                                   | Solo cambia su estado. | Run ID y estado terminal.                   |
| Publicación  | Selección controlada de resultados para el portal.          | Sí, según estado.      | Publication ID y estado.                    |
| Consola      | Superficie operacional limitada y auditable.                | Su configuración sí.   | Console ID, revisión y estado.              |

### 4.1 Diferencias que no se deben confundir

- **Versión de set** (`version_label`, por ejemplo `v1` o `dry_year`) es una
  identidad elegida por el analista.
- **Revisión de set** aumenta cuando se editan valores o se reemplaza el
  archivo de ese mismo set.
- **Versión de escenario** es un snapshot ejecutable e inmutable.
- **Run** es una ejecución concreta de una versión de escenario.
- **Draft guardado** no significa caso validado.
- **Caso validado** no significa versión promovida.
- **Versión promovida** no significa corrida ejecutada.
- **Run exitoso** no significa publicado.
- **Publicación creada** no significa visible: debe estar en estado
  `published` y el usuario externo debe tener capacidad `portal_view`.

## 5. Preparar y arrancar la aplicación

Esta sección es para una instalación local. Si el experto entrega una URL ya
desplegada, saltar a la sección 6.

### 5.1 Prerrequisitos

Comprobar:

- entorno virtual Python del repositorio;
- dependencias de `requirements.txt`;
- PostgreSQL accesible, salvo que se use una base SQLite aislada;
- Julia disponible en el PATH o indicada por `JULIA` si se ejecutarán corridas;
- bundle React compilado en `frontend/dist`, o servidor Vite en desarrollo.

El archivo `.env` de la raíz suele contener:

```text
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=energy_dispatch
DB_USER=energy_dispatch_user
DB_PASSWORD=<secreto local>
ARTIFACT_ROOT=<directorio de artefactos>
INPUT_SOURCE_ROOT=<directorio de fuentes>
JULIA=<ruta opcional al ejecutable>
```

No copiar contraseñas, tokens de conectores ni rutas privadas en este manual,
capturas o registros compartidos.

### 5.2 Arranque normal con el frontend compilado

Desde la raíz del repositorio:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd frontend
npm ci
npm run build
cd ..
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Abrir:

```text
http://127.0.0.1:8000/
```

El backend redirige a la aplicación React, cuyo prefijo canónico es
`/react`.

### 5.3 Arranque en modo desarrollo de frontend

En una terminal, iniciar el backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

En otra terminal:

```powershell
cd frontend
$env:BESS_API_ORIGIN = "http://127.0.0.1:8000"
npm run dev
```

Usar la URL indicada por Vite. El backend continúa siendo responsable de API,
autenticación, uploads, descargas y ejecución.

### 5.4 Pruebas de salud antes de la sesión

El experto debería confirmar:

1. la página responde y no queda en blanco;
2. el login carga;
3. PostgreSQL no muestra errores de conexión;
4. `ARTIFACT_ROOT` e `INPUT_SOURCE_ROOT` son escribibles;
5. Julia responde si se ejecutarán casos reales;
6. la hora y zona horaria del equipo son correctas.

La ruta **Sistema** muestra `Frontend React conectado al API FastAPI`. Es una
comprobación básica de integración, no una validación del solver ni de la base
de datos.

## 6. Primer acceso, login y roles

### 6.1 Crear el primer administrador

En una base sin usuarios, la aplicación muestra **Crear admin**.

1. Completar **Email**.
2. Completar **Nombre**.
3. Definir **Password**.
4. Presionar **Crear admin**.

El bootstrap se cierra después de crear la primera cuenta. Las cuentas
posteriores se crean desde **Admin**.

### 6.2 Iniciar y cerrar sesión

En **Iniciar sesión**:

1. escribir email;
2. escribir password;
3. presionar **Entrar**.

La cabecera muestra nombre o email, un badge con el rol y el botón **Salir**.
Usar **Salir** al terminar; no basta con cerrar la pestaña en un equipo
compartido.

### 6.3 Roles vigentes

| Rol        | Superficie         | Funciones principales                                                                                            |
| ---------- | ------------------ | ---------------------------------------------------------------------------------------------------------------- |
| `admin`    | Workspace interno. | Todo el trabajo analítico, usuarios, capacidades externas, schedules y migraciones administrativas.              |
| `analyst`  | Workspace interno. | Proyectos, escenarios, drafts, catálogo, variantes, runs, dashboards, publicaciones y configuración de consolas. |
| `external` | Portal o consola.  | Solo lo permitido por `portal_view` y/o `operate` para proyectos asignados.                                      |

El nombre de rol vigente es `external`. `client` es una denominación legado y
no debe seleccionarse al crear una cuenta nueva. Si la interfaz llegara a
mostrar una opción `client`, elegir `external`; el backend actual acepta
`admin`, `analyst` y `external`.

### 6.4 Capacidades de un usuario externo

Las capacidades se asignan por proyecto:

- `portal_view`: permite ver publicaciones activas del proyecto;
- `operate`: permite usar consolas activas del proyecto.

Una misma cuenta puede recibir ambas. Cuando `operate` está habilitado, la
página de aterrizaje favorece la consola: si existe una sola consola visible,
puede abrirla directamente; con cero o varias, abre la lista de consolas. El
portal sigue en `/react/client` si también tiene `portal_view`.

## 7. Mapa de navegación

Las rutas se indican para diagnóstico y para que el experto pueda reconocer la
ubicación. Es preferible navegar mediante enlaces y breadcrumbs.

| Pantalla                   | Ruta React                                                        |
| -------------------------- | ----------------------------------------------------------------- |
| Inicio analista            | `/react/projects`                                                 |
| Proyecto                   | `/react/projects/{projectId}`                                     |
| Catálogo temporal          | `/react/projects/{projectId}/time-series-sets`                    |
| Detalle de set             | `/react/projects/{projectId}/time-series-sets/{setId}`            |
| Set hidráulico legado      | `/react/projects/{projectId}/time-series-sets/hydraulic/{setId}`  |
| Escenario                  | `/react/scenarios/{scenarioId}`                                   |
| Draft                      | `/react/scenarios/{scenarioId}/draft`                             |
| Diagrama hidráulico        | `/react/scenarios/{scenarioId}/hydraulic-diagram`                 |
| Configurar consola         | `/react/scenarios/{scenarioId}/consoles/{consoleId}`              |
| Comparar runs              | `/react/scenarios/{scenarioId}/runs/compare`                      |
| Versión                    | `/react/scenario-versions/{versionId}`                            |
| Run                        | `/react/runs/{runId}`                                             |
| Preview de publicación     | `/react/publications/{publicationId}/preview`                     |
| Administración             | `/react/admin/users`                                              |
| Lista de consolas externas | `/react/console`                                                  |
| Consola externa            | `/react/console/{consoleId}`                                      |
| Portal externo             | `/react/client`                                                   |
| Proyecto en portal         | `/react/client/projects/{projectId}`                              |
| Publicación en portal      | `/react/client/projects/{projectId}/publications/{publicationId}` |

La navegación interna principal muestra **Analista**, **Admin** solo para el
administrador, y **Sistema**.

## 8. Definir el ejercicio antes de usar la web

Antes de crear objetos, el experto debería preparar una hoja de control:

| Decisión          | Ejemplo                                       |
| ----------------- | --------------------------------------------- |
| Objetivo del caso | Arbitraje de BESS con demanda y solar.        |
| Horizonte         | 2026-01-01 00:00 a 2026-01-02 00:00, Chile.   |
| Resolución        | 1 hora.                                       |
| Zona horaria      | `America/Santiago`.                           |
| Precio            | Único, o importación y exportación separados. |
| Assets            | `bess_1`, `load_1`, `solar_1`.                |
| Unidades          | MW, MWh, USD/MWh; hidro en m3/s y hm3.        |
| Caso base         | Variante `Default`.                           |
| Sensibilidad      | Variante `Precio alto`.                       |
| Evidencia         | IDs, revisiones, hashes, versión y Run ID.    |

Esta preparación evita construir el draft primero y descubrir después que los
nombres de activos o columnas no permiten asociar las series.

## 9. Crear un proyecto

1. Entrar en **Analista**.
2. Localizar **Proyectos activos** y **Nuevo proyecto**.
3. En **Nombre del proyecto**, usar un nombre inequívoco, por ejemplo
   `Tutorial BESS 2026-08`.
4. En **Descripción del proyecto**, escribir propósito, propietario y carácter
   de prueba o producción.
5. Presionar **Crear proyecto**.
6. Abrir el proyecto desde la lista.

La tarjeta del proyecto tiene un menú de acciones con **Eliminar proyecto**.
Esa acción borra también escenarios, versiones, corridas, series y
publicaciones, y no se puede deshacer desde la interfaz. No usarla como forma de
"limpiar" un caso; crear otro proyecto de prueba es más seguro.

### 9.1 Qué contiene la pantalla del proyecto

La pantalla del proyecto reúne:

- **Escenarios** y el formulario **Nuevo escenario**;
- enlace **Ver catálogo de series de tiempo**;
- **Capacidades externas**, solo para admin;
- **Portal del cliente**;
- **Dashboard templates**.

No es necesario configurar portal y dashboards antes de modelar. Para el flujo
principal, crear primero escenario, datos y corrida; preparar la publicación al
final.

## 10. Crear un escenario

1. En **Nuevo escenario**, escribir **Nombre del escenario**.
2. Añadir **Descripción del escenario** con la hipótesis que representa.
3. Presionar **Crear escenario**.
4. La aplicación navega al detalle del escenario.

Usar un escenario distinto cuando cambia la topología o la lógica del caso.
Usar variantes de entrada cuando solo cambian las fuentes de datos o una
sensibilidad temporal.

La pantalla del escenario contiene, en este orden aproximado:

1. **Abrir draft**;
2. **Variante de entrada**;
3. **Consolas de operador**;
4. **Versiones inmutables**;
5. **Versión experta**;
6. **Corridas** y **Comparar corridas**.

## 11. Crear y editar el draft estructurado

Presionar **Abrir draft**. Si el escenario aún no tiene draft, la pantalla
ofrece crear el documento inicial. El editor muestra estado, fecha del último
guardado y **Guardar draft**.

### 11.1 Estados de edición

- **saved** o equivalente: el documento visible coincide con lo persistido;
- cambios sin guardar: se modificó al menos un campo;
- guardando: la petición está en curso;
- error: revisar el mensaje y los campos marcados.

Si se intenta navegar con cambios sin guardar aparece **Cambios sin guardar**:

- **Seguir editando** conserva la pantalla;
- **Descartar cambios** navega sin guardar.

Guardar el draft antes de subir fuentes, cambiar de pantalla, abrir el diagrama
hidráulico, validar o promover.

### 11.2 Sección Caso

| Campo               | Uso                              | Recomendación                                                                         |
| ------------------- | -------------------------------- | ------------------------------------------------------------------------------------- |
| **Nombre del caso** | Nombre incluido en el contrato.  | Estable y descriptivo; no usar espacios ambiguos si también se consumirá por scripts. |
| **Draft schema**    | Versión del documento de editor. | Mantener `bess_editor_draft.v1`; no experimentar con este valor.                      |
| **Descripción**     | Contexto humano.                 | Registrar objetivo, fecha de datos y supuestos principales.                           |

### 11.3 Sección Graph, grid y solver

| Campo                                      | Significado                                    | Control experto                                                |
| ------------------------------------------ | ---------------------------------------------- | -------------------------------------------------------------- |
| **PCC ID**                                 | Identificador del bus o punto común.           | Debe ser único y estable, por ejemplo `bus_1`.                 |
| **PCC type**                               | `bus` o `pcc`.                                 | Elegir según convención del caso; no agrega una red multi-bus. |
| **Grid ID**                                | Identificador de la conexión a red.            | Por ejemplo `grid_1`.                                          |
| **Maximum import (MW)**                    | Potencia máxima comprada a red.                | Número no negativo y coherente con el sistema.                 |
| **Maximum export (MW)**                    | Potencia máxima inyectada.                     | Número no negativo y coherente con el PCC.                     |
| **Solver**                                 | Solver solicitado.                             | Mantener `HiGHS` salvo diseño validado.                        |
| **Prevent simultaneous import and export** | Evita importar y exportar en el mismo periodo. | Normalmente activado. Puede introducir variables binarias.     |
| **Solver options (JSON)**                  | Opciones avanzadas.                            | Debe ser JSON válido; dejar `{}` si no se necesitan.           |

El experto debe comprobar si el precio será único
`price_usd_per_mwh` o separado en `import_price_usd_per_mwh` y
`export_price_usd_per_mwh`. La elección afecta las señales requeridas.

### 11.4 Agregar assets

La sección **Assets** ofrece como máximo una tarjeta inicial por tipo mediante:

- **Agregar BESS**;
- **Agregar load**;
- **Agregar renewable**;
- **Agregar hydro**.

Cada asset tiene una acción para quitarlo con confirmación. Quitar un asset
puede cambiar las señales requeridas, dejar variantes desactualizadas y bloquear
consolas activas que dependían de sus campos.

#### 11.4.1 BESS

| Campo                                         | Unidad o valores                        | Interpretación                                                 |
| --------------------------------------------- | --------------------------------------- | -------------------------------------------------------------- |
| **BESS asset ID**                             | texto                                   | Identidad usada por series y resultados, por ejemplo `bess_1`. |
| **Maximum charge**                            | MW                                      | Límite de carga.                                               |
| **Maximum discharge**                         | MW                                      | Límite de descarga.                                            |
| **Minimum energy**                            | MWh                                     | Piso de estado de energía.                                     |
| **Maximum energy**                            | MWh                                     | Capacidad superior.                                            |
| **Initial energy**                            | MWh                                     | Estado al comienzo del horizonte.                              |
| **Charge efficiency**                         | fracción                                | Normalmente entre 0 y 1.                                       |
| **Discharge efficiency**                      | fracción                                | Normalmente entre 0 y 1.                                       |
| **Degradation cost**                          | USD/MWh                                 | Costo lineal asociado al movimiento de energía/SOC.            |
| **Terminal condition**                        | `none`, `equal_initial`, `min_terminal` | Condición al final del horizonte.                              |
| **Minimum terminal energy**                   | MWh                                     | Se usa con `min_terminal`.                                     |
| **Prevent simultaneous charge and discharge** | checkbox                                | Evita carga y descarga simultáneas.                            |
| **Apply linear degradation**                  | checkbox                                | Activa el término de degradación configurado.                  |

Comprobar siempre:

```text
energy_min <= initial_energy <= energy_max
0 < charge_efficiency <= 1
0 < discharge_efficiency <= 1
```

#### 11.4.2 Renewable

| Campo                             | Uso                                                                            |
| --------------------------------- | ------------------------------------------------------------------------------ |
| **Renewable asset ID**            | Identificador que debe coincidir con la entidad de su señal de disponibilidad. |
| **Technology**                    | `solar` o `wind`; principalmente clasificación visible.                        |
| **Curtailment penalty (USD/MWh)** | Penalización por energía disponible no utilizada.                              |

La potencia disponible no se escribe como parámetro fijo: se suministra como
serie `renewable_available_power_mw` para la entidad correspondiente.

#### 11.4.3 Load

El campo principal es **Load asset ID**. La demanda se suministra mediante la
serie `load_demand_mw` vinculada a ese ID.

#### 11.4.4 Hydro simple v2

| Campo                                   | Unidad o valores                        |
| --------------------------------------- | --------------------------------------- |
| **Hydro asset ID**                      | texto                                   |
| **Minimum / Maximum / Initial storage** | hm3                                     |
| **Generation mode**                     | `linear` o `piecewise_linear`           |
| **Power per flow**                      | MW por m3/s, solo modo lineal           |
| **Minimum / Maximum turbine flow**      | m3/s                                    |
| **Maximum power**                       | MW                                      |
| **Minimum release**                     | m3/s                                    |
| **Spill penalty**                       | USD/hm3                                 |
| **Terminal condition**                  | `none`, `equal_initial`, `min_terminal` |
| **Minimum terminal storage**            | hm3                                     |
| **Terminal water value**                | USD/hm3                                 |
| **Generation curve (JSON)**             | puntos caudal-potencia                  |
| **Reservoir curve (JSON)**              | puntos almacenamiento-cota              |

En modo lineal se requiere una relación potencia/caudal válida. En modo
piecewise, la curva debe tener caudales estrictamente crecientes. La curva de
embalse debe tener almacenamientos estrictamente crecientes y cotas no
decrecientes.

Para cascadas, nodos, tramos o varias unidades, usar el diagrama hidráulico v3
de la sección 23, no intentar representar esa topología con un asset v2 simple.

### 11.5 Guardar el draft

1. Revisar campos obligatorios y JSON avanzado.
2. Presionar **Guardar draft**.
3. Esperar el estado guardado.
4. Si aparece **Corrige los campos marcados antes de guardar**, corregir cada
   campo; no recargar la página como primera respuesta.
5. Si el mensaje indica consolas activas bloqueadas por el cambio, anotar sus
   nombres y revisar la sección 27 antes de volver a activarlas.

Guardar no crea una versión ni ejecuta Julia. Es solo la persistencia del
documento mutable.

## 12. Preparar las series de tiempo fuera de la web

La preparación del archivo suele determinar si el resto del flujo será simple
o frustrante. Antes del upload, revisar la estructura con el experto.

### 12.1 Reglas de tiempo

- timestamps en orden ascendente;
- timestamps sin duplicados;
- zona horaria conocida y consistente;
- duración positiva en horas;
- periodos sin solapes;
- cobertura continua para el rango que se quiere ejecutar;
- la semántica de rango es `[inicio, fin)`: incluye el inicio y excluye el fin.

Ejemplo horario de 24 periodos:

```text
inicio = 2026-01-01T00:00:00-03:00
fin    = 2026-01-02T00:00:00-03:00
```

El último periodo comienza a las 23:00 y termina a las 00:00 del día siguiente.

### 12.2 Reglas de archivo

Para CSV:

- usar UTF-8;
- una sola fila de encabezados;
- nombres de columna únicos y no vacíos;
- separador y decimales consistentes;
- no mezclar texto con valores numéricos en columnas físicas.

Para XLSX:

- elegir la hoja correcta;
- evitar celdas combinadas, tablas complejas, fórmulas, encabezados vacíos,
  rangos con nombre y formatos que oculten el valor real;
- preferir una tabla rectangular simple.

### 12.3 Unidades canónicas frecuentes

| Señal                                     | Unidad  | Dominio esperado                  |
| ----------------------------------------- | ------- | --------------------------------- |
| `price_usd_per_mwh`                       | USD/MWh | Puede admitir valores negativos.  |
| `import_price_usd_per_mwh`                | USD/MWh | Según mercado; revisar negativos. |
| `export_price_usd_per_mwh`                | USD/MWh | Según mercado; revisar negativos. |
| `load_demand_mw`                          | MW      | No negativa.                      |
| `renewable_available_power_mw`            | MW      | No negativa.                      |
| `hydro_inflow_m3s` / `natural_inflow_m3s` | m3/s    | No negativa.                      |
| `minimum_flow_m3s`                        | m3/s    | No negativa.                      |
| `duration_hours`                          | h       | Estrictamente positiva.           |

La clave exacta disponible se toma del catálogo canónico que muestra la
interfaz. No inventar nombres parecidos.

### 12.4 Sets anchos frente a sets por entidad

Un set puede contener varias señales distintas con el mismo horizonte. Sin
embargo, cuando una familia se repite para varias entidades —por ejemplo dos
cargas con `load_demand_mw`— conviene que cada señal conserve una entidad
inequívoca. Si la pantalla de importación no permite expresar esa relación de
forma segura, separar los datos en sets distintos.

Convención recomendada:

```text
<proyecto>__<fuente>__<entidad o alcance>__<resolucion>
```

Ejemplos:

```text
tutorial__mercado__precios__1h
tutorial__medidor__load_1__1h
tutorial__pronostico__solar_1__1h
```

## 13. Subir una fuente desde el draft

En el draft, la sección **Time-series metadata** contiene el workflow de
fuentes.

1. Guardar el draft.
2. En **Source file**, elegir CSV o XLSX.
3. Iniciar el upload.
4. Si el XLSX tiene varias hojas, elegir **Sheet**.
5. Revisar **Time-series source**:
   - archivo;
   - tipo;
   - Source ID;
   - hoja seleccionada;
   - columnas detectadas;
   - preview de filas.
6. Corregir el archivo si el encabezado o preview no coincide con lo esperado.

La aplicación conserva el archivo bajo `INPUT_SOURCE_ROOT` y expone
identificadores seguros. El usuario no debería depender de una ruta absoluta
local para reproducir una corrida.

### 13.1 Editar filas antes de importar

La sección **Editable rows** permite corregir celdas de la fuente.

1. Localizar fila y columna.
2. Editar únicamente los valores necesarios.
3. Presionar **Save rows**.
4. Esperar **Rows saved**.
5. Revisar nuevamente validación y preview.

La interfaz puede mostrar solo las primeras filas de archivos grandes. Eso no
implica que el resto se haya eliminado. Para cambios masivos, corregir y volver
a subir el archivo suele ser más seguro que editar muchas celdas manualmente.

## 14. Importar la fuente al catálogo

Existen dos caminos. Para trabajo nuevo, usar **Import mapped columns to
catalog**. El camino **Column mapping** + **Extract legacy series to catalog**
existe para compatibilidad con drafts antiguos.

### 14.1 Camino recomendado: mapeo directo al catálogo

Completar:

| Campo                        | Qué ingresar                                    |
| ---------------------------- | ----------------------------------------------- |
| **Catalog set name**         | Nombre estable del set.                         |
| **Catalog version label**    | Por ejemplo `v1`, `forecast_20260830` o `base`. |
| **Catalog data kind**        | Clase de dato ofrecida por la interfaz.         |
| **Catalog timezone**         | Zona IANA, por ejemplo `America/Santiago`.      |
| **Catalog timestamp column** | Columna que contiene el inicio del periodo.     |
| **Catalog duration column**  | Columna de duración en horas.                   |

En **Signal mappings**, cada fila relaciona:

1. **Mapped source column**: la columna del archivo;
2. **Canonical signal**: la clave aceptada por la aplicación;
3. **Source unit**: unidad real de la columna.

Agregar o quitar mappings según corresponda. No mapear la misma columna a dos
conceptos diferentes sin una razón validada. La unidad declarada debe coincidir
con la magnitud, no solo con el texto del encabezado.

Cuando todo esté completo:

1. ejecutar la importación;
2. abrir el set creado;
3. anotar Set ID, nombre, versión, revisión y hash;
4. comprobar horizonte, señales, entidad, valores y fuente.

### 14.2 Camino legado

En **Column mapping** se asignan:

- **Timestamp column**;
- **Duration column**;
- **Legacy price column** o precios de importación/exportación;
- disponibilidad por renewable;
- demanda por load;
- afluente por hydro.

Presionar **Save mapping** y revisar **Valid mapped rows**. Luego usar
**Extract legacy series to catalog**, completar nombre, versión, clase y zona
horaria, y ejecutar la extracción.

La extracción reutiliza las filas ya validadas del draft. No modifica el draft
y registra procedencia `legacy_draft_extraction` en el set resultante.

### 14.3 Cuándo detenerse

No seguir al binding si ocurre cualquiera de estas situaciones:

- horizonte vacío;
- número de periodos inesperado;
- timezone incorrecta;
- señal canónica equivocada;
- entidad incorrecta o ausente;
- unidades incompatibles;
- valores no numéricos;
- timestamps duplicados, desordenados o con huecos no intencionales.

## 15. Usar el catálogo de series de tiempo

Desde el proyecto, abrir **Ver catálogo de series de tiempo**. Cada set muestra:

- nombre y `version_label`;
- `data_kind` y estado;
- timezone;
- revisión actual;
- cantidad de señales y periodos;
- `content_hash`;
- badge **Desactualizado** si es derivado y cambió su origen;
- datos de programa oficial, si corresponde.

### 15.1 Revisar el detalle de un set

La pantalla del set contiene:

1. **Revision** y `content_hash`;
2. **Programa oficial**, si existe;
3. **Origen legacy**, si fue extraído o migrado;
4. **Lineage de transformación**, si es derivado;
5. **Horizonte**;
6. **Señales** con unidad y entidad;
7. **Origen** del archivo o conector;
8. **Valores**;
9. **Reemplazar con nuevo archivo**;
10. **Transformaciones**;
11. **Historial de revisiones**.

El experto debe seleccionar algunos periodos —primero, intermedio y último— y
compararlos con la fuente original.

### 15.2 Editar valores manualmente

1. Cambiar una o más celdas en **Valores**.
2. Escribir **Resumen del cambio**, aunque sea opcional; por ejemplo
   `Corrección medidor 2026-01-01 03:00 aprobada por XX`.
3. Guardar los cambios.
4. Confirmar que aumenta la revisión y cambia el hash.
5. Revisar **Historial de revisiones**.

La revisión anterior permanece en el historial. Las corridas históricas no se
re-escriben.

### 15.3 Reemplazar el archivo de un set

Usar **Reemplazar con nuevo archivo** cuando cambia una parte importante del
horizonte.

1. Seleccionar **Archivo de reemplazo**.
2. Elegir hoja si es XLSX.
3. Confirmar `data_kind`, timezone, timestamp y duración.
4. Revisar todos los mappings de señales y unidades.
5. Escribir **Resumen del reemplazo**.
6. Ejecutar el reemplazo.
7. Confirmar nueva revisión, hash, horizonte y valores.

El nombre y la identidad del set se conservan; el reemplazo crea una revisión,
no un set paralelo.

## 16. Transformar y combinar series

Las transformaciones son allowlisted: la interfaz no ejecuta scripts libres.
Cada operación crea un set derivado y conserva lineage de inputs, revisiones,
hashes, parámetros y versión de implementación.

### 16.1 `scale_signal`

1. Elegir **Tipo de transformación** `scale_signal`.
2. Elegir **Señal a escalar**.
3. Ingresar **Factor de escala**.
4. Opcionalmente definir nombre y versión del output.
5. Presionar **Aplicar scale_signal**.

Ejemplo: factor `1.10` representa +10 %. El experto debe comprobar que la
unidad no cambia y que solo se transforma la señal elegida.

### 16.2 `resample`

1. Elegir `resample`.
2. Definir **Resolución objetivo (horas)**.
3. Seleccionar método por señal, normalmente `mean` o `sum`.
4. Crear el derivado.

Elegir `mean` para magnitudes medias como potencia o precio cuando esa semántica
sea correcta. Elegir `sum` solo cuando los valores representen una cantidad
aditiva. El upsampling se rechaza; no se inventan periodos más finos.

### 16.3 `interpolate_gaps`

1. Elegir `interpolate_gaps`.
2. Mantener o seleccionar método `linear`.
3. Definir **Gap máximo a rellenar (horas)**.
4. Crear el derivado.

Solo deben interpolarse huecos pequeños y justificables. Las filas rellenadas
quedan identificadas y el lineage conserva la operación.

### 16.4 Combinar señales

El panel **Combinar series** aparece cuando existen al menos dos sets.

1. Seleccionar el primer **Set de entrada** y marcar señales.
2. Seleccionar el segundo set y marcar señales.
3. Agregar más inputs si hace falta.
4. Definir nombre y versión de salida opcionales.
5. Presionar **Aplicar combine_signals**.

Los inputs deben tener horizonte y resolución compatibles. Los sets origen no
se modifican.

### 16.5 Derivado desactualizado

Si cambia la revisión de un input, el derivado muestra **Set derivado
desactualizado**.

1. Leer cada motivo.
2. Confirmar con el experto que la receta sigue siendo válida.
3. Presionar **Regenerar set derivado**.
4. Confirmar nueva revisión/hash.
5. Revalidar las variantes que usen ese derivado.

No vincular deliberadamente un derivado desactualizado para "ver si corre".

## 17. Ingesta mediante conector HTTP JSON

En el catálogo, **Ingesta de pronóstico (conector externo)** permite incorporar
una API JSON.

Completar:

- **URL del conector**;
- **Ruta de registros en el JSON**, si los records no están en la raíz;
- **Token Bearer**, si corresponde;
- **Nombre del set**;
- **Versión**;
- **Zona horaria**;
- **Columna de timestamp**;
- **Columna de duración**;
- una o más parejas **Columna de origen** / **Señal canónica**.

Si se marca **Programa oficial** se requieren además:

- emisor;
- fecha de emisión ISO-8601 con zona;
- vigencia desde;
- vigencia hasta.

Presionar **Ingerir desde conector**. El resultado informa uno de estos casos:

- set creado;
- datos sin cambios y revisión reutilizada;
- datos cambiados y nueva revisión creada.

El token no debe aparecer en screenshots ni logs compartidos. Validar el
destino, cantidad de registros y `fetched_at` antes de usar el set.

## 18. Generar, validar y promover el caso del draft

Al final del draft está **Caso generado**.

### 18.1 Generar preview

1. Guardar el draft.
2. Presionar **Generar preview**.
3. Revisar el textarea read-only **Generated system_case**.
4. Comprobar schema, IDs, límites, edges y señales.

El preview es evidencia de lo que se generaría; todavía no es una versión
inmutable.

### 18.2 Validar con Julia

1. Con el draft guardado, presionar **Validar con Julia**.
2. Esperar la validación.
3. Revisar fase, status y mensaje.
4. Confirmar **Validación vigente**.

Si se cambia el draft después, aparece **Validación stale; valida de nuevo antes
de promover**. Es obligatorio repetir la validación.

### 18.3 Promover versión

El botón **Promover versión** solo se habilita con una validación actual y
exitosa.

1. Presionarlo una sola vez.
2. Volver al escenario.
3. Comprobar la nueva entrada en **Versiones inmutables**.
4. Abrirla y revisar Metadata, Procedencia, Validation payload, Generation
   metadata y Snapshot ejecutable.

No editar el snapshot. Cualquier cambio requiere volver al draft y crear una
nueva versión.

## 19. Variantes de entrada y bindings

La pantalla del escenario contiene **Variante de entrada: {nombre}**.

### 19.1 Elegir o clonar una variante

- Todo caso tiene una variante default.
- **Variante activa** determina qué bindings se editan y ejecutan.
- Para una sensibilidad, escribir **Nombre nueva variante** y presionar
  **Clonar variante activa**.

La clonación hereda los bindings. Cambiar la copia no debe alterar la variante
de origen.

### 19.2 Leer las señales requeridas

La lista **Señales requeridas** se deriva de la topología y parámetros del caso.
Cada fila muestra entidad, clave y si está vinculada.

Ejemplos:

```text
price_usd_per_mwh (grid_1): falta vincular
load_demand_mw (load_1): vinculada (set #12)
renewable_available_power_mw (solar_1): vinculada (set #13)
```

Para cada selector:

1. identificar la señal y entidad;
2. elegir un set que realmente contenga esa combinación;
3. comprobar unidad;
4. comprobar timezone, horizonte y resolución;
5. no seleccionar un set solo porque su nombre parece correcto.

La web muestra todos los sets del proyecto en el selector; la responsabilidad
de verificar semántica sigue siendo del analista y del experto.

### 19.3 Elegir el rango

Completar **Inicio de rango** y **Fin de rango** en ISO-8601 con offset. La UI
propone el horizonte del primer set seleccionado, pero ese valor debe revisarse.

La validación comprueba:

- inicio anterior a fin;
- cobertura completa en todos los sets;
- timestamps compatibles;
- resolución consistente;
- ausencia de huecos o solapes incompatibles.

Esperar el mensaje **Rango válido para correr** o equivalente. Si hay distintas
resoluciones, crear previamente un set resampleado; la corrida no transforma
datos.

### 19.4 Variante desactualizada

Un banner **Variante desactualizada: revalida antes de correr** puede aparecer
por:

- nueva revisión de un set vinculado;
- cambio de topología;
- cambio de parámetros;
- derivado stale;
- cambio en dependencias del caso.

Procedimiento:

1. leer **Motivos de desactualización**;
2. corregir orígenes o modelo;
3. regenerar derivados si corresponde;
4. confirmar rango;
5. presionar **Revalidar variante**;
6. esperar que desaparezca el bloqueo.

Revalidar significa aceptar conscientemente la nueva combinación. No es un
botón para ocultar el aviso.

## 20. Ejecutar una corrida desde una variante

Cuando todos los bindings están completos, el rango es válido y la variante no
está stale, se habilita **Vincular y correr variante**.

Al presionarlo, la aplicación:

1. persiste los bindings seleccionados;
2. materializa el rango exacto;
3. congela topología, parámetros, variante y hashes de series;
4. crea una versión inmutable;
5. crea el run;
6. lo encola;
7. navega al detalle del run.

No hacer doble clic. Esperar la navegación o el mensaje de error.

### 20.1 Estados del run

| Estado backend | Significado                                          |
| -------------- | ---------------------------------------------------- |
| `queued`       | Creado y esperando worker.                           |
| `running`      | Julia está ejecutándose.                             |
| `succeeded`    | Finalizó correctamente y se registraron resultados.  |
| `failed`       | Falló validación, ejecución o persistencia asociada. |

La vista refresca automáticamente mientras no hay estado terminal.

### 20.2 Verificar el detalle del run

Revisar en este orden:

1. **Run state**: estado, timestamps, exit code y trigger.
2. **Lineage**: proyecto, escenario y versión.
3. **Procedencia**: hashes o información de generación.
4. **Series de entrada**: set, versión, revisión y hash por señal.
5. **Snapshot técnico**: contrato congelado.
6. **Run Results**: summary, tablas y charts.
7. **Publication Drafts**, si el run fue exitoso.
8. **Artifacts**.

El experto debe comparar al menos un hash de **Series de entrada** con el set
del catálogo y confirmar que el rango del snapshot es el solicitado.

### 20.3 Interpretar resultados

Los resultados pueden incluir:

- summary y KPIs del solver;
- tabla system dispatch;
- tabla asset dispatch;
- gráficos de precio;
- importación/exportación;
- renovable utilizada/vertida;
- carga, descarga y energía del BESS;
- potencia, caudales, almacenamiento y cota hidráulica;
- profit por periodo.

Los gráficos no disponibles aparecen como tales cuando faltan columnas. Eso no
convierte automáticamente el run en fallido; puede ser un caso legado o un
dashboard que pide una señal no producida.

Validaciones mínimas del experto:

- `solver_status` y `termination_status` esperados;
- objective con signo y magnitud plausibles;
- balance energético razonable en tres periodos;
- límites de potencia respetados;
- SOC/almacenamiento dentro de límites;
- condición terminal satisfecha;
- número de filas igual al horizonte esperado.

### 20.4 Artefactos

Según el caso pueden aparecer:

- `summary.json`;
- `dispatch.csv`;
- `asset_dispatch.csv`;
- `model_metadata.json`;
- `system_case_resolved.json`;
- input snapshot;
- stdout y stderr.

Descargar desde los enlaces registrados. No construir rutas de archivo
manualmente. Guardar junto con la evidencia de la sesión el Run ID y los hashes,
no solo un CSV suelto.

### 20.5 Diagnosticar un run fallido

La sección de fallo puede mostrar:

- error estructurado;
- stdout;
- stderr;
- referencia técnica.

Clasificar antes de actuar:

1. **input**: datos o contrato inválido;
2. **model**: infactibilidad o restricciones incoherentes;
3. **runtime**: Julia, paquetes, permisos o proceso;
4. **persistence**: artefactos o base de datos;
5. **UI/network**: la vista no pudo refrescar aunque el worker siga.

No editar una versión histórica. Corregir draft o series, revalidar y generar
otra versión/run.

## 21. Versiones expertas y ejecución manual

El escenario ofrece **Versión experta** como camino avanzado.

### 21.1 Pegar JSON

1. Pegar un `system_case JSON` completo.
2. Presionar **Crear versión**.
3. Revisar el mensaje de versión creada.
4. Abrir la versión.

### 21.2 Subir JSON

1. Elegir **Subir system_case JSON**.
2. Seleccionar un `.json` UTF-8.
3. Presionar **Subir versión**.

La validación se realiza antes de guardar. Este camino no debe usarse para
evitar corregir el editor: es apropiado para contratos generados externamente o
reproducciones controladas.

### 21.3 Lanzar run desde una versión

En el detalle de versión, la sección **Manual run** ofrece **Lanzar run**. Esta
acción ejecuta exactamente el snapshot inmutable abierto. Es diferente de
**Vincular y correr variante**, que primero materializa la variante y crea una
nueva versión.

Eliminar una versión es una acción destructiva con confirmación. Puede estar
bloqueada si hay corridas o referencias asociadas. Conservar versiones usadas
para auditoría.

## 22. Comparar corridas

Desde el escenario, presionar **Comparar corridas**.

1. Elegir **Corrida base**.
2. Elegir **Corrida candidata**.
3. Deben ser distintas, exitosas y del mismo caso.
4. Revisar **Contexto de las corridas**.
5. Revisar **Diferencias en KPIs**.
6. En **Diferencias por periodo**, elegir una **Serie**.
7. Revisar base, candidata y diferencia periodo a periodo.

Interpretar una diferencia en tres capas:

1. **datos**: variante, rango, sets, revisiones o hashes;
2. **modelo**: topología o parámetros;
3. **ejecución**: versión del contrato, solver y status.

No concluir que una sensibilidad de precio explica el resultado hasta comprobar
que topología y demás señales son iguales.

## 23. Configurar dashboards y portal del proyecto

La configuración se hace en la pantalla del proyecto. Conviene tener al menos
un run exitoso para poder decidir qué información es útil.

### 23.1 Dashboard templates

En **Nuevo template**:

1. escribir **Nombre nuevo template**;
2. activar o desactivar:
   - Summary;
   - Price chart;
   - Grid chart;
   - Renewable chart;
   - BESS chart;
   - Hydro chart;
   - Profit chart;
   - System dispatch table;
   - Asset dispatch table;
3. definir **Table row limit**;
4. presionar **Crear template**.

Los templates existentes se pueden abrir con **Editar {nombre}** y guardar con
**Actualizar template**.

La plantilla decide qué secciones de resultados se solicitan para una
publicación. Si una señal no existe en un run, la sección puede aparecer como no
disponible sin exponer datos técnicos ni romper el resto del reporte.

### 23.2 Configuración del portal

**Portal del cliente** controla presentación y selección pública. Sus elementos
principales son:

- **Nombre público**;
- **Logo del portal**, con opciones de upload o retiro;
- mostrar u ocultar KPIs, gráficos, tablas y descargas;
- título público de cada sección;
- orden y configuración de cada elemento;
- estado **Borrador** o **Activa**.

#### KPIs

Cada KPI permite definir:

- **Id público**: identificador estable para la salida;
- **Ruta canónica**: ruta al valor en resultados;
- **Etiqueta pública**;
- **Unidad**;
- **Decimales**, entre 0 y 6;
- **Signo**: automático, siempre o sin signo;
- **Énfasis**: normal o destacado.

La ruta canónica debe existir en el payload de resultados. El experto debe
probarla con un run real antes de activar el portal.

#### Gráficos

Elegir un gráfico del catálogo, agregarlo y ajustar:

- etiqueta pública del gráfico;
- etiqueta pública de cada serie;
- orden de visualización.

No renombrar una serie de forma que invierta su significado físico. Por ejemplo,
no presentar importación como "venta".

#### Tablas

Elegir una tabla del catálogo y configurar:

- etiqueta pública;
- filas visibles;
- columnas seleccionadas;
- etiqueta pública de cada columna.

Mantener límites de filas prudentes para el portal. Los archivos completos se
pueden exponer como descarga si fueron permitidos en la publicación.

#### Descargas y estado

**Mostrar descargas** controla la sección, y **Título de la sección de
descargas** su encabezado. Los tipos concretos autorizados se eligen en cada
publicación.

Guardar con **Guardar portal**. Mantener **Borrador** mientras se diseña;
cambiar a **Activa** una vez revisados branding, labels y resultados.

## 24. Crear, previsualizar y publicar un reporte

La sección **Publication Drafts** aparece en un run `succeeded`.

### 24.1 Crear publicación

Si no hay templates, la interfaz solicita crear uno en el proyecto.

En **Nueva publicación**:

1. elegir **Dashboard Template**;
2. completar **Public Title**;
3. completar **Analyst Notes** con contexto útil para el receptor;
4. marcar los **Allowed artifact types**;
5. presionar **Crear publicación**.

Por defecto, limitar descargas a artefactos de negocio como summary y dispatch.
No habilitar input snapshots, stdout, stderr o metadata técnica sin una razón
explícita.

### 24.2 Preview

Abrir **Preview as client {título}**.

Comprobar:

- marca y nombre del proyecto;
- título y notas;
- fecha de publicación o contexto de preview;
- periodo reportado;
- KPIs, unidades, decimales y signos;
- series y leyendas de gráficos;
- columnas y límite de tablas;
- descargas permitidas;
- ausencia de controles internos.

El preview incluye **Contexto interno** para el analista. El usuario externo no
debe recibir ese contexto técnico salvo lo incorporado deliberadamente al
reporte público.

### 24.3 Editar, publicar y despublicar

Una publicación `draft` puede editarse. Presionar **Publicar {título}** para
cambiarla a `published`.

Una publicación publicada ofrece **Unpublicar {título}**. La despublicación
retira acceso externo de inmediato sin borrar run, versión ni publicación.

Registrar quién publicó, cuándo y qué artefactos quedaron autorizados. Si se
modifica el template o portal, repetir el preview.

## 25. Administrar usuarios y capacidades externas

Esta sección requiere rol `admin`.

### 25.1 Crear usuario

En **Admin** > **Nuevo usuario**:

1. completar Email;
2. completar Nombre;
3. definir Password inicial;
4. elegir `admin`, `analyst` o `external`;
5. presionar **Crear usuario**.

No elegir el valor legado `client` si aparece en un selector antiguo. Después de
crear una cuenta externa, todavía no tiene acceso a ningún proyecto.

### 25.2 Otorgar capacidades en un proyecto

En el proyecto, la sección **Capacidades externas** solo aparece para admin.

1. En **Otorgar capacidades**, elegir **Usuario externo**.
2. Marcar **Portal al otorgar**, **Operar al otorgar** o ambos.
3. Presionar **Otorgar capacidades**.
4. Verificar que el usuario aparezca en la lista.

Para una asignación existente:

- cambiar checkboxes **Portal {email}** y **Operar {email}**;
- presionar **Guardar capacidades de {email}**.

### 25.3 Revocar o desactivar

- **Revocar {email}** quita capacidades de ese proyecto.
- **Desactivar {email}** en Admin desactiva la cuenta completa.

Ambas operaciones tienen efecto inmediato sobre nuevas peticiones. Una sesión
abierta deja de resolver cuando el usuario está desactivado. Antes de confirmar,
verificar email y proyecto; una revocación no borra publicaciones ni consolas,
solo el acceso.

## 26. Usar el portal como usuario externo

Iniciar sesión con una cuenta `external` que tenga `portal_view`.

### 26.1 Inicio del portal

En **Portal cliente** se listan **Proyectos asignados**. Si no aparece un
proyecto:

1. confirmar que la cuenta está activa;
2. confirmar `portal_view` en ese proyecto;
3. confirmar que el portal está activo;
4. confirmar que existe al menos una publicación `published`.

### 26.2 Proyecto y publicación

1. Abrir un proyecto.
2. Revisar branding y logo.
3. En **Publicaciones**, abrir el título deseado.
4. Revisar encabezado, notas, periodo, KPIs, gráficos y tablas.
5. Descargar solo los archivos mostrados.

El usuario externo no puede abrir drafts, catálogo, variantes, runs internos ni
artefactos no permitidos. Un `403` o una pantalla de no encontrado ante una URL
interna es el comportamiento esperado, no una ausencia de enlace accidental.

## 27. Preparar una consola de operador

La consola separa el trabajo del analista de la operación externa. Cada consola
posee una variante clonada; el operador no modifica la variante del analista.

### 27.1 Crear consola

En el escenario, **Consolas de operador**:

1. escribir **Nombre de la consola**;
2. elegir **Variante de origen**;
3. presionar **Crear consola**.

La tabla muestra:

- consola;
- estado;
- bloqueo;
- espera desde;
- origen de copias;
- acciones **Configurar** y **Probar**;
- acción de reparación si existe un bloqueo;
- enlace al fallo técnico, si corresponde.

### 27.2 Configurar identidad y documento

Abrir **Configurar**. Revisar:

- estado y revisión;
- identidad pública;
- quién la preparó;
- variante propia;
- motivo de bloqueo.

Editar:

- **Nombre público**;
- **Descripción pública**;
- columnas existentes de grupos: etiqueta, señal canónica y entidad;
- **Parámetros y resultados (JSON)**;
- guardar con **Guardar configuración**.

La señal debe existir en el catálogo canónico. La pantalla informa unidad y si
admite negativos.

La UI actual edita grupos y columnas ya presentes, pero no ofrece un botón para
crear grupos o columnas desde cero. Si una consola recién creada necesita una
estructura compleja, el experto debe partir de una configuración ya
provisionada por el flujo/API autorizado; no inventar JSON de grupos en el campo
**Parámetros y resultados**, porque ese campo solo cubre `parameters` y
`results`.

### 27.3 Activar y probar

1. Guardar la configuración.
2. Presionar **Activar**.
3. Si queda bloqueada, usar la acción concreta:
   - **Revalidar variante**;
   - **Corregir {campo}**;
   - abrir **Ver fallo técnico**.
4. Presionar **Probar consola**.

La franja **Estas probando esta consola como {usuario}** indica prueba interna y
ofrece volver al workspace.

### 27.4 Coordinación de series

La configuración muestra **Coordinación e historial de series**:

- leases de edición por grupo;
- usuario que edita y expiración;
- opción admin **Forzar liberación**;
- copias operativas y revisiones;
- notas, actor y número de celdas;
- **Restaurar revisión** cuando está permitido;
- badge de copia antigua si el origen avanzó.

Forzar un lease solo después de confirmar que el otro operador ya no está
editando. Restaurar crea una acción auditable; no elimina las revisiones
posteriores del historial.

## 28. Usar la consola como operador externo

La cuenta necesita `operate` y una consola activa del proyecto.

### 28.1 Periodo y parámetros

En **Periodo y parámetros**:

1. revisar el mensaje del run gate;
2. elegir **Inicio** y **Fin** dentro del rango disponible;
3. editar parámetros expuestos respetando mínimo y máximo;
4. presionar **Guardar parámetros**;
5. esperar que desaparezca **Guarda los cambios antes de ejecutar**.

Si aparece un bloqueo de ingeniería, usar **Solicitar revisión**. Un lock de
otro operador no se resuelve con esa acción: hay que esperar o coordinar la
liberación.

### 28.2 Elegir fuentes

En **Fuentes de series**, cada selector **Fuente de {label}** ofrece únicamente
opciones permitidas. No se puede cambiar fuente mientras hay series sin guardar.
Después de cambiar una fuente, revisar rango y valores.

### 28.3 Editar grupos de valores

Para cada grupo:

1. elegir **Granularidad** antes de tomar edición;
2. presionar **Editar valores**;
3. modificar celdas editables;
4. opcionalmente pegar una matriz tabular desde una hoja de cálculo;
5. revisar warnings y errores;
6. usar **Revisar cambios** para ver el diff;
7. presionar **Guardar valores**;
8. al terminar, **Liberar edición**.

Reglas del pegado:

- una primera fila que parece encabezado puede omitirse;
- columnas bloqueadas se ignoran con warning;
- el excedente se trunca al rango; no crea periodos;
- una celda no numérica invalida el pegado;
- el guardado es atómico: los errores deben resolverse antes de persistir.

La tabla virtualiza horizontes grandes. Navegar con los controles de ventana;
no asumir que solo existen las filas visibles.

**Deshacer último guardado** restaura el estado anterior cuando el contrato lo
permite. Confirmar el historial después.

### 28.4 Ejecutar y revisar

El botón **Ejecutar** se habilita solo cuando:

- run gate permite correr;
- parámetros son válidos y están guardados;
- series están guardadas;
- rango tiene inicio y fin;
- no hay otra operación pendiente.

Después:

1. seguir estado **En espera** -> **Ejecutando** -> **Lista** o **Fallida**;
2. abrir el run en **Historial reciente**;
3. revisar resultados configurados;
4. si falla, anotar mensaje y referencia;
5. seleccionar exactamente dos runs y presionar **Comparar corridas** para ver
   KPIs y reportes lado a lado.

## 29. Diagrama hidráulico v3

Usar esta superficie para red hidráulica con embalses, uniones, tramos,
centrales y unidades. Desde un asset hydro del draft, presionar **Editar diagrama
hidráulico**; el draft se guarda antes de navegar.

### 29.1 Barra de acciones

La barra muestra estado, revisión y:

- **Guardar diagrama**;
- **Recargar diagrama**;
- **Validar topología**;
- **Generar preview v3**;
- **Promover versión v3**.

Promover solo se habilita con diagrama guardado, validación `ok`, no stale y
payload generado.

### 29.2 Agregar y conectar componentes

En **Diagrama**:

1. **Agregar embalse**;
2. **Agregar unión**;
3. **Agregar central**;
4. arrastrar componentes para ordenar el layout;
5. conectar desde el puerto **Salida** del origen al puerto **Entrada** del
   destino, mediante clics o drag-and-drop;
6. seleccionar nodos o conexiones para abrir **Propiedades**.

Conectar nodos hidráulicos crea un tramo dirigido. Las conexiones hacia/desde
una central representan toma o descarga de sus unidades. La leyenda distingue
river, canal, tunnel, spillway y central.

### 29.3 Propiedades de nodo

Todo nodo permite editar **Etiqueta**. El `technical_key` es su identidad y no
debe confundirse con la etiqueta visible.

#### Embalse

Configurar:

- almacenamiento mínimo, máximo e inicial;
- condición terminal;
- almacenamiento terminal mínimo, si aplica;
- valor terminal del agua;
- curva cota-volumen;
- afluente natural.

La curva requiere puntos `storage_hm3` / `elevation_masl`. Se puede editar,
agregar puntos o seleccionar una versión ya guardada. Mantener almacenamiento
estrictamente creciente y cota no decreciente.

#### Unión

Puede recibir afluente natural y participar en tramos. Su función es topológica;
no introducir parámetros de embalse en una unión.

#### Central y unidades

Configurar central:

- no modelada, si corresponde;
- potencia mínima y máxima;
- **Agregar unidad**.

Por unidad:

- etiqueta y estado activo;
- nodo de toma;
- nodo de descarga;
- límites de caudal y potencia disponibles en el formulario;
- curva caudal-potencia;
- modos soportados por el contrato.

La curva `flow_m3s` / `power_mw` debe tener caudal estrictamente creciente.
Evitar modos fuera de alcance como bombeo puro, reversible o generación
dependiente de head si la validación los rechaza.

### 29.4 Propiedades de tramo

Seleccionar un tramo y revisar:

- etiqueta;
- origen;
- destino;
- tipo;
- caudal mínimo escalar;
- penalidad de vertedero para `spillway`;
- serie de caudal mínimo, si corresponde.

La serie de mínimo permite versión guardada o puntos editados con timestamp,
duración y valor.

### 29.5 Afluentes y CSV

En **Afluente natural {nodo}**:

- importar la serie desde archivo si la UI lo ofrece;
- o editar puntos;
- elegir una versión existente;
- revisar timestamp, duración y m3/s;
- guardar el diagrama.

Un embalse sin afluente requerido produce `missing_natural_inflow_series`.

### 29.6 Validar y promover

1. Guardar diagrama.
2. Presionar **Validar topología**.
3. Leer resumen, errores y warnings.
4. Usar **Enfocar {technical_key}** para localizar un error.
5. Corregir y volver a guardar.
6. Generar **Payload v3**.
7. Confirmar `bess_system_dispatch.v3`, nodos, reaches, curvas y series.
8. Presionar **Promover versión v3**.
9. Abrir la versión y ejecutar un run manual.

Errores típicos:

| Código o síntoma                   | Revisión                                      |
| ---------------------------------- | --------------------------------------------- |
| `missing_natural_inflow_series`    | Agregar afluente al nodo requerido.           |
| `non_increasing_storage_points`    | Ordenar y corregir la curva de embalse.       |
| `missing_flow_power_curve`         | Definir curva de la unidad.                   |
| `unsupported_reach_routing`        | Usar routing soportado, normalmente `none`.   |
| `unsupported_cycle`                | Eliminar ciclo dirigido no soportado.         |
| `island_without_boundary`          | Conectar la isla a embalse o afluente válido. |
| `unsupported_unit_operation_mode`  | Quitar pump-only/reversible no soportado.     |
| `unsupported_unit_generation_mode` | Usar generación soportada, no head-dependent. |

Mover nodos solo cambia layout; cambiar parámetros o topología puede dejar la
validación stale. Una versión ya promovida permanece inmutable.

## 30. Series hidráulicas legado

El catálogo tiene **Series hidráulicas (origen legacy)**. Son sets antiguos
expuestos mediante adaptador, sin reescribir automáticamente sus filas.

En el detalle se puede usar **Migrar al catálogo genérico**. La migración:

- crea un set genérico;
- preserva origen, versión y hash legado;
- no modifica el set antiguo;
- no reescribe runs históricos;
- converge si se repite.

El admin puede usar **Migrar todas las series hidráulicas legacy** y revisar
conteos de migradas, ya migradas y fallidas. Hacer backup y probar una migración
individual antes del bulk en un entorno importante.

## 31. Schedules administrados

Solo `admin` ve **Schedules** en la pantalla de administración.

### 31.1 Crear schedule

Completar:

- **Nombre schedule**;
- **Scenario ID**;
- **Variant ID**;
- **Rango inicio** y **Rango término**;
- **Modo de rango** `fixed` o `rolling`;
- offset inicial y duración, si es rolling;
- cadencia `hourly`, `daily` o `weekly`;
- **Próxima ejecución**.

Usar timestamps ISO-8601 con zona. Para `fixed`, el mismo rango se materializa
en cada disparo. Para `rolling`, el rango se calcula respecto del instante de
ejecución.

Presionar **Crear schedule** y revisar ID de scenario/variant, próxima
ejecución y rango.

### 31.2 Ejecutar vencidos

**Ejecutar vencidos** evalúa los schedules debidos. **Refrescar** actualiza
lista e historial.

Cada intento crea un tick con estado, rango, Run ID o error. Un schedule pasa
por las mismas protecciones que un run manual: variante stale o cobertura
insuficiente produce tick fallido y no una corrida silenciosamente parcial.

La programación periódica real se dispara externamente, por ejemplo con
`scripts/run_due_schedules.py` desde Task Scheduler o cron. No hay scheduler
residente dentro del proceso web.

## 32. Tabla de diagnóstico

| Síntoma                             | Causa probable                                       | Acción correcta                                                   |
| ----------------------------------- | ---------------------------------------------------- | ----------------------------------------------------------------- |
| Página en blanco                    | Bundle no compilado o error JS.                      | Revisar build, consola y respuesta `/react`.                      |
| Login vuelve al mismo formulario    | Credencial inválida o cuenta desactivada.            | Verificar email, estado y password; no repetir masivamente.       |
| Rol externo no ve proyecto          | Falta capacidad o publicación.                       | Revisar `portal_view`/`operate`, estado del portal y publicación. |
| **Crear proyecto** no responde      | Petición pendiente o API/DB caída.                   | Esperar, leer alert, comprobar backend; no duplicar clic.         |
| Draft no guarda                     | Campo requerido o JSON inválido.                     | Ir al resumen de validación y corregir campos marcados.           |
| Preview desactualizado              | Se cambió el draft después de generar.               | Guardar, regenerar y validar.                                     |
| Set con 0 periodos                  | Mapeo de timestamp/duración o fuente inválida.       | Volver al archivo y mapping; no vincular.                         |
| Unidad no coincide                  | `source_unit` o señal canónica incorrecta.           | Corregir mapping/reimportar; no compensar mentalmente.            |
| Derivado **Desactualizado**         | Cambió un input.                                     | Revisar receta y regenerar.                                       |
| Falta una señal requerida           | Asset agregado sin set compatible.                   | Importar/matchear set para esa entidad.                           |
| Rango inválido                      | Falta cobertura, huecos, resoluciones o timezone.    | Acortar rango o normalizar datos explícitamente.                  |
| **Vincular y correr** deshabilitado | Binding, rango o staleness bloquea.                  | Resolver el mensaje asociado.                                     |
| Run queda `queued`                  | Worker no avanza.                                    | Revisar proceso, cola y logs del backend.                         |
| Run falla al iniciar                | Julia o entorno no disponible.                       | Verificar `JULIA`, proyecto y paquetes.                           |
| Run infactible                      | Restricciones o datos incompatibles.                 | Revisar límites, condiciones terminales y series.                 |
| Chart no disponible                 | Run no produjo columnas solicitadas.                 | Revisar schema/template; usar tablas/artefactos disponibles.      |
| No se puede publicar                | Run no exitoso o no hay template.                    | Crear template y usar un run `succeeded`.                         |
| Consola bloqueada                   | Variante stale, campo removido, lease o fallo.       | Usar acción específica; no activar a la fuerza.                   |
| Pegado de consola falla             | Celdas no numéricas o fuera del rango.               | Corregir matriz y revisar errores por celda.                      |
| Promoción hidráulica deshabilitada  | No guardado, validación fallida/stale o sin payload. | Guardar, validar y generar preview v3.                            |
| `403` en URL interna de externo     | Límite de autorización correcto.                     | Volver a portal/consola; solicitar capacidad si procede.          |
| `404` de publicación externa        | No publicada, revocada o proyecto no visible.        | Revisar publicación y asignación con admin.                       |

## 33. Qué evidencia registrar

Para que el experto pueda auditar una sesión, guardar una tabla como esta:

| Evidencia               | Valor |
| ----------------------- | ----- |
| Fecha/hora y timezone   |       |
| Usuario y rol           |       |
| Project ID / nombre     |       |
| Scenario ID / nombre    |       |
| Draft guardado a        |       |
| Variante ID / nombre    |       |
| Rango `[inicio, fin)`   |       |
| Sets por señal          |       |
| Revisiones y hashes     |       |
| Version ID / número     |       |
| Run ID / status         |       |
| Objective / KPIs clave  |       |
| Artefactos descargados  |       |
| Publication ID / estado |       |
| Observaciones           |       |

No usar una captura como única evidencia de procedencia. IDs, hashes y rangos
permiten reconstruir qué ocurrió.

## 34. Guion de una sesión guiada completa

### Bloque A: orientación, 20-30 minutos

- [ ] Entrar con `analyst` o `admin`.
- [ ] Identificar cabecera, rol, Salir y navegación.
- [ ] Explicar proyecto, escenario, draft, set, variante, versión y run.
- [ ] Confirmar alcance one-bus y política fail-closed.

### Bloque B: modelo, 30-60 minutos

- [ ] Crear proyecto de prueba.
- [ ] Crear escenario.
- [ ] Crear/abrir draft.
- [ ] Configurar caso, PCC, grid y solver.
- [ ] Agregar assets y revisar todas las unidades.
- [ ] Guardar draft.
- [ ] Generar preview y discutir el contrato.

### Bloque C: datos, 45-90 minutos

- [ ] Revisar CSV/XLSX fuera de la web.
- [ ] Subir fuente.
- [ ] Revisar preview y columnas.
- [ ] Mapear timestamp, duración y señales.
- [ ] Importar al catálogo.
- [ ] Revisar horizonte, señales, valores, revisión y hash.
- [ ] Opcional: crear derivado y explicar lineage.

### Bloque D: ejecución, 30-60 minutos

- [ ] Volver al escenario.
- [ ] Clonar variante si se hará sensibilidad.
- [ ] Vincular cada señal requerida.
- [ ] Definir rango `[inicio, fin)`.
- [ ] Confirmar validación de rango.
- [ ] Ejecutar.
- [ ] Seguir estado.
- [ ] Revisar lineage, snapshot, resultados y artefactos.

### Bloque E: comparación y publicación, 30-45 minutos

- [ ] Crear segunda corrida controlada.
- [ ] Comparar contexto, KPIs y una serie.
- [ ] Crear template.
- [ ] Configurar portal.
- [ ] Crear publicación.
- [ ] Ver preview.
- [ ] Publicar.
- [ ] Entrar como externo y verificar visibilidad.

### Bloque F: funciones avanzadas, según necesidad

- [ ] Consola de operador.
- [ ] Diagrama hidráulico v3.
- [ ] Conector externo.
- [ ] Programas oficiales.
- [ ] Schedules.
- [ ] Migración hidráulica legado.

## 35. Checklist final antes de una corrida importante

### Modelo

- [ ] IDs de PCC, grid y assets son únicos y estables.
- [ ] Límites y eficiencias usan unidades correctas.
- [ ] Condiciones terminales son deliberadas.
- [ ] Draft está guardado.
- [ ] Preview coincide con el diseño.
- [ ] Validación Julia está vigente.

### Datos

- [ ] Timezone y offset son correctos.
- [ ] Timestamps están ordenados y sin duplicados.
- [ ] Duraciones son positivas.
- [ ] No hay huecos o solapes inesperados.
- [ ] Señales canónicas y entidades son correctas.
- [ ] Unidades son correctas.
- [ ] Revisión y hash fueron registrados.
- [ ] Derivados no están stale.

### Variante

- [ ] Es la variante activa correcta.
- [ ] Todas las señales requeridas están vinculadas.
- [ ] Cada set contiene la señal y entidad esperadas.
- [ ] El rango es `[inicio, fin)` y tiene cobertura completa.
- [ ] Resoluciones son compatibles.
- [ ] La variante no está desactualizada.

### Resultado

- [ ] Run terminó `succeeded`.
- [ ] Lineage coincide con el plan.
- [ ] Snapshot tiene el rango y parámetros correctos.
- [ ] KPIs son plausibles.
- [ ] Límites físicos se respetan.
- [ ] Artefactos están registrados y descargables.
- [ ] La publicación, si existe, fue previsualizada.

## 36. Glosario operativo

- **Binding**: referencia de una señal requerida a un set del catálogo.
- **Content hash**: huella del contenido de una revisión de set.
- **Draft**: modelo editable previo a un snapshot ejecutable.
- **Fail-closed**: bloquear cuando no se puede demostrar validez.
- **Granularidad**: resolución temporal mostrada/editada en consola.
- **Lease**: permiso temporal exclusivo para editar un grupo de series.
- **Lineage**: procedencia completa de datos, transformaciones y versiones.
- **PCC**: punto común de conexión eléctrica del modelo one-bus.
- **Programa oficial**: set con emisor, fecha de emisión y vigencia explícitos.
- **Publicación**: vista controlada de un run para usuarios externos.
- **Revisión**: actualización inmutable dentro de la identidad de un set.
- **Run gate**: conjunto de condiciones que habilitan o bloquean Ejecutar.
- **Schedule tick**: evaluación auditable de un schedule en un instante.
- **Set**: colección versionada de una o más señales y un horizonte común.
- **Snapshot**: documento congelado usado por una versión/run.
- **Stale / desactualizado**: la evidencia validada ya no coincide con sus
  dependencias actuales.
- **Variante**: conjunto nombrado de bindings para un caso.

## 37. Referencias internas para profundizar

- `docs/tutorials/carga_y_matcheo_series_tiempo.md`: tratamiento exhaustivo de
  carga, diseño de sets, mappings, bindings y rangos.
- `docs/tutorials/guia_analista.md`: introducción breve al flujo analítico.
- `docs/final/objetivo_final.md`: visión de producto y alcance.
- `docs/iter1/mathematical_model.md`: formulación del BESS base.
- `docs/iter5/mathematical_model.md`: formulación hidro simple v2.
- `docs/hydro_diagram/iter1/pruebas_manuales_iteracion1.md`: checklist del
  diagrama hidráulico v3.
- `docs/series_tiempo/iter6/pruebas_manuales_ts6.md`: transformaciones,
  conectores y schedules.
- `docs/capa_configuracion/architecture_configuration_layer_final.md`:
  arquitectura de portal y consola.
- `docs/capa_configuracion/verification_configuration_layer_final.md`:
  evidencia de verificación de la capa de configuración.

## 38. Criterio de término de la capacitación

La capacitación se considera completa cuando la persona guiada puede, sin
instrucciones de clic a clic:

1. explicar la diferencia entre draft, variante, versión y run;
2. detectar un problema de unidad, horizonte o entidad antes del binding;
3. justificar por qué una variante o validación está stale;
4. ejecutar un caso y demostrar qué revisión/hash consumió;
5. interpretar un resultado sin depender solo del gráfico;
6. publicar únicamente información deliberadamente seleccionada;
7. reconocer cuándo debe detenerse y pedir revisión experta.

El éxito no es conseguir que el botón **Ejecutar** se habilite. Es poder
demostrar que el caso ejecutado representa el problema que se quería resolver y
que sus resultados son trazables.
