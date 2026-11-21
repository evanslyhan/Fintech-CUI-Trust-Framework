# Agentic Payment & Lifecycle Resilience Extension (v0.4-AP)

**Status:** Draft Extension to [Specification v0.4](./protocol-spec-v0.4.md)  
**Author:** Lenyen Han  
**License:** MIT  
**Reference Mapping:** [`../mappings/agentic_payment.yaml`](../mappings/agentic_payment.yaml)

---

## 1. Purpose & Structural Premise

As conversational AI agents move from product discovery to **agentic payment and checkout execution** (evaluating debit, credit cards, digital wallets, promotional financing, and buy-now-pay-later options), prompt-level instructions alone cannot guarantee that a probabilistic model will verify disclosures, respect consumer cash-flow limits, or withhold unauthorized execution.

This extension applies the five-layer runtime control plane of Specification v0.4 to agentic payment workflows around a **dual-sided governance premise**:

### 1.1 For Consumers: Neutral Financial Resilience & Autonomy Handoff
An agent operating at checkout MUST function as a **neutral financial resilience guardian**, not a checkout conversion accelerator. Its role is to help the user evaluate *whether* and *how* to pay—treating paying in full, using installments, waiting, or declining the purchase altogether as equal, first-class outcomes—and to enforce an unconditional **autonomy handoff** back to the human decision-maker when risk thresholds are reached:

1. **Verified-Terms Gate (Generation Boundary)**: The agent MUST NOT state APRs, fees, repayment schedules, or promotional expiration rules recalled from training memory. If transaction-specific terms are not retrieved and verified in the current session, the Generation Boundary blocks numeric cost claims and prevents the unverified option from being recommended.
2. **Downside & Resilience Stress-Testing (`advise` Posture)**: Before recommending any financing or installment option, the control plane binds the turn to `advise` (`AUTH` posture), requiring disclosure of total effective net cost (distinguishing lower monthly payments from total cost) and adverse-path consequences (missed payment fees, deferred-interest retroactive accrual, or refund-timing mismatch).
3. **Stress-Triggered Autonomy Handoff (`Authority Circuit Breaker`)**: If the user indicates cash-flow strain, overdraft exposure, difficulty meeting essential expenses, or overlapping installment obligations (loan stacking), the `Authority Circuit Breaker` immediately severs financing recommendation and execution privileges (`decision: breaker`) and returns full decision control to the user.

### 1.2 For Enterprises: Lifecycle Risk Management vs. Short-Term GMV
In commercial deployments, optimizing conversational agents purely for frictionless checkout conversion inflates short-term Gross Merchandise Volume (GMV) by routing financially stretched consumers into unsustainable credit commitments—driving downstream delinquency, charge-offs, customer churn, and regulatory exposure.

Embedding deterministic authority boundaries and resilience-triggered circuit breakers at the interaction layer serves as an upstream **Lifecycle Delinquency Hedge**:

- **Pre-Origination Risk Filtering**: Preventing credit upsells during conversational vulnerability signals filters out high-default-probability transactions before origination.
- **Sustainable User Retention**: Preserving user agency and preventing surprise debt obligations increases long-term customer trust, repeat healthy usage, and compliant portfolio performance.
- **Auditability Under Multi-Jurisdictional Rules**: Every classification, term-verification gate, user authorization, scoped-credential issuance, and circuit-breaker handoff is recorded in an immutable, hash-chained audit log (`Section 6`), while jurisdiction-specific disclosure and timing thresholds remain isolated in the configurable Mapping layer (`Section 8`).

---

## 2. Control-Plane Binding for Agentic Checkout Stages

| Checkout Stage | Bound Action Object | Control-Plane Enforcement |
|---|---|---|
| **Stage 1: Option Discovery & Term Retrieval** | `inform` | Allowed as `FREE` only when transaction disclosures are verified. If terms are missing (`unverified_terms=True`), the **Generation Boundary** blocks numeric rate/fee outputs (`boundary:unverified_financial_terms_stated_as_fact`) and upgrades the turn to `AUTH` / `ESCALATE`. |
| **Stage 2: Payment-Choice Comparison & Stress-Test** | `advise` | Raised to `AUTH` via `agentic_payment.yaml`. If user utterances contain financial-stress or overdraft signals, the **Authority Circuit Breaker** fires (`breaker_reason: vulnerability_signal`), halting financing recommendations and returning control to the user. |
| **Stage 3: Checkout Commitment & Execution** | `commit` / `transact` | Requires explicit affirmative user confirmation via the **Authorization Trigger**. No durable card number, PAN, or account credential enters the LLM context; only after confirmation does the control plane issue a single-use, amount-capped, short-TTL **Scoped Credential** and append a `credential_issued` event to the **Audit Trail Pipeline**. |
| **Stage 4: Legal / Coverage / Dispute Representation** | `represent` | Raised to `ESCALATE`, routing binding contractual or dispute determinations to deterministic institutional workflows or human specialists. |

---

## 3. CLI Verification Examples

Using the reference sidecar (`src/cf_gov/sidecar.py`) with `mappings/agentic_payment.yaml`:

```bash
# 1. Unverified checkout terms stated by candidate model output -> Blocked by Generation Boundary
PYTHONPATH=src python3 -m cf_gov.sidecar \
  --mapping mappings/agentic_payment.yaml \
  --utterance "What is the monthly cost for the installment plan?" \
  --candidate-response "You can pay $45 per month at 14.9% APR." \
  --unverified-terms

# 2. Consumer expresses cash-flow strain while asking about financing -> Circuit Breaker severs financing recommendation
PYTHONPATH=src python3 -m cf_gov.sidecar \
  --mapping mappings/agentic_payment.yaml \
  --utterance "I am behind on bills and worried about overdraft. Should I borrow with BNPL?"

# 3. Payment execution before vs. after explicit user confirmation -> Scoped Credential issued only post-AUTH
PYTHONPATH=src python3 -m cf_gov.sidecar \
  --mapping mappings/agentic_payment.yaml \
  --utterance "Pay now. Send 200 dollars to merchant."

PYTHONPATH=src python3 -m cf_gov.sidecar \
  --mapping mappings/agentic_payment.yaml \
  --utterance "Pay now. Send 200 dollars to merchant." \
  --confirm-auth
```
