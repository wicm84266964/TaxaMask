from __future__ import annotations


class TifWorkbenchView:
    def __init__(self, workbench):
        self._workbench = workbench
        self._scopes = {}

    def register_scope(self, scope, *widget_names):
        names = tuple(dict.fromkeys(str(name) for name in widget_names if str(name)))
        missing = [name for name in names if not hasattr(self._workbench, name)]
        if missing:
            raise AttributeError(f"Missing TIF workbench widgets for {scope}: {', '.join(missing)}")
        self._scopes[str(scope)] = names
        return self.scope(scope)

    def scope(self, scope):
        names = self._scopes.get(str(scope), ())
        return {name: getattr(self._workbench, name) for name in names}

    def require(self, scope, name):
        names = self._scopes.get(str(scope), ())
        if name not in names:
            raise KeyError(f"{name} is not registered in TIF view scope {scope}")
        return getattr(self._workbench, name)

    def registered_names(self, scope):
        return self._scopes.get(str(scope), ())
