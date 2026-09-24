"""Stable internal failure categories; raw messages are evidence, not a diagnosis."""

ACTIONS = {
    "code_data": "Corregir el código o los datos indicados y volver a probar la regla.",
    "capacity": "Revisar las capacidades del motor y las cuotas; reducir el tamaño o habilitar la capacidad requerida.",
    "timeout": "Revisar el límite de tiempo de esta etapa y reintentar explícitamente.",
    "cancelled": "Revisar la cancelación o interrupción y volver a iniciar la operación si corresponde.",
    "solve": "Consultar el estado y los registros del solver antes de reintentar.",
}


def failure_diagnostic(error, *, status=None):
    code = str(error.get("code") or "SOLVE_ERROR")
    if "TIMEOUT" in code or code == "SOLVER_TIME_LIMIT":
        category = "timeout"
    elif "CANCEL" in code or "INTERRUPTED" in code or status == "cancelled":
        category = "cancelled"
    elif "LIMIT" in code or "CAPABILITY" in code or code == "RULE_RUNTIME_UNAVAILABLE":
        category = "capacity"
    elif code.startswith("RULE_") or code == "RUN_VALIDATION_ERROR":
        category = "code_data"
    else:
        category = "solve"
    return {"code": code, "category": category, "message": error.get("message", "La operación no pudo completarse."),
            "action": ACTIONS[category], **{key: error[key] for key in ("period", "line", "name", "application_id") if key in error}}
