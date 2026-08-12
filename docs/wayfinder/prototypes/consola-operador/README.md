# Prototipo desechable: consola de operador

Tres variantes de la consola de operador, intercambiables con `?variant=`,
en una pagina autonoma que no toca `frontend/src`.

## Ejecutar

Desde la raiz del repositorio:

```powershell
.\.venv\Scripts\python.exe -m http.server 4173 --directory docs/wayfinder/prototypes/consola-operador
```

Abrir <http://localhost:4173/?variant=A>.

## Variantes

- `A` — **Mesa de trabajo**: preparacion y ejecucion conviven en una sola
  pantalla; la accion de correr siempre permanece a la vista. Los datos se
  organizan en grupos definidos por el analista y alternan entre tabla editable
  y grafico. Cada serie permite elegir una version nombrada; editar deja
  cambios pendientes y guardarlos simula la revision persistida en la base SQL.
- `B` — **Recorrido guiado**: divide la preparacion en pasos y obliga a revisar
  antes de ejecutar.
- `C` — **Resultados primero**: al entrar muestra la ultima corrida y el
  historial; preparar una nueva corrida ocurre en un panel lateral.

La barra inferior cambia de variante. El laboratorio de estado permite forzar
`listo`, `en cola`, `ejecutando`, `completado` y `error`. Los botones y las
flechas izquierda/derecha del teclado actualizan la URL para que cada vista se
pueda compartir.

La persistencia del prototipo es solo una simulacion en memoria. El contrato
validado para el producto es leer y guardar en SQL; cambiar una version elige
otro set nombrado y guardar valores crea una revision auditable del set elegido.

## Preguntas para la sesion de reaccion

1. ¿Cual debe ser la primera informacion que ve un operador recurrente?
2. ¿La preparacion necesita pasos obligatorios o basta una pantalla unica?
3. ¿Que informacion del caso da confianza sin exponer el modelo interno?
4. ¿Cuanto detalle merece una corrida activa o fallida?
5. ¿El historial y la comparacion son parte de la tarea principal o una
   consulta secundaria?

> **PROTOTIPO DESECHABLE.** Usa datos simulados, no persiste cambios y no es
> una base de implementacion.
