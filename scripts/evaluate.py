"""Run a reproducible retrieval benchmark against explicitly synthetic fixtures."""
import argparse
import json
import os
from pathlib import Path
import tempfile
import time

from recall_loop.service import MemoryService
from recall_loop.sample import LESSONS, seed

CASES = [
    ("The first screen thinks I am signed out after login", "Persist the session before redirecting"),
    ("How must logout handle refresh tokens?", "Invalidate refresh tokens on logout"),
    ("What regression checks authentication callback ordering?", "Run the callback regression test"),
    ("Should I edit a migration which has already run?", "Keep migrations in timestamp order"),
    ("Prevent duplicate payments when a request is retried", "Use idempotency keys for checkout"),
    ("Verify double clicking the checkout button", "Replay the double-click checkout case"),
    ("Can a green TypeScript build prove the payment workflow works?", "A passing build is not a passing checkout"),
    ("Which customer details should appear in logging?", "Keep customer records out of logs"),
    ("Data from the previous workspace remains in cache", "Cache keys must include the workspace"),
    ("How should missing environment variables be reported?", "Validate environment variables on startup"),
]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", default="evaluation.json")
    p.add_argument("--model-cache")
    p.add_argument("--keyword-only", action="store_true")
    args = p.parse_args()
    if args.model_cache:
        os.environ["RECALL_MODEL_CACHE"] = str(Path(args.model_cache).resolve())
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    # Scratch state stays alongside the requested output, not in the user's home.
    with tempfile.TemporaryDirectory(dir=output.parent) as directory:
        service = MemoryService(Path(directory), embeddings=False)
        if not args.keyword_only:
            service.index.embedding_enabled = True
            service.index.load_embeddings()
            if service.index.embedding_state != "ready":
                raise SystemExit("Semantic embeddings unavailable. Supply --model-cache or explicitly use --keyword-only.")
        project = service.create_project("Synthetic retrieval benchmark", project="evaluation", sample=True)
        seed(service, project)
        rows = []
        for query, expected in CASES:
            start = time.perf_counter()
            result = service.search(project, query)
            labels = [m["label"] for m in result["results"]]
            rows.append({"query": query, "expected": expected, "returned": labels,
                         "hit_at_5": expected in labels, "latency_ms": round((time.perf_counter()-start)*1000, 2)})
        report = {"dataset": "Synthetic Atlas fixtures; not evidence of real coding productivity",
                  "mode": "keyword" if args.keyword_only else "hybrid",
                  "hit_at_5": sum(r["hit_at_5"] for r in rows), "cases": len(rows), "results": rows,
                  "paired_real_coding_tasks": {"status": "not_run",
                      "reason": "Requires fresh Codex sessions, an enabled integration, and controlled real task trials. No productivity improvement is claimed."}}
        service.close()
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({k: v for k,v in report.items() if k != "results"}, indent=2))


if __name__ == "__main__":
    main()
