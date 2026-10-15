import { useRef } from "react";

function clampAnchor(anchor: number) {
  return Math.min(1, Math.max(0, Math.round(anchor * 1000) / 1000));
}

export function HydraulicConnectionHandle({
  label,
  x,
  y,
  anchor,
  anchorFromClientX,
  onChange,
}: {
  label: string;
  x: number;
  y: number;
  anchor: number;
  anchorFromClientX: (clientX: number) => number;
  onChange: (anchor: number) => void;
}) {
  const drag = useRef<{
    pointerId: number;
    offsetX: number;
    initialAnchor: number;
  } | null>(null);

  return (
    <button
      type="button"
      className="hydraulic-connection-handle"
      role="slider"
      aria-label={label}
      aria-orientation="horizontal"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(anchor * 100)}
      aria-valuetext={`${Math.round(anchor * 100)}% del borde`}
      title={`${label}. Arrastra por el borde o usa las flechas.`}
      style={{ left: x, top: y }}
      onPointerDown={(event) => {
        if (event.button !== 0) return;
        event.stopPropagation();
        const rect = event.currentTarget.getBoundingClientRect();
        drag.current = {
          pointerId: event.pointerId,
          offsetX: event.clientX - (rect.left + rect.width / 2),
          initialAnchor: anchor,
        };
        event.currentTarget.setPointerCapture(event.pointerId);
      }}
      onPointerMove={(event) => {
        if (!drag.current || drag.current.pointerId !== event.pointerId) return;
        onChange(
          clampAnchor(anchorFromClientX(event.clientX - drag.current.offsetX)),
        );
      }}
      onPointerUp={(event) => {
        if (!drag.current || drag.current.pointerId !== event.pointerId) return;
        drag.current = null;
        event.currentTarget.releasePointerCapture(event.pointerId);
      }}
      onPointerCancel={(event) => {
        if (!drag.current || drag.current.pointerId !== event.pointerId) return;
        onChange(drag.current.initialAnchor);
        drag.current = null;
      }}
      onLostPointerCapture={() => {
        drag.current = null;
      }}
      onKeyDown={(event) => {
        const step = event.shiftKey ? 0.1 : 0.01;
        const anchors: Record<string, number> = {
          ArrowLeft: anchor - step,
          ArrowDown: anchor - step,
          ArrowRight: anchor + step,
          ArrowUp: anchor + step,
          Home: 0,
          End: 1,
        };
        if (!(event.key in anchors)) return;
        event.preventDefault();
        event.stopPropagation();
        onChange(clampAnchor(anchors[event.key]));
      }}
    />
  );
}
