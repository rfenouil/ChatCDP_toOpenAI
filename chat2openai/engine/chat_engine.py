import asyncio
import logging
import os
import subprocess
import tempfile

from chat2openai.engine.cdp import CDPClient, find_page_target, wait_for_debug_port
from chat2openai.engine.rpc import ChatRPC
from chat2openai.engine.session_cache import SessionCache

log = logging.getLogger("chat2openai.engine")


class CDPChatEngine:
    def __init__(self, settings):
        self.settings = settings
        self.chrome = None
        self.cdp = None
        self.rpc = None
        self.cache = SessionCache()
        self._heartbeat_task = None

    async def start(self):
        env = dict(os.environ)
        if self.settings.chrome_ld_library_path:
            env["LD_LIBRARY_PATH"] = self.settings.chrome_ld_library_path + ":" + env.get("LD_LIBRARY_PATH", "")
        if self.settings.chrome_fontconfig_file:
            env["FONTCONFIG_FILE"] = self.settings.chrome_fontconfig_file
        profile = tempfile.mkdtemp(prefix="chat2openai-profile-")
        self.chrome = subprocess.Popen([
            self.settings.chrome_path, "--headless", "--no-sandbox", "--disable-gpu",
            f"--remote-debugging-port={self.settings.debug_port}",
            f"--user-data-dir={profile}",
            "about:blank",
        ], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        wait_for_debug_port(self.settings.debug_port)
        target = find_page_target(self.settings.debug_port)
        self.cdp = await CDPClient(target["webSocketDebuggerUrl"]).__aenter__()
        await self.cdp.send("Page.enable")
        await self.cdp.send("Page.navigate", {"url": self.settings.chat_url})
        await asyncio.sleep(1.0)
        self.rpc = ChatRPC(self.cdp)
        self._heartbeat_task = asyncio.create_task(self._heartbeat())

    async def _heartbeat(self, interval=30):
        while True:
            await asyncio.sleep(interval)
            try:
                await self.rpc.call("ping", timeout=10, attempts=1)
            except Exception as exc:
                log.warning("heartbeat failed: %s", exc)

    async def stop(self):
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
        if self.cdp is not None:
            await self.cdp.__aexit__(None, None, None)
        if self.chrome is not None:
            self.chrome.terminate()
            self.chrome.wait(timeout=10)

    async def list_models(self):
        resp = await self.rpc.call("tools/list", timeout=10)
        if "error" in resp:
            raise RuntimeError(resp["error"])
        return [{"id": "chat-via-cdp", "object": "model"}]

    async def complete(self, messages, tools=None, session_id="default"):
        all_payload = [
            {"role": m.role, "content": m.content or ""}
            for m in messages
        ]
        delta = self.cache.delta(session_id, all_payload)
        params = {"messages": delta, "full_length": len(all_payload)}
        if tools:
            params["tools"] = tools
        resp = await self.rpc.call("chat", params)
        if "error" in resp:
            raise RuntimeError(f"chat error {resp['error'].get('code')}: {resp['error'].get('message')}")
        return resp["result"]
