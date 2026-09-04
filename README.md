# Project 1: GenAI — Enterprise Risk Intelligence Assistant

An enterprise-grade, regulated Generative AI assistant embedded inside the **Enterprise Risk Management (ERM) Portal** to assist risk analysts, managers, compliance officers, and auditors in searching and summarizing approved enterprise risk information.

---

## Business Objective
Risk analysts face fragmented enterprise repositories containing thousands of risk policies, risk appetite statements (RAS), controls (SOX 404, ITGC), audit findings, operational risk incidents, and supervisory documentation.

This system provides a high-assurance AI assistant built specifically for banking and financial environments, adhering to the core principle: **Zero Unauthorized Context Exposure**.

---

## Core Architecture & Flow

```
                     ERM Portal (Web UI)
                             │
                             ▼
                     Authentication
              (User Identity, BU, Clearance)
                             │
                             ▼
                  Authorization Layer
               RBAC + ABAC + Entitlements
              (Enforced BEFORE Retrieval!)
                             │
                             ▼
                     API Gateway
                 ┌───────────┴───────────┐
                 ▼                       ▼
          Input Guardrails        Security Checks
      (Direct Injection, PII)   (Rate limits, quotas)
                 └───────────┬───────────┘
                             │
                             ▼
                     Query Processing
                             │
                             ▼
                     Access Filtering
               (Strictly Authorized Scope)
                             │
                             ▼
                     Hybrid Retrieval
                 ┌───────────┴───────────┐
                 ▼                       ▼
           Vector Search           Keyword Search
         (Semantic Cosine)         (Lexical BM25)
                 └───────────┬───────────┘
                             │
                             ▼
                         Reranking
                 (RRF + Score Thresholding)
                             │
                             ▼
                     Permission Check
                             │
                             ▼
                         LLM / RAG
          (Structural XML Boundary: Evidence as DATA)
                             │
                             ▼
                     Output Guardrails
                 ┌───────────┴───────────┐
                 ▼                       ▼
         Source Citations         Sensitive Data Check
       (Grounded in docs)          (PII / Secret mask)
                 └───────────┬───────────┘
                             │
                             ▼
                     Audit Logging
         (SHA-256 Chained Immutable Ledger)
                             │
                             ▼
                  Human-in-the-Loop (HITL)
             (Risk Analyst: Approve / Amend / Reject)
                             │
                             ▼
                     ERM Portal Response
```

---

## Key Enterprise Talking Points

### 1. Pre-Retrieval RBAC + ABAC Enforcement
- **Crucial Rule:** Permissions are enforced **before** retrieval, never after the LLM generates an answer.
- Unauthorized documents are excluded before vector/keyword indexing occurs, ensuring the LLM is never exposed to restricted information.
- Combines:
  - **RBAC**: Role-based permissions (`Risk_Analyst`, `Risk_Manager`, `Compliance_Analyst`, `Auditor`, `Administrator`).
  - **ABAC**: Clearance hierarchy (`Public` < `Internal` < `Confidential` < `Restricted`), regional jurisdictions (`US`, `EMEA`, `Global`), and need-to-know entitlement tags.

### 2. Banking-Grade Data Protection
- Sensitive enterprise documents and prompts are protected at every tier:
  - Input & output PII detection/masking (SSNs, credit cards, bank accounts, emails).
  - Restricted logging: Only sanitized, PII-masked queries are persisted in the audit ledger.
  - Zero-leakage data boundaries preventing external model contamination.

### 3. Prompt-Injection Protection (Dual-Vector)
- **Direct Injection Defense:** Intercepts jailbreaks and override attempts ("Ignore previous instructions", "Reveal system prompt", "Developer mode") at the API gateway before model execution.
- **Indirect Document Poisoning Defense:** Treats retrieved enterprise documents as **untrusted data**, not instructions. Passages are encapsulated in strict XML boundaries (`<evidence_item><untrusted_content_data>...</untrusted_content_data></evidence_item>`), preventing embedded payloads from hijacking model behavior.

### 4. Hallucination Guardrails & Safe Abstention
- **Grounding & Faithfulness Verification:** Calculates overlap between generated claims and retrieved evidence chunks.
- **Citation Validation:** Enforces bracketed source identifiers (`[DOC-POL-001]`). Any ungrounded or hallucinated citations are flagged.
- **Safe Abstention:** If retrieval confidence falls below 0.50 or no authorized evidence exists:
  > *"I couldn't find sufficient supporting information in the authorized knowledge sources."*

### 5. Tamper-Evident Audit Logging
- Every query event is recorded with: `request_id`, `timestamp`, `user_id`, `user_role`, `masked_query`, `retrieved_doc_ids`, `confidence_score`, `grounding_score`, `guardrail_results`, and `approval_status`.
- Cryptographic SHA-256 hash chaining links every record to the previous one, allowing 1-click regulatory verification of ledger integrity.

### 6. Human-in-the-Loop (HITL) Governance
- The AI assists but does **not** make uncontrolled, unilateral risk or regulatory determinations.
- Outputs use non-definitive advisory phrasing ("Based on retrieved evidence, there appears to be a potential control deficiency...").
- Integrated review queue enables Risk Analysts to review, amend, approve, or reject assessments with mandatory justification notes.

---

## Running the Application

### 1. Launch Server
Double-click `run.bat` or execute:
```powershell
python -m uvicorn backend.server:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Access the ERM Portal
Open your browser to:
[http://127.0.0.1:8000](http://127.0.0.1:8000)

### 3. Run Automated Tests
```powershell
python -m unittest tests/test_enterprise_risk.py
```
*(10 tests covering all 7 pillars pass in ~0.02s)*

---

## Interactive Features in the Portal
1. **Persona Switcher**: Switch between Sarah Jenkins (Analyst), Marcus Vance (Manager), Elena Rostova (Compliance), David Kim (Auditor), and System Administrator in real time.
2. **Live 7-Stage Pipeline Inspector**: Step-by-step visualizer revealing ABAC filtering, input guardrails, hybrid search scoring, reranker fusion, sandboxed prompt synthesis, output guardrails, and audit hashing.
3. **Document Vault**: Visualizes green (authorized) vs red (restricted) locks across 20+ enterprise documents based on active user attributes.
4. **HITL Queue**: Review drafted assessments, amend text, approve or reject findings with audit trail recording.
5. **Security & Guardrail Lab**: 1-click attack simulations for direct injection, indirect document poisoning, PII redaction, cross-BU escalation, and safe abstention.
