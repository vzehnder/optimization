export function resultUnit(key: string): string {
  const units: Array<[string, string]> = [
    ["_usd_per_mwh", "USD/MWh"],
    ["_mwh", "MWh"],
    ["_mw", "MW"],
    ["_m3s", "m³/s"],
    ["_hm3", "hm³"],
    ["_masl", "m s. n. m."],
    ["_usd", "USD"],
    ["_hours", "h"],
  ];
  return units.find(([suffix]) => key.endsWith(suffix))?.[1] || "";
}

export function resultLabel(key: string): string {
  return (
    (
      {
        objective_value_usd: "Valor objetivo",
        total_market_value_usd: "Valor de mercado",
        case_name: "Nombre del caso",
        solver_status: "Estado del solver",
        termination_status: "Motivo de finalización",
        total_hydro_generation_mwh: "Generación hidráulica",
        total_generation_mwh: "Generación hidráulica",
        total_turbine_volume_hm3: "Volumen turbinado",
        total_spill_volume_hm3: "Volumen vertido",
        total_spill_penalty_usd: "Costo de vertimiento",
        terminal_water_value_usd: "Valor terminal del agua",
        final_storage_hm3: "Almacenamiento final",
      } as Record<string, string>
    )[key] || key
  );
}

export function formatResultValue(value: unknown): string {
  if (value === null || value === undefined || value === "")
    return "No disponible";
  if (typeof value === "number")
    return Number.isFinite(value)
      ? value.toLocaleString("es-CL", { maximumSignificantDigits: 12 })
      : "No disponible";
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}
