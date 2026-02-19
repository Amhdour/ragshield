# Baseline Audit (Prompt 0)

## Repository snapshot
- Current branch: `work`.
- Local branches present: `work` only.
- No separate local default branch (`main`/`master`) is available for comparison in this checkout.
- Recent history shows:
  - `47ddf46` (HEAD) Fix OPA confidence-rule parse and add reliable local readiness retry
  - `7be6872` Initialize repository

## Top-level structure (<=3 levels)
- Runtime: `app/`
  - `app/config.py`
  - `app/main.py`
  - `app/graph.py`
  - `app/retrieval.py`
  - `app/llm.py`
  - `app/schema.py`
  - `app/policy.py`
  - `app/tracing.py`
  - `app/prompts.py`
- Infra/config:
  - `docker-compose.yml`
  - `Dockerfile`
  - `.env.example`
  - `pyproject.toml`
  - `litellm_config.yaml`
- Security/policy:
  - `opa/policy.rego`
- Red-team:
  - `redteam/promptfoo.yaml`
  - `redteam/run_promptfoo.sh`
- Scripts:
  - `scripts/seed_test_docs.py`
  - `scripts/ingest.py`
- Docs:
  - `README.md`
  - `docs/.gitkeep`

## App start / entrypoint
- API entrypoint is FastAPI app in `app/main.py` (`app = FastAPI(...)`).
- Recommended run command from README:
  - `uvicorn app.main:app --host 0.0.0.0 --port 8000`

## Tracing
- Tracing implementation exists in `app/tracing.py`.
- It is local tracing (UUID trace IDs + stdout event count), not Langfuse SDK-backed tracing.
- Called from `app/main.py` via `start_trace(...)` and passed through graph execution.

## OPA policy gate
- OPA client exists in `app/policy.py`.
- `/chat` calls `check_policy(payload.model_dump())` in `app/main.py` before returning response.
- On deny, `/chat` rewrites payload to refusal (`answer`, `confidence=low`, `refusal_reason`, empty citations).

## CI / workflows
- No `.github/workflows/*` files found in this repository checkout.

## What exists vs missing (Langfuse / Ragas / CI)
- Langfuse:
  - Config keys exist in `app/config.py`, but runtime tracing is currently local only.
  - No active Langfuse SDK integration is present.
- Ragas:
  - No Ragas package or evaluation pipeline found in dependencies or scripts.
- CI:
  - No GitHub Actions workflow files found.
