from __future__ import annotations

from textual.reactive import reactive
from textual.widgets import Static


def format_status_bar(
    count: int,
    last_update: str,
    sort_info: str,
    ai_status: str,
) -> str:
    """Build the status bar text from its components. Pure function, testable without Textual."""
    sort_part = f"  |  {sort_info}" if sort_info else ""
    ai_part = f"  |  {ai_status}" if ai_status else ""
    return (
        f" Соединений: [bold]{count}[/bold]"
        f"  |  Обновлено: {last_update}"
        f"{sort_part}"
        f"{ai_part}"
    )


class StatusBar(Static):
    """Bottom status bar showing connection count, last update time, sort and AI status."""

    count: reactive[int] = reactive(0)
    last_update: reactive[str] = reactive("—")
    ai_status: reactive[str] = reactive("")
    sort_info: reactive[str] = reactive("")

    def render(self) -> str:
        return format_status_bar(self.count, self.last_update, self.sort_info, self.ai_status)
