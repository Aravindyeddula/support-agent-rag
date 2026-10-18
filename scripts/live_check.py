"""Opt-in live API regression check using the running server's configured key."""
import argparse
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
QUESTION = "How should I handle HTTP 429 rate limit errors?"


def check(url, models, repeats):
    with urlopen(url + "/api/health", timeout=10) as response:
        health = json.load(response)
    if health.get("response_contract") != "claims-v1":
        raise RuntimeError("Restart Atlas first: the server is not using the structured answer contract")
    if not health.get("live_available"):
        raise RuntimeError("A server-side API key is required for this opt-in check")
    results = []
    for model in models:
        for attempt in range(1, repeats + 1):
            body = {"question": QUESTION, "mode": "live", "model": model, "allow_draft": False}
            request = Request(url + "/api/runs/stream", data=json.dumps(body).encode(),
                              headers={"Content-Type": "application/json"})
            with urlopen(request, timeout=180) as response:
                events = [json.loads(line[6:]) for line in response if line.startswith(b"data: ")]
            result = events[-1]
            references = set(re.findall(r"\[([a-zA-Z0-9_-]+)\]", result.get("answer", "")))
            known = {s["id"] for s in result.get("sources", [])}
            passed = (result.get("outcome") == "answered" and result.get("model") == model
                      and bool(references) and references.issubset(known)
                      and "retry-after" in result.get("answer", "").lower())
            row = {"model": model, "attempt": attempt, "passed": passed,
                   "outcome": result.get("outcome"), "citation_count": len(references),
                   "latency_ms": result.get("latency_ms"), "usage": result.get("usage")}
            results.append(row)
            print(json.dumps(row), flush=True)
    report = {"question": QUESTION, "scope": "Live smoke check of one synthetic support question; not an accuracy benchmark.",
              "passed": all(r["passed"] for r in results), "results": results}
    path = ROOT / "reports" / "live-smoke.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if not report["passed"]:
        raise RuntimeError("One or more live checks failed; inspect reports/live-smoke.json")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--models", nargs="+", default=["gpt-4.1-mini"])
    parser.add_argument("--repeats", type=int, choices=range(1, 6), default=1)
    options = parser.parse_args()
    check(options.url.rstrip("/"), options.models, options.repeats)
