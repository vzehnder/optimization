export const ruleUnit = (unit: string) =>
  ({
    m3_per_s: "m³/s",
    mw: "MW",
    mwh: "MWh",
    m3: "m³",
    s: "s",
    hm3_per_m3_per_s: "hm³/(m³/s)",
    hm3: "hm³",
    dimensionless: "adimensional",
    mw_per_h: "MW/h",
    m3_per_s_per_h: "m³/s por hora",
    h: "h",
  })[unit] ?? unit;
