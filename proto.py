import asyncio
import itertools
import json
import os
import subprocess
import sys
import tempfile

from cdp_client import CDPClient, find_page_target, wait_for_debug_port

PORT = 9333
CHROME = os.path.expanduser(
    "~/.cache/ms-playwright/chromium-1254/chrome-linux64/chrome"
)
CHAT_URL = "file://" + os.path.join(os.path.dirname(os.path.abspath(__file__)), "chat.html")

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

    async def call(self, method, params=None, timeout=8):
        rid = next(self._ids)
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
        raise TimeoutError(f"pas de réponse MCP pour {method} (id={rid})")


async def main():
    env = dict(os.environ)
    env["LD_LIBRARY_PATH"] = "/tmp/libs/usr/lib/x86_64-linux-gnu:/tmp/libs/usr/lib:" + env.get("LD_LIBRARY_PATH", "")
    env["FONTCONFIG_FILE"] = "/tmp/fontconfig/fonts.conf"

    profile = tempfile.mkdtemp(prefix="cdp-proto-profile-")
    chrome = subprocess.Popen([
        CHROME, "--headless", "--no-sandbox", "--disable-gpu",
        f"--remote-debugging-port={PORT}", f"--user-data-dir={profile}",
        "about:blank",
    ], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        wait_for_debug_port(PORT)
        target = find_page_target(PORT)
        async with CDPClient(target["webSocketDebuggerUrl"]) as cdp:
            await cdp.send("Page.enable")
            await cdp.send("Page.navigate", {"url": CHAT_URL})
            await asyncio.sleep(1.0)

            rpc = ChatRPC(cdp)

            r = await rpc.call("ping")
            print("[1] ping          ->", json.dumps(r))

            r = await rpc.call("tools/list")
            print("[2] tools/list    ->", json.dumps(r, ensure_ascii=False))

            r = await rpc.call("tools/call", {"name": "echo", "arguments": {"text": "bonjour le chat !"}})
            print("[3] echo          ->", json.dumps(r, ensure_ascii=False))

            r = await rpc.call("tools/call", {"name": "get_time", "arguments": {}})
            print("[4] get_time      ->", json.dumps(r, ensure_ascii=False))

            r = await rpc.call("tools/call", {"name": "inexistant", "arguments": {}})
            print("[5] outil inconnu ->", json.dumps(r, ensure_ascii=False))

            r = await rpc.call("nimportequoi")
            print("[6] méthode inconnue ->", json.dumps(r, ensure_ascii=False))
    finally:
        chrome.terminate()
        chrome.wait(timeout=10)
        print("[7] Navigateur arrêté. Mini-MCP sur chat fonctionnel.")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
