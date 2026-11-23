# Conversational Finance Governance Framework

> An open-source, model-agnostic, engineering-level governance protocol for conversational AI in financial contexts. Also referred to as An Open Governance Standard for Conversational Finance Agents. MIT Licensed.

**Current specification:** [v0.4](./spec/protocol-spec-v0.4.md)  
**Agentic payment extension:** [v0.4-AP — Agentic Payment & Lifecycle Resilience](./spec/agentic-payment-extension.md)  
**U.S. regulatory mappings:** [v1.0 — Reg Z, Reg E, FCRA & State Insurance](./spec/us-regulatory-mapping.md)  
**Prior specification:** [v0.3](./spec/protocol-spec-v0.3.md)

## What is this?

The Conversational Finance Governance Framework is an open, MIT-licensed engineering specification that defines the structural governance components a conversational AI agent must implement before being deployed in any Fintech context where its outputs could create financial obligations, regulatory exposure, or consumer harm. It is not a commercial software product. It is a public technical specification — analogous to an RFC — accompanied by a zero-dependency state-machine and audit-schema reference validator.

This framework is engineered under the **AI Native Engineering** paradigm: governance is not retrofitted onto AI systems after deployment as an external audit layer, nor left to prompt-level instructions that a probabilistic model may fail to follow. Governance mechanisms — intent classification, action-level authority control, authorization gating, generation boundary enforcement, scoped credentials, circuit-breaking, and immutable audit logging — are embedded as structural components of the runtime control plane.

Scope is **Fintech CUI only**: payments, agentic checkout, lending, BNPL, insurance, collections, KYC/onboarding, wallets, and remittance — any conversational surface where an agent can inform, advise, commit, transact, or make a compliance representation.

## Core Design Premise: Dual-Sided Alignment

The framework is built around a dual-sided governance objective detailed in the [Agentic Payment & Lifecycle Resilience Extension](./spec/agentic-payment-extension.md):

1. **For Consumers (Neutral Financial Resilience & Autonomy Handoff):** A financial agent must act as a neutral resilience guardian rather than a checkout conversion accelerator. It enforces a hard **Verified-Terms Gate** (blocking unverified APR, fee, or schedule claims recalled from model memory), evaluates downside repayment risks, and triggers an unconditional **Authority Circuit Breaker** to hand decision authority back to the human whenever signals of cash-flow stress, overdraft exposure, or overlapping debt appear.
2. **For Enterprises (Lifecycle Risk Management vs. Short-Term GMV):** Optimizing conversational agents purely for frictionless checkout conversion inflates short-term GMV at the expense of downstream delinquency, charge-offs, and regulatory exposure. Enforcing pre-commitment authority boundaries and stress-triggered circuit breakers at the interaction layer functions as an upstream **Lifecycle Delinquency Hedge**, increasing the share of durable, sustainable customer relationships.

## Architecture

```
User → [Agent Runtime] → [Protocol Middleware] → [LLM]
                              │
                        ┌─────┴─────┐
                        │  Intent   │
                        │Classification│
                        │  Matrix   │
                        └─────┬─────┘
                              │
                        ┌─────┴─────┐
                        │  Action   │
                        │  Object   │
                        └─────┬─────┘
                              │
           ┌──────────────────┼──────────────────┐
           │                  │                  │
    ┌──────┴──────┐   ┌──────┴──────┐   ┌──────┴──────┐
    │Authorization│   │ Generation  │   │  Authority  │
    │  Trigger    │   │  Boundary   │   │  Circuit    │
    │ + Scoped    │   │             │   │  Breaker    │
    │ Credential  │   │             │   │             │
    └──────┬──────┘   └──────┬──────┘   └──────┬──────┘
           │                  │                  │
           └──────────────────┼──────────────────┘
                              │
              ┌───────────────┼───────────────┐
              │                               │
        ┌─────┴─────┐                  ┌──────┴──────┐
        │   Audit   │                  │  Visible    │
        │   Trail   │                  │  Authority  │
        │  Pipeline │                  │  State      │
        └───────────┘                  └─────────────┘
```

## Five-Layer Architecture (unchanged control plane)

v0.4 does **not** replace the five layers. It adds three runtime objects that the layers operate on.

1. **Intent Classification Matrix** — Classifies each conversational turn along two independent axes: Financial Commitment Risk (F0–F3) and Regulatory Sensitivity (R0–R3), before any response is generated. v0.4 adds a Classification Assurance rule: low-confidence classifications MUST default to the stricter action.
2. **Authorization Trigger** — Applies the Authorization Trigger Decision Table. If the classified action requires authorization, the agent suspends generation and obtains explicit user confirmation before proceeding.
3. **Generation Boundary** — Constrains the model's permissible response space before a user-facing answer is delivered (including blocking unverified financial terms stated as fact and prohibiting credit upsells under financial-distress signals).
4. **Audit Trail Pipeline** — Produces an immutable, hash-chained, machine-readable log of every generation, authorization, escalation, credential issue, and circuit-break decision.
5. **Authority Circuit Breaker** — Severs the agent's generation privilege in real time when conversation state reaches pre-defined risk or vulnerability thresholds, and transfers control back to the user, a human specialist, or a deterministic SOP.

## v0.4 Runtime Objects

- **Action Object** — Every turn is bound to one of: `inform`, `advise`, `commit`, `transact`, `represent`. Authority is assigned to the action, not to the model.
- **Scoped Credential** — For `transact` (and any binding `commit` that would execute), the agent MUST NOT receive a durable account or card secret. Only **after** explicit user authorization does the control plane issue a single-use, amount-capped, time-bounded credential.
- **Visible Authority State** — The user-facing control surface exposes the current action class, live permissions, last authorization timestamp, boundary violations, and circuit-breaker reason.

## Core/Mapping Decoupling

The five layers remain architecturally invariant across Fintech products. Product-line and jurisdictional requirements — which actions are free, which require authorization, which must escalate or break — are configured through a Compliance Mapping Layer without modifying the core specification.

Reference mappings (not legal advice):

- [`mappings/agentic_payment.yaml`](./mappings/agentic_payment.yaml) — Agentic checkout, payment-choice comparison & consumer resilience gates
- [`mappings/payments.yaml`](./mappings/payments.yaml) — P2P payments, wallets & remittance
- [`mappings/lending.yaml`](./mappings/lending.yaml) — Consumer lending & credit origination
- [`mappings/insurance.yaml`](./mappings/insurance.yaml) — Insurance comparison, binding & claims
- [`mappings/collections.yaml`](./mappings/collections.yaml) — Collections & repayment communications
- [`mappings/us_reg_z_credit.yaml`](./mappings/us_reg_z_credit.yaml) — U.S. Truth in Lending Act (Regulation Z)
- [`mappings/us_reg_e_eft.yaml`](./mappings/us_reg_e_eft.yaml) — U.S. Electronic Fund Transfer Act (Regulation E)
- [`mappings/us_fcra_credit_reporting.yaml`](./mappings/us_fcra_credit_reporting.yaml) — U.S. Fair Credit Reporting Act (FCRA)
- [`mappings/us_state_insurance.yaml`](./mappings/us_state_insurance.yaml) — U.S. State Insurance Regulation (CA, NY, TX illustrative overlay)

The same utterance compiles to different authority decisions under different mappings.

## Getting Started (Control-Plane Validator)

- **Lite Validator (`src/`)** — A zero-dependency deterministic state-machine and audit-schema validator demonstrating the control plane without calling an external LLM.
- **Standard / Full** — Connect a production intent classifier and compliance infrastructure to the Mapping Layer while preserving core triggers, boundaries, and circuit-breaker invariants.

```bash
# Run from repository root (no external dependencies required)
PYTHONPATH=src python3 -m cf_gov.sidecar \
  --mapping mappings/agentic_payment.yaml \
  --utterance "What is the monthly cost for the installment plan?" \
  --candidate-response "You can pay $45 per month at 14.9% APR." \
  --unverified-terms

PYTHONPATH=src python3 -m cf_gov.sidecar \
  --mapping mappings/agentic_payment.yaml \
  --utterance "I am behind on bills and worried about overdraft. Should I borrow with BNPL?"

PYTHONPATH=src python3 tests/test_sidecar.py
```

See [`/spec/protocol-spec-v0.4.md`](./spec/protocol-spec-v0.4.md), [`/spec/agentic-payment-extension.md`](./spec/agentic-payment-extension.md), and [`/spec/us-regulatory-mapping.md`](./spec/us-regulatory-mapping.md) for the specifications.

## Repository Structure

```
├── README.md                 ← You are here
├── LICENSE                   ← MIT
├── spec/                     ← Normative specifications (v0.3, v0.4, v0.4-AP) & U.S. mapping reference
├── src/                      ← Deterministic control-plane & audit-schema validator
├── mappings/                 ← Configurable product-line & jurisdiction mappings
└── tests/                    ← Classification gold standard + control-plane conformance tests
```

## License

MIT — see [LICENSE](./LICENSE).
