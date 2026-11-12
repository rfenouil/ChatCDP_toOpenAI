import json
import logging
import time
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse

from chat2openai.engine.fingerprints import is_compaction_request
from chat2openai.models import ChatCompletionRequest, ChatCompletionResponse, ChatCompletionChoice, ChatMessage

log = logging.getLogger("chat2openai.api")

CHUNK_SIZE = 20


def _chunk(completion_id, created, model, delta, finish_reason):
    return {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }


async def _sse_stream(result, req):
    completion_id = "chatcmpl-" + uuid.uuid4().hex[:12]
    created = int(time.time())
    yield f"data: {json.dumps(_chunk(completion_id, created, req.model, {'role': 'assistant'}, None))}\n\n"
    tool_calls = result.get("tool_calls") or []
    if tool_calls:
        for tc in tool_calls:
            fn = tc.get("function", {})
            name = fn.get("name", "")
            args = fn.get("arguments", "")
            yield f"data: {json.dumps(_chunk(completion_id, created, req.model, {'tool_calls': [{'index': 0, 'id': tc.get('id'), 'type': 'function', 'function': {'name': name, 'arguments': ''}}]}, None))}\n\n"
            for i in range(0, len(args), CHUNK_SIZE):
                piece = args[i:i + CHUNK_SIZE]
                yield f"data: {json.dumps(_chunk(completion_id, created, req.model, {'tool_calls': [{'index': 0, 'function': {'arguments': piece}}]}, None))}\n\n"
        yield f"data: {json.dumps(_chunk(completion_id, created, req.model, {}, 'tool_calls'))}\n\n"
    else:
        content = result.get("reply", "")
        for i in range(0, len(content), CHUNK_SIZE):
            piece = content[i:i + CHUNK_SIZE]
            yield f"data: {json.dumps(_chunk(completion_id, created, req.model, {'content': piece}, None))}\n\n"
        yield f"data: {json.dumps(_chunk(completion_id, created, req.model, {}, 'stop'))}\n\n"
    yield "data: [DONE]\n\n"


def make_router(get_engine, expected_token):
    router = APIRouter(prefix="/v1")

    async def auth(authorization: str = Header(default="")):
        token = authorization.removeprefix("Bearer ").strip()
        if token != expected_token:
            raise HTTPException(status_code=401, detail={"error": {"message": "invalid bearer token", "type": "authentication_error"}})

    @router.get("/models", dependencies=[Depends(auth)])
    async def models():
        engine = get_engine()
        return {"object": "list", "data": await engine.list_models()}

    @router.get("/debug/sessions", dependencies=[Depends(auth)])
    async def debug_sessions():
        return get_engine().cache.stats()

    @router.post("/chat/completions", dependencies=[Depends(auth)])
    async def chat_completions(req: ChatCompletionRequest, x_session_id: str = Header(default="default", alias="X-Session-Id")):
        log.debug("chat.completions session=%s messages=%d tools=%s", x_session_id, len(req.messages), bool(req.tools))
        payload = [m.model_dump() for m in req.messages]
        if is_compaction_request(payload):
            log.info("compaction request detected (session=%s), returning empty summary", x_session_id)
            completion_id = "chatcmpl-" + uuid.uuid4().hex[:12]
            empty = ChatCompletionResponse(
                id=completion_id,
                created=int(time.time()),
                model=req.model,
                choices=[ChatCompletionChoice(message=ChatMessage(role="assistant", content=""))],
            )
            if req.stream:
                async def _empty_stream():
                    yield f"data: {json.dumps(_chunk(completion_id, empty.created, req.model, {'role': 'assistant', 'content': ''}, 'stop'))}\n\n"
                    yield "data: [DONE]\n\n"
                return StreamingResponse(_empty_stream(), media_type="text/event-stream")
            return empty
        engine = get_engine()
        try:
            result = await engine.complete(req.messages, tools=req.tools, session_id=x_session_id)
        except TimeoutError as exc:
            raise HTTPException(status_code=504, detail={"error": {"message": str(exc), "type": "upstream_timeout"}})
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail={"error": {"message": str(exc), "type": "upstream_error"}})
        completion_id = "chatcmpl-" + uuid.uuid4().hex[:12]
        created = int(time.time())
        finish_reason = result.get("finish_reason", "stop")
        if req.stream:
            return StreamingResponse(
                _sse_stream(result, req),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )
        tool_calls = result.get("tool_calls") or []
        message = ChatMessage(role="assistant", content=result.get("reply", ""))
        if tool_calls:
            message.tool_calls = tool_calls
        return ChatCompletionResponse(
            id=completion_id,
            created=created,
            model=req.model,
            choices=[ChatCompletionChoice(message=message, finish_reason=finish_reason)],
        )

    return router
