from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.evaluate import seed_store
from app.main import create_app
from app.store import Store


@pytest.fixture
def store(tmp_path):
    value = Store(tmp_path / "test.sqlite3")
    seed_store(value)
    return value


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path))) as value:
        yield value


def events(response):
    import json
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


class FakeProvider:
    """A scripted protocol double, never a claimed live model evaluation."""
    embedding_model = "test-v1"

    def __init__(self, settings=None, replies=None):
        self.replies = iter(replies or [])
        self.calls = []
        self.usage = {"input_tokens": 0, "output_tokens": 0, "embedding_tokens": 0, "requests": 0}

    def embed(self, texts):
        # Lexical tests establish relevance. This double exercises vector plumbing.
        return [[1.0, float("webhook" in text.lower()), .5] for text in texts]

    def respond(self, instructions, items, tools, *, response_schema=None):
        self.calls.append({"items": list(items), "tools": tools, "response_schema": response_schema})
        reply = next(self.replies)
        return reply(items) if callable(reply) else reply


def final_message(text):
    return {"output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}]}


def grounded_message(text="", source_ids=None, status="answered"):
    import json
    claims = [{"text": text, "source_ids": source_ids or []}] if status == "answered" else []
    return final_message(json.dumps({"status": status, "claims": claims}))


def tool_call(name, args, call_id="test-call"):
    import json
    return {"output": [{"type": "function_call", "id": call_id, "call_id": call_id,
                        "name": name, "arguments": json.dumps(args)}]}
