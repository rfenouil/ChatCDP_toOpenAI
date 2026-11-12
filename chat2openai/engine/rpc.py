import asyncio
import itertools
import json

from chat2openai.engine.retry import with_retry

INJECT_JS = """
(text) => {
  const input = document.getElementById('input');
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
  setter.call(input, text);
  input.dispatchEvent(new Event('input', { bubbles: true }));
  document.getElementById('send').click();
}
"""

READ_MESSAGES_JS = """
JSON.stringify(
  [...document.querySelectorAll('#messages .msg')].map(m => ({
    author: m.dataset.author, text: m.textContent
  }))
)
"""


class ChatRPC:
    def __init__(self, cdp):
        self.cdp = cdp
        self._ids = itertools.count(1)
        self._lock = asyncio.Lock()

    async def call(self, method, params=None, timeout=30, attempts=3):
        async with self._lock:
            rid = next(self._ids)

            async def _once():
                request = {"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}}
                await self.cdp.evaluate(f"({INJECT_JS})({json.dumps('MCP:' + json.dumps(request))})")
                deadline = asyncio.get_event_loop().time() + timeout
                while asyncio.get_event_loop().time() < deadline:
                    raw = await self.cdp.evaluate(READ_MESSAGES_JS)
                    messages = json.loads(raw)
                    for m in reversed(messages):
                        if m["author"] == "bot" and m["text"].startswith("MCP:"):
                            try:
                                resp = json.loads(m["text"][4:])
                            except json.JSONDecodeError:
                                continue
                            if resp.get("id") == rid:
                                return resp
                    await asyncio.sleep(0.2)
                raise TimeoutError(f"pas de reponse MCP pour {method} (id={rid})")

            return await with_retry(_once, attempts=attempts)
