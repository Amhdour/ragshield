"""Run RAGAS evaluation against the local /chat endpoint and emit reports."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any


def _load_dataset(path: Path) -> list[dict[str, Any]]:
    """Load JSONL dataset rows with at least question + ground_truth."""
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if "question" not in row or "ground_truth" not in row:
            raise RuntimeError("Each dataset row must include 'question' and 'ground_truth'.")
        rows.append(row)
    if not rows:
        raise RuntimeError(f"Dataset is empty: {path}")
    return rows


def _post_chat(base_url: str, query: str, timeout_s: float, retries: int) -> dict[str, Any]:
    """Query /chat with retries and return decoded JSON."""
    try:
        import requests
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Missing dependency 'requests'. Install project dependencies with `pip install -e .`."
        ) from exc

    url = f"{base_url.rstrip('/')}/chat"
    last_error: Exception | None = None
    for attempt in range(1, retries + 2):
        try:
            response = requests.post(url, json={"query": query}, timeout=timeout_s)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise RuntimeError("/chat response was not a JSON object")
            return data
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt <= retries:
                time.sleep(1.0)
                continue
            break
    raise RuntimeError(f"Failed to query {url}: {last_error}")


def _retrieve_contexts(query: str, top_k: int = 5) -> list[str]:
    """Retrieve chunk texts directly from retrieval pipeline for groundedness metrics."""
    try:
        from app.retrieval import retrieve

        docs = retrieve(query, top_k=top_k)
        texts = [str(d.get("text", d.get("content", ""))) for d in docs]
        return [t for t in texts if t]
    except Exception:
        return []


def _failure_reason(row: dict[str, Any]) -> str:
    """Derive a brief failure reason used in the markdown report."""
    if row.get("refusal_reason"):
        return f"refusal_reason={row['refusal_reason']}"
    if row.get("faithfulness", 1.0) < 0.5:
        return "low_faithfulness"
    if row.get("answer_relevancy", 1.0) < 0.5:
        return "low_answer_relevancy"
    if not row.get("contexts"):
        return "missing_contexts"
    return "lowest_combined_score"


def _evaluate(
    rows: list[dict[str, Any]],
    base_url: str,
    timeout_s: float,
    retries: int,
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    """Run /chat + retrieval context collection and compute ragas metrics."""
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import answer_relevancy, faithfulness
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Missing ragas dependencies. Install with `pip install -e .` and ensure ragas extras are available."
        ) from exc

    eval_rows: list[dict[str, Any]] = []
    for row in rows:
        question = str(row["question"])
        truth = str(row["ground_truth"])
        response = _post_chat(base_url=base_url, query=question, timeout_s=timeout_s, retries=retries)
        contexts = _retrieve_contexts(question)

        # Fallback contexts from citations if retrieval path is unavailable.
        if not contexts:
            citations = response.get("citations") or []
            contexts = [str(c.get("quote", "")) for c in citations if isinstance(c, dict)]

        eval_rows.append(
            {
                "question": question,
                "ground_truth": truth,
                "answer": str(response.get("answer", "")),
                "contexts": contexts,
                "confidence": str(response.get("confidence", "")),
                "refusal_reason": response.get("refusal_reason"),
            }
        )

    dataset = Dataset.from_list(eval_rows)
    metrics = [faithfulness, answer_relevancy]
    try:
        result = evaluate(dataset=dataset, metrics=metrics)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "RAGAS evaluation failed. Check model provider credentials and that /chat is returning valid structured output."
        ) from exc

    frame = result.to_pandas()
    metric_names = ["faithfulness", "answer_relevancy"]
    averages: dict[str, float] = {}
    for name in metric_names:
        if name in frame:
            averages[name] = float(frame[name].fillna(0.0).mean())

    scored_rows: list[dict[str, Any]] = []
    for idx, eval_row in enumerate(eval_rows):
        row_data = dict(eval_row)
        scores: list[float] = []
        for metric_name in metric_names:
            value = 0.0
            if metric_name in frame:
                value = frame.loc[idx, metric_name]
                if value != value:  # NaN
                    value = 0.0
            value = float(value)
            row_data[metric_name] = value
            scores.append(value)
        row_data["mean_score"] = float(sum(scores) / len(scores)) if scores else 0.0
        row_data["failure_reason"] = _failure_reason(row_data)
        scored_rows.append(row_data)

    scored_rows.sort(key=lambda item: item.get("mean_score", 0.0))
    return averages, scored_rows


def _write_reports(
    report_json: Path,
    report_md: Path,
    averages: dict[str, float],
    scored_rows: list[dict[str, Any]],
) -> None:
    """Write machine-readable and markdown reports."""
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_md.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "averages": averages,
        "total_examples": len(scored_rows),
        "worst_cases": scored_rows[:3],
        "rows": scored_rows,
    }
    report_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# RAGAS Evaluation Report",
        "",
        f"Total examples: {len(scored_rows)}",
        "",
        "## Mean metrics",
        "",
        f"- **faithfulness**: {averages.get('faithfulness', 0.0):.4f}",
        f"- **answer_relevancy**: {averages.get('answer_relevancy', 0.0):.4f}",
        "",
        "## Worst 3 examples",
        "",
    ]

    for idx, row in enumerate(scored_rows[:3], start=1):
        lines.extend(
            [
                f"### {idx}. {row.get('question', '')}",
                f"- Answer: {row.get('answer', '')}",
                f"- Mean score: {float(row.get('mean_score', 0.0)):.4f}",
                f"- Failure reason: {row.get('failure_reason', 'n/a')}",
                "",
            ]
        )

    report_md.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Run RAGAS evaluation against ragshield /chat")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base URL for the running API")
    parser.add_argument("--dataset", default="eval/dataset.jsonl", help="Path to evaluation dataset JSONL")
    parser.add_argument("--report-json", default="eval/report.json", help="Output JSON report path")
    parser.add_argument("--report-md", default="eval/report.md", help="Output markdown report path")
    parser.add_argument("--timeout", type=float, default=20.0, help="HTTP timeout per /chat call")
    parser.add_argument("--retries", type=int, default=2, help="Retries per /chat call")
    args = parser.parse_args()

    try:
        dataset_rows = _load_dataset(Path(args.dataset))
        averages, scored_rows = _evaluate(
            rows=dataset_rows,
            base_url=args.base_url,
            timeout_s=args.timeout,
            retries=args.retries,
        )
        _write_reports(
            report_json=Path(args.report_json),
            report_md=Path(args.report_md),
            averages=averages,
            scored_rows=scored_rows,
        )
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"RAGAS eval failed: {exc}") from exc

    print(f"Wrote {args.report_json} and {args.report_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
