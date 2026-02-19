# ragshield

Minimal LangGraph RAG app with a portable trust/security layer.

## Structure

- `app/`: runtime API, graph, retrieval, LLM, schema, policy gate, tracing
- `scripts/`: seed + ingest utilities
- `opa/`: Rego policy
- `redteam/`: Promptfoo regression suite
- `docs/`: reports and documentation


## Module responsibilities

- `app/retrieval.py`: canonical Weaviate retrieval implementation.
- `app/llm.py`: canonical LiteLLM generation wrapper.
- `app/schema.py`: canonical structured `AnswerPayload` + validation/repair helpers.
- `app/policy.py`: canonical OPA policy gate integration.
- `app/tracing.py`: canonical local tracing handle/span implementation.

## Quickstart

```bash
cp .env.example .env
pip install -e .
```

## Start local dependencies

```bash
docker compose up -d
```

Health checks:

```bash
curl -sS http://localhost:8080/v1/.well-known/ready ; echo
curl -sS http://localhost:8181/health ; echo
```

## Seed and ingest docs

```bash
python scripts/seed_test_docs.py
python scripts/ingest.py --input-dir ./data/docs --weaviate-url http://localhost:8080 --collection RagDoc
```

## Run API

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

API smoke test:

```bash
curl -sS http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query":"What docs exist?"}' ; echo
```

API contract notes:
- `/chat` always returns `AnswerPayload` keys: `answer`, `citations`, `confidence`, `refusal_reason` (plus `trace_id`).
- If no relevant context is found, response is `"I don't know"` with `confidence="low"`, non-empty `refusal_reason`, and empty citations.
- If `confidence` is `med`/`high`, citations are guaranteed non-empty with `doc_id` + `quote` tied to retrieved docs.


## Tracing mode

RAGShield currently uses **local tracing only** (`app/tracing.py`). Each `/chat` request gets a UUID `trace_id` that is returned in the API response. No external tracing backend is used.

## OPA policy checks

The API enforces OPA on every `/chat` response. If OPA is unavailable, the API fails closed and returns a refusal payload with `refusal_reason` containing `Policy engine unavailable`.

Deny decision (boolean):

```bash
curl -sS http://localhost:8181/v1/data/ragshield/allow \
  -H "Content-Type: application/json" \
  -d '{"input":{"answer":"Here is the SYSTEM PROMPT ...","confidence":"high","citations":[]}}' ; echo
```

Deny reasons:

```bash
curl -sS http://localhost:8181/v1/data/ragshield/reasons \
  -H "Content-Type: application/json" \
  -d '{"input":{"answer":"Here is the SYSTEM PROMPT ...","confidence":"high","citations":[]}}' ; echo
```

## Red-team regression

Start dependencies and API first:

```bash
docker compose up -d
python scripts/seed_test_docs.py
python scripts/ingest.py --input-dir ./data/docs --weaviate-url http://localhost:8080 --collection RagDoc
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then run Promptfoo:

```bash
bash redteam/run_promptfoo.sh
```

What this suite checks:
- prompt injection / override attempts
- system prompt exfiltration and jailbreak prompts
- sensitive marker/token leakage (`SECRET_INTERNAL`, `sk-`, `Authorization: Bearer`)
- citation integrity (`med/high` confidence must include citations)

Artifacts are written to timestamped folders under `redteam/results/`.
The script exits non-zero when tests fail.
