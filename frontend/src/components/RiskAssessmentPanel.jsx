import { useSelector } from "react-redux";

const SEVERITY_CLASS = {
  Minor: "badge badge--minor",
  Major: "badge badge--major",
  Critical: "badge badge--critical",
};

export default function RiskAssessmentPanel() {
  const risk = useSelector((s) => s.complaint.risk);
  const highlighted = useSelector((s) => s.complaint.lastUpdatedFields);
  const hasData = Object.values(risk).some(Boolean);

  return (
    <div className="panel risk-panel">
      <div className="panel__header">
        <h2>AI Copilot — Risk Assessment</h2>
        <span className="panel__subtitle">Reasoned automatically from the complaint</span>
      </div>
      <div className="panel__body">
        {!hasData ? (
          <p className="risk-panel__empty">No complaint logged yet — the risk assessment will appear here.</p>
        ) : (
          <>
            <div className={`field ${highlighted.includes("severity") ? "field--highlighted" : ""}`}>
              <label>Severity</label>
              <div>
                {risk.severity ? (
                  <span className={SEVERITY_CLASS[risk.severity] || "badge"}>{risk.severity}</span>
                ) : (
                  "—"
                )}
              </div>
            </div>
            <div className={`field ${highlighted.includes("regulatory_reportable") ? "field--highlighted" : ""}`}>
              <label>Regulatory Reportable</label>
              <div className="field__value">{risk.regulatory_reportable || "—"}</div>
            </div>
            <div className={`field ${highlighted.includes("next_action") ? "field--highlighted" : ""}`}>
              <label>Recommended Next Action</label>
              <div className="field__value">{risk.next_action || "—"}</div>
            </div>
            <div className={`field ${highlighted.includes("root_cause_hint") ? "field--highlighted" : ""}`}>
              <label>Likely Root Cause</label>
              <div className="field__value">{risk.root_cause_hint || "—"}</div>
            </div>
            <div className={`field ${highlighted.includes("capa_suggestion") ? "field--highlighted" : ""}`}>
              <label>CAPA Suggestion</label>
              <div className="field__value">{risk.capa_suggestion || "—"}</div>
            </div>
            <div className={`field ${highlighted.includes("rationale") ? "field--highlighted" : ""}`}>
              <label>Rationale</label>
              <div className="field__value field__value--block">{risk.rationale || "—"}</div>
            </div>
            {risk.regulatory_basis && (
              <div className={`field ${highlighted.includes("regulatory_basis") ? "field--highlighted" : ""}`}>
                <label>Regulatory Basis</label>
                <div className="field__value">
                  <span className="tool-chip">{risk.regulatory_basis}</span>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}