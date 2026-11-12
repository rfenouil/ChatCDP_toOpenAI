import re
import sys
from html.parser import HTMLParser

import requests


class TextExtractor(HTMLParser):
    SKIP_TAGS = {"script", "style", "noscript", "head"}

    def __init__(self):
        super().__init__()
        self.parts = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self._skip += 1
        if tag in {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.parts.append(data.strip() + " ")

    def text(self):
        raw = "".join(self.parts)
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n\s*\n+", "\n\n", raw)
        return raw.strip()


def fetch_text(url, timeout=20):
    headers = {"User-Agent": "cdp-chat-fetcher/1.0 (python-requests)"}
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    ctype = resp.headers.get("Content-Type", "")
    if "html" not in ctype and "text" not in ctype:
        raise RuntimeError(f"contenu non texte: {ctype}")
    if "html" not in ctype:
        return resp.text
    parser = TextExtractor()
    parser.feed(resp.text)
    return parser.text()


def main():
    if len(sys.argv) != 2:
        print("usage: python fetch_page.py <url>")
        return 1
    url = sys.argv[1]
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    text = fetch_text(url)
    print(f"=== {url} ===\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
