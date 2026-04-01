# Statutory Compliance Audit Engine (SCAE)

## Overview
The Statutory Compliance Audit Engine (SCAE) is an enterprise-grade Model Context Protocol (MCP) implementation designed to enforce deterministic, traceable compliance decisions based on the **Indian Companies Act, 2013**.

This system acts as an isolated, high-assurance context server and decision engine. It evaluates internal corporate transactions against external Ministry of Corporate Affairs (MCA) watchlists and specific legislative clauses extracted directly from the Statutory Bare Act. Every operation results in an append-only, immutable audit record mathematically linked to the exact data inputs used at the time of execution.

---

## Core Architecture

To guarantee absolute data sovereignty and prevent unauthorized state manipulation, this system operates on a strictly flat-file data architecture. **No external databases (SQL/NoSQL) are permitted.**

- **Context Ingestion (MCP):** Dynamically loads INR-denominated financial ledgers, MCA disqualified entity lists, and live textual extraction from the Statutory Bare Act (`Companies_Act_2013.pdf`).
- **Decision Engine:** A tightly constrained, deterministic Python evaluation module that cross-references ingested context against corporate legal thresholds (e.g., Section 188 - Related Party Transactions).
- **Immutable Ledger:** All inputs, execution UUIDs, and final decisions are hashed and appended to an air-gapped JSON Lines (`.jsonl`) audit log.
- **Execution Interface:** A state-driven Streamlit interface enforcing manual, gated execution to guarantee visual transparency of the underlying processing sequence.

---

## System Requirements

- **Python:** 3.9+
- **OS:** Linux, macOS, or Windows
- **Environment:** Strictly mandated Python Virtual Environment (`venv`)

---

## Project Structure

```
suraj_nalawade_mcp_compliences/
|-- app.py                          # Streamlit UI (three manual gates)
|-- requirements.txt                # Locked dependencies
|-- venv/                           # Python virtual environment
|-- engine/
|   |-- context_loader.py           # load_mcp_context()
|   |-- decision_maker.py           # evaluate_compliance()
|   |-- logger.py                   # commit_to_ledger()
|-- data/
    |-- mock_transactions.json      # INR financial ledger (5 transactions)
    |-- mock_sanctions.json         # MCA watchlist (struck-off + disqualified DINs)
    |-- Companies_Act_2013.pdf      # Statutory Bare Act (A2013-18, 370 pages)
    |-- audit_log.jsonl             # Append-only audit output
```

---

## How to Run

### Step 1 — Navigate to the project root

```cmd
cd "E:\Windows Software\Tesarract\suraj_nalawade_mcp_compliences"
```

### Step 2 — Activate the virtual environment

**Windows (Command Prompt):**
```cmd
venv\Scripts\activate
```

**Windows (PowerShell):**
```powershell
venv\Scripts\Activate.ps1
```

**Git Bash on Windows:**
```bash
source venv/Scripts/activate
```

**macOS / Linux:**
```bash
source venv/bin/activate
```

You should see `(venv)` appear at the start of your prompt.

### Step 3 — Install dependencies (first time only)

```cmd
pip install -r requirements.txt
```

Authorized packages only: `streamlit==1.35.0`, `pypdf==4.2.0`.

### Step 4 — Launch the application

```cmd
streamlit run app.py
```

The browser will open automatically at `http://localhost:8501`.

---

## Operational Workflow (Gated Execution)

The UI enforces sequential, manual execution through three gates:

| Gate | Button | Action |
|------|--------|--------|
| **Gate 1** | Connect MCP & Fetch Context | Loads transaction ledger, queries MCA watchlist, extracts Statutory Bare Act clauses |
| **Gate 2** | Evaluate Statutory Compliance | Runs the deterministic rules engine against ingested context |
| **Gate 3** | Commit Immutable Audit Log | Hashes lineage IDs and appends a permanent record to `audit_log.jsonl` |

Use the **Transaction Selector** in the sidebar to switch between the five demo scenarios (TXN-IN-001 through TXN-IN-005). Use **Reset Scenario** to clear state and re-run a transaction from scratch.

---

## Data Layer Specifications

All operational data lives in `/data`:

| File | Description |
|------|-------------|
| `mock_transactions.json` | 5 INR-denominated transactions covering BLOCK, REVIEW, and PASS scenarios |
| `mock_sanctions.json` | MCA watchlist: 3 struck-off companies (Sec 248), 2 disqualified directors (Sec 164) |
| `Companies_Act_2013.pdf` | Statutory Bare Act — Sections 164, 185, 188, 248 extracted at runtime via `pypdf` |
| `audit_log.jsonl` | Append-only audit output; clear with `truncate -s 0 data/audit_log.jsonl` before a fresh demo |

---

## Security & Compliance Notice

- **Immutability:** The `audit_log.jsonl` is strictly append-only. Manual editing violates audit trail integrity.
- **Statutory Updates:** If an amendment to the Companies Act is passed, replace `Companies_Act_2013.pdf` with the updated Statutory Bare Act to ensure the decision engine extracts currently enforced law.
- **Isolation:** All dependencies must be installed inside `venv`. Never install packages globally.
