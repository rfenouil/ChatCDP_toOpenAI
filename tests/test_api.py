import json

import pytest
from httpx import ASGITransport, AsyncClient

from chat2openai.config import Settings
from chat2openai.server import create_app


class FakeEngine:
    def __init__(self):
        self.calls = []
        self.cache = type("C", (), {"stats": lambda self: {}})()

    async def list_models(self):
        return [{"id": "chat-via-cdp", "object": "model"}]

    async def complete(self, messages, tools=None, session_id="default"):
        self.calls.append({"messages": [m.model_dump() for m in messages], "tools": bool(tools), "session_id": session_id})
        if tools:
            return {
                "finish_reason": "tool_calls",
                "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": tools[0]["function"]["name"], "arguments": "{\"a\":1}"}}],
            }
        return {"finish_reason": "stop", "reply": "pong"}


@pytest.fixture
def settings():
    return Settings(api_token="tok")


@pytest.fixture
async def client(settings):
    app = create_app(settings, engine=FakeEngine())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


AUTH = {"Authorization": "Bearer tok"}


async def test_models_requires_auth(client):
    r = await client.get("/v1/models")
    assert r.status_code == 401
    r = await client.get("/v1/models", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["data"][0]["id"] == "chat-via-cdp"


async def test_chat_completion_non_streaming(client):
    r = await client.post("/v1/chat/completions", headers=AUTH, json={
        "model": "chat-via-cdp",
        "messages": [{"role": "user", "content": "hi"}],
    })
    assert r.status_code == 200
    body = r.json()
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"]["content"] == "pong"
    assert body["choices"][0]["finish_reason"] == "stop"


async def test_chat_completion_tool_calls(client):
    r = await client.post("/v1/chat/completions", headers=AUTH, json={
        "model": "chat-via-cdp",
        "messages": [{"role": "user", "content": "run"}],
        "tools": [{"type": "function", "function": {"name": "bash", "parameters": {}}}],
    })
    body = r.json()
    assert body["choices"][0]["finish_reason"] == "tool_calls"
    tc = body["choices"][0]["message"]["tool_calls"][0]
    assert tc["function"]["name"] == "bash"
    assert json.loads(tc["function"]["arguments"]) == {"a": 1}


async def test_streaming_sse(client):
    r = await client.post("/v1/chat/completions", headers=AUTH, json={
        "model": "chat-via-cdp", "stream": True,
        "messages": [{"role": "user", "content": "hi"}],
    })
    assert r.status_code == 200
    text = r.text
    assert "data: " in text and "data: [DONE]" in text
    chunks = [json.loads(l[6:]) for l in text.splitlines() if l.startswith("data: ") and l != "data: [DONE]"]
    content = "".join(c["choices"][0]["delta"].get("content", "") for c in chunks)
    assert content == "pong"
    assert chunks[-1]["choices"][0]["finish_reason"] == "stop"


async def test_compaction_request_short_circuit(client, settings):
    app_engine = None
    r = await client.post("/v1/chat/completions", headers=AUTH, json={
        "model": "chat-via-cdp",
        "messages": [{"role": "user", "content": "Summarize only the history shown above. Do not answer the conversation itself."}],
    })
    assert r.status_code == 200
    assert r.json()["choices"][0]["message"]["content"] == ""


async def test_upstream_error_mapped(client, settings):
    class FailingEngine(FakeEngine):
        async def complete(self, messages, tools=None, session_id="default"):
            raise RuntimeError("chat error -32601: methode inconnue")

    app = create_app(settings, engine=FailingEngine())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/v1/chat/completions", headers=AUTH, json={
            "model": "chat-via-cdp",
            "messages": [{"role": "user", "content": "hi"}],
        })
    assert r.status_code == 502
    assert r.json()["detail"]["error"]["type"] == "upstream_error"
