import json
import re
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .agent import Agent
from .config import ROOT, Settings
from .retrieval import ingest
from .store import Store


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=2000)
    mode: str = Field(default="demo", pattern="^(demo|live)$")
    model: str | None = Field(default=None, min_length=1, max_length=100)
    allow_draft: bool = False


class DocumentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=3, max_length=120)
    content: str = Field(min_length=40, max_length=60000)


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=20, max_length=100)


def create_app(settings=None, provider_factory=None):
    settings = settings or Settings.from_env()
    store = Store(settings.data_dir / "atlas.sqlite3")
    if not store.documents():
        for path in sorted((ROOT / "data" / "knowledge").glob("*.md")):
            content = path.read_text(encoding="utf-8")
            title = content.splitlines()[0].lstrip("# ")
            ingest(store, path.stem, title, content)
    agent = Agent(store, settings, **({"provider_factory": provider_factory} if provider_factory else {}))
    app = FastAPI(title="Atlas Support Agent", version="1.0.0")
    app.state.store, app.state.agent = store, agent
    gate = threading.BoundedSemaphore(3)

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        # Prevent browser cross-origin writes to a local unauthenticated demo.
        origin = request.headers.get("origin")
        if request.method not in ("GET", "HEAD") and origin and origin != str(request.base_url).rstrip("/"):
            raise_error = {"detail": "Cross-origin writes are disabled"}
            from fastapi.responses import JSONResponse
            return JSONResponse(raise_error, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
        return response

    @app.get("/api/health")
    def health():
        return {"status": "ok", "live_available": bool(settings.api_key), "model": settings.model,
                "models": list(settings.model_options), "response_contract": "claims-v1",
                "documents": len(store.documents()), "chunks": len(store.chunks()), "version": "1.0.0"}

    @app.get("/api/documents")
    def documents():
        return store.documents()

    @app.get("/api/documents/{doc_id}")
    def document(doc_id: str):
        value = store.document(doc_id)
        if not value:
            raise HTTPException(404, "Document not found")
        return value

    @app.post("/api/documents", status_code=201)
    def add_document(body: DocumentRequest):
        title, content = body.title.strip(), body.content.strip()
        if len(title) < 3 or len(content) < 40:
            raise HTTPException(422, "Document title or body is empty")
        import hashlib
        doc_id = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:55]
        doc_id = "custom-" + (doc_id or "document") + "-" + hashlib.sha256(title.encode()).hexdigest()[:6]
        changed = ingest(store, doc_id, title, content)
        return {"id": doc_id, "changed": changed, "chunks": len([c for c in store.chunks() if c["document_id"] == doc_id])}

    @app.post("/api/runs/stream")
    def run(body: RunRequest):
        question = body.question.strip()
        if len(question) < 3:
            raise HTTPException(422, "Question must contain text")
        if body.model is not None and body.model not in settings.model_options:
            raise HTTPException(400, "Choose one of the configured models")
        if body.mode == "live" and not settings.api_key:
            raise HTTPException(400, "Set OPENAI_API_KEY on the server to use live mode")
        if not gate.acquire(blocking=False):
            raise HTTPException(429, "Three runs are already active; retry shortly")

        def stream():
            try:
                for item in agent.run(question, body.mode, body.allow_draft, model=body.model):
                    yield "data: " + json.dumps(item) + "\n\n"
            finally:
                gate.release()
        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/api/runs")
    def runs():
        return store.runs()

    @app.post("/api/runs/{run_id}/approve")
    def approve(run_id: str, body: ApprovalRequest):
        try:
            return store.approve(run_id, body.token)
        except PermissionError:
            raise HTTPException(403, "Invalid approval token") from None
        except ValueError:
            raise HTTPException(409, "This run has no completed draft") from None

    @app.get("/api/tickets")
    def tickets():
        return store.tickets()

    @app.get("/api/evaluation")
    def evaluation():
        from .evaluate import evaluate
        return evaluate(store)

    @app.get("/")
    def home():
        return FileResponse(ROOT / "web" / "index.html")

    app.mount("/static", StaticFiles(directory=ROOT / "web"), name="static")
    return app


app = create_app()
