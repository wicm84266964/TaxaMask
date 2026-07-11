from __future__ import annotations


class TifWorkbenchSignalRouter:
    def __init__(self):
        self._connections = {}

    def bind(self, scope, key, signal, slot):
        connection_key = (str(scope), str(key))
        existing = self._connections.get(connection_key)
        if existing is not None:
            if existing == (signal, slot):
                return False
            self._disconnect(*existing)
        signal.connect(slot)
        self._connections[connection_key] = (signal, slot)
        return True

    def unbind_scope(self, scope):
        scope = str(scope)
        keys = [key for key in self._connections if key[0] == scope]
        for key in keys:
            self._disconnect(*self._connections.pop(key))
        return len(keys)

    def unbind_all(self):
        for signal, slot in tuple(self._connections.values()):
            self._disconnect(signal, slot)
        count = len(self._connections)
        self._connections.clear()
        return count

    def connection_count(self, scope=None):
        if scope is None:
            return len(self._connections)
        scope = str(scope)
        return sum(key[0] == scope for key in self._connections)

    @staticmethod
    def _disconnect(signal, slot):
        try:
            signal.disconnect(slot)
        except (RuntimeError, TypeError):
            pass
