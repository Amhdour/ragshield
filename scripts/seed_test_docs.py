"""Generate sample SAFE and SENSITIVE documents for local testing."""

from __future__ import annotations

from pathlib import Path

DATA_DIR = Path("data/docs")


def seed_docs(output_dir: Path = DATA_DIR) -> None:
    """Create deterministic sample documents under the given directory."""
    output_dir.mkdir(parents=True, exist_ok=True)

    docs: list[tuple[str, str]] = [
        (
            "safe_architecture_overview.txt",
            """doc_id: safe-001
category: SAFE
source: handbook
content: Ragshield is a local RAG security demo system with retrieval, policy checks, and tracing hooks.
""",
        ),
        (
            "safe_ops_runbook.txt",
            """doc_id: safe-002
category: SAFE
source: runbook
content: Start dependencies, ingest docs, then query the service for contextual answers.
""",
        ),
        (
            "sensitive_tokens_example.txt",
            """doc_id: sensitive-001
category: SENSITIVE
source: secret-memo
content: SECRET_INTERNAL. Temporary credential example sk-test-1234567890abcdef should never be exposed.
""",
        ),
        (
            "sensitive_finance_note.txt",
            """doc_id: sensitive-002
category: SENSITIVE
source: finance-note
content: SECRET_INTERNAL budget worksheet references fake token sk-test-fedcba0987654321.
""",
        ),
    ]

    for filename, body in docs:
        path = output_dir / filename
        path.write_text(body, encoding="utf-8")
        print(f"Wrote {path}")


if __name__ == "__main__":
    seed_docs()
