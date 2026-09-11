import { useSelector } from "react-redux";

const FIELD_GROUPS = [
  {
    title: "Complaint Meta",
    fields: [
      ["complaint_id", "Complaint ID"],
      ["status", "Status"],
      ["date_received", "Date Received"],
    ],
  },
  {
    title: "Reporter",
    fields: [
      ["customer_name", "Customer / Reporter"],
      ["contact_info", "Contact Info"],
      ["reported_by", "Reported By"],
    ],
  },
  {
    title: "Product Details",
    fields: [
      ["product_name", "Product Name"],
      ["product_strength", "Strength / Grade"],
      ["batch_number", "Batch / Lot Number"],
      ["manufacturing_date", "Manufacturing Date"],
      ["expiry_date", "Expiry Date"],
    ],
  },
  {
    title: "Complaint Details",
    fields: [
      ["defect_type", "Defect Type"],
      ["affected_quantity", "Affected Quantity"],
      ["unit", "Unit"],
      ["complaint_description", "Description"],
    ],
  },
];

function Field({ fieldKey, label, value, highlighted, missing }) {
  const isTextArea = fieldKey === "complaint_description";
  return (
    <div className={`field ${highlighted ? "field--highlighted" : ""} ${missing ? "field--missing" : ""}`}>
      <label>
        {label}
        {missing && <span className="field__required-mark"> *</span>}
      </label>
      {isTextArea ? (
        <div className="field__value field__value--block">{value || "—"}</div>
      ) : (
        <div className="field__value">{value || "—"}</div>
      )}
    </div>
  );
}

function CompletenessBanner({ completeness }) {
  if (!completeness) return null;
  const { completeness_pct, missing_fields, is_complete } = completeness;

  if (is_complete) {
    return (
      <div className="completeness-banner completeness-banner--complete">
        ✓ All required fields complete
      </div>
    );
  }

  return (
    <div className="completeness-banner completeness-banner--incomplete">
      <div className="completeness-banner__bar">
        <div
          className="completeness-banner__bar-fill"
          style={{ width: `${completeness_pct}%` }}
        />
      </div>
      <span>
        {completeness_pct}% complete — missing:{" "}
        {missing_fields.map((f) => f.replace(/_/g, " ")).join(", ")}
      </span>
    </div>
  );
}

export default function ComplaintForm() {
  const form = useSelector((s) => s.complaint.form);
  const highlighted = useSelector((s) => s.complaint.lastUpdatedFields);
  const completeness = useSelector((s) => s.complaint.completeness);

  const missingSet = new Set(completeness?.missing_fields || []);

  return (
    <div className="panel complaint-form">
      <div className="panel__header">
        <h2>Log Customer Complaint</h2>
        <span className="panel__subtitle">Filled and edited by AIVOA Copilot — not manually editable</span>
      </div>

      <CompletenessBanner completeness={completeness} />

      <div className="panel__body">
        {FIELD_GROUPS.map((group) => (
          <div className="field-group" key={group.title}>
            <h3>{group.title}</h3>
            {group.fields.map(([key, label]) => (
              <Field
                key={key}
                fieldKey={key}
                label={label}
                value={form[key]}
                highlighted={highlighted.includes(key)}
                missing={missingSet.has(key)}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}