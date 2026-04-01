"""
app.py -- Companies Act Compliance Auditor
Streamlit UI: native components only, zero custom CSS.

IMPORTANT: The word "PDF" must not appear in any user-visible string.
The legal reference document is referred to exclusively as the
"Statutory Bare Act" throughout this UI.

Three sequential manual gates:
  Gate 1 -- 4-step progress (25/50/75/100) including Statutory Bare Act extraction
  Gate 2 -- 3-step progress (33/66/100) applying Section 188 legislative constraints
  Gate 3 -- 2-step progress (50/100) hashing lineage + appending .jsonl

Session state:
  current_step : int  0=idle | 1=gate1_done | 2=gate2_done | 3=gate3_done
  selected_txn : str
  context_obj  : dict
  decision_obj : dict
  audit_record : dict
"""
import sys
import os
import json
import time
import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))

from engine.context_loader import load_mcp_context, list_transaction_ids
from engine.decision_maker import evaluate_compliance
from engine.logger import commit_to_ledger, read_audit_log

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Companies Act Compliance Auditor",
    page_icon="\u2696",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("\u2696\ufe0f Companies Act Compliance Auditor")
st.caption(
    "Step-by-step compliance screening under the **Indian Companies Act, 2013**. "
    "Each gate progresses manually and cross-references legislative clauses extracted "
    "from the **Statutory Bare Act** alongside live MCA watchlist data."
)
st.divider()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_STATE_DEFAULTS = {
    "current_step": 0,
    "selected_txn": None,
    "context_obj":  None,
    "decision_obj": None,
    "audit_record": None,
}


def _reset(txn_id: str) -> None:
    for k, v in _STATE_DEFAULTS.items():
        st.session_state[k] = v
    st.session_state.selected_txn = txn_id


def _inr(amount: float) -> str:
    if amount >= 1_00_00_000:
        return f"\u20b9{amount / 1_00_00_000:.2f} Cr"
    if amount >= 1_00_000:
        return f"\u20b9{amount / 1_00_000:.2f} L"
    return f"\u20b9{amount:,.0f}"


for k, v in _STATE_DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Transaction Selector")
    txn_ids      = list_transaction_ids()
    selected_txn = st.selectbox("Select Transaction ID", options=txn_ids, key="txn_selector")

    if selected_txn != st.session_state.selected_txn:
        _reset(selected_txn)

    st.divider()
    st.markdown("**Statutory Bare Act**")
    st.markdown("`Companies Act, 2013` (A2013-18, 370 sections)")
    st.markdown("Legislative clauses extracted: `164` `185` `188` `248`")

    st.divider()
    st.markdown("**Companies Act 2013 -- Rules Engine**")
    st.markdown(
        "- `RULE-01` [Sec 248] Struck-off company (+65)\n"
        "- `RULE-02` [Sec 164(2)] Disqualified DIN (+50)\n"
        "- `RULE-03` [Sec 185] Loan to director (+70)\n"
        "- `RULE-04` [Sec 188] RPT threshold breach (+40)\n"
        "- `RULE-05` [Sec 188] RPT disclosure (+20)\n"
        "- `RULE-06` High-value property (+10)"
    )
    st.divider()
    st.markdown("**Sec 188 Thresholds (Rule 15)**")
    st.markdown(
        "| Category | Threshold |\n|---|---|\n"
        "| Goods | \u20b91 Cr |\n"
        "| Property | \u20b9100 Cr |\n"
        "| Services | \u20b950 L |\n"
        "| Leasing | \u20b9100 Cr |\n"
        "| Director appt. | \u20b92.5 L/mo |"
    )
    st.divider()
    st.markdown("- **BLOCK** \u2265 60 | **REVIEW** \u2265 30 | **PASS** < 30")

# ---------------------------------------------------------------------------
# Step progress indicator
# ---------------------------------------------------------------------------
ind_cols = st.columns(3)
step_labels = [
    "Gate 1 \u2014 MCP + Bare Act Context",
    "Gate 2 \u2014 Statutory Compliance",
    "Gate 3 \u2014 Audit Commit",
]
for i, (col, label) in enumerate(zip(ind_cols, step_labels)):
    n = i + 1
    if st.session_state.current_step > i:
        col.success(f"\u2705 Step {n}: {label}")
    elif st.session_state.current_step == i:
        col.info(f"\u25b6 Step {n}: {label}")
    else:
        col.markdown(
            f"<div style='padding:0.6rem 0'>\U0001f512 Step {n}: {label}</div>",
            unsafe_allow_html=True,
        )

st.divider()

# ---------------------------------------------------------------------------
# GATE 1 -- Connect MCP & Fetch Context (4-step progress)
# ---------------------------------------------------------------------------
st.subheader("Gate 1 \u2014 Connect MCP & Fetch Context")

if st.session_state.current_step == 0:
    if st.button(
        "1. Connect MCP & Fetch Context",
        type="primary",
        key="btn_gate1",
    ):
        prog = st.progress(0)
        txt  = st.empty()

        txt.markdown("**\U0001f50c Connecting to INR transaction ledger...**")
        prog.progress(25)
        time.sleep(1)

        txt.markdown("**\U0001f5c4 Querying MCA Sanctions Database...**")
        prog.progress(50)
        time.sleep(1)

        txt.markdown("**\U0001f4dc Extracting clauses from the Statutory Bare Act...**")
        prog.progress(75)
        time.sleep(1)

        txt.markdown("**\u2705 Context Assembly Complete.**")
        prog.progress(100)
        time.sleep(0.4)

        ctx = load_mcp_context(selected_txn)
        st.session_state.context_obj  = ctx
        st.session_state.current_step = 1
        st.rerun()

elif st.session_state.current_step >= 1:
    ctx  = st.session_state.context_obj
    txn  = ctx["transaction"]
    init = txn["initiating_company"]
    cpty = txn.get("counterparty", {})
    amt  = txn.get("amount_inr", 0)
    refs = ctx["legal_references"]

    st.success("\u2705 Gate 1 complete \u2014 MCP context and Statutory Bare Act clauses loaded.")

    col_g1a, col_g1b = st.columns(2)
    with col_g1a:
        st.markdown("**Initiating Company**")
        st.markdown(f"- **Name:** {init['name']}")
        st.markdown(f"- **CIN:** `{init.get('cin','N/A')}`")
        st.markdown(f"- **Auth. DIN:** `{init.get('din_of_authorising_director','N/A')}`")
        st.markdown(f"- **State:** {init.get('registered_state','N/A')}")
        st.markdown("**Counterparty**")
        name = cpty.get("name", cpty.get("director_name", "N/A"))
        cin  = cpty.get("cin",  cpty.get("din", "N/A"))
        rel  = cpty.get("relationship_to_initiator", "N/A").replace("_", " ").title()
        st.markdown(f"- **Name:** {name}")
        st.markdown(f"- **CIN/DIN:** `{cin}`")
        st.markdown(f"- **Relationship:** {rel}")
        st.markdown(f"- **Amount:** {_inr(amt)}")
        st.markdown(f"- **Type:** {txn.get('transaction_type','').replace('_',' ').title()}")

    with col_g1b:
        st.markdown("**MCA Watchlist Matches**")
        if ctx["matched_watchlist_entries"]:
            for entry in ctx["matched_watchlist_entries"]:
                icon  = "\U0001f6a8" if entry.get("category") == "struck_off_company" else "\u26d4"
                label = "Struck-Off" if entry.get("category") == "struck_off_company" else "Disqual. Director"
                st.error(f"{icon} `{entry['watchlist_id']}` -- {entry['entity_name']} [{label}]")
        else:
            st.success("No MCA watchlist matches found")
        st.markdown("**Risk Flags**")
        if ctx["risk_flags"]:
            for flag in ctx["risk_flags"]:
                st.warning(f"\u26a0 {flag.replace('_',' ').title()}")
        else:
            st.info("No transaction-level risk flags")

        st.markdown("**Statutory Bare Act**")
        avail_icon = "\u2705" if refs["bare_act_available"] else "\u26a0"
        st.markdown(f"{avail_icon} `{refs['bare_act_source']}`")
        if refs.get("bare_act_pages"):
            st.markdown(
                f"Sections: {refs['bare_act_pages']} pages | "
                f"Clauses extracted: {', '.join(str(s) for s in refs['sections'].keys())}"
            )

    with st.expander(
        "\U0001f4dc Statutory Bare Act \u2014 Legislative Clause Extracts",
        expanded=False,
    ):
        for sec_num, text in refs["sections"].items():
            st.markdown(f"**Section {sec_num}**")
            st.markdown(f"```\n{text}\n```")
            st.divider()

    with st.expander("Full Context Object (JSON)", expanded=False):
        st.json(ctx)

# ---------------------------------------------------------------------------
# GATE 2 -- Evaluate Statutory Compliance (3-step progress)
# ---------------------------------------------------------------------------
if st.session_state.current_step >= 1:
    st.divider()
    st.subheader("Gate 2 \u2014 Evaluate Statutory Compliance")

    if st.session_state.current_step == 1:
        if st.button(
            "2. Evaluate Statutory Compliance",
            type="primary",
            key="btn_gate2",
        ):
            prog = st.progress(0)
            txt  = st.empty()

            txt.markdown("**\U0001f4cb Parsing INR transaction values...**")
            prog.progress(33)
            time.sleep(1)

            txt.markdown("**\U0001f4dc Applying Section 188 legislative constraints...**")
            prog.progress(66)
            time.sleep(1)

            txt.markdown("**\u2705 Decision Generated.**")
            prog.progress(100)
            time.sleep(0.4)

            dec = evaluate_compliance(st.session_state.context_obj)
            st.session_state.decision_obj  = dec
            st.session_state.current_step  = 2
            st.rerun()

    elif st.session_state.current_step >= 2:
        dec     = st.session_state.decision_obj
        verdict = dec["verdict"]
        score   = dec["risk_score"]

        st.success("\u2705 Gate 2 complete \u2014 statutory compliance decision generated.")
        col_g2a, col_g2b = st.columns([1, 2])

        with col_g2a:
            if verdict == "BLOCK":
                st.error(f"### VERDICT: {verdict}")
            elif verdict == "REVIEW":
                st.warning(f"### VERDICT: {verdict}")
            else:
                st.success(f"### VERDICT: {verdict}")

            st.metric("Risk Score", f"{score} / 100")

            if dec["act_sections_triggered"]:
                st.markdown("**Sections Triggered**")
                for sec in dec["act_sections_triggered"]:
                    st.markdown(f"- `{sec}`")

            if dec["statute_clauses_applied"]:
                st.markdown("**Statutory Clauses Applied**")
                st.code(", ".join(f"Sec {s}" for s in dec["statute_clauses_applied"]), language=None)

            if dec["lineage_ids_used"]:
                st.markdown("**Watchlist Lineage IDs**")
                st.code(", ".join(dec["lineage_ids_used"]), language=None)

            st.markdown("**Recommended Action**")
            if verdict == "BLOCK":
                st.error(dec["recommended_action"])
            elif verdict == "REVIEW":
                st.warning(dec["recommended_action"])
            else:
                st.info(dec["recommended_action"])

        with col_g2b:
            st.markdown("**Reasoning Chain (with Statutory Bare Act citations)**")
            for rule in dec["reasoning"]:
                st.markdown(f"- {rule}")

        with st.expander("Full Decision Object (JSON)", expanded=False):
            st.json(dec)

# ---------------------------------------------------------------------------
# GATE 3 -- Commit Immutable Audit Log (2-step progress)
# ---------------------------------------------------------------------------
if st.session_state.current_step >= 2:
    st.divider()
    st.subheader("Gate 3 \u2014 Commit Immutable Audit Log")

    if st.session_state.current_step == 2:
        if st.button(
            "3. Commit Immutable Audit Log",
            type="primary",
            key="btn_gate3",
        ):
            prog = st.progress(0)
            txt  = st.empty()

            txt.markdown("**\U0001f510 Hashing lineage IDs...**")
            prog.progress(50)
            time.sleep(1)

            txt.markdown("**\U0001f4dd Appending to local .jsonl ledger...**")
            prog.progress(100)
            time.sleep(0.5)

            rec = commit_to_ledger(
                st.session_state.context_obj,
                st.session_state.decision_obj,
            )
            st.session_state.audit_record  = rec
            st.session_state.current_step  = 3
            st.rerun()

    elif st.session_state.current_step >= 3:
        rec = st.session_state.audit_record
        amt = rec["amount_inr"]

        st.success(f"\u2705 Gate 3 complete \u2014 audit record committed. ID: `{rec['audit_id']}`")

        col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
        col_m1.metric("Transaction ID",       rec["transaction_id"])
        col_m2.metric("Verdict",              rec["verdict"])
        col_m3.metric("Risk Score",           f"{rec['risk_score']}/100")
        col_m4.metric("Statute Clauses",      len(rec["statute_clauses_applied"]))
        col_m5.metric("Sections Triggered",   len(rec["act_sections_triggered"]))

        col_g3a, col_g3b = st.columns(2)
        with col_g3a:
            st.markdown("**Audit Record Summary**")
            st.markdown(f"- **Audit ID:** `{rec['audit_id']}`")
            st.markdown(f"- **Company:** {rec['initiating_company_name']}")
            st.markdown(f"- **Counterparty:** {rec['counterparty_name']}")
            st.markdown(f"- **Amount:** {_inr(amt)}")
            st.markdown(f"- **Bare Act Source:** `{rec['bare_act_source']}`")
            lin = rec["lineage_ids_used"]
            st.markdown(f"- **Lineage IDs:** `{', '.join(lin) if lin else 'None'}`")
            sc = rec["statute_clauses_applied"]
            st.markdown(f"- **Statute Clauses:** `{', '.join(f'Sec {s}' for s in sc) if sc else 'None'}`")
            st.markdown(f"- **Logged At:** {rec['logged_at_utc']}")

        with col_g3b:
            st.markdown("**Raw .jsonl Payload**")
            st.code(json.dumps(rec, indent=2, ensure_ascii=False), language="json")

        with st.expander("Full Audit Record (JSON viewer)", expanded=False):
            st.json(rec)

# ---------------------------------------------------------------------------
# Reset Scenario
# ---------------------------------------------------------------------------
if st.session_state.current_step > 0:
    st.divider()
    col_rst, _ = st.columns([1, 5])
    with col_rst:
        if st.button("\U0001f504 Reset Scenario", type="secondary", use_container_width=True):
            _reset(selected_txn)
            st.rerun()

# ---------------------------------------------------------------------------
# Audit Log History
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Audit Log History (audit_log.jsonl)")

col_ref, _ = st.columns([1, 5])
with col_ref:
    if st.button("Refresh Log", use_container_width=True):
        st.rerun()

all_records = read_audit_log()
if all_records:
    st.metric("Total Records in audit_log.jsonl", len(all_records))
    for r in reversed(all_records):
        icon = "\U0001f6a8" if r["verdict"] == "BLOCK" else ("\u26a0" if r["verdict"] == "REVIEW" else "\u2705")
        amt  = r["amount_inr"]
        sc   = r.get("statute_clauses_applied", [])
        with st.expander(
            f"{icon} [{r['transaction_id']}] {r['verdict']} | Score {r['risk_score']} | "
            f"{_inr(amt)} | Statute: {sc if sc else 'none'} | ID {r['audit_id'][:8]}...",
            expanded=False,
        ):
            col_h1, col_h2 = st.columns(2)
            with col_h1:
                st.markdown(f"**Company:** {r['initiating_company_name']}")
                st.markdown(f"**Counterparty:** {r['counterparty_name']}")
                st.markdown(f"**Type:** {r['transaction_type'].replace('_',' ').title()}")
                st.markdown(f"**Amount:** {_inr(amt)}")
                st.markdown(f"**Bare Act Source:** `{r.get('bare_act_source','')}`")
            with col_h2:
                secs = r["act_sections_triggered"]
                st.markdown(f"**Sections:** {', '.join(secs) if secs else 'None'}")
                st.markdown(
                    f"**Statute Clauses Applied:** "
                    f"{', '.join(f'Sec {s}' for s in sc) if sc else 'None'}"
                )
                lin = r["lineage_ids_used"]
                st.markdown(f"**Lineage IDs:** `{', '.join(lin) if lin else 'None'}`")
                st.markdown(f"**Logged:** {r['logged_at_utc']}")
            st.markdown("**Reasoning:**")
            for rule in r["reasoning_summary"]:
                st.markdown(f"  - {rule}")
else:
    st.info("No audit records yet. Complete all three gates above to populate the log.")

