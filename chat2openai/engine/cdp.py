import itertools
import json
import time

import requests
import websockets


class CDPClient:
    def __init__(self, ws_url):
        self.ws_url = ws_url
        self._ids = itertools.count(1)
        self._ws = None

    async def __aenter__(self):
        self._ws = await websockets.connect(self.ws_url, max_size=64 * 1024 * 1024)
        return self

    async def __aexit__(self, *exc):
        await self._ws.close()

    async def send(self, method, params=None):
        msg_id = next(self._ids)
        await self._ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
        while True:
            raw = await self._ws.recv()
            data = json.loads(raw)
            if data.get("id") == msg_id:
                if "error" in data:
                    raise RuntimeError(f"{method}: {data['error']}")
                return data.get("result", {})

    async def evaluate(self, expression, await_promise=False):
        result = await self.send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": await_promise,
        })
        if result.get("exceptionDetails"):
            raise RuntimeError(f"JS error: {result['exceptionDetails']}")
        return result.get("result", {}).get("value")


def http_get(port, path):
    return requests.get(f"http://127.0.0.1:{port}{path}", timeout=5).json()


def wait_for_debug_port(port, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            return http_get(port, "/json/version")
        except requests.ConnectionError:
            time.sleep(0.3)
    raise TimeoutError(f"port de debug {port} injoignable")


def find_page_target(port, url_contains=None):
    for target in http_get(port, "/json/list"):
        if target.get("type") == "page" and (url_contains is None or url_contains in target.get("url", "")):
            return target
    raise RuntimeError("aucune cible 'page' trouvee")
