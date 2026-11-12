# Architecture decision records — chat2openai

## ADR-1: Proxy architecture, not a custom TUI

**Decision**: expose an OpenAI-compatible endpoint; reuse an existing open-source TUI
(OpenCode) as the agent harness.

**Rationale**: the harness (sessions, tools Read/Edit/Bash, agent loop, UI) is thousands
of stars of mature work. The proxy only translates protocols. llm-proxy (Codeberg,
jbousquie) validated the same pattern for Albert API.

## ADR-2: The chat owns its history; the proxy forwards deltas only

**Decision**: never resend the full TUI `messages[]` into the chat. The OpenAI API is
stateless (each request carries the full history — verified in OpenCode docs), while the
chat keeps and resubmits its own history to the model. Forwarding everything would
double-count context (quadratic cost).

**Implementation**: `engine/session_cache.py` — per-session index cursor + **prefix
hash**. If `hash(messages[:last_index])` matches the known prefix → append-only → send
`messages[last_index:]`. Otherwise → full resync (send all, count `resyncs`).

**Why not pure per-message hash dedup**: it failed in practice — OpenCode's internal
title-generation request and the agent request contained a byte-identical user message,
so the pure hash set dropped the agent's message (found during the P4 OpenCode test).

## ADR-3: No proxy-side compaction of the chat history

**Decision**: the proxy never asks the model (via the chat) for a summary and never
alters history.

**Rationale**: the model's context is assembled by the chat from its own history; the
user cares about the model's context, not the TUI's. The chat handles its own window.

## ADR-4: Anti-compaction policy against TUI-side compaction

**Decision**: three layers —
1. Prevention: configure the TUI with a huge `limit.context` (e.g. 10 000 000) so it
   never auto-compacts.
2. Firewall: if a summarization request is detected (fingerprint of the exact
   compaction prompt, pinned per client version from its open-source repo — e.g. OpenCode
   `packages/core/src/session/compaction.ts`; note v2 sends the prompt in the **last
   user message, no system prompt**), reply with an **empty summary** without calling the
   chat. This also caps TUI→proxy payload growth (the summary replaces the head of
   `messages[]`).
3. Fallback: generic markers ("summarize only the history", …) for unknown clients.

## ADR-5: Auth and network posture

Loopback-only bind (`127.0.0.1`), mandatory bearer token (random if unset), never
exposed publicly. Sandbox note: GitHub writes from the sandbox are blocked by the egress
proxy; delivery used OAuth device flow for `gh` + explicit-URL `git push` with
`gh auth git-credential`.

## ADR-6: Tech stack

Python 3.11+, FastAPI + uvicorn (SSE via StreamingResponse), websockets (CDP),
pydantic / pydantic-settings, click CLI, hatchling packaging, pytest + httpx for
contract tests with a fake engine.

## ADR-7: Error mapping

Chat timeout → HTTP 504; upstream chat error → 502 with OpenAI-shaped error body;
auth failure → 401. Retries: 3 attempts, linear backoff, on TimeoutError/RuntimeError.
