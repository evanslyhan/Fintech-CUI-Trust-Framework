# U.S. Regulatory Mapping Reference (v1.0 — Aligned with Specification v0.4 / v0.4-AP)

**Status:** Illustrative Reference Mapping Overlay  
**Author:** Lenyen Han  
**License:** MIT  
**Core Specification:** [Specification v0.4](./protocol-spec-v0.4.md) · [Agentic Payment Extension v0.4-AP](./agentic-payment-extension.md)

---

## 1. Purpose & Architectural Principle

This document illustrates how the **Compliance Mapping Layer** (Specification v0.4, Section 8) configures the invariant five-layer control plane for selected U.S. federal consumer-finance regulations and fragmented state insurance regimes—**without modifying a single rule in the Core engine**.

Across all four regimes below, the same Core components and v0.4 runtime objects operate unchanged:

1. **Intent Classification Matrix + Action Object (`inform` / `advise` / `commit` / `transact` / `represent`) + Classification Assurance**
2. **Authorization Trigger + Post-AUTH Scoped Credential**
3. **Generation Boundary (Pre/Post-Generation Output Constraints)**
4. **Audit Trail Pipeline (Immutable, Hash-Chained JSONL Reconstruction)**
5. **Authority Circuit Breaker + Visible Authority State**

Only the YAML Mapping parameters differ across jurisdictions (`mappings/us_reg_z_credit.yaml`, `mappings/us_reg_e_eft.yaml`, `mappings/us_fcra_credit_reporting.yaml`, `mappings/us_state_insurance.yaml`).

---

## 2. Mapped U.S. Regulatory Regimes

### 2.1 Mapping 1: Regulation Z — Truth in Lending Act (12 CFR Part 1026)
**Executable Mapping:** [`../mappings/us_reg_z_credit.yaml`](../mappings/us_reg_z_credit.yaml)

- **Relevant Obligations:** Clear disclosure of credit terms (APR, finance charge, payment schedule) prior to consummation; accuracy rules for credit-term representations; statutory consumer right of rescission in covered transactions.
- **Control-Plane Binding:**
  - **Intent Classification Matrix & Action Object:** Distinguishes general credit education (`inform`, e.g., *"How does APR work?"*) from requests that initiate, modify, or bind a credit obligation (`commit` / `transact`, raised to `ESCALATE` in `us_reg_z_credit.yaml`).
  - **Authorization Trigger & Scoped Credential:** Actions constituting credit consummation require explicit, recorded consumer consent *after* required disclosures are delivered (`max_amount: 0` in Lite validator; routed to institutional workflow).
  - **Generation Boundary:** Outputs presenting numeric credit terms without accompanying required disclosure context are blocked (`unverified_financial_terms_stated_as_fact` / `prohibited_binding_commitment_or_completed_action`).
  - **Audit Trail Pipeline:** Records disclosure-delivery sequence, consent status, and classification tuple for later compliance reconstruction.
  - **Authority Circuit Breaker:** Requests attempting to waive or shorten a statutory rescission period immediately trigger `breaker` (`decision: breaker`), transferring interaction control to human review.

---

### 2.2 Mapping 2: Regulation E — Electronic Fund Transfer Act (12 CFR Part 1005)
**Executable Mapping:** [`../mappings/us_reg_e_eft.yaml`](../mappings/us_reg_e_eft.yaml)

- **Relevant Obligations:** Error resolution within statutory timeframes upon consumer report; preauthorized transfer authorization rules; statutory consumer liability limits for unauthorized transfers.
- **Control-Plane Binding:**
  - **Intent Classification Matrix & Action Object:** Distinguishes routine balance or transaction inquiries (`inform`) from EFT error reports (`R2`/`R3` sensitivity), ensuring statutory resolution clocks begin upon consumer report rather than manual staff triage.
  - **Authorization Trigger & Scoped Credential:** Preauthorized EFT execution (`commit` / `transact`) requires explicit affirmative consumer confirmation (`--confirm-auth`) before any single-use, amount-capped `ScopedCredential` is issued.
  - **Generation Boundary:** Prohibits stating or implying premature dispute outcomes before investigation completion (e.g., *"your dispute is approved"*).
  - **Audit Trail Pipeline:** Preserves immutable timestamps and hash-chained summaries of error-report intake to evidence the start of the statutory resolution window.
  - **Authority Circuit Breaker:** Requests seeking to waive error-resolution rights or prematurely cancel a pending dispute trigger `breaker` / human escalation.

---

### 2.3 Mapping 3: Fair Credit Reporting Act — FCRA (15 U.S.C. § 1681 et seq.)
**Executable Mapping:** [`../mappings/us_fcra_credit_reporting.yaml`](../mappings/us_fcra_credit_reporting.yaml)

- **Relevant Obligations:** Permissible purpose required before obtaining consumer reports; adverse-action notice duties when a report influences a decision; accuracy and dispute-handling obligations.
- **Control-Plane Binding:**
  - **Intent Classification Matrix & Action Object:** Separates general credit education (`inform`, e.g., *"What factors affect a credit score?"*) from interactions triggering consumer-report access (`transact` / `commit`, raised to `ESCALATE`).
  - **Authorization Trigger & Scoped Credential:** `scoped_credential.enabled: false` prevents autonomous credit-report pulls without a recorded permissible-purpose gate.
  - **Generation Boundary:** Blocks communicating report-influenced adverse decisions lacking required notice disclosures.
  - **Audit Trail Pipeline:** Logs the asserted permissible-purpose basis and notice delivery state alongside `VisibleAuthorityState`.
  - **Authority Circuit Breaker / Escalation:** Any interaction that would finalize an adverse-action determination is escalated (`decision: escalate` / `breaker`); the agent does not autonomously finalize adverse credit outcomes.

---

### 2.4 Mapping 4: State Insurance Regulation (Illustrative Multi-State Overlay: CA, NY, TX)
**Executable Mapping:** [`../mappings/us_state_insurance.yaml`](../mappings/us_state_insurance.yaml)

- **Relevant Obligations (Illustrative):** State-specific comparative disclosures for policy replacements; state-mandated minimum auto/liability coverage limits; non-renewal notice rules and lender lien requirements.
- **Control-Plane Binding:**
  - **Intent Classification Matrix & Action Object:** Distinguishes routine renewal schedule inquiries (`inform`) from policy replacement comparisons (`advise`, raised to `AUTH`) and binding policy switches (`commit` / `transact`, raised to `ESCALATE`).
  - **Authorization Trigger:** Configured per state parameter overlay (`jurisdiction_id`), allowing strict item-by-item confirmation gates without altering Core code.
  - **Generation Boundary:** Blocks completed-tense switching claims (*"your policy has been switched"*) and unauthorized cancellation confirmations.
  - **Audit Trail Pipeline:** Preserves the causal chain from utterance classification through authorization path and delivered comparison disclosures.
  - **Authority Circuit Breaker:** Requests attempting to reduce liability coverage below state statutory minimums or lender lien thresholds fire the `Authority Circuit Breaker` (`decision: breaker`), returning control to a licensed human agent or deterministic SOP.

---

## 3. Configuration Summary Across U.S. Regimes

| Regime | Mapping File | `confidence_floor` | `commit` / `transact` Override | Dedicated Circuit-Breaker Trigger |
|---|---|---|---|---|
| **Regulation Z (TILA)** | `mappings/us_reg_z_credit.yaml` | `0.80` | `raise_to_escalate` | Waiving or shortening statutory rescission period |
| **Regulation E (EFTA)** | `mappings/us_reg_e_eft.yaml` | `0.80` | `raise_to_auth` | Canceling pending EFT dispute / waiving error rights |
| **FCRA** | `mappings/us_fcra_credit_reporting.yaml` | `0.80` | `raise_to_escalate` (`scoped_credential: false`) | Autonomous adverse-action finalization |
| **State Insurance (CA/NY/TX)** | `mappings/us_state_insurance.yaml` | `0.80` | `raise_to_escalate` | Reducing coverage below statutory minimum or lien floor |

---

## 4. Scope & Disclaimer

This reference specification and its accompanying YAML mapping files describe **illustrative software configuration logic only**. They do not assert that any configuration shown here has been certified or approved by the CFPB, Federal Reserve, FTC, state departments of insurance, or any other regulator, and they do not constitute legal advice or replace institution-specific legal and compliance review prior to production deployment.
