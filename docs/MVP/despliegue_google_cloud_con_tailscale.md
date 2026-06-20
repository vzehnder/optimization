# MVP en Google Cloud con Tailscale

## 1. Objetivo

Desplegar la aplicacion web y el motor de optimizacion de este repositorio en
Google Cloud, manteniendo la base de datos en un computador ubicado en la casa
del administrador.

La propuesta prioriza un MVP simple, privado y operable por una sola persona:

- Una VM de Compute Engine ejecuta FastAPI, Julia y HiGHS.
- PostgreSQL se ejecuta en el computador de la casa.
- Tailscale entrega conectividad privada entre ambos equipos.
- Los archivos de entrada y los artefactos permanecen en un Persistent Disk.
- La VM se enciende antes de una sesion de trabajo y se apaga al terminar.

Esta arquitectura evita Kubernetes, Cloud Run, Cloud Tasks y una cola
distribuida durante la primera etapa.

## 2. Arquitectura propuesta

```text
Analista o cliente
        |
        | HTTPS
        v
Compute Engine (Google Cloud)
+-----------------------------------+
| Proxy HTTPS (Caddy o Nginx)       |
| FastAPI                           |
| Cola local de una sola instancia  |
| Julia + BESSDispatch + HiGHS      |
|                                   |
| Persistent Disk                   |
| - archivos CSV/XLSX               |
| - inputs de cada corrida          |
| - logs                            |
| - resultados y artefactos         |
+-----------------------------------+
        |
        | Tailscale, TCP 5432
        v
Computador en la casa
+-----------------------------------+
| PostgreSQL                        |
| Backups de la base de datos       |
+-----------------------------------+
```

Tailscale reemplaza en este MVP la necesidad de configurar WireGuard
manualmente o contratar Cloud VPN. PostgreSQL no debe exponerse mediante el
router domestico ni aceptar conexiones desde Internet.

## 3. Encendido de Compute Engine

Para la primera version se propone una sola VM bajo demanda:

1. El administrador enciende la VM antes de usar la aplicacion.
2. El sistema inicia Tailscale, Docker y la aplicacion.
3. El analista utiliza la interfaz web y ejecuta las optimizaciones.
4. Antes de apagar se comprueba que no existan corridas en estado `queued` o
   `running`.
5. El administrador apaga la VM al terminar la sesion.

Mientras la VM este apagada, la interfaz web no estara disponible. El
Persistent Disk conserva los archivos y el disco de arranque conserva la
identidad de Tailscale para reconectarse al mismo tailnet.

Si posteriormente se requiere acceso permanente para clientes, se debera
separar la aplicacion web de la maquina de optimizacion. Esa separacion no es
necesaria para validar el MVP.

## 4. Cambios necesarios en el repositorio

### 4.1 Migrar SQLite a PostgreSQL

La implementacion actual usa `sqlite3` y solo acepta URLs `sqlite:///`. Un
archivo SQLite no se debe abrir remotamente a traves de Tailscale ni mediante
un filesystem compartido.

Se requiere:

1. Agregar soporte para `postgresql://` en `DATABASE_URL`.
2. Reemplazar el acceso directo con `sqlite3` por una capa compatible con
   PostgreSQL. SQLAlchemy es una opcion practica.
3. Crear migraciones versionadas, por ejemplo con Alembic.
4. Adaptar autoincrementos, placeholders, booleanos, fechas y transacciones.
5. Mantener los contratos actuales de proyectos, escenarios, versiones,
   corridas, artefactos, usuarios, dashboards y publicaciones.
6. Agregar pruebas de integracion contra PostgreSQL.
7. Preparar una migracion desde el SQLite actual si se deben conservar datos.

La aplicacion recibe componentes separados y construye internamente la URL:

```text
DB_HOST=<tailscale-db-ip>
DB_PORT=5432
DB_NAME=energy_dispatch
DB_USER=energy_dispatch_app
DB_PASSWORD=<password>
```

La variable `DATABASE_URL` se conserva como override opcional para tests y
entornos administrados. La contraseña no se debe guardar en el repositorio ni
dentro de la imagen.

### 4.2 Dockerizar Python y Julia

La imagen de produccion debe incluir:

- Python y las dependencias de `requirements.txt`.
- Julia en una version compatible con `Project.toml`.
- Las dependencias fijadas en `Manifest.toml`.
- El paquete local `BESSDispatch`.
- HiGHS y las dependencias del modelo.
- FastAPI, Uvicorn y los scripts Julia.

La construccion debe instalar y precompilar dependencias para reducir el tiempo
de la primera optimizacion. La imagen se publica en Artifact Registry y la VM
la ejecuta mediante Docker Compose o un servicio `systemd`.

### 4.3 Persistir inputs y artefactos

El MVP debe montar un Persistent Disk en rutas estables:

```text
/srv/energy_dispatch/artifacts
/srv/energy_dispatch/input-sources
```

Variables sugeridas:

```text
ARTIFACT_ROOT=/srv/energy_dispatch/artifacts
INPUT_SOURCE_ROOT=/srv/energy_dispatch/input-sources
JULIA=/usr/local/bin/julia
BESS_AUTH_ENABLED=true
```

El contenedor debe recibir esas rutas como volumen. Cloud Storage puede usarse
para backups, pero no es necesario modificar la aplicacion para consumir
objetos directamente en el primer despliegue.

### 4.4 Hacer recuperable la cola local

La cola actual vive en memoria dentro de FastAPI. Para mantener este diseño en
una unica VM se requieren controles minimos:

- Ejecutar una sola instancia de la aplicacion y un solo worker.
- Al iniciar, detectar corridas que quedaron en `queued` o `running`.
- Reencolar las corridas seguras o marcarlas como interrumpidas.
- Evitar apagar la VM mientras exista una corrida activa.
- Reiniciar automaticamente el contenedor si el proceso falla.
- Conservar timeout, stdout, stderr y snapshots de entrada.

### 4.5 Operacion web segura

Se debe agregar o verificar:

- Endpoint de salud para la VM y el contenedor.
- Cookies con `Secure`, `HttpOnly` y `SameSite` apropiado.
- HTTPS mediante Caddy, Nginx o un balanceador de Google Cloud.
- Limites de tamaño para archivos CSV, XLSX y JSON.
- Limites de tiempo y memoria para las optimizaciones.
- Logs de aplicacion enviados a Cloud Logging.
- Uso controlado de `/bootstrap` para crear el administrador inicial.

## 5. Configuracion de Tailscale

### 5.1 Computador de base de datos

1. Mantener Tailscale activo como servicio del sistema.
2. Asignar un nombre reconocible, por ejemplo `energy-dispatch-db-home`.
3. Etiquetar el dispositivo, por ejemplo `tag:energy-dispatch-db`.
4. Obtener su IP Tailscale IPv4 o habilitar MagicDNS.
5. Configurar PostgreSQL para escuchar en localhost y en Tailscale.
6. En `pg_hba.conf`, aceptar solamente al usuario de aplicacion desde la IP
   Tailscale de la VM.
7. Usar autenticacion SCRAM y una contraseña exclusiva.
8. Bloquear TCP 5432 en las interfaces LAN y publicas.

No se debe compartir el archivo de datos PostgreSQL ni el archivo SQLite a
traves de Tailscale. La conexion se realiza mediante el protocolo normal
cliente-servidor de PostgreSQL.

### 5.2 VM de Compute Engine

1. Instalar Tailscale en el host de la VM.
2. Registrar la maquina con una credencial almacenada de forma segura.
3. Usar un nombre como `energy-dispatch-gcp-mvp` y la etiqueta
   `tag:energy-dispatch-app`.
4. Iniciar Tailscale antes del contenedor.
5. Probar `tailscale ping energy-dispatch-db-home`.
6. Probar una conexion `psql` desde la VM.
7. Probar finalmente la conexion desde el contenedor.

Para el MVP, Tailscale debe ejecutarse en el host y no como sidecar. El
contenedor puede conectarse a la IP Tailscale de PostgreSQL. Si el bridge de
Docker impide el routing o MagicDNS, se puede usar la IP directamente o
ejecutar el contenedor con red de host en Linux.

### 5.3 Politica de acceso

La politica del tailnet debe permitir solo:

```text
tag:energy-dispatch-app -> tag:energy-dispatch-db:5432/tcp
```

No se debe conceder acceso general de la VM al resto de la red domestica. Una
conexion marcada como `direct` por Tailscale es preferible. Una conexion por
relay funciona, pero agrega latencia.

## 6. Recursos de Google Cloud

| Necesidad | Recurso |
| --- | --- |
| Aplicacion web y optimizador | Compute Engine |
| Disco de artefactos e inputs | Persistent Disk |
| Imagen Docker | Artifact Registry |
| Credenciales | Secret Manager |
| Logs y alertas | Cloud Logging y Cloud Monitoring |
| Acceso web | IP estatica y proxy HTTPS |

La VM debe ubicarse en una region cercana al computador de PostgreSQL porque
cada operacion de persistencia atraviesa Tailscale e Internet.

La cuenta de servicio debe aplicar minimo privilegio: leer la imagen, acceder a
los secretos necesarios y escribir logs o backups si estan habilitados. El
firewall de Google Cloud no necesita exponer PostgreSQL.

## 7. Secuencia de implementacion

### Fase 1: Persistencia portable

1. Introducir una capa de persistencia PostgreSQL.
2. Crear migraciones del esquema.
3. Ejecutar las pruebas actuales contra PostgreSQL.
4. Validar autenticacion, corridas, artefactos y publicaciones.

### Fase 2: Imagen reproducible

1. Crear el Dockerfile para Python y Julia.
2. Precompilar dependencias Julia.
3. Ejecutar las suites Python y Julia dentro de la imagen.
4. Probar una corrida completa con volumenes Docker locales.

### Fase 3: Infraestructura cloud

1. Crear proyecto, red, VM y Persistent Disk.
2. Crear Artifact Registry y publicar la imagen.
3. Crear secretos y cuenta de servicio.
4. Instalar Docker, el proxy HTTPS y Tailscale en la VM.
5. Configurar el arranque automatico.

### Fase 4: Base de datos domestica

1. Crear base, usuario y esquema PostgreSQL.
2. Restringir PostgreSQL a Tailscale.
3. Aplicar la politica de acceso del tailnet.
4. Probar conectividad, autenticacion y latencia.
5. Ejecutar las migraciones desde la VM.

### Fase 5: Despliegue y aceptacion

1. Iniciar la aplicacion con autenticacion habilitada.
2. Crear el primer administrador.
3. Crear un proyecto, escenario y version.
4. Subir CSV/XLSX y validar el caso generado.
5. Ejecutar casos BESS, hibrido e hidro.
6. Verificar tablas, graficos, artefactos y descargas.
7. Crear y revisar una publicacion para cliente.
8. Reiniciar el contenedor y validar recuperacion.
9. Reiniciar la VM y validar Tailscale, volumenes y aplicacion.
10. Simular perdida de la conexion domestica y comprobar un fallo visible y
    recuperable.

## 8. Operacion cotidiana

1. Confirmar que el computador de la base y PostgreSQL estan activos.
2. Encender la VM desde Google Cloud.
3. Esperar a que Tailscale y la aplicacion esten saludables.
4. Ingresar a la aplicacion por HTTPS.
5. Ejecutar y revisar las optimizaciones.
6. Confirmar que no existan corridas activas.
7. Verificar los backups requeridos.
8. Apagar la VM.

Aunque la VM se apague, los recursos persistentes como discos continuan
almacenados y pueden seguir generando cobros.

## 9. Riesgos aceptados

| Riesgo | Mitigacion inicial |
| --- | --- |
| Corte de energia o Internet en la casa | UPS, monitoreo y errores visibles |
| Latencia hacia PostgreSQL | Region cercana, enlace directo y consultas eficientes |
| Cola perdida al reiniciar | Recuperar estados desde PostgreSQL |
| VM apagada | Procedimiento manual de encendido y apagado |
| Falla del disco de artefactos | Snapshots y backups periodicos |
| Credencial Tailscale filtrada | Secret Manager, etiquetas y rotacion |
| Acceso lateral por el tailnet | Restringir a TCP 5432 |
| Una sola instancia | Riesgo aceptado durante el MVP |

La base de datos domestica sera un punto unico de falla. Esto es coherente con
la restriccion inicial, pero debe reconsiderarse antes de ofrecer compromisos
de disponibilidad a clientes.

## 10. Evolucion posterior

Cuando la interfaz deba permanecer disponible sin mantener encendido el motor:

```text
Servicio web siempre activo
        |
        | cola durable
        v
Worker Compute Engine bajo demanda
        |
        | Tailscale
        v
PostgreSQL domestico
```

Esta etapa requiere separar el worker de FastAPI, reemplazar la cola en memoria,
iniciar y detener el worker mediante la API de Compute Engine y mover los
artefactos a almacenamiento accesible por ambos servicios.

No se recomienda incorporar esa complejidad antes de comprobar que el flujo
monolitico cubre las necesidades reales del analista y los primeros clientes.

## 11. Criterio de termino

El despliegue MVP se considera exitoso cuando:

- La VM recupera automaticamente sus servicios al encender.
- La VM accede a PostgreSQL exclusivamente mediante Tailscale.
- PostgreSQL no esta publicado en Internet.
- La aplicacion conserva autenticacion y separacion de roles.
- Un analista puede crear, validar y ejecutar un escenario completo.
- Julia genera resultados y artefactos en el Persistent Disk.
- Los resultados pueden revisarse y publicarse para un cliente.
- Un reinicio no pierde la base de datos ni los artefactos.
- Los errores de base de datos, optimizacion y archivos son observables.
- La VM puede apagarse de forma segura al terminar una sesion.
