"""
engine/context_loader.py
Standalone module -- function: load_mcp_context()

Reads static MCA JSON files AND extracts key legislative clauses from the
Statutory Bare Act (Companies_Act_2013.pdf) using pypdf.
Returns a combined Context Object.
No side effects beyond file I/O. All visual pacing is handled by the UI layer.

Statutory Bare Act page anchors (A2013-18, 370 pages):
  Section 164 -- page 112  (Disqualifications for appointment of director)
  Section 185 -- page 124  (Loans to directors -- prohibition)
  Section 188 -- page 128  (Related party transactions)
  Section 248 -- page 166  (Power of Registrar to remove name from register)
"""
import json
import os
import re
from typing import Optional

try:
    from pypdf import PdfReader
    _PYPDF_AVAILABLE = True
except ImportError:
    _PYPDF_AVAILABLE = False

_BASE_DIR         = os.path.join(os.path.dirname(__file__), "..", "data")
_BARE_ACT_PATH    = os.path.join(_BASE_DIR, "Companies_Act_2013.pdf")

# Page indices (0-based) where each section begins in the Statutory Bare Act
_BARE_ACT_PAGE_ANCHORS = {
    164: 111,   # 0-based -> page 112
    185: 123,   # 0-based -> page 124
    188: 127,   # 0-based -> page 128
    248: 165,   # 0-based -> page 166
}
_BARE_ACT_EXTRACT_CHARS = 700   # characters to capture per section


def _load_json(filename: str) -> list:
    path = os.path.join(_BASE_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _norm(value: str) -> str:
    return value.strip().lower()


def _extract_bare_act_sections() -> dict:
    """
    Opens the Statutory Bare Act and extracts the opening text of each
    key legislative section using targeted page reads.

    Returns a dict under key 'sections' keyed by section number.
    Falls back to authoritative hardcoded excerpts if the Bare Act is unavailable.
    """
    fallback = {
        164: (
            "164. Disqualifications for appointment of director. (1) A person shall not be "
            "eligible for appointment as a director of a company, if he is of unsound mind; "
            "he is an undischarged insolvent; he has been convicted of an offence and sentenced "
            "to imprisonment for not less than six months. (2) No person who is or has been a "
            "director of a company which has not filed financial statements or annual returns for "
            "any continuous period of three financial years shall be eligible to be re-appointed "
            "as a director of that company or appointed in other company for a period of five "
            "years from the date on which the said company fails to do so."
        ),
        185: (
            "185. Loans to directors, etc. (1) No company shall, directly or indirectly, "
            "advance any loan, including any loan represented by a book debt to, or give any "
            "guarantee or provide any security in connection with any loan taken by, any "
            "director of company, or of a company which is its holding company or any partner "
            "or relative of any such director; or any firm in which any such director or "
            "relative is a partner."
        ),
        188: (
            "188. Related party transactions. (1) Except with the consent of the Board of "
            "Directors given by a resolution at a meeting of the Board and subject to such "
            "conditions as may be prescribed, no company shall enter into any contract or "
            "arrangement with a related party with respect to sale, purchase or supply of any "
            "goods or materials; selling or otherwise disposing of, or buying, property of any "
            "kind; leasing of property of any kind; availing or rendering of any services; "
            "appointment of any agent for purchase or sale of goods, materials, services or "
            "property."
        ),
        248: (
            "248. Power of Registrar to remove name of company from register of companies. "
            "(1) Where the Registrar has reasonable cause to believe that a company has failed "
            "to commence its business within one year of its incorporation; or a company is "
            "not carrying on any business or operation for a period of two immediately "
            "preceding financial years and has not made any application within such period for "
            "obtaining the status of a dormant company."
        ),
    }

    if not _PYPDF_AVAILABLE or not os.path.exists(_BARE_ACT_PATH):
        return {
            "bare_act_available": False,
            "bare_act_source":    "Companies_Act_2013.pdf (not found -- fallback text used)",
            "sections":           fallback,
        }

    extracted = {}
    try:
        reader = PdfReader(_BARE_ACT_PATH)
        for sec_num, page_idx in _BARE_ACT_PAGE_ANCHORS.items():
            if page_idx >= len(reader.pages):
                extracted[sec_num] = fallback[sec_num]
                continue

            # Read two consecutive pages to avoid truncation at a page boundary
            page_text = reader.pages[page_idx].extract_text() or ""
            if page_idx + 1 < len(reader.pages):
                page_text += "\n" + (reader.pages[page_idx + 1].extract_text() or "")

            m = re.search(rf"(?<!\d){sec_num}\.", page_text)
            if m:
                raw   = page_text[m.start(): m.start() + _BARE_ACT_EXTRACT_CHARS]
                clean = re.sub(r"  +", " ", raw).replace("\n", " ").strip()
                extracted[sec_num] = clean
            else:
                extracted[sec_num] = fallback[sec_num]

    except Exception:
        return {
            "bare_act_available": False,
            "bare_act_source":    "Companies_Act_2013.pdf (read error -- fallback text used)",
            "sections":           fallback,
        }

    return {
        "bare_act_available": True,
        "bare_act_source":    os.path.basename(_BARE_ACT_PATH),
        "bare_act_pages":     len(reader.pages),
        "sections":           extracted,
    }


def load_mcp_context(transaction_id: Optional[str] = None) -> dict:
    """
    Assembles the Context Object from:
      1. mock_transactions.json      -- transaction under review
      2. mock_sanctions.json         -- MCA watchlist (struck-off companies, disqualified DINs)
      3. Statutory Bare Act          -- extracted legislative clause text for key sections

    Context Object schema:
    {
        "transaction":               {...},
        "mca_watchlist":             [...],
        "matched_watchlist_entries": [...],
        "struck_off_entities":       [...],
        "disqualified_directors":    [...],
        "section_188_applicable":    bool,
        "section_185_applicable":    bool,
        "risk_flags":                [...],
        "legal_references": {
            "bare_act_available": bool,
            "bare_act_source":    str,
            "bare_act_pages":     int,
            "sections": {
                164: str,
                185: str,
                188: str,
                248: str,
            }
        }
    }
    """
    transactions = _load_json("mock_transactions.json")
    watchlist    = _load_json("mock_sanctions.json")

    if transaction_id:
        txn = next((t for t in transactions if t["transaction_id"] == transaction_id), None)
        if txn is None:
            raise ValueError(f"Transaction ID '{transaction_id}' not found.")
    else:
        txn = transactions[0]

    counterparty      = txn.get("counterparty", {})
    counterparty_cin  = _norm(counterparty.get("cin", ""))
    counterparty_name = _norm(counterparty.get("name", ""))
    counterparty_din  = _norm(counterparty.get("din", ""))
    auth_din          = _norm(txn["initiating_company"].get("din_of_authorising_director", ""))

    matched = []
    for entry in watchlist:
        entry_cin  = _norm(entry.get("cin", ""))
        entry_name = _norm(entry.get("entity_name", ""))
        entry_din  = _norm(entry.get("din", ""))

        hit = False
        if entry_cin  and counterparty_cin  and entry_cin == counterparty_cin:
            hit = True
        if entry_name and (entry_name == counterparty_name or entry_name == counterparty_din):
            hit = True
        if entry_din  and (entry_din == counterparty_din or entry_din == auth_din):
            hit = True
        if hit:
            matched.append(entry)

    struck_off   = [e for e in matched if e.get("category") == "struck_off_company"]
    disqualified = [e for e in matched if e.get("category") == "disqualified_director"]

    legal_refs = _extract_bare_act_sections()

    return {
        "transaction":               txn,
        "mca_watchlist":             watchlist,
        "matched_watchlist_entries": matched,
        "struck_off_entities":       struck_off,
        "disqualified_directors":    disqualified,
        "section_188_applicable":    txn.get("section_188_category") is not None,
        "section_185_applicable":    txn.get("section_185_applicable", False),
        "risk_flags":                txn.get("risk_flags", []),
        "legal_references":          legal_refs,
    }


def list_transaction_ids() -> list:
    """Returns all transaction IDs from mock data (no latency -- metadata only)."""
    return [t["transaction_id"] for t in _load_json("mock_transactions.json")]
