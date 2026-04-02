from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


SORT_COLUMNS: list[tuple[str, str]] = [
    ("process_name", "Процесс"),
    ("pid",          "PID"),
    ("protocol",     "Протокол"),
    ("local_addr",   "Локальный адрес"),
    ("remote_addr",  "Удалённый адрес"),
    ("status",       "Статус"),
    ("app_protocol", "Сервис"),
]


@dataclass
class SortState:
    """Current sort column and direction for the connection table."""

    column: Optional[int] = None  # 1-6 matching SORT_COLUMNS index, None = default order
    ascending: bool = True

    @property
    def is_active(self) -> bool:
        return self.column is not None

    def apply(self, column: int) -> None:
        """Select a column, or toggle direction if it is already selected."""
        if self.column == column:
            self.ascending = not self.ascending
        else:
            self.column = column
            self.ascending = True

    def reset(self) -> None:
        self.column = None
        self.ascending = True

    def column_name(self) -> str:
        if self.column is None:
            return ""
        return SORT_COLUMNS[self.column - 1][1]

    def arrow(self) -> str:
        return "▲" if self.ascending else "▼"
