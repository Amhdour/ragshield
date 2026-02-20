.PHONY: up up-langfuse seed ingest run redteam eval down

up:
	docker compose up -d weaviate opa

up-langfuse:
	docker compose --profile langfuse up -d

seed:
	python scripts/seed_test_docs.py

ingest:
	python scripts/ingest.py --input-dir ./data/docs --weaviate-url http://localhost:8080 --collection RagDoc

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000

redteam:
	bash redteam/run_promptfoo.sh

eval:
	python eval/run_ragas.py --base-url http://localhost:8000

down:
	docker compose down -v
