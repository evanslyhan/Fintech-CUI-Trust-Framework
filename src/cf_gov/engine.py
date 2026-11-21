"""v0.4 control plane: classify → assure → decide → generation boundary → post-AUTH scoped credential → log."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]


def _parse_scalar(val: str) -> Any:
    val = val.strip()
    if not val or val == "[]":
        return [] if val == "[]" else ""
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        return val[1:-1]
    low = val.lower()
    if low in ("true", "enabled", "yes"):
        return True
    if low in ("false", "disabled", "no"):
        return False
    try:
        return int(val) if "." not in val else float(val)
    except ValueError:
        return val


def _load_yaml_text(text: str) -> dict[str, Any]:
    if yaml is not None:
        return yaml.safe_load(text) or {}
    out: dict[str, Any] = {}
    section: str | None = None
    multiline_key: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if multiline_key is not None:
            if indent > 0:
                out[multiline_key] = (out.get(multiline_key, "") + " " + stripped).strip()
                continue
            multiline_key = None
        if indent == 0 and ":" in stripped:
            k, v = stripped.split(":", 1)
            k, v = k.strip(), v.strip()
            if v == ">":
                multiline_key = k
                out[k] = ""
                section = None
            elif v == "":
                section = k
                out[k] = {}
            else:
                section = None
                out[k] = _parse_scalar(v)
        elif indent > 0 and section is not None:
            if stripped.startswith("- "):
                if not isinstance(out[section], list):
                    out[section] = []
                out[section].append(_parse_scalar(stripped[2:]))
            elif ":" in stripped and isinstance(out[section], dict):
                k, v = stripped.split(":", 1)
                out[section][k.strip()] = _parse_scalar(v)
    return out

FCR_ORDER = ("F0", "F1", "F2", "F3")
RS_ORDER = ("R0", "R1", "R2", "R3")
ACTION_ORDER = ("inform", "advise", "commit", "transact", "represent")
DECISION_ORDER = ("free", "auth_required", "escalate", "breaker")

DECISION_TABLE = {
    ("F0", "R0"): "free",
    ("F0", "R1"): "free",
    ("F0", "R2"): "auth_required",
    ("F0", "R3"): "auth_required",
    ("F1", "R0"): "free",
    ("F1", "R1"): "auth_required",
    ("F1", "R2"): "auth_required",
    ("F1", "R3"): "escalate",
    ("F2", "R0"): "auth_required",
    ("F2", "R1"): "auth_required",
    ("F2", "R2"): "escalate",
    ("F2", "R3"): "escalate",
    ("F3", "R0"): "auth_required",
    ("F3", "R1"): "escalate",
    ("F3", "R2"): "escalate",
    ("F3", "R3"): "escalate",
}

ACTION_RAISE = {
    "inherit": None,
    "raise_to_auth": "auth_required",
    "raise_to_escalate": "escalate",
    "raise_to_breaker": "breaker",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _rank(seq: tuple[str, ...], value: str) -> int:
    return seq.index(value)


def _stricter_decision(a: str, b: str) -> str:
    return a if _rank(DECISION_ORDER, a) >= _rank(DECISION_ORDER, b) else b


def _stricter_action(a: str, b: str) -> str:
    return a if _rank(ACTION_ORDER, a) >= _rank(ACTION_ORDER, b) else b


@dataclass
class MappingConfig:
    product_line: str
    confidence_floor: float
    action_overrides: dict[str, str]
    cumulative_trigger_limit: int
    vulnerability_detection: bool
    trajectory_window: int
    scoped_credential: dict[str, Any]
    boundary_additions: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path) -> "MappingConfig":
        data = _load_yaml_text(Path(path).read_text(encoding="utf-8"))
        breaker = data.get("breaker_overrides") or {}
        return cls(
            product_line=str(data.get("product_line") or "unspecified"),
            confidence_floor=float(data.get("confidence_floor") or 0.70),
            action_overrides=data.get("action_overrides") or {},
            cumulative_trigger_limit=int(breaker.get("cumulative_trigger_limit") or 3),
            vulnerability_detection=bool(breaker.get("vulnerability_detection", True)),
            trajectory_window=int(breaker.get("trajectory_window") or 5),
            scoped_credential=data.get("scoped_credential") or {},
            boundary_additions=list(data.get("boundary_additions") or []),
            raw=data,
        )


@dataclass
class Classification:
    fcr: str
    rs: str
    action: str
    confidence: float
    intent_label: str
    notes: list[str] = field(default_factory=list)


@dataclass
class ScopedCredential:
    credential_id: str
    session_id: str
    max_amount: float
    currency: str
    merchant_or_rail_scope: str
    expires_at: str
    single_use: bool
    secret_material_in_model_context: bool = False


@dataclass
class VisibleAuthorityState:
    action: str
    fcr: str
    rs: str
    decision: str
    live_permissions: list[str]
    last_authorization: str
    breaker_reason: str | None
    product_line: str
    classification_confidence: float
    boundary_violations: list[str] = field(default_factory=list)


@dataclass
class DecisionResult:
    classification: Classification
    decision: str
    visible_authority_state: VisibleAuthorityState
    credential: ScopedCredential | None
    event: dict[str, Any]


# ---------------------------------------------------------------------------
# Deterministic Lite classifier
# This is a control-plane reference implementation, not a statistical NLU model.
# Gold-standard labels live in tests/classification/gold.jsonl.
# ---------------------------------------------------------------------------

_VULN = re.compile(
    r"\b(can't pay|cannot pay|cannot afford|can't afford|no money|desperate|scared|"
    r"confused|i don't understand|help me|overdraft|behind on bills|struggling to pay|"
    r"financial distress)\b",
    re.I,
)
_REPRESENT = re.compile(
    r"\b(compliant|compliance|covered by|fully covered|legal|regulator|approved)\b",
    re.I,
)
_TRANSACT = re.compile(
    r"\b(pay now|charge|send .* now|transfer now|debit|disburse|buy now|renew now|"
    r"complete purchase|confirm payment|use the .* plan now)\b",
    re.I,
)
_COMMIT = re.compile(
    r"\b(lock|locked|guarantee|guaranteed|will never|total will be|premium is)\b",
    re.I,
)
_ADVISE = re.compile(
    r"\b(should i|should you|you should|i recommend|take the loan|pay off|borrow|"
    r"which way to pay|how should i pay|best way to pay)\b",
    re.I,
)
_BINDING = re.compile(
    r"\b(charge my|pay with my card|send \d|transfer \d|book .* if)\b",
    re.I,
)
_CONSIDER = re.compile(
    r"\b(how much|fee|apr|premium|price|cost|rate|installment|monthly payment)\b",
    re.I,
)
_REGULATED = re.compile(
    r"\b(cancel|rights|terms|policy|coverage|interest|apr|loan|debt|collection|bnpl)\b",
    re.I,
)

# Section 5 Generation Boundary patterns (pre/post-generation enforcement)
_BOUNDARY_COMMITMENT = re.compile(
    r"\b(guaranteed approval|unconditional fee waiver|rate is locked at|guaranteed never to increase|"
    r"i have switched your policy|your dispute is approved)\b",
    re.I,
)
_BOUNDARY_COMPLIANCE_REP = re.compile(
    r"\b(fully compliant with all state and federal laws|certified by the regulator|legally guaranteed)\b",
    re.I,
)
_BOUNDARY_DISTRESS_UPSELL = re.compile(
    r"\b(take out a new loan|finance this purchase anyway|split into easy payments|borrow more)\b",
    re.I,
)
_BOUNDARY_NUMERIC_TERMS = re.compile(
    r"\b(\d+(\.\d+)?%\s*apr|\$\d+(\.\d+)?\s*(per month|/mo|monthly|fee))\b",
    re.I,
)


def classify_utterance(utterance: str) -> Classification:
    text = utterance.strip()
    notes: list[str] = []
    action = "inform"
    fcr = "F0"
    rs = "R0"
    confidence = 0.82

    if _REPRESENT.search(text):
        action = "represent"
        rs = "R3"
        notes.append("represent_pattern")
    elif _TRANSACT.search(text):
        action = "transact"
        fcr = "F3"
        notes.append("transact_pattern")
    elif _COMMIT.search(text):
        action = "commit"
        fcr = "F2"
        notes.append("commit_pattern")
    elif _ADVISE.search(text):
        action = "advise"
        rs = _stricter_rs(rs, "R2")
        fcr = "F1"
        notes.append("advise_pattern")
    elif _CONSIDER.search(text):
        fcr = "F1"
        notes.append("consideration_pattern")

    if _BINDING.search(text) and action != "represent":
        fcr = "F3" if re.search(r"\b(charge|card|send|transfer)\b", text, re.I) else "F2"
        notes.append("binding_pattern")

    if _REGULATED.search(text) and rs == "R0":
        rs = "R1"
        notes.append("regulated_info_pattern")

    if action == "inform" and (_rank(FCR_ORDER, fcr) >= 2 or _rank(RS_ORDER, rs) >= 2):
        action = "advise"
        notes.append("rebound_inform_to_advise")

    if _VULN.search(text):
        notes.append("vulnerability_signal")
        confidence = min(confidence, 0.55)

    if not notes:
        confidence = 0.90

    label = f"{action}:{fcr}/{rs}"
    return Classification(
        fcr=fcr,
        rs=rs,
        action=action,
        confidence=confidence,
        intent_label=label,
        notes=notes,
    )


def _stricter_rs(a: str, b: str) -> str:
    return a if _rank(RS_ORDER, a) >= _rank(RS_ORDER, b) else b


def apply_assurance(c: Classification, floor: float) -> Classification:
    notes = list(c.notes)
    action = c.action
    confidence = c.confidence
    if action == "inform" and (_rank(FCR_ORDER, c.fcr) >= 2 or _rank(RS_ORDER, c.rs) >= 2):
        action = _stricter_action(action, "advise")
        notes.append("assurance_rebind_inform")
    if confidence < floor:
        notes.append("below_confidence_floor")
    return Classification(
        fcr=c.fcr,
        rs=c.rs,
        action=action,
        confidence=confidence,
        intent_label=c.intent_label,
        notes=notes,
    )


def core_decision(fcr: str, rs: str) -> str:
    return DECISION_TABLE[(fcr, rs)]


def apply_action_override(decision: str, action: str, mapping: MappingConfig) -> str:
    raw = (mapping.action_overrides or {}).get(action, "inherit")
    raised = ACTION_RAISE.get(raw, None)
    if raised is None:
        return decision
    return _stricter_decision(decision, raised)


def check_generation_boundary(
    candidate_response: str,
    classification: Classification,
    *,
    unverified_terms: bool = False,
) -> list[str]:
    """Section 5 Generation Boundary check on candidate model output before delivery."""
    violations: list[str] = []
    if not candidate_response:
        return violations
    if _BOUNDARY_COMMITMENT.search(candidate_response):
        violations.append("prohibited_binding_commitment_or_completed_action")
    if _BOUNDARY_COMPLIANCE_REP.search(candidate_response):
        violations.append("prohibited_compliance_representation")
    if unverified_terms and _BOUNDARY_NUMERIC_TERMS.search(candidate_response):
        violations.append("unverified_financial_terms_stated_as_fact")
    if "vulnerability_signal" in classification.notes and _BOUNDARY_DISTRESS_UPSELL.search(
        candidate_response
    ):
        violations.append("credit_upsell_under_vulnerability_signal")
    return violations


def maybe_break(
    decision: str,
    classification: Classification,
    mapping: MappingConfig,
    session_auth_count: int,
    boundary_violations: list[str] | None = None,
) -> tuple[str, str | None]:
    reason = None
    if boundary_violations and "credit_upsell_under_vulnerability_signal" in boundary_violations:
        return "breaker", "credit_upsell_under_vulnerability_signal"
    if mapping.vulnerability_detection and "vulnerability_signal" in classification.notes:
        if mapping.cumulative_trigger_limit <= 1 or classification.action in {
            "advise",
            "commit",
            "transact",
            "represent",
        }:
            reason = "vulnerability_signal"
            return "breaker", reason
    if session_auth_count >= mapping.cumulative_trigger_limit and decision in {
        "auth_required",
        "escalate",
    }:
        reason = "cumulative_trigger_limit"
        return "breaker", reason
    return decision, reason


def issue_credential(session_id: str, mapping: MappingConfig) -> ScopedCredential:
    sc = mapping.scoped_credential
    ttl = int(sc.get("ttl_minutes") or 15)
    return ScopedCredential(
        credential_id=str(uuid.uuid4()),
        session_id=session_id,
        max_amount=float(sc.get("max_amount") or 0),
        currency=str(sc.get("currency") or "USD"),
        merchant_or_rail_scope=str(sc.get("merchant_or_rail_scope") or "declared_payee_only"),
        expires_at=_iso(_utcnow() + timedelta(minutes=ttl)),
        single_use=bool(sc.get("single_use", True)),
        secret_material_in_model_context=False,
    )


class AuditLog:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self.prev_hash = "0" * 64
        self.seq = 0

    def append(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.seq += 1
        body = dict(payload)
        body["seq"] = self.seq
        encoded = json.dumps(body, sort_keys=True, ensure_ascii=False)
        digest = hashlib.sha256((encoded + self.prev_hash).encode("utf-8")).hexdigest()
        record = {**body, "prev_hash": self.prev_hash, "hash": digest}
        self.prev_hash = digest
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record


class Session:
    def __init__(self, mapping: MappingConfig, audit: AuditLog | None = None) -> None:
        self.mapping = mapping
        self.session_id = str(uuid.uuid4())
        self.auth_or_escalate_count = 0
        self.last_authorization = "none"
        self.audit = audit or AuditLog()

    def handle(
        self,
        utterance: str,
        *,
        confirmed_auth: bool = False,
        candidate_response: str | None = None,
        unverified_terms: bool = False,
    ) -> DecisionResult:
        raw = classify_utterance(utterance)
        assured = apply_assurance(raw, self.mapping.confidence_floor)
        decision = core_decision(assured.fcr, assured.rs)
        if assured.confidence < self.mapping.confidence_floor:
            decision = _stricter_decision(decision, "auth_required")
            if assured.action == "represent" or decision == "escalate":
                decision = "escalate"
        decision = apply_action_override(decision, assured.action, self.mapping)

        boundary_violations = check_generation_boundary(
            candidate_response or "",
            assured,
            unverified_terms=unverified_terms,
        )
        if boundary_violations:
            assured.notes.extend(f"boundary:{v}" for v in boundary_violations)
            if "prohibited_compliance_representation" in boundary_violations:
                decision = _stricter_decision(decision, "escalate")
            else:
                decision = _stricter_decision(decision, "auth_required")

        decision, breaker_reason = maybe_break(
            decision,
            assured,
            self.mapping,
            self.auth_or_escalate_count,
            boundary_violations=boundary_violations,
        )

        if decision in {"auth_required", "escalate"}:
            self.auth_or_escalate_count += 1

        # Section 3A.4 & 3.3: Scoped credential is issued ONLY after explicit user AUTH confirmation.
        credential = None
        if (
            decision == "auth_required"
            and confirmed_auth
            and assured.action in {"transact", "commit"}
            and self.mapping.scoped_credential.get("enabled")
        ):
            credential = issue_credential(self.session_id, self.mapping)
            self.last_authorization = _iso(_utcnow())

        live = ["generate:inform"]
        if decision == "free":
            live = [f"generate:{assured.action}"]
        elif decision == "auth_required":
            if confirmed_auth:
                live = [f"authorized:{assured.action}"]
                if credential:
                    live.append(f"credential:{credential.credential_id}")
            else:
                live = ["pending_authorization", f"action:{assured.action}"]
        elif decision == "escalate":
            live = ["human_or_sop"]
        else:
            live = ["generation_severed"]

        vas = VisibleAuthorityState(
            action=assured.action,
            fcr=assured.fcr,
            rs=rs_val(assured.rs),
            decision=decision,
            live_permissions=live,
            last_authorization=self.last_authorization,
            breaker_reason=breaker_reason,
            product_line=self.mapping.product_line,
            classification_confidence=assured.confidence,
            boundary_violations=boundary_violations,
        )

        if decision == "auth_required" and confirmed_auth and credential is not None:
            event_type = "credential_issued"
        else:
            event_type = {
                "free": "generation",
                "auth_required": "authorization_request",
                "escalate": "escalation",
                "breaker": "circuit_breaker_activation",
            }[decision]

        event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": _iso(_utcnow()),
            "session_id": self.session_id,
            "event_type": event_type,
            "utterance_summary": utterance[:240],
            "intent_classification": {
                "fcr_level": assured.fcr,
                "rs_level": assured.rs,
                "intent_label": assured.intent_label,
            },
            "action": assured.action,
            "classification_confidence": assured.confidence,
            "trigger_decision": decision,
            "visible_authority_state": asdict(vas),
            "credential_id": credential.credential_id if credential else None,
            "boundary_violations": boundary_violations,
            "notes": assured.notes,
            "compliance_mapping_id": self.mapping.product_line,
        }
        logged = self.audit.append(event)
        return DecisionResult(
            classification=assured,
            decision=decision,
            visible_authority_state=vas,
            credential=credential,
            event=logged,
        )


def rs_val(rs: str) -> str:
    return rs
