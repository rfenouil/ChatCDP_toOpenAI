# Functional specification — chat2openai

## Goal

Expose a local, OpenAI-compatible HTTP endpoint (`/v1/models`, `/v1/chat/completions`)
whose backend is an **existing web chat** driven through CDP (Chrome DevTools Protocol),
so that any OpenAI-compatible TUI (OpenCode, …) can use that chat as its LLM/agent backend.

## Functional requirements

| ID | Requirement | Status |
|---|---|---|
| F1 | `GET /v1/models` returns the available model list | ✅ |
| F2 | `POST /v1/chat/completions` non-streaming, OpenAI response shape | ✅ |
| F3 | `POST /v1/chat/completions` with `stream: true` → SSE (`data: …` + `data: [DONE]`) | ✅ |
| F4 | Tool calling: `tools` in request → `tool_calls` in response, `function.name` only in first SSE chunk | ✅ |
| F5 | Bearer-token auth on all endpoints; loopback bind only | ✅ |
| F6 | Forward only **new** messages to the chat (delta), chat keeps its own history | ✅ |
| F7 | Session isolation via `X-Session-Id` header | ✅ |
| F8 | Detect TUI compaction/summarization requests (prompt fingerprints) → reply empty summary, never call the chat | ✅ (heuristic + fingerprint file) |
| F9 | Retries with backoff on chat timeouts/errors; map to 502/504 | ✅ |
| F10 | Heartbeat ping to detect chat disconnection | ✅ |
| F11 | JSON structured logs | ✅ |
| F12 | `pip install .` packaging + `chat2openai` CLI | ✅ |
| F13 | Configurable chat URL / DOM selectors per provider | ⬜ (selectors hardcoded in test page) |
| F14 | Multi-chat / multi-page sessions | ⬜ |
| F15 | CI (GitHub Actions running pytest) | ⬜ |

## Non-goals

- Reimplementing the agent harness (the TUI does it)
- Compacting or altering the chat's own history (owned by the chat)
- Exposing anything beyond 127.0.0.1

## Chat-side contract (MCP: protocol)

Messages injected into the chat are prefixed `MCP:` and carry JSON-RPC 2.0 payloads
(`ping`, `tools/list`, `tools/call`, `chat`, …); responses come back as bot messages
prefixed `MCP:` and are correlated by `id`. See `chat.html` for the reference
implementation.
