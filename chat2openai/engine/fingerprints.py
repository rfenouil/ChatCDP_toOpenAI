import hashlib
import json

DEFAULT_FINGERPRINTS = {}

GENERIC_COMPACTION_MARKERS = (
    "summarize only the history",
    "compaction",
    "summarize the conversation",
    "condense the conversation",
)


def _normalize(text):
    return " ".join((text or "").lower().split())


def _hash(text):
    return hashlib.sha256(_normalize(text).encode("utf-8")).hexdigest()


def is_compaction_request(messages, fingerprints=None):
    fingerprints = fingerprints or DEFAULT_FINGERPRINTS
    if not messages:
        return False
    last_user = next((m for m in reversed(messages) if m.get("role") == "user"), None)
    if not last_user:
        return False
    content = last_user.get("content") or ""
    if _hash(content) in fingerprints.get("hashes", set()):
        return True
    normalized = _normalize(content)
    return any(marker in normalized for marker in GENERIC_COMPACTION_MARKERS)
