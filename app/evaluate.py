"""Offline retrieval evaluation. This does not grade LLM answer correctness."""
import argparse
import json
import tempfile
from pathlib import Path

from .config import ROOT
from .retrieval import Retriever, ingest
from .store import Store


def seed_store(store):
    for path in sorted((ROOT / "data" / "knowledge").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        ingest(store, path.stem, text.splitlines()[0].lstrip("# "), text)


def evaluate(store):
    cases = json.loads((ROOT / "data" / "eval_cases.json").read_text(encoding="utf-8"))
    retriever, rows = Retriever(store), []
    for case in cases:
        hits = retriever.search(case["question"], k=4)
        ids = [h["document_id"] for h in hits]
        relevant = set(case["relevant"])
        rank = next((i for i, doc_id in enumerate(ids, 1) if doc_id in relevant), None)
        rows.append({**case, "retrieved": ids, "hit": bool(rank) if relevant else not hits,
                     "reciprocal_rank": 1 / rank if rank else 0.0})
    answerable = [r for r in rows if r["relevant"]]
    unanswerable = [r for r in rows if not r["relevant"]]
    return {"retrieval": "BM25", "k": 4, "cases": len(rows),
            "answerable_cases": len(answerable), "unanswerable_cases": len(unanswerable),
            "hit_rate_at_4": round(sum(r["hit"] for r in answerable) / len(answerable), 4),
            "mrr_at_4": round(sum(r["reciprocal_rank"] for r in answerable) / len(answerable), 4),
            "no_evidence_accuracy": round(sum(r["hit"] for r in unanswerable) / len(unanswerable), 4),
            "scope": "Small synthetic retrieval regression set; not an independent benchmark or LLM factuality evaluation.",
            "results": rows}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "retrieval.json")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as temp:
        store = Store(Path(temp) / "eval.sqlite3")
        seed_store(store)
        result = evaluate(store)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "results"}, indent=2))


if __name__ == "__main__":
    main()
