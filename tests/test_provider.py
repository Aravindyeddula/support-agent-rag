import httpx
import pytest

from app.config import Settings
from app.provider import OpenAIProvider, ProviderError


def test_responses_http_contract_and_usage():
    def handler(request):
        import json
        payload = json.loads(request.content)
        assert request.url.path == "/v1/responses"
        assert payload["store"] is False and payload["parallel_tool_calls"] is False
        assert payload["input"][0]["content"] == "hello"
        return httpx.Response(200, json={"output": [], "usage": {"input_tokens": 10, "output_tokens": 4}})
    provider = OpenAIProvider(Settings(api_key="test-key"), httpx.MockTransport(handler))
    provider.respond("instructions", [{"role": "user", "content": "hello"}], [])
    assert provider.usage["input_tokens"] == 10 and provider.usage["requests"] == 1


def test_final_output_contract_is_strict_json_schema():
    from app.agent import answer_schema
    def handler(request):
        import json
        payload = json.loads(request.content)
        config = payload["text"]["format"]
        assert config["type"] == "json_schema" and config["strict"] is True
        allowed = config["schema"]["properties"]["claims"]["items"]["properties"]["source_ids"]["items"]["enum"]
        assert allowed == ["known-source"]
        return httpx.Response(200, json={"output": []})
    provider = OpenAIProvider(Settings(api_key="test-key"), httpx.MockTransport(handler))
    provider.respond("instructions", [], [], response_schema=answer_schema({"known-source"}))


def test_embedding_rows_are_reordered_and_validated():
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json={"data": [
        {"index": 1, "embedding": [0., 1.]}, {"index": 0, "embedding": [1., 0.]}], "usage": {"total_tokens": 3}}))
    provider = OpenAIProvider(Settings(api_key="test-key"), transport)
    assert provider.embed(["a", "b"]) == [[1., 0.], [0., 1.]]
    assert provider.usage["embedding_tokens"] == 3


def test_http_errors_are_sanitized():
    provider = OpenAIProvider(Settings(api_key="test-key"), httpx.MockTransport(
        lambda _: httpx.Response(401, json={"error": "sensitive-provider-detail"})))
    with pytest.raises(ProviderError) as error:
        provider.embed(["hello"])
    assert "401" in str(error.value) and "sensitive" not in str(error.value) and "test-key" not in str(error.value)


def test_transient_errors_retry_then_succeed():
    attempts = []
    def handler(request):
        attempts.append(1)
        return httpx.Response(429 if len(attempts) == 1 else 200, json={"data": [{"index": 0, "embedding": [1., 2.]}]})
    provider = OpenAIProvider(Settings(api_key="test-key"), httpx.MockTransport(handler))
    assert provider.embed(["hello"]) == [[1., 2.]] and len(attempts) == 2
