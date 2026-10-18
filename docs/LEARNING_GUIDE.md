# Atlas implementation and interview guide

Use this guide with the source open. The goal is to understand each behavior well enough to explain it, debug it, and change it yourself. Atlas is a working local demonstration, with deliberate limits described in the README.

## A useful reading order

1. **`app/main.py`**: Start at `create_app`. Follow configuration, SQLite creation, initial corpus seeding, request validation, and `/api/runs/stream`. Notice that the concurrency gate is acquired before streaming and released in `finally`.
2. **`app/retrieval.py`**: Read `chunk_document`, `ingest`, `lexical_rank`, then `Retriever.search`. Follow one paragraph from a Markdown document into a chunk, a lexical score, an embedding-cache key, and a fused result.
3. **`app/provider.py`**: Inspect the exact HTTP payloads for embeddings and Responses. Find the structured answer format, finite retries, timeout, and usage accounting. No orchestration framework or OpenAI SDK hides these calls.
4. **`app/agent.py`**: Read the argument models, answer schema, reference validator, then `Agent.run`. Trace mandatory initial retrieval, model-selected calls, matching tool outputs, format repair, and the final result.
5. **`app/store.py`**: Follow the document replacement transaction, saved result, approval hash, and `approve`. Explain where duplicate-ticket prevention comes from.
6. **`web/app.js`**: Find the streaming reader, citation rendering, model selection, and approval handler. Observe how the browser separates text from DOM structure and keeps the capability in session storage.
7. **`app/evaluate.py` and `tests/`**: Compare the behavior claimed by the README with the checks that establish it. Identify what remains unmeasured.

## Concepts you should be able to explain

### What is RAG?

Retrieval-augmented generation first finds relevant external text and then supplies that text to a language model as evidence for an answer. Retrieval happens at request time; it does not retrain the model. Updating the indexed corpus changes available evidence without fine-tuning.

In Atlas, offline mode exercises retrieval and excerpts only. Live mode adds query/document embeddings and a model that generates a structured answer from retrieved text.

### What makes this an agent?

The live model can decide to call a follow-up search or prepare an authorized draft, receive the tool result, and continue within a step budget. That is a model-directed action loop. The first retrieval is fixed application orchestration. Offline mode follows fixed steps, so describing it as an autonomous model agent would be inaccurate.

The model proposes operations. Python decides which operations exist, validates their inputs, executes them, and enforces the approval boundary.

### Why split documents?

Retrieval should select a focused passage rather than put every source into every request. Small chunks improve focus but can lose context; large chunks preserve context but increase irrelevant text and token use. Atlas uses headings, 150-word windows, and 25-word overlap as readable defaults. These values are not proven optimal. Evaluate changes against held-out questions.

### Why use both BM25 and embeddings?

BM25 rewards exact terms and is easy to inspect. Dense retrieval can match different wording with similar meaning. Each can miss what the other finds. RRF uses rank positions because a BM25 score and a cosine similarity are not directly comparable. Fusion is a hypothesis to test, not a guarantee of improvement.

### How does caching stay correct?

The embedding cache key contains the embedding model and a fingerprint of title, section, and chunk text. Editing those inputs produces a different fingerprint. Changing models uses a different namespace. Old vectors may remain in storage, but retrieval only uses vectors for current chunks. The query is embedded for each search; it is not cached across requests.

### Do valid citations eliminate hallucinations?

No. Atlas can prove that a referenced ID belongs to retrieved evidence. It does not prove that the referenced passage entails the claim. A model could attach a real source to an unsupported statement. Structured output and validation improve format and provenance; semantic support needs a separate evaluation or human review.

### Why separate drafting from approval?

The model is allowed to propose a ticket only for the selected drafting task. Creation happens through another endpoint after a user supplies the per-run approval capability. The database's unique run constraint and approval transaction make repeated approval idempotent. A future external ticket adapter would also need its own idempotency mechanism to handle retries across a network boundary.

### Is the stream showing model reasoning?

No. It shows observable tool activity, results, validation, and timings. Private chain-of-thought is not exposed. Final answer text is validated before the application emits answer chunks; provider tokens are not streamed directly.

## Follow one request by hand

Use the HTTP 429 example and answer these from the code or UI:

1. Which four chunks were returned, and which document contains the retry policy?
2. In live mode, which embeddings were already cached and which API calls were necessary?
3. Did the model answer immediately or request another tool?
4. What IDs were allowed by the answer schema at the final step?
5. Which application function turned those IDs into displayed citation brackets?
6. What outcome was saved, and where are latency and token counts recorded?

Then repeat with an unsupported question. Check the distinction between no retrieved evidence, a model abstention, a validation failure, and a provider error.

## Practical exercises

### Exercise 1: Own the knowledge base

Add an original fictional policy with one precise fact, ask about it, then update the same title with a changed fact. Confirm that the latest chunks are used and unchanged ingestion is idempotent. Add a meaningful regression test if you change ingestion behavior.

### Exercise 2: Run a retrieval experiment

Write new paraphrased questions before tuning. Include exact identifiers, ambiguous wording, multi-document questions, and out-of-scope questions. Compare retrieval variants using the same labels and `k`. Report per-case failures as well as averages. Do not tune on the held-out set and then describe it as independent validation.

### Exercise 3: Evaluate generated answers

Define a small human rubric: factual correctness, completeness, source entailment, unnecessary claims, and appropriate abstention. Save model, corpus version, settings, and token use. Grade multiple runs because generation can vary. Keep retrieval relevance and answer quality as separate measurements.

### Exercise 4: Test the action boundary

Try requesting a draft while the task permits answers only. Inspect a scripted test where an unknown tool or unknown source ID is rejected. Approve a valid draft twice and verify a single ticket. Avoid testing against real customer accounts or expanding tool permissions for the experiment.

### Exercise 5: Make a measured improvement

Choose one change, such as heading-aware query expansion or a reranker. Record the baseline, implement it, run the same held-out checks, and explain the latency/cost tradeoff. A documented unsuccessful experiment is more informative than an unsupported improvement claim.

## Interview questions and concise answers

| Question | A grounded answer for this implementation |
| --- | --- |
| Why no agent framework? | A small explicit loop makes tool validation, call IDs, budget handling, and failures directly inspectable. A framework could help with larger workflows but would add abstraction here. |
| Why SQLite rather than a vector database? | The shipped corpus is small, so one local dependency keeps the project easy to run. Linear scans will become a bottleneck; measure before selecting an index. |
| What happens when a model returns malformed output? | The application validates the answer contract, permits one repair within the step budget, and withholds generated claims if validation still fails. |
| What does a score of 1.000 mean here? | Every relevant document was ranked first for the 11 answerable synthetic baseline questions, and all three out-of-scope questions returned no chunks. This does not establish generalization or answer accuracy. |
| How would you deploy it for several users? | Add identity, tenant-aware document/run access, quotas, durable jobs, secrets management, retention controls, audit records, and deployment monitoring; then test those boundaries. |
| What is the biggest remaining quality gap? | Citation IDs are validated, but semantic source support and broad answer quality are not systematically measured. A held-out retrieval set and an answer-quality rubric are the next steps. |
| What happens if a document contains malicious instructions? | It enters the model as untrusted evidence. Prompt framing helps, but the enforced protections are the restricted tools, argument validation, execution budget, and separate approval path. Resistance needs adversarial live testing. |

## Present the project accurately

Say what you personally changed and can explain. It is reasonable to describe Atlas as a local agentic RAG portfolio project with a working live integration and human-approved local escalation workflow. Do not claim real customers, production scale, guaranteed hallucination prevention, autonomous ticket execution, or an independently validated accuracy figure. Explain AI assistance and demonstrate ownership through experiments, tests, and informed design decisions.
