# ragshield

Minimal LangGraph RAG app with a portable trust/security layer.

## Repo structure

- `app/` runtime application code
- `scripts/` ingestion scripts
- `redteam/` promptfoo regression tests
- `opa/` OPA policy bundles
- `docs/` project documentation

## Quickstart

```bash
cp .env.example .env
python -c "from app.config import settings; print(settings.WEAVIATE_URL)"
```

## Local dev dependencies (Docker Compose)

Start Weaviate and OPA:

```bash
docker compose up -d
```

Check Weaviate readiness:

```bash
curl -s http://localhost:8080/v1/.well-known/ready
```

Check OPA health:

```bash
curl -s http://localhost:8181/health
```

> Langfuse is intentionally not included as a local Docker service here. It is optional and supported via environment variables (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`) for remote setups.

## Seed test documents

```bash
python scripts/seed_test_docs.py
```

This creates SAFE and SENSITIVE sample docs under `./data/docs/`.

## Ingest documents into Weaviate

```bash
python scripts/ingest.py --input-dir ./data/docs --weaviate-url http://localhost:8080 --collection RagDoc
```

## Validate retrieval

```bash
python -c "from app.retrieval import retrieve; print(len(retrieve('what is this system', 3)))"
```

Expected output is an integer from `1` to `3`.


## Tiny LiteLLM self-test (optional)

```bash
python -c "from app.llm import generate; print(generate([{'role':'user','content':'Say hello in one word.'}], request_id='readme-smoke'))"
```

If your LiteLLM endpoint/model/key are not configured, this command will fail with an actionable RuntimeError.

## Run server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Run red-team regression

```bash
promptfoo eval -c redteam/promptfooconfig.yaml
```

## Run API and test /chat

```bash
uvicorn app.main:app --reload
```

```bash
curl -s localhost:8000/chat -H "Content-Type: application/json" -d '{"query":"What docs exist?"}'
```

Expected shape:

```json
{"answer":"...","citations":[],"confidence":"low","refusal_reason":null,"trace_id":"..."}
```
