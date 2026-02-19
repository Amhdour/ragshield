# ragshield

Minimal LangGraph RAG app with a portable trust/security layer.

## Structure

- `app/`: runtime API, graph, retrieval, LLM, schema, policy gate, tracing
- `scripts/`: seed + ingest utilities
- `opa/`: Rego policy
- `redteam/`: Promptfoo regression suite
- `docs/`: reports and documentation

## Quickstart

```bash
cp .env.example .env
pip install -e .
```

## Required environment variables

`app/config.py` loads the following values (see `.env.example`):

- `LITELLM_BASE_URL`
- `LITELLM_MODEL`
- `LITELLM_API_KEY` (optional)
- `WEAVIATE_URL`
- `LANGFUSE_PUBLIC_KEY` (optional)
- `LANGFUSE_SECRET_KEY` (optional)
- `LANGFUSE_HOST` (optional)
- `OPA_URL`
- `TOP_K` (default `5`)

## Start local dependencies

```bash
docker compose up -d
```

Readiness wait/retry helper:

```bash
for i in {1..20}; do
  curl -fsS http://localhost:8080/v1/.well-known/ready && break
  sleep 1
done
curl -fsS http://localhost:8181/health ; echo
```

## Seed and ingest docs

```bash
python scripts/seed_test_docs.py
python scripts/ingest.py --input-dir ./data/docs --weaviate-url http://localhost:8080 --collection RagDoc
```

## Run the API

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Smoke test:

```bash
curl -sS http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query":"What docs exist?"}' ; echo
```

## Run Promptfoo red-team checks

Start dependencies + API first, then:

```bash
bash redteam/run_promptfoo.sh
```

Artifacts are written under `redteam/results/`.
