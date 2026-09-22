export const ruleUnit = (unit: string) =>
  ({ m3_per_s: "m³/s", mw: "MW", hm3: "hm³", dimensionless: "adimensional" })[
    unit
  ] ?? unit;
