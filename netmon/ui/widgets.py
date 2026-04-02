from __future__ import annotations

from textual.reactive import reactive
from textual.widgets import Static


def format_bytes(n: int) -> str:
    """Форматирует количество байт в человекочитаемую строку."""
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    if n < 1024 ** 3:
        return f"{n / 1024 ** 2:.1f} MB"
    return f"{n / 1024 ** 3:.2f} GB"


def _format_duration(seconds: int) -> str:
    """Форматирует секунды как HH:MM:SS."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def format_traffic_bar(sent: int, recv: int, seconds: int) -> str:
    """Строит текст строки трафика. Чистая функция, тестируется без Textual."""
    return (
        f" ↑ {format_bytes(sent)}  ↓ {format_bytes(recv)}"
        f"  |  Сессия: {_format_duration(seconds)}"
    )


class TrafficBar(Static):
    """Верхняя строка состояния — трафик и время сессии."""

    bytes_sent: reactive[int] = reactive(0)
    bytes_recv: reactive[int] = reactive(0)
    session_seconds: reactive[int] = reactive(0)

    def render(self) -> str:
        return format_traffic_bar(self.bytes_sent, self.bytes_recv, self.session_seconds)


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
