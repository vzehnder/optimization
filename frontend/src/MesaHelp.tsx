import { useRef } from "react";
import { createPortal } from "react-dom";

export function MesaHelp() {
  const dialog = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  return (
    <>
      <button
        ref={trigger}
        type="button"
        onClick={() => dialog.current?.showModal()}
      >
        Cómo usar la mesa
      </button>
      {createPortal(
        <dialog
          ref={dialog}
          className="mesa-dialog mesa-help"
          aria-labelledby="mesa-help-title"
          onClose={() => trigger.current?.focus()}
        >
          <header>
            <h2 id="mesa-help-title">Cómo usar la mesa</h2>
            <form method="dialog">
              <button autoFocus type="submit">
                Cerrar ayuda
              </button>
            </form>
          </header>
          <ol>
            <li>
              <strong>Organiza tus vistas.</strong> Agrega pestañas y vistas,
              elige cuántas filas y columnas tendrá cada cuadrícula y alterna
              Gráfico/Tabla. En Configurar → Elegir espacio, marca una celda o
              dos esquinas para ocupar un rectángulo. Las celdas de otras vistas
              están bloqueadas. Para reducir la cuadrícula, mueve o reduce antes
              las vistas que quedarían fuera. Guardar mesa conserva la
              distribución.
            </li>
            <li>
              <strong>Elige los ejes.</strong> En Configurar, selecciona las
              series del componente y asigna cada una al eje Y primario
              (izquierda) o secundario (derecha). Cada eje acepta varias series;
              si tienen unidades distintas, muestra «Múltiples unidades» y las
              enumera, sin convertir sus valores.
            </li>
            <li>
              <strong>Ajusta la altura.</strong> Arrastra el control del borde
              derecho de una fila para agrandar juntos sus gráficos. Puedes
              seguir hacia abajo sin un límite fijo; también puedes enfocar la
              barra y usar las flechas arriba y abajo. Guardar mesa conserva
              ejes y alturas.
            </li>
            <li>
              <strong>Edita las entradas.</strong> En Tabla, usa Editar entrada,
              revisa el alcance y guarda con un motivo. Los resultados
              históricos son de solo lectura. Ante un conflicto, compara la
              revisión actual antes de volver a guardar.
            </li>
            <li>
              <strong>Prepara y ejecuta.</strong> Elige inicio, fin exclusivo y
              zona horaria; valida antes de ejecutar. Un cambio en entradas o
              fechas exige validar otra vez. El avance y el run se recuperan al
              recargar; una pérdida de conexión permite reintentar.
            </li>
            <li>
              <strong>Compara y recupera.</strong> Selecciona un run completado
              y pulsa Antes, Comparar o Después. Sin referencia previa no hay
              diferencia de salidas; elige una ejecución compatible. Historial
              de ejecuciones recupera las corridas del caso conservando su
              procedencia.
            </li>
            <li>
              <strong>Exporta lo que consultas.</strong> Período de consulta
              recorta el histórico, sin cambiar la preparación. Exportar CSV de
              vistas visibles incluye ese rango, las unidades y los orígenes de
              las series seleccionadas.
            </li>
            <li>
              <strong>Agrega apoyo.</strong> Crear serie manual publica una
              serie que puedes agregar a una vista. En Gestionar serie manual,
              Vincular revisión publicada requiere un destino compatible y
              confirmación para modificar la próxima preparación.
            </li>
          </ol>
          <p>
            <strong>Red hidráulica:</strong> Editar activos hidráulicos permite
            completar embalses, centrales, curvas, unidades y conexiones.
            Guarda, genera el preview y promueve una versión; luego usa Preparar
            versión en la mesa. La red v3 ejecuta esa fuente promovida; sus
            series manuales son apoyo. El hidro simple v2 participa en el caso
            eléctrico.
          </p>
          <p>
            <strong>Teclado:</strong> Tab recorre controles; las flechas, Inicio
            y Fin cambian de pestaña. Escape cierra los diálogos y devuelve el
            foco. Si hay una edición pendiente, revisa la confirmación antes de
            descartarla.
          </p>
        </dialog>,
        document.body,
      )}
    </>
  );
}
