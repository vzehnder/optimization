# Prototipo desechable: portal cliente configurado

Tres variantes de la vista de una publicacion cliente, intercambiables con
`?variant=`, en una pagina autonoma que no toca `frontend/src`.

## Ejecutar

Desde la raiz del repositorio:

```powershell
.\.venv\Scripts\python.exe -m http.server 4174 --directory docs/wayfinder/prototypes/portal-cliente
```

Abrir <http://localhost:4174/?variant=A>.

## Variantes

- `A` — **Informe ejecutivo**: una lectura guiada y lineal. El ingeniero elige
  KPIs, nombres y paneles; el orden macro permanece fijo. La publicacion aporta
  titulo, comentario, fecha y archivos aprobados.
- `B` — **Tablero explorable**: archivo de publicaciones a la izquierda y
  navegacion por temas. El cliente puede cambiar de tema y entre grafico/tabla,
  pero nunca modifica datos ni configuracion.
- `C` — **Dossier tecnico**: documento con indice, figuras, tablas y bloque de
  trazabilidad en lenguaje cliente. Prioriza evidencia y una descarga integral.

La barra inferior cambia de variante y actualiza la URL. Las flechas izquierda
y derecha del teclado tambien cambian de alternativa. Los tabs, el selector
Grafico/Tabla y las descargas son simulaciones en memoria.

## Decisiones que el prototipo pone a prueba

1. Si el portal debe leerse como informe, explorarse como tablero o consultarse
   como dossier.
2. Si el orden macro es fijo y el ingeniero solo elige contenido, nombres y
   enfasis, o si debe poder ordenar paneles.
3. Si las etiquetas configurables llegan hasta KPI, serie y columna.
4. Si una configuracion se comparte por proyecto con todos sus clientes.
5. Si la configuracion define las descargas posibles y cada publicacion elige
   el subconjunto efectivamente compartido.
6. Si la publicacion conserva titulo, notas, fecha, corrida y archivos, mientras
   la configuracion conserva la forma visual y el vocabulario.

> **PROTOTIPO DESECHABLE.** Usa datos simulados, no descarga archivos y no es
> una base de implementacion.

## Decision

El usuario eligio la variante `A` — **Informe ejecutivo** el 2026-08-12. Las
otras variantes quedan conservadas solo como evidencia de la comparacion; la
implementacion debera reescribir la alternativa ganadora con contratos y
pruebas de produccion.
