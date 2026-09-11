# app/completeness.py
REQUIRED_FIELDS = [
    "customer_name", "product_name", "batch_number",
    "defect_type", "complaint_description", "affected_quantity",
    "reported_by", "date_received",
]

def check_completeness(form: dict) -> dict:
    missing = [f for f in REQUIRED_FIELDS if not form.get(f)]
    total = len(REQUIRED_FIELDS)
    filled = total - len(missing)
    return {
        "missing_fields": missing,
        "completeness_pct": round((filled / total) * 100),
        "is_complete": not missing,
    }