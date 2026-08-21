# Prototipo desechable: tabla editable y pegado desde Excel

Activo del ticket
[Contrato de la tabla editable y del pegado desde Excel](../../capa-de-configuracion/07-contrato-tabla-editable-y-pegado.md),
resuelto en la sesion de reaccion del 2026-08-20.

Tres formas de tabla intercambiables con `?variant=`, sobre 8760 periodos
horarios virtualizados, con pegado de portapapeles de verdad: el prototipo
parsea el TSV que entrega Excel, aplica las politicas y marca las celdas
ofensoras antes de dejar guardar.

**La variante decidida es `A`.** `B` y `C` se conservan porque son el contraste
que sostiene la decision, no como alternativas vivas.

## Ejecutar

Desde la raiz del repositorio:

```powershell
.\.venv\Scripts\python.exe -m http.server 4174 --directory docs/wayfinder/prototypes/tabla-editable
```

Abrir <http://localhost:4174/?variant=A>.

## Variantes (forma de la tabla)

- `A` — **Por grupo** *(decidida)*: pestañas que define el analista, como fijo el
  cascaron. Un grupo puede mezclar señales de copias operativas distintas:
  Potencia toca dos. Comodo de leer, y obliga a que el guardado sea
  transaccional entre copias.
- `B` — **Unificada por caso**: una sola tabla con las 7 señales habilitadas.
  Lo mas parecido a la hoja de Excel de origen; tambien lo que mas copias mezcla
  en un mismo guardado (4).
- `C` — **Por copia operativa**: la pestaña *es* la copia. Un guardado = una
  revision de un set = la primitiva de backend tal cual. Atomicidad gratis, a
  costa de exponerle al operador que su plan vive repartido en cuatro tablas.

## Politicas decididas

El laboratorio de la derecha conmuta cada politica en vivo y **re-evalua las
celdas ya pegadas**, para poder contrastar la regla decidida con la descartada.
El valor por defecto de cada control es el decidido.

| Politica | Decision |
| --- | --- |
| Formato numerico | **Rechazar lo ambiguo.** Regla estructural simetrica, sin locale configurable. |
| Bloque mas largo que el tramo | **Truncar y avisar.** |
| Celdas invalidas al guardar | **Todo o nada.** |
| Tramo editable | **Acota la edicion**, no solo la vista. Sin tope de tamaño: el año completo es editable. |
| Diff previo | **Siempre disponible, nunca obligatorio.** |

### La regla del numero ambiguo

Una cadena es ambigua cuando tiene **un unico separador seguido de exactamente
tres digitos, precedido de un grupo de miles valido** (1 a 3 digitos, sin cero a
la izquierda). Esos casos se rechazan y obligan a corregir en el origen. Todo lo
demas tiene lectura unica y no necesita locale:

| Entrada | Lectura | Motivo |
| --- | --- | --- |
| `1.234` | **rechazada** | 1234 o 1,234 |
| `1,234` | **rechazada** | simetrico del anterior |
| `12,345` | **rechazada** | 12345 o 12,345 |
| `1.234,5` | 1234,5 | ambos separadores: el ultimo es el decimal |
| `1,234.5` | 1234,5 | idem |
| `12,5` / `12.5` | 12,5 | un separador, no son tres digitos |
| `1.234.567` | 1234567 | dos separadores iguales: miles |
| `1234,567` | 1234,567 | cuatro digitos delante: no es grupo de miles |
| `0,001` | 0,001 | `0` no es grupo de miles valido |

## Que probar

1. Copiar una columna de Excel y pegarla sobre una celda: con el ancla puesta,
   el bloque se alinea hacia abajo y a la derecha.
2. Pegar un rango rectangular de 2-3 columnas, con y sin fila de encabezado: el
   encabezado se detecta y se descarta con aviso.
3. Pegar sobre la columna **Caudal minimo** (bloqueada) y ver que se omite.
4. Pegar los casos de la tabla de ambiguedad de arriba.
5. Escribir un negativo en Demanda (`nonnegative`) y en Precio compra (que si
   admite negativos).
6. Cambiar el tramo a *Dia 12 ago* y pegar 200 valores: se truncan 176 y el
   aviso lo dice.
7. Abrir la revision: resume celdas, periodos, copias tocadas, rango
   antes/despues por señal y los rechazos.
8. Forzar un conflicto de revision y ver la recuperacion.
9. Poner el lease en *De otro* y comprobar que toda la tabla pasa a solo lectura.

> **PROTOTIPO DESECHABLE.** Datos simulados, sin persistencia y sin backend. No
> es base de implementacion: valida el contrato, no el codigo.
