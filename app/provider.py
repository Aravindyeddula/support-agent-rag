import math
import time

import httpx


class ProviderError(RuntimeError):
    pass


class OpenAIProvider:
    def __init__(self, settings, transport=None):
        self.key = settings.api_key
        self.model = settings.model
        self.embedding_model = settings.embedding_model
        self.transport = transport
        self.usage = {"input_tokens": 0, "output_tokens": 0, "embedding_tokens": 0, "requests": 0}

    def _post(self, route, payload):
        if not self.key:
            raise ProviderError("Live mode needs OPENAI_API_KEY on the server. Demo mode needs no key.")
        with httpx.Client(base_url="https://api.openai.com/v1/", timeout=45,
                          transport=self.transport, follow_redirects=False) as client:
            for attempt in range(3):
                try:
                    response = client.post(route, json=payload, headers={"Authorization": f"Bearer {self.key}"})
                except httpx.RequestError:
                    if attempt == 2:
                        raise ProviderError("OpenAI could not be reached. Check the server network and retry.") from None
                    time.sleep(.3 * (2 ** attempt))
                    continue
                if response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep(.3 * (2 ** attempt))
                    continue
                if response.status_code >= 400:
                    raise ProviderError(f"OpenAI returned HTTP {response.status_code}. Check model access, quota, and server configuration.")
                self.usage["requests"] += 1
                try:
                    return response.json()
                except ValueError:
                    raise ProviderError("OpenAI returned an unreadable response.") from None
        raise ProviderError("OpenAI request failed.")

    def embed(self, texts):
        data = self._post("embeddings", {"model": self.embedding_model, "input": texts, "encoding_format": "float"})
        rows = sorted(data.get("data", []), key=lambda r: r["index"])
        if len(rows) != len(texts) or [r["index"] for r in rows] != list(range(len(texts))):
            raise ProviderError("Embedding response did not match the requested batch.")
        vectors = [r.get("embedding", []) for r in rows]
        if any(not v or any(not isinstance(x, (float, int)) or not math.isfinite(x) for x in v) for v in vectors):
            raise ProviderError("Embedding response contained invalid vectors.")
        self.usage["embedding_tokens"] += data.get("usage", {}).get("total_tokens", 0)
        return vectors

    def respond(self, instructions, items, tools, *, response_schema=None):
        payload = {"model": self.model, "instructions": instructions,
            "input": items, "tools": tools, "parallel_tool_calls": False,
            "max_output_tokens": 1400, "store": False}
        if response_schema is not None:
            payload["text"] = {"format": {"type": "json_schema", "name": "grounded_answer",
                                          "strict": True, "schema": response_schema}}
        result = self._post("responses", payload)
        usage = result.get("usage", {})
        self.usage["input_tokens"] += usage.get("input_tokens", 0)
        self.usage["output_tokens"] += usage.get("output_tokens", 0)
        return result
