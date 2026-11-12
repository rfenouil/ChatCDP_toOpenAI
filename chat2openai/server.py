from contextlib import asynccontextmanager

from fastapi import FastAPI

from chat2openai.engine.chat_engine import CDPChatEngine
from chat2openai.logging_conf import setup_logging
from chat2openai.openai_api import make_router


def create_app(settings, engine=None):
    setup_logging()
    state = {"engine": engine}

    @asynccontextmanager
    async def lifespan(app):
        if state["engine"] is None:
            state["engine"] = CDPChatEngine(settings)
            await state["engine"].start()
        yield
        if state["engine"] is not None:
            await state["engine"].stop()

    app = FastAPI(title="chat2openai", lifespan=lifespan)
    token = settings.effective_token()
    app.state.token = token
    app.include_router(make_router(lambda: state["engine"], token))
    return app
