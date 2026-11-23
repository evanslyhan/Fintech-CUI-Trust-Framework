# Reference Implementation — Deterministic Control-Plane & Schema Validator

**Status:** v0.4 / v0.4-AP Lite control plane (zero external LLM dependency)  
**License:** MIT

This directory contains a zero-dependency **deterministic control-plane and audit-schema validator** for specification [v0.4](../spec/protocol-spec-v0.4.md) and the [Agentic Payment & Lifecycle Resilience Extension (v0.4-AP)](../spec/agentic-payment-extension.md). It sits conceptually between a conversational agent and an LLM. This validator classifies an utterance, binds an Action Object, applies a product-line mapping, enforces Section 5 Generation Boundary checks on candidate outputs, issues a single-use scoped credential record strictly **after** explicit user authorization (`--confirm-auth`), writes a hash-chained JSONL audit event, and prints Visible Authority State.

It is a protocol state-machine reference validator, not a commercial NLU model or payment processor.

## Run

```bash
# Run from repository root (no third-party packages required)
PYTHONPATH=src python3 -m cf_gov.sidecar --mapping mappings/agentic_payment.yaml --utterance "What is the monthly cost for the installment plan?" --candidate-response "You can pay $45 per month at 14.9% APR." --unverified-terms
PYTHONPATH=src python3 -m cf_gov.sidecar --mapping mappings/agentic_payment.yaml --utterance "I am behind on bills and worried about overdraft. Should I borrow with BNPL?"
PYTHONPATH=src python3 -m cf_gov.sidecar --mapping mappings/payments.yaml --utterance "Pay now. Send 200 dollars to Jane."
PYTHONPATH=src python3 -m cf_gov.sidecar --mapping mappings/payments.yaml --utterance "Pay now. Send 200 dollars to Jane." --confirm-auth
PYTHONPATH=src python3 -m cf_gov.sidecar --mapping mappings/lending.yaml --utterance "Should I take the loan?"
PYTHONPATH=src python3 -m cf_gov.sidecar --mapping mappings/insurance.yaml --utterance "Is this claim fully covered by my plan?"
PYTHONPATH=src python3 -m cf_gov.sidecar --mapping mappings/collections.yaml --utterance "Pay now."
```

Optional audit file:

```bash
PYTHONPATH=src python3 -m cf_gov.sidecar \
  --mapping mappings/payments.yaml \
  --utterance "Pay now. Send 200 dollars to Jane." \
  --confirm-auth \
  --audit /tmp/cf-gov-audit.jsonl
```

Conformance tests from repository root:

```bash
python3 tests/test_sidecar.py
```

## What this validator enforces

- `(FCR, RS, Action)` tuple bound before any generation or execution decision
- Classification Assurance (`confidence_floor` from the mapping)
- Section 3.2 FREE / AUTH / ESCALATE decision table
- Product-line and U.S. regulatory action overrides (`agentic_payment`, `payments`, `lending`, `insurance`, `collections`, `us_reg_z_credit`, `us_reg_e_eft`, `us_fcra_credit_reporting`, `us_state_insurance`)
- Section 5 Generation Boundary checks (blocking unverified financial terms stated as fact, prohibited commitments, and credit upsells under financial-distress signals)
- Post-AUTH single-use Scoped Credential issuance with `secret_material_in_model_context=false`
- Visible Authority State in the JSON output
- Append-only SHA-256 hash-chained JSONL when `--audit` is set

## Layout

```
src/
  requirements.txt
  cf_gov/
    __init__.py
    engine.py      ← control plane & generation boundary validator
    sidecar.py     ← CLI
```
