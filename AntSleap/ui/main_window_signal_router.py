class MainWindowSignalRouter:
    def __init__(self):
        self._bindings = set()

    def connect_once(self, key, signal, slot):
        binding_key = str(key)
        if binding_key in self._bindings:
            return False
        signal.connect(slot)
        self._bindings.add(binding_key)
        return True

    def is_connected(self, key):
        return str(key) in self._bindings
