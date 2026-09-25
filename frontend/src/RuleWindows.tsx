export interface WindowPolicy {
  kind: "horizon" | "civil_day";
  timezone: string;
  partial: "reject" | "allow";
}

export function RuleWindows({
  policy,
  onChange,
  battery = false,
}: {
  policy: WindowPolicy | null;
  onChange: (policy: WindowPolicy | null) => void;
  battery?: boolean;
}) {
  return (
    <fieldset>
      <legend>Presupuestos de agua y energía</legend>
      <label>
        Ventanas de presupuesto
        <select
          value={policy?.kind ?? ""}
          onChange={(event) =>
            onChange(
              event.target.value
                ? {
                    kind: event.target.value as WindowPolicy["kind"],
                    timezone: policy?.timezone ?? "UTC",
                    partial: "reject",
                  }
                : null,
            )
          }
        >
          <option value="">Sin presupuestos por ventana</option>
          <option value="horizon">Horizonte completo</option>
          <option value="civil_day">Días civiles</option>
        </select>
      </label>
      {policy && (
        <>
          <label>
            Zona horaria IANA
            <input
              value={policy.timezone}
              onChange={(event) =>
                onChange({ ...policy, timezone: event.target.value })
              }
              placeholder="America/Santiago"
            />
          </label>
          {policy.kind === "civil_day" && (
            <label>
              <input
                type="checkbox"
                checked={policy.partial === "allow"}
                onChange={(event) =>
                  onChange({
                    ...policy,
                    partial: event.target.checked ? "allow" : "reject",
                  })
                }
              />
              Acepto días parciales con el presupuesto completo
            </label>
          )}
          <p>
            Las integrales usan la duración real de cada intervalo: MW por horas
            → MWh; m³/s por segundos → m³. Los intervalos no pueden cruzar
            bordes de día. No se prorratea el presupuesto.
          </p>
          {battery ? (
            <details>
              <summary>Ejemplo de presupuesto de energía</summary>
              <p>
                Define presupuesto en mwh. Integra la carga o descarga en MW por
                su duración en horas.
              </p>
              <pre>
                {
                  'def construir(ctx):\n    for ventana in ctx.ventanas():\n        ctx.restriccion("energia", ventana, ventana.integral(ctx.objeto.descarga) <= ctx.parametros.presupuesto)'
                }
              </pre>
            </details>
          ) : (
            <details>
              <summary>Ejemplo de presupuesto de agua</summary>
              <p>
                Define el parámetro agua en hm3. Para energía, usa potencia y un
                parámetro en mwh, sin convertir a hm3.
              </p>
              <pre>
                {
                  'def construir(ctx):\n    for ventana in ctx.ventanas():\n        agua = ventana.integral(ctx.objeto.caudal).a("hm3")\n        ctx.restriccion("agua", ventana, agua <= ctx.parametros.agua)'
                }
              </pre>
            </details>
          )}
        </>
      )}
    </fieldset>
  );
}
