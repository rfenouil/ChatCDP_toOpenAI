import asyncio
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

SEND_MESSAGE_JS = """
(text) => {
  const input = document.getElementById('input');
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
  setter.call(input, text);
  input.dispatchEvent(new Event('input', { bubbles: true }));
  document.getElementById('send').click();
  return input.value;
}
"""

READ_MESSAGES_JS = """
JSON.stringify(
  [...document.querySelectorAll('#messages .msg')].map(m => ({
    author: m.dataset.author, text: m.textContent
  }))
)
"""


async def main():
    env = dict(os.environ)
    libdir = "/tmp/libs/usr/lib/x86_64-linux-gnu:/tmp/libs/usr/lib"
    env["LD_LIBRARY_PATH"] = libdir + ":" + env.get("LD_LIBRARY_PATH", "")
    env["FONTCONFIG_FILE"] = "/tmp/fontconfig/fonts.conf"

    profile = tempfile.mkdtemp(prefix="cdp-chat-profile-")
    chrome = subprocess.Popen([
        CHROME, "--headless", "--no-sandbox", "--disable-gpu",
        f"--remote-debugging-port={PORT}", f"--user-data-dir={profile}",
        "about:blank",
    ], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        version = wait_for_debug_port(PORT)
        print(f"[1] Navigateur connecté : {version['Browser']} (port {PORT})")

        target = find_page_target(PORT)
        print(f"[2] Cible page trouvée : {target['url']}")

        async with CDPClient(target["webSocketDebuggerUrl"]) as cdp:
            await cdp.send("Page.enable")
            await cdp.send("Page.navigate", {"url": CHAT_URL})
            await asyncio.sleep(1.0)

            initial = await cdp.evaluate(READ_MESSAGES_JS)
            print(f"[3] Lecture initiale du chat : {initial}")

            await cdp.evaluate(f"({SEND_MESSAGE_JS})('Bonjour depuis le protocole CDP !')")
            print("[4] Message écrit et envoyé dans le chat via Runtime.evaluate")

            await asyncio.sleep(1.0)
            final = await cdp.evaluate(READ_MESSAGES_JS)
            print(f"[5] Lecture après envoi (avec la réponse du bot) : {final}")
    finally:
        chrome.terminate()
        chrome.wait(timeout=10)
        print("[6] Navigateur arrêté. Faisabilité démontrée.")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
