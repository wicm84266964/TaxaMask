import os
import shlex


_SHELL_OPERATORS = frozenset({"&", "&&", "|", "||", ";", ">", ">>", "<", "<<"})


def render_external_command(template, **values):
    """Render a configured command without passing it through a system shell."""
    raw = str(template or "").strip()
    if not raw:
        return []
    parts = shlex.split(raw, posix=os.name != "nt")
    if os.name == "nt":
        parts = [
            item[1:-1]
            if len(item) >= 2 and item[0] == item[-1] and item[0] in {"'", '"'}
            else item
            for item in parts
        ]
    if any(part in _SHELL_OPERATORS for part in parts):
        raise ValueError("external_command_shell_operator_not_allowed")
    return [part.format(**values) for part in parts]
