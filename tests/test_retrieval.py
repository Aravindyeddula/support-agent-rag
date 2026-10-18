from app.evaluate import evaluate
from app.retrieval import Retriever, chunk_document, ingest
from conftest import FakeProvider


def test_refund_query_finds_billing(store):
    hits = Retriever(store).search("first subscription refund eligibility")
    assert hits[0]["document_id"] == "billing"
    assert "14 days" in hits[0]["content"]


def test_out_of_domain_has_no_evidence(store):
    assert Retriever(store).search("chocolate brownies recipe") == []


def test_chunking_preserves_headings_and_deterministic_ids():
    content = "# Access\n\n## SSO\n" + " ".join(f"word{i}" for i in range(200))
    chunks = chunk_document("access", "Access", content)
    assert len(chunks) == 2
    assert chunks[0]["section"] == "SSO"
    assert set(chunks[0]["content"].split()) & set(chunks[1]["content"].split())
    assert chunks == chunk_document("access", "Access", content)


def test_reingest_is_idempotent_and_replaces_stale_chunks(store):
    ingest(store, "custom", "Pineapple", "# Pineapple\n\nPineapple means version one.")
    original = [c["id"] for c in store.chunks() if c["document_id"] == "custom"]
    assert not ingest(store, "custom", "Pineapple", "# Pineapple\n\nPineapple means version one.")
    assert ingest(store, "custom", "Pineapple", "# Pineapple\n\nPineapple means version two.")
    current = [c for c in store.chunks() if c["document_id"] == "custom"]
    assert len(current) == 1 and current[0]["id"] not in original
    assert "version two" in Retriever(store).search("Pineapple")[0]["content"]


def test_hybrid_caches_document_vectors_and_reuses_them(store):
    class CountingProvider(FakeProvider):
        batches = []
        def embed(self, texts):
            self.batches.append(list(texts))
            return super().embed(texts)
    provider = CountingProvider()
    retriever = Retriever(store, provider)
    first = retriever.search("webhook signature", hybrid=True)
    assert first and first[0]["retrieval"] == "hybrid-rrf"
    document_batch_count = len(provider.batches) - 1
    retriever.search("webhook signature", hybrid=True)
    assert len(provider.batches) == document_batch_count + 2  # second search embeds only the query


def test_synthetic_retrieval_regression(store):
    report = evaluate(store)
    assert report["cases"] == 14
    assert report["hit_rate_at_4"] >= .9
    assert report["mrr_at_4"] >= .8
    assert report["no_evidence_accuracy"] == 1


def test_title_change_updates_provenance(store):
    text = "This shared document describes a custom workspace procedure."
    ingest(store, "rename", "Old title", text)
    assert ingest(store, "rename", "New title", text)
    assert store.document("rename")["title"] == "New title"
    assert [c for c in store.chunks() if c["document_id"] == "rename"][0]["title"] == "New title"
