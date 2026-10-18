import hashlib
import json
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, content TEXT NOT NULL,
                    fingerprint TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id),
                    title TEXT NOT NULL, section TEXT NOT NULL, content TEXT NOT NULL,
                    fingerprint TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS embeddings (
                    fingerprint TEXT NOT NULL, model TEXT NOT NULL, vector TEXT NOT NULL,
                    PRIMARY KEY (fingerprint, model)
                );
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, question TEXT NOT NULL, mode TEXT NOT NULL,
                    status TEXT NOT NULL, created_at TEXT NOT NULL,
                    result TEXT, approval_hash TEXT
                );
                CREATE TABLE IF NOT EXISTS tickets (
                    id TEXT PRIMARY KEY, run_id TEXT NOT NULL UNIQUE REFERENCES runs(id),
                    title TEXT NOT NULL, summary TEXT NOT NULL, priority TEXT NOT NULL,
                    evidence_ids TEXT NOT NULL, created_at TEXT NOT NULL
                );
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def upsert_document(self, doc_id, title, content, chunks):
        fingerprint = hashlib.sha256((title + "\0" + content).encode()).hexdigest()
        with self.connect() as db:
            row = db.execute("SELECT fingerprint FROM documents WHERE id=?", (doc_id,)).fetchone()
            if row and row[0] == fingerprint:
                return False
            db.execute("""INSERT INTO documents VALUES (?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET title=excluded.title,content=excluded.content,
                fingerprint=excluded.fingerprint,updated_at=excluded.updated_at""",
                (doc_id, title, content, fingerprint, now()))
            db.execute("DELETE FROM chunks WHERE document_id=?", (doc_id,))
            db.executemany("INSERT INTO chunks VALUES (?,?,?,?,?,?)", [
                (c["id"], doc_id, title, c["section"], c["content"], c["fingerprint"])
                for c in chunks
            ])
        return True

    def documents(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute("""SELECT d.id,d.title,d.updated_at,
                count(c.id) AS chunks FROM documents d LEFT JOIN chunks c ON d.id=c.document_id
                GROUP BY d.id ORDER BY d.title""")]

    def document(self, doc_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
            return dict(row) if row else None

    def chunks(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM chunks ORDER BY id")]

    def cached_embeddings(self, model):
        with self.connect() as db:
            return {r[0]: json.loads(r[1]) for r in db.execute(
                "SELECT fingerprint,vector FROM embeddings WHERE model=?", (model,))}

    def save_embeddings(self, model, rows):
        with self.connect() as db:
            db.executemany("INSERT OR REPLACE INTO embeddings VALUES (?,?,?)", [
                (fingerprint, model, json.dumps(vector)) for fingerprint, vector in rows
            ])

    def start_run(self, question, mode):
        run_id = uuid.uuid4().hex
        with self.connect() as db:
            db.execute("INSERT INTO runs VALUES (?,?,?,?,?,?,?)",
                (run_id, question, mode, "running", now(), None, None))
        return run_id

    def finish_run(self, run_id, result, status="completed", approval_token=None):
        token_hash = hashlib.sha256(approval_token.encode()).hexdigest() if approval_token else None
        with self.connect() as db:
            db.execute("UPDATE runs SET status=?,result=?,approval_hash=? WHERE id=?",
                (status, json.dumps(result), token_hash, run_id))

    def runs(self):
        with self.connect() as db:
            rows = db.execute("SELECT id,question,mode,status,created_at,result FROM runs ORDER BY created_at DESC LIMIT 50")
            return [{**dict(r), "result": json.loads(r["result"]) if r["result"] else None} for r in rows]

    def approve(self, run_id, token):
        with self.connect() as db:
            # A transaction serializes two approval requests; run_id is also UNIQUE.
            db.execute("BEGIN IMMEDIATE")
            run = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            supplied = hashlib.sha256(token.encode()).hexdigest()
            if not run or not run["approval_hash"] or not secrets.compare_digest(run["approval_hash"], supplied):
                raise PermissionError("Invalid approval token")
            existing = db.execute("SELECT * FROM tickets WHERE run_id=?", (run_id,)).fetchone()
            if existing:
                return dict(existing)
            result = json.loads(run["result"])
            draft = result.get("draft")
            if run["status"] != "completed" or not draft:
                raise ValueError("This run has no completed draft")
            ticket_id = "ATL-" + uuid.uuid4().hex[:8].upper()
            db.execute("INSERT INTO tickets VALUES (?,?,?,?,?,?,?)", (
                ticket_id, run_id, draft["title"], draft["summary"], draft["priority"],
                json.dumps(draft["evidence_ids"]), now()))
            return dict(db.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone())

    def tickets(self):
        with self.connect() as db:
            return [{**dict(r), "evidence_ids": json.loads(r["evidence_ids"])}
                for r in db.execute("SELECT * FROM tickets ORDER BY created_at DESC")]
