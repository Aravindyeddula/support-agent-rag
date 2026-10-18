# Demo and interview guide

## Opening explanation

"Atlas is a support copilot with an inspectable retrieval layer and an explicit action boundary. It searches a fictional product knowledge base, provides source-linked responses, and can propose an escalation. A ticket exists only after human approval."

Show the mode badge first. Offline mode is deterministic and extractive. Only live mode uses a model and semantic embeddings.

## Demo sequence

1. Ask about HTTP 429 errors. Open a citation and read the original document. Explain that BM25 finds exact terminology such as error codes, while live semantic retrieval can also rank paraphrases.
2. Choose the draft task and ask about SSO administrator lockout. Inspect the execution trace and the evidence IDs. Open Runs & tickets before approving to demonstrate that no ticket exists yet.
3. Approve the draft, then show the local ticket. Explain capability validation and idempotency.
4. Add a document titled "Quasar onboarding" with a unique fictional fact, such as "Quasar activation uses port 8123." Query it immediately to demonstrate ingestion.
5. Ask for a chocolate brownie recipe. Demonstrate no-evidence abstention in the seeded corpus.
6. Run the evaluation. Explain its synthetic scope and why 100% on 14 authored questions is not a production accuracy claim.

## Design questions to prepare for

- Why combine sparse and dense retrieval? Exact error codes and semantic paraphrases are different relevance signals.
- Why reciprocal rank fusion? Raw BM25 and cosine scores have incompatible scales; rank fusion combines ordering instead.
- Why a custom loop? The small implementation makes tool authorization, evidence validation, and step limits easy to inspect. A larger system may benefit from an orchestration framework.
- How are citations produced? The model returns structured paragraphs and source-ID arrays; the server validates the IDs and renders the links. This proves reference provenance, not semantic support for every claim.
- What happens if a document tells the model to create a ticket? Retrieved instructions have no application authority. There is no model-accessible ticket-creation tool.
- What would change for production? Add authentication, tenant-scoped queries, a vector index, async ingestion, queueing, rate limits, better observability, and held-out live evaluations.
- What was tested live? The exact HTTP 429 support question completed with embedding retrieval, structured answers, and source citations on all three model-picker choices. Repeated `gpt-4.1-mini` checks passed. The broader HTTP contract and tool loop are regression-tested using mocks and scripted responses. These checks are not an independent quality benchmark.

## Honest portfolio wording

"Implemented a FastAPI support copilot with BM25 and optional embedding retrieval, a bounded tool-calling loop, source-ID validation, an SSE execution trace, and human-approved local ticket creation. Added behavioral tests and a synthetic retrieval regression report."

Avoid claiming enterprise deployment, real customer use, measured live LLM accuracy, or independent authorship of AI-assisted implementation. Make the project your own by extending it and documenting your decisions.

## Next personal contributions

1. Write 20 held-out paraphrases before modifying the retriever.
2. Run an ablation comparing BM25, dense-only, and fusion after enabling live mode.
3. Add one real integration with a sandbox account, keeping the approval boundary.
4. Record a two-minute walkthrough explaining one failure and the fix.
