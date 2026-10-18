# Verification record

Verified locally on Windows with Python 3.12.14 and headless Microsoft Edge. Application dependencies are pinned in `requirements.txt`; test and browser dependencies are pinned in `requirements-dev.txt`.

## Executed

- 43 Python behavioral and HTTP protocol tests passed: retrieval, document updates, cache reuse, structured answer references, bounded format repair, incomplete outputs, refusals, task authorization, unknown tools, bounded loops, approved and rejected drafts, source-derived priority, idempotent approval, model validation, and per-request model selection.
- Real browser flows: model selection, missing-key setup guidance, answering with citations, source navigation, draft approval, ingestion, safe rendering of untrusted text, evaluation results, history, and mobile overflow checks.
- Browser console: no application JavaScript errors during the smoke check.
- Python compilation and JavaScript syntax checking.
- Offline evaluation from a temporary database seeded only with the shipped corpus.
- Live OpenAI checks: the exact question "How should I handle HTTP 429 rate limit errors?" produced source-cited answers with `gpt-4.1-mini`, `gpt-4.1`, and `gpt-4.1-nano`. Three consecutive additional `gpt-4.1-mini` checks passed. These exercised embeddings, cached-vector reuse, structured final outputs, and source-ID validation. Credentials were loaded from the local environment and are excluded from source packages.
- The same question was rerun in the user's open in-app browser. The cited answer and verified-source status were visible. Screenshots are saved in `docs/live-workbench.jpg` and `docs/live-answer.jpg`.

The evaluation report contains 14 synthetic cases: 11 answerable and three with no relevant source. The measured BM25 baseline has hit rate@4 1.000, MRR@4 1.000, and no-evidence accuracy 1.000. The test set is authored alongside the documents and is intended as a regression check.

## Not executed

- A systematic live answer-quality evaluation across diverse questions. Scripted doubles and HTTP mocks cover the broader provider protocol.
- A Docker build or hosted deployment.
- Production-load testing, independent answer-quality review, or a live-model prompt-injection evaluation.
- GitHub Actions: the workflow is supplied; it has not run on a remote repository.

The installed Starlette test client currently emits a deprecation warning about its `httpx` integration. Tests pass with the pinned versions; the warning is not suppressed.
