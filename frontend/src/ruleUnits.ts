export const ruleUnit = (unit: string) =>
  ({
    m3_per_s: "m³/s",
    mw: "MW",
    hm3: "hm³",
    dimensionless: "adimensional",
    mw_per_h: "MW/h",
    m3_per_s_per_h: "m³/s por hora",
    h: "h",
  })[unit] ?? unit;
