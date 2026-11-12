# chat2openai

A local proxy that exposes an **OpenAI-compatible endpoint** (`/v1/models`, `/v1/chat/completions`)
backed not by a classic LLM API, but by an **existing web chat driven via CDP**
(Chrome DevTools Protocol). Any OpenAI-compatible TUI (OpenCode, etc.) can then use
that chat as its coding-agent backend.

```
[TUI: OpenCode...] ── POST /v1/chat/completions ──► [chat2openai : 127.0.0.1] ── CDP ──► [browser + web chat]
                                                               ▲                           │
                                                               └──── MCP: JSON ◄─────────┘
```

## Principles

- The **TUI does the agent work**; the proxy only translates the protocol
- The **chat keeps its own history**: the proxy only forwards new messages
  (index cursor + prefix hash to detect resyncs)
- **No proxy-side compaction**: if a TUI summarization request is detected
  (compaction prompt fingerprint), the proxy replies with an empty summary without
  involving the chat
- Security: loopback (`127.0.0.1`) only, bearer token required

## Installation

```bash
python3 -m venv .venv && .venv/bin/pip install .
# or for development: .venv/bin/pip install -e ".[dev]"
```

Dependencies: fastapi, uvicorn, websockets, requests, pydantic, pydantic-settings, click.

## Running

```bash
chat2openai serve --port 8080 --token MY_TOKEN --chat-url https://chat.example.com
# the token is randomly generated and printed if not provided
```

Environment variables: prefix `CHAT2OPENAI_` (e.g. `CHAT2OPENAI_API_TOKEN`, `CHAT2OPENAI_CHAT_URL`).

## Configuring OpenCode (example)

See `examples/opencode.json` — custom `local` provider pointing at `http://127.0.0.1:8080/v1`,
model `chat-via-cdp` with a very high `limit.context` (avoids premature TUI-side compaction).

## Endpoints

| Route | Description |
|---|---|
| `GET /v1/models` | model list (bearer auth required) |
| `POST /v1/chat/completions` | completion, `stream: true` → SSE, tool_calls supported |
| `GET /v1/debug/sessions` | per-session delta-cache stats |

Header `X-Session-Id` isolates sessions on the proxy side.

## Architecture

```
chat2openai/
├── cli.py            # click: serve
├── config.py         # pydantic-settings
├── server.py         # FastAPI + lifespan
├── openai_api.py     # OpenAI translation, auth, SSE, compaction fingerprints
├── models.py         # pydantic schemas
├── logging_conf.py   # JSON logs
└── engine/
    ├── cdp.py        # CDP client (websocket)
    ├── rpc.py        # ChatRPC: inject/read MCP: messages in the chat, retries
    ├── chat_engine.py# browser lifecycle, heartbeat, complete()
    ├── session_cache.py  # delta: index + prefix hash
    ├── fingerprints.py   # compaction request detection
    └── retry.py      # with_retry
```

## Tests

```bash
.venv/bin/python -m pytest tests/ -q
```

## Completed phases

P0 CDP foundations · P1 base endpoint · P2 SSE + tool_calls · P3 robust delta ·
P4 real OpenCode integration · P5 robustness + tests · P6 packaging + docs

## Known limitations

- One chat = one browser page = one conversation; multi-session (multiple pages) is future work
- The target chat must be drivable via DOM selectors (see `chat.html` for the MCP: contract)
- Check the chat provider's ToS before plugging a third-party TUI into it
