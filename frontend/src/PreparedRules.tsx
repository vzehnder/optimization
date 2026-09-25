import { Link } from "react-router-dom";
import type { PreparedRuleSummary } from "./api/client";

export function PreparedRules({ rules }: { rules?: PreparedRuleSummary }) {
  if (!rules?.items.length) return null;
  return (
    <section className="content-panel" aria-label="Reglas preparadas">
      <h2>Reglas preparadas</h2>
      <p>
        {rules.ready
          ? "Revisiones fijadas listas para ejecutar."
          : "Revisa las reglas antes de ejecutar."}
      </p>
      {!rules.runtime_available && (
        <p role="status">El ejecutor de reglas no está disponible.</p>
      )}
      <ul className="resource-list">
        {rules.items.map((rule) => (
          <li key={rule.application_id}>
            <strong>{rule.name}</strong>
            <p>
              Revisión fijada: <code>{rule.publication_id}</code>
            </p>
            {rule.validation_causes.map((cause, index) => (
              <p key={index}>{cause.message}</p>
            ))}
            <Link to={rule.rule_url.replace(/^\/react/, "")}>
              Revisar {rule.name}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
