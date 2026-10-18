import hashlib
import math
import re
from collections import Counter

STOP = set("a an and are as at be been by can do does for from how i if in into is it me my of on or our please that the their this to us was we what when where which who why will with would you your".split())


def tokenize(text):
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOP and len(t) > 1]


def chunk_document(doc_id, title, content, size=150, overlap=25):
    """Keep heading provenance and cap windows by words, with deterministic IDs."""
    section = title
    blocks = []
    for block in re.split(r"(^#{1,6}\s+[^\n]+$)", content, flags=re.M):
        if block.lstrip().startswith("#") and "\n" not in block.strip():
            section = block.lstrip("# ").strip()
        elif block.strip():
            words = block.strip().split()
            for start in range(0, len(words), size - overlap):
                text = " ".join(words[start:start + size])
                full = f"{title} / {section}\n{text}"
                fingerprint = hashlib.sha256(full.encode()).hexdigest()
                chunk_id = hashlib.sha256(f"{doc_id}:{len(blocks)}:{full}".encode()).hexdigest()[:12]
                blocks.append(dict(id=chunk_id, section=section, content=text, fingerprint=fingerprint))
                if start + size >= len(words):
                    break
    return blocks


def ingest(store, doc_id, title, content):
    return store.upsert_document(doc_id, title, content, chunk_document(doc_id, title, content))


def cosine(left, right):
    if len(left) != len(right):
        raise ValueError("Embedding dimensions differ; rebuild the cache with a consistent model")
    norm = math.sqrt(sum(x*x for x in left) * sum(x*x for x in right))
    return sum(x*y for x, y in zip(left, right)) / norm if norm else 0.0


def lexical_rank(chunks, query):
    terms = set(tokenize(query))
    if not chunks or not terms:
        return []
    docs = [Counter(tokenize(c["title"] + " " + c["section"] + " " + c["content"])) for c in chunks]
    avg_len = sum(sum(d.values()) for d in docs) / len(docs)
    frequencies = {t: sum(t in d for d in docs) for t in terms}
    ranked = []
    for chunk, counts in zip(chunks, docs):
        length = sum(counts.values())
        score = 0.0
        for t in terms:
            tf = counts[t]
            if tf:
                idf = math.log(1 + (len(docs) - frequencies[t] + .5) / (frequencies[t] + .5))
                score += idf * tf * 2.5 / (tf + 1.5 * (.25 + .75 * length / max(avg_len, 1)))
        if score > 0:
            ranked.append((chunk, score))
    return sorted(ranked, key=lambda r: (-r[1], r[0]["id"]))


class Retriever:
    def __init__(self, store, provider=None):
        self.store = store
        self.provider = provider

    def search(self, query, k=4, hybrid=False):
        chunks = self.store.chunks()
        lexical = lexical_rank(chunks, query)
        if not hybrid:
            return [{**c, "score": round(s, 4), "retrieval": "bm25"} for c, s in lexical[:k]]
        if not self.provider:
            raise ValueError("Hybrid search requires an embedding provider")
        model = self.provider.embedding_model
        cached = self.store.cached_embeddings(model)
        missing = {c["fingerprint"]: c["title"] + " / " + c["section"] + "\n" + c["content"]
                   for c in chunks if c["fingerprint"] not in cached}
        pending = list(missing.items())
        for start in range(0, len(pending), 32):
            batch = pending[start:start + 32]
            vectors = self.provider.embed([text for _, text in batch])
            rows = [(fingerprint, vector) for (fingerprint, _), vector in zip(batch, vectors)]
            self.store.save_embeddings(model, rows)
            cached.update(rows)
        query_vector = self.provider.embed([query])[0]
        dense = sorted([(c, cosine(query_vector, cached[c["fingerprint"]])) for c in chunks],
                       key=lambda r: (-r[1], r[0]["id"]))
        dense = [(c, s) for c, s in dense if s >= .20]
        # Reciprocal rank fusion avoids combining incompatible raw score scales.
        fused = {}
        for ranking in (lexical[:20], dense[:20]):
            for rank, (chunk, _) in enumerate(ranking, 1):
                fused[chunk["id"]] = fused.get(chunk["id"], 0) + 1 / (60 + rank)
        ordered = sorted(chunks, key=lambda c: (-fused.get(c["id"], 0), c["id"]))
        return [{**c, "score": round(fused[c["id"]], 5), "retrieval": "hybrid-rrf"}
                for c in ordered if c["id"] in fused][:k]
