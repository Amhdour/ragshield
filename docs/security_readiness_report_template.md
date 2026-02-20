# Security Readiness Report Template

## 1) Release Information
- Project:
- Version/Commit:
- Date:
- Assessor:
- Environment (dev/staging/prod-like):

## 2) Architecture Snapshot
- Components in scope:
- Data flows in scope:
- External dependencies:

## 3) Policy Pack Status
- Pre-action policy inputs implemented (`action`, `requested_data_scope`, `user_role`, `risk_flags`):
- Post-response guardrails enabled:
- Fail-closed behavior validated:

## 4) Threat Scenario Results
| Scenario | Test Method | Expected | Observed | Status |
|---|---|---|---|---|
| Prompt injection |  | Denied/refusal |  |  |
| Exfiltration |  | Denied/refusal |  |  |
| Sensitive scope (non-admin) |  | Denied |  |  |
| Citation spoofing |  | Dropped/denied |  |  |
| Tool hijack |  | Blocked |  |  |

## 5) Validation & Regression Evidence
- Promptfoo run link/artifacts:
- RAGAS report link/artifacts:
- CI workflow run ID:
- Manual smoke test evidence:

## 6) Findings
### Critical
- 

### High
- 

### Medium
- 

### Low
- 

## 7) Risk Acceptance / Exceptions
- Exception ID:
- Description:
- Owner:
- Expiration date:

## 8) Go/No-Go Recommendation
- Recommendation:
- Conditions (if any):
- Approvers:
