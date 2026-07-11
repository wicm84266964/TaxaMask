class MainWindowCoordinator:
    def __init__(self, *, enter_image, enter_tif, open_agent, return_to_start):
        self._enter_image = enter_image
        self._enter_tif = enter_tif
        self._open_agent = open_agent
        self._return_to_start = return_to_start
        self._transition_active = False

    def _run_transition(self, callback, *args, **kwargs):
        if self._transition_active:
            return False
        self._transition_active = True
        try:
            callback(*args, **kwargs)
            return True
        finally:
            self._transition_active = False

    def enter_image(self):
        return self._run_transition(self._enter_image)

    def enter_tif(self):
        return self._run_transition(self._enter_tif)

    def open_agent(self, context):
        return self._run_transition(self._open_agent, context)

    def return_to_start(self):
        return self._run_transition(self._return_to_start)
