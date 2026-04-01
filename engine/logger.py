"""
engine/logger.py
Standalone module -- function: commit_to_ledger(context, decision)

Maps Context and Decision objects into the Audit Record schema and strictly
appends one JSON line to data/audit_log.jsonl (append-only).
Includes statute_clauses_applied and bare_act_source for full traceability.
No side effects beyond file I/O. All visual pacing is handled by the UI layer.
"""
import json
import os
from datetime import datetime, timezone

_AUDIT_LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "audit_log.jsonl")


def commit_to_ledger(context: dict, decision: dict) -> dict:
    """
    Constructs an Audit Record and appends it as a single JSON line.

    Audit Record schema:
    {
        "audit_id":                  str,
        "logged_at_utc":             str,
        "transaction_id":            str,
        "initiating_company_cin":    str,
        "initiating_company_name":   str,
        "counterparty_name":         str,
        "counterparty_cin":          str,
        "amount_inr":                float,
        "transaction_type":          str,
        "section_188_category":      str | null,
        "section_185_applicable":    bool,
        "matched_watchlist_ids":     [...],
        "struck_off_entity_ids":     [...],
        "disqualified_director_ids": [...],
        "risk_flags_observed":       [...],
        "act_sections_triggered":    [...],
        "statute_clauses_applied":   [...],
        "bare_act_source":           str,
        "verdict":                   str,
        "risk_score":                int,
        "reasoning_summary":         [...],
        "lineage_ids_used":          [...],
        "recommended_action":        str
    }
    """
    txn          = context["transaction"]
    initiating   = txn["initiating_company"]
    counterparty = txn.get("counterparty", {})
    legal_refs   = context.get("legal_references", {})

    audit_record = {
        "audit_id":                  decision["decision_id"],
        "logged_at_utc":             datetime.now(timezone.utc).isoformat(),
        "transaction_id":            txn["transaction_id"],
        "initiating_company_cin":    initiating.get("cin", ""),
        "initiating_company_name":   initiating.get("name", ""),
        "counterparty_name":         counterparty.get("name", counterparty.get("director_name", "")),
        "counterparty_cin":          counterparty.get("cin", counterparty.get("din", "")),
        "amount_inr":                txn.get("amount_inr", 0),
        "transaction_type":          txn.get("transaction_type", ""),
        "section_188_category":      txn.get("section_188_category"),
        "section_185_applicable":    txn.get("section_185_applicable", False),
        "matched_watchlist_ids":     [e["watchlist_id"] for e in context["matched_watchlist_entries"]],
        "struck_off_entity_ids":     [e["watchlist_id"] for e in context["struck_off_entities"]],
        "disqualified_director_ids": [e["watchlist_id"] for e in context["disqualified_directors"]],
        "risk_flags_observed":       context["risk_flags"],
        "act_sections_triggered":    decision["act_sections_triggered"],
        "statute_clauses_applied":   decision.get("statute_clauses_applied", []),
        "bare_act_source":           legal_refs.get("bare_act_source", ""),
        "verdict":                   decision["verdict"],
        "risk_score":                decision["risk_score"],
        "reasoning_summary":         decision["reasoning"],
        "lineage_ids_used":          decision["lineage_ids_used"],
        "recommended_action":        decision["recommended_action"],
    }

    log_path = os.path.abspath(_AUDIT_LOG_PATH)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(audit_record, ensure_ascii=False) + "\n")

    return audit_record


def read_audit_log() -> list:
    """Returns all audit records from audit_log.jsonl as a list of dicts."""
    log_path = os.path.abspath(_AUDIT_LOG_PATH)
    if not os.path.exists(log_path) or os.path.getsize(log_path) == 0:
        return []
    records = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records
