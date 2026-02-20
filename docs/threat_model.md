# Threat Model

## Scope
This document models primary threats for the RAGShield demo stack (retrieval + policy gating + output validation).

## Threat Categories

### 1) Prompt Injection
**Description:** User attempts to override system/developer instructions (e.g., “ignore previous instructions”).

**Risks:**
- policy bypass
- unsafe tool invocation
- model behavior drift

**Mitigations in this project:**
- pre-action policy gate with `injection_suspected` risk flag
- strict system prompt + structured output schema
- post-response policy checks

### 2) Exfiltration Attempts
**Description:** User asks for secrets/system prompts/hidden instructions/API keys.

**Risks:**
- system prompt disclosure
- secret leakage
- policy circumvention narratives

**Mitigations in this project:**
- pre-action policy with `exfil_suspected`
- denial of unsafe actions before execution
- refusal-only path for suspicious requests
- post-response deny rules for secret-like patterns

### 3) Data Leakage
**Description:** Output cites or reveals information not grounded in approved context.

**Risks:**
- hallucinated citations
- disclosure of non-retrieved content
- trust/compliance failure

**Mitigations in this project:**
- citation schema with stable chunk metadata
- validation that quote is verbatim in referenced chunk
- confidence downgrades / citation dropping on invalid references

### 4) Tool Hijack
**Description:** Adversarial prompt attempts to force unintended action/scope/role usage.

**Risks:**
- sensitive scope access by normal users
- debug/admin-like behavior escalation
- unsafe pre-action transitions

**Mitigations in this project:**
- policy-as-code input fields: `action`, `requested_data_scope`, `user_role`, `risk_flags`
- OPA deny rules for role/scope mismatch
- action-level gating in graph runtime

## Assumptions
- OPA and Weaviate are reachable and healthy.
- Secret management for provider keys is handled by environment/CI secrets.
- Demo scope: local/dev deployment, not full production hardening.

## Residual Risks
- lexical heuristics for risk flags can under/over-trigger
- model/provider behavior can shift over time
- policy drift if Rego and app payload contracts diverge

## Recommended Next Steps
- expand risk detection with classifier signals and telemetry feedback
- add explicit negative/allowlist policy tests in CI
- formalize threat scenarios into regression suites (promptfoo + RAGAS segments)
