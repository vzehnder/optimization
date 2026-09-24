export const validationLabel = (status: string) =>
  ({
    valid: "Validada",
    stale: "Obsoleta",
    invalid: "Inválida",
    pending: "Pendiente",
  })[status] ?? status;

export const definitionLabel = (status: string) =>
  ({ draft: "Borrador", published: "Publicada", archived: "Archivada" })[
    status
  ] ?? status;
