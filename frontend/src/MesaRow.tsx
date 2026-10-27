import { useEffect, useRef, useState } from "react";

export function MesaRow({
  index,
  height,
  onResize,
}: {
  index: number;
  height?: number | null;
  onResize: (height: number) => void;
}) {
  const row = useRef<HTMLDivElement>(null);
  const drag = useRef<{
    startY: number;
    height: number;
    clientY: number;
    lastHeight: number;
  } | null>(null);
  const [dragging, setDragging] = useState(false);
  const resize = useRef(onResize);
  useEffect(() => {
    resize.current = onResize;
  }, [onResize]);
  useEffect(() => {
    if (!dragging) return;
    let frame = 0;
    const apply = () => {
      const current = drag.current;
      if (!current) return;
      const next = Math.max(
        180,
        Math.round(
          current.height + current.clientY + window.scrollY - current.startY,
        ),
      );
      if (next !== current.lastHeight) {
        current.lastHeight = next;
        resize.current(next);
      }
    };
    const move = (event: PointerEvent) => {
      if (drag.current) drag.current.clientY = event.clientY;
      apply();
    };
    const tick = () => {
      const current = drag.current;
      if (current) {
        const distance =
          current.clientY > window.innerHeight - 48
            ? 12
            : current.clientY < 48
              ? -12
              : 0;
        if (distance) window.scrollBy(0, distance);
        apply();
        frame = requestAnimationFrame(tick);
      }
    };
    const stop = () => {
      drag.current = null;
      cancelAnimationFrame(frame);
      setDragging(false);
    };
    frame = requestAnimationFrame(tick);
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
    window.addEventListener("pointercancel", stop);
    window.addEventListener("blur", stop);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
      window.removeEventListener("pointercancel", stop);
      window.removeEventListener("blur", stop);
    };
  }, [dragging]);
  const currentHeight = () =>
    height ?? row.current!.getBoundingClientRect().height;
  return (
    <div
      className="mesa-row"
      ref={row}
      style={{ gridRow: index + 1, gridColumn: "-2 / -1" }}
    >
      <button
        type="button"
        className="mesa-row-resize"
        aria-label={`Ajustar altura de la fila ${index + 1}`}
        title={`Altura de fila ${index + 1}: arrastra o usa las flechas arriba y abajo.`}
        onPointerDown={(event) => {
          if (event.button !== 0) return;
          event.currentTarget.setPointerCapture(event.pointerId);
          const initialHeight = currentHeight();
          drag.current = {
            startY: event.clientY + window.scrollY,
            height: initialHeight,
            clientY: event.clientY,
            lastHeight: initialHeight,
          };
          setDragging(true);
        }}
        onKeyDown={(event) => {
          if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
          event.preventDefault();
          onResize(
            Math.max(
              180,
              Math.round(
                currentHeight() + (event.key === "ArrowDown" ? 40 : -40),
              ),
            ),
          );
        }}
      >
        <span aria-hidden="true">⋯</span>
      </button>
    </div>
  );
}
