import hashlib
import json


def _hash(obj):
    canonical = json.dumps(obj, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class SessionState:
    def __init__(self):
        self.last_index = 0
        self.prefix_hash = None
        self.sent_count = 0
        self.resyncs = 0


class SessionCache:
    def __init__(self):
        self.sessions = {}

    def state(self, session_id):
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionState()
        return self.sessions[session_id]

    def delta(self, session_id, messages):
        state = self.state(session_id)
        if (
            state.last_index > 0
            and len(messages) >= state.last_index
            and _hash(messages[:state.last_index]) == state.prefix_hash
        ):
            new_messages = messages[state.last_index:]
        else:
            new_messages = list(messages)
            state.resyncs += 1
        state.last_index = len(messages)
        state.prefix_hash = _hash(messages)
        state.sent_count += len(new_messages)
        return new_messages

    def stats(self):
        return {
            sid: {
                "last_index": s.last_index,
                "sent_count": s.sent_count,
                "resyncs": s.resyncs,
            }
            for sid, s in self.sessions.items()
        }
