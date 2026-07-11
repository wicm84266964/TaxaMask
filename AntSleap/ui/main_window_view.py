from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class MainWindowViewAdapter:
    show_start_center: Callable[[], None]
    show_tab: Callable[[int], None]
    refresh_project_console: Callable[[], None]
    update_agent_status: Callable[[], None]
