"""
engine/decision_maker.py
Standalone module -- function: evaluate_compliance(context)

Evaluates the Context Object against Companies Act 2013 rules. When
legislative clauses are available from the Statutory Bare Act, reasoning
strings cite the exact statutory text.

No side effects. All visual pacing is handled by the UI layer.
"""
import uuid
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Section 188 RPT monetary thresholds (INR)
# Source: Companies (Meetings and Powers of Board) Rules 2014, Rule 15(3)
# ---------------------------------------------------------------------------
_SEC188_THRESHOLDS_INR = {
    "sale_purchase_of_goods":       10_000_000,    # Rs.1 crore
    "sale_purchase_of_property":    1_000_000_000, # Rs.100 crore
    "leasing_of_property":          1_000_000_000, # Rs.100 crore
    "availing_rendering_services":  5_000_000,     # Rs.50 lakh
    "director_appointment":         250_000,       # Rs.2.5 lakh/month
}

_WEIGHT_STRUCK_OFF_ENTITY       = 65
_WEIGHT_DISQUALIFIED_DIRECTOR   = 50
_WEIGHT_SEC185_LOAN_TO_DIRECTOR = 70
_WEIGHT_SEC188_RPT_BREACH       = 40
_WEIGHT_RELATED_PARTY_FLAG      = 20
_WEIGHT_HIGH_VALUE_PROPERTY     = 10

_BLOCK_THRESHOLD  = 60
_REVIEW_THRESHOLD = 30


def _fmt_inr(amount: float) -> str:
    if amount >= 1_00_00_000:
        return f"Rs.{amount / 1_00_00_000:.2f} Cr"
    if amount >= 1_00_000:
        return f"Rs.{amount / 1_00_000:.2f} L"
    return f"Rs.{amount:,.0f}"


def _statute_cite(legal_refs: dict, section_num: int, max_chars: int = 180) -> str:
    """
    Returns a bracketed statutory citation from the Bare Act if available.
    Labels the source as 'Bare Act' -- never as 'PDF'.
    """
    if not legal_refs.get("bare_act_available"):
        return ""
    text = legal_refs.get("sections", {}).get(section_num, "")
    if not text:
        return ""
    excerpt = text[:max_chars].rstrip() + ("..." if len(text) > max_chars else "")
    return f' [Bare Act: "{excerpt}"]'


def evaluate_compliance(context: dict) -> dict:
    """
    Applies Companies Act 2013 compliance rules to the Context Object.
    Reasoning strings include verbatim excerpts from the Statutory Bare Act
    where applicable.

    Decision Object schema:
    {
        "decision_id":              str (UUID4),
        "transaction_id":           str,
        "timestamp_utc":            str (ISO-8601),
        "verdict":                  "BLOCK" | "REVIEW" | "PASS",
        "risk_score":               int (0-100),
        "act_sections_triggered":   [...],
        "statute_clauses_applied":  [...],   # section numbers cited from Bare Act
        "reasoning":                [...],
        "lineage_ids_used":         [...],
        "recommended_action":       str
    }
    """
    txn          = context["transaction"]
    struck_off   = context["struck_off_entities"]
    disqualified = context["disqualified_directors"]
    risk_flags   = context["risk_flags"]
    amount_inr   = txn.get("amount_inr", 0)
    legal_refs   = context.get("legal_references", {})

    reasoning              = []
    lineage_ids            = []
    sections_triggered     = []
    statute_clauses        = []
    risk_score             = 0

    # RULE-01 | Section 248 -- counterparty is a struck-off company
    for entry in struck_off:
        risk_score = min(100, risk_score + _WEIGHT_STRUCK_OFF_ENTITY)
        lineage_ids.append(entry["watchlist_id"])
        sections_triggered.append("Section 248")
        statute_clauses.append(248)
        cite = _statute_cite(legal_refs, 248)
        reasoning.append(
            f"RULE-01 [Sec 248]: Counterparty '{entry['entity_name']}' is struck off "
            f"per MCA order {entry['roc_order_reference']} (ID: {entry['watchlist_id']}) "
            f"-- risk +{_WEIGHT_STRUCK_OFF_ENTITY}.{cite}"
        )

    # RULE-02 | Section 164(2) -- director/authorising DIN is disqualified
    for entry in disqualified:
        risk_score = min(100, risk_score + _WEIGHT_DISQUALIFIED_DIRECTOR)
        lineage_ids.append(entry["watchlist_id"])
        sections_triggered.append("Section 164(2)")
        statute_clauses.append(164)
        cite = _statute_cite(legal_refs, 164)
        reasoning.append(
            f"RULE-02 [Sec 164(2)]: DIN {entry['din']} ({entry.get('director_name','Unknown')}) "
            f"is disqualified per MCA order {entry['roc_order_reference']} "
            f"(ID: {entry['watchlist_id']}) -- risk +{_WEIGHT_DISQUALIFIED_DIRECTOR}.{cite}"
        )

    # RULE-03 | Section 185 -- loan to director strictly prohibited
    if context.get("section_185_applicable"):
        risk_score = min(100, risk_score + _WEIGHT_SEC185_LOAN_TO_DIRECTOR)
        sections_triggered.append("Section 185")
        statute_clauses.append(185)
        cite = _statute_cite(legal_refs, 185)
        reasoning.append(
            f"RULE-03 [Sec 185]: Direct loan/advance of {_fmt_inr(amount_inr)} to a director. "
            f"Section 185 categorically prohibits companies from advancing loans to directors "
            f"-- risk +{_WEIGHT_SEC185_LOAN_TO_DIRECTOR}.{cite}"
        )

    # RULE-04 | Section 188 -- RPT threshold breach
    if context.get("section_188_applicable") and "related_party" in risk_flags:
        category  = txn.get("section_188_category", "")
        threshold = _SEC188_THRESHOLDS_INR.get(category, 0)
        if amount_inr >= threshold > 0:
            risk_score = min(100, risk_score + _WEIGHT_SEC188_RPT_BREACH)
            sections_triggered.append("Section 188")
            statute_clauses.append(188)
            cite = _statute_cite(legal_refs, 188)
            reasoning.append(
                f"RULE-04 [Sec 188]: RPT ({category.replace('_', ' ')}) of "
                f"{_fmt_inr(amount_inr)} meets or exceeds approval threshold of "
                f"{_fmt_inr(threshold)}. Board/special resolution required "
                f"-- risk +{_WEIGHT_SEC188_RPT_BREACH}.{cite}"
            )

    # RULE-05 | Section 188 -- related party below threshold, disclosure required
    if "related_party" in risk_flags and "Section 188" not in sections_triggered:
        risk_score = min(100, risk_score + _WEIGHT_RELATED_PARTY_FLAG)
        sections_triggered.append("Section 188 (disclosure)")
        statute_clauses.append(188)
        cite = _statute_cite(legal_refs, 188)
        reasoning.append(
            f"RULE-05 [Sec 188]: Transaction involves related party "
            f"({txn['counterparty'].get('relationship_to_initiator','N/A')}). "
            f"Disclosure in Board's Report mandatory "
            f"-- risk +{_WEIGHT_RELATED_PARTY_FLAG}.{cite}"
        )

    # RULE-06 | High-value property -- stamp duty and valuation certificate
    if "high_value_property" in risk_flags:
        risk_score = min(100, risk_score + _WEIGHT_HIGH_VALUE_PROPERTY)
        reasoning.append(
            f"RULE-06: High-value property transfer ({_fmt_inr(amount_inr)}). "
            f"Stamp duty compliance and registered valuation certificate required "
            f"-- risk +{_WEIGHT_HIGH_VALUE_PROPERTY}."
        )

    # Verdict
    if risk_score >= _BLOCK_THRESHOLD:
        verdict = "BLOCK"
        recommended_action = (
            "Immediately suspend transaction. Mandatory reporting to the Registrar of Companies (RoC). "
            "Board must convene within 48 hours. Engage Company Secretary for NCLT/MCA e-filing. "
            "Retain all board minutes and transaction documents for SFIO inspection."
        )
    elif risk_score >= _REVIEW_THRESHOLD:
        verdict = "REVIEW"
        recommended_action = (
            "Hold transaction pending enhanced due diligence. Obtain board resolution under Section 188. "
            "Verify director DIN status on MCA21 portal. "
            "Seek legal opinion from a practicing Company Secretary."
        )
    else:
        verdict = "PASS"
        recommended_action = (
            "Transaction cleared. Ensure routine disclosure in Board's Report under "
            "Section 134 of the Companies Act, 2013. Standard record-keeping applies."
        )

    if not reasoning:
        reasoning.append(
            "RULE-00: No Companies Act 2013 violation indicators detected. "
            "Transaction is within statutory thresholds and no watchlist matches found."
        )

    return {
        "decision_id":             str(uuid.uuid4()),
        "transaction_id":          txn["transaction_id"],
        "timestamp_utc":           datetime.now(timezone.utc).isoformat(),
        "verdict":                 verdict,
        "risk_score":              risk_score,
        "act_sections_triggered":  list(dict.fromkeys(sections_triggered)),
        "statute_clauses_applied": sorted(set(statute_clauses)),
        "reasoning":               reasoning,
        "lineage_ids_used":        lineage_ids,
        "recommended_action":      recommended_action,
    }
