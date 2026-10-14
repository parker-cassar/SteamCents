import threading
import time


class TtlCache:
    def __init__(self):
        self._lock = threading.Lock()
        self._data = {}

    def get_or_set(self, key, ttl_s, fn):
        now = time.monotonic()
        with self._lock:
            hit = self._data.get(key)
            if hit and hit[0] > now:
                return hit[1]
        value = fn()
        with self._lock:
            self._data[key] = (now + ttl_s, value)
        return value

    def clear(self):
        with self._lock:
            self._data.clear()


store = TtlCache()
