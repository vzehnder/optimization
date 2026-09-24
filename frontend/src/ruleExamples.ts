import type { RuleDraft, RuleParameter } from "./ComponentRules";

const parameter = (
  name: string,
  unit: string,
  value: number,
): RuleParameter => ({
  name,
  type: "number",
  unit,
  value,
  min: 0,
  max: null,
  object_id: null,
});

// Editable scripts using the installed SDK; they do not add model variables.
export const ruleExamples: Pick<
  RuleDraft,
  "name" | "code" | "parameters" | "temporal" | "windows"
>[] = [
  {
    name: "Máximo de caudal",
    parameters: [parameter("limite", "m3_per_s", 5)],
    code: 'def construir(ctx):\n    for t in ctx.periodos:\n        ctx.restriccion("maximo", t, ctx.objeto.caudal[t] <= ctx.parametros.limite)\n',
  },
  {
    name: "Límite horario y salida calculada",
    parameters: [parameter("capacidad", "m3_per_s", 20)],
    code: 'def construir(ctx):\n    # Selecciona una entrada horaria con alias disponibilidad.\n    for t in ctx.periodos:\n        limite = ctx.parametros.capacidad * ctx.entradas.disponibilidad[t]\n        ctx.restriccion("maximo", t, ctx.objeto.caudal[t] <= limite)\n        ctx.salida("limite_calculado", t, limite)\n',
  },
  {
    name: "Potencia conjunta",
    parameters: [parameter("limite", "mw", 10)],
    code: 'def construir(ctx):\n    # Selecciona una planta con alias central.\n    for t in ctx.periodos:\n        ctx.restriccion("conjunto", t, ctx.objetos.central.potencia[t] <= ctx.parametros.limite)\n',
  },
  {
    name: "Rampas de potencia",
    parameters: [
      parameter("subida", "mw_per_h", 4),
      parameter("bajada", "mw_per_h", 2),
    ],
    temporal: { first_period: "omit", initial_values: [] },
    code: 'def construir(ctx):\n    for paso in ctx.transiciones(ctx.objeto.potencia):\n        cambio = paso.actual - paso.anterior\n        ctx.restriccion("subida", paso.periodo, cambio <= ctx.parametros.subida * paso.horas)\n        ctx.restriccion("bajada", paso.periodo, -cambio <= ctx.parametros.bajada * paso.horas)\n',
  },
  {
    name: "Presupuesto de agua",
    parameters: [parameter("agua", "hm3", 0.036)],
    windows: { kind: "horizon", timezone: "UTC", partial: "reject" },
    code: 'def construir(ctx):\n    for ventana in ctx.ventanas():\n        agua = ventana.integral(ctx.objeto.caudal).a("hm3")\n        ctx.restriccion("agua", ventana, agua <= ctx.parametros.agua)\n',
  },
  {
    name: "Presupuesto de energía",
    parameters: [parameter("energia", "mwh", 12)],
    windows: { kind: "horizon", timezone: "UTC", partial: "reject" },
    code: 'def construir(ctx):\n    for ventana in ctx.ventanas():\n        ctx.restriccion("energia", ventana, ventana.integral(ctx.objeto.potencia) <= ctx.parametros.energia)\n',
  },
];
