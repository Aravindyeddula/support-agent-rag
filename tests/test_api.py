from conftest import events


def test_health_never_exposes_api_key(client):
    result = client.get("/api/health")
    assert result.status_code == 200 and result.json()["documents"] == 7
    assert "api_key" not in result.text
    assert result.json()["models"] == ["gpt-4.1-mini", "gpt-4.1", "gpt-4.1-nano"]


def test_stream_returns_evidence_and_complete_event(client):
    response = client.post("/api/runs/stream", json={"question": "How do I handle HTTP 429?"})
    assert response.headers["content-type"].startswith("text/event-stream")
    data = events(response)
    assert data[0]["type"] == "started" and data[-1]["type"] == "done"
    assert any(e["type"] == "answer_delta" for e in data)
    assert client.get("/api/runs").json()[0]["status"] == "completed"


def test_approval_rejects_bad_token_and_is_idempotent(client):
    result = events(client.post("/api/runs/stream", json={"question": "Escalate duplicate charges", "allow_draft": True}))[-1]
    path = f"/api/runs/{result['run_id']}/approve"
    assert client.get("/api/tickets").json() == []
    assert client.post(path, json={"token": "incorrect-approval-token-value"}).status_code == 403
    first = client.post(path, json={"token": result["approval_token"]})
    second = client.post(path, json={"token": result["approval_token"]})
    assert first.status_code == 200 and first.json()["id"] == second.json()["id"]
    assert len(client.get("/api/tickets").json()) == 1
    # Exported history must never expose the approval capability or its hash.
    history = client.get("/api/runs").text
    assert result["approval_token"] not in history and "approval_hash" not in history


def test_live_mode_without_key_fails_explicitly(client):
    result = client.post("/api/runs/stream", json={"question": "refund eligibility", "mode": "live"})
    assert result.status_code == 400


def test_unconfigured_model_is_rejected(client):
    result = client.post("/api/runs/stream", json={"question": "refund eligibility", "model": "unconfigured-model"})
    assert result.status_code == 400 and "configured models" in result.json()["detail"]


def test_model_selection_is_per_request_and_recorded(tmp_path):
    import json
    from fastapi.testclient import TestClient
    from app.config import Settings
    from app.main import create_app
    from conftest import FakeProvider, grounded_message
    selected = []

    def factory(settings):
        selected.append(settings.model)
        def answer(items):
            sources = json.loads(items[1]["content"].split("\n", 1)[1])
            return grounded_message("Verify the raw webhook body.", [sources[0]['id']])
        return FakeProvider(replies=[answer])

    with TestClient(create_app(Settings(data_dir=tmp_path, api_key="test-only"), factory)) as live_client:
        first = events(live_client.post("/api/runs/stream", json={"question": "webhook signatures", "mode": "live", "model": "gpt-4.1-nano"}))[-1]
        second = events(live_client.post("/api/runs/stream", json={"question": "webhook signatures", "mode": "live"}))[-1]
        assert selected == ["gpt-4.1-nano", "gpt-4.1-mini"]
        assert first["model"] == "gpt-4.1-nano" and second["model"] == "gpt-4.1-mini"
        assert live_client.get("/api/runs").json()[1]["result"]["model"] == "gpt-4.1-nano"


def test_demo_records_no_model_even_if_live_choice_is_selected(client):
    result = events(client.post("/api/runs/stream", json={"question": "refund eligibility", "model": "gpt-4.1-nano"}))[-1]
    assert result["model"] is None and result["usage"] is None


def test_ingestion_is_immediately_searchable_and_deduplicated(client):
    payload = {"title": "Quasar troubleshooting", "content": "# Quasar troubleshooting\n\nA quasar connection uses port 8123. Restart the quasar worker after a port change."}
    first = client.post("/api/documents", json=payload)
    assert first.status_code == 201 and first.json()["changed"]
    assert not client.post("/api/documents", json=payload).json()["changed"]
    run = events(client.post("/api/runs/stream", json={"question": "Which port does quasar use?"}))[-1]
    assert "8123" in run["answer"]
    assert first.json()["id"] in [s["document_id"] for s in run["sources"]]


def test_input_limits_and_cross_origin_writes(client):
    assert client.post("/api/runs/stream", json={"question": "   "}).status_code == 422
    assert client.post("/api/runs/stream", json={"question": "x" * 2001}).status_code == 422
    assert client.post("/api/runs/stream", json={"question": "refund", "mode": "unknown"}).status_code == 422
    assert client.post("/api/documents", json={"title": "abc", "content": "short"}).status_code == 422
    assert client.post("/api/runs/stream", json={"question": "refund"}, headers={"Origin": "https://untrusted.example"}).status_code == 403


def test_static_assets_and_api_evaluation(client):
    assert "Atlas" in client.get("/").text
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/../.env").status_code == 404
    report = client.get("/api/evaluation").json()
    assert report["cases"] == 14 and report["hit_rate_at_4"] >= .9
