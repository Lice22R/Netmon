from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import ClassVar

import psutil

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Label, RichLog

from netmon import config
from netmon.ai.analyzer import AIAnalyzer
from netmon.monitor.collector import Connection, collect
from netmon.monitor.logger import ConnectionLogger
from netmon.ui.sorting import SORT_COLUMNS, SortState
from netmon.ui.widgets import StatusBar, TrafficBar


def _connection_sort_key(conn: Connection, attr: str) -> str:
    value = getattr(conn, attr)
    return str(value).lower() if value is not None else ""


class NetmonApp(App):
    """Main TUI application."""

    CSS_PATH = "app.tcss"

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("q", "quit", "Выход"),
        Binding("a", "analyze", "AI Анализ"),
        Binding("c", "clear_ai", "Очистить AI"),
        Binding("r", "refresh", "Обновить"),
        Binding("0", "sort(0)", "Сброс сорт.", show=False),
        Binding("1", "sort(1)", "Сорт: Процесс", show=False),
        Binding("2", "sort(2)", "Сорт: PID", show=False),
        Binding("3", "sort(3)", "Сорт: Протокол", show=False),
        Binding("4", "sort(4)", "Сорт: Сервис", show=False),
        Binding("5", "sort(5)", "Сорт: Лок. адрес", show=False),
        Binding("6", "sort(6)", "Сорт: Удал. адрес", show=False),
        Binding("7", "sort(7)", "Сорт: Статус", show=False),
    ]

    TITLE = config.APP_TITLE
    SUB_TITLE = config.APP_SUB_TITLE

    def __init__(self) -> None:
        super().__init__()
        self._conn_logger = ConnectionLogger()
        self._connections: list[Connection] = []
        self._ai_analyzer: AIAnalyzer | None = None
        self._sort = SortState()
        self._col_keys: list = []
        self._traffic_baseline = psutil.net_io_counters()
        self._session_start = time.monotonic()

    # ------------------------------------------------------------------ compose

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-container"):
            yield TrafficBar(id="traffic-bar")
            with Vertical(id="table-panel"):
                yield DataTable(id="conn-table", zebra_stripes=True, cursor_type="row")
            with Vertical(id="ai-panel"):
                yield Label("AI Анализ", id="ai-label")
                yield RichLog(id="ai-log", highlight=True, markup=True, wrap=True)
            with Horizontal(id="controls"):
                yield Button("AI Анализ [A]", id="btn-analyze", variant="primary")
                yield Button("Очистить [C]", id="btn-clear", variant="default")
            yield StatusBar(id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#conn-table", DataTable)
        self._col_keys = list(table.add_columns(
            "Процесс [1]", "PID [2]", "Протокол [3]", "Сервис [4]",
            "Локальный адрес [5]", "Удалённый адрес [6]", "Статус [7]",
        ))
        self._start_auto_refresh()

    # ------------------------------------------------------------------ refresh loop

    def _start_auto_refresh(self) -> None:
        asyncio.get_event_loop().create_task(self._auto_refresh_loop())

    async def _auto_refresh_loop(self) -> None:
        while True:
            self._refresh_connections()
            await asyncio.sleep(config.REFRESH_INTERVAL)

    def _refresh_connections(self) -> None:
        self._connections = collect()
        self._conn_logger.log(self._connections)
        self._update_table()
        self._update_status_bar()
        self._update_traffic_bar()

    # ------------------------------------------------------------------ table

    def _sorted_connections(self) -> list[Connection]:
        if not self._sort.is_active:
            return self._connections
        attr = SORT_COLUMNS[self._sort.column - 1][0]
        return sorted(
            self._connections,
            key=lambda c: _connection_sort_key(c, attr),
            reverse=not self._sort.ascending,
        )

    def _update_traffic_bar(self) -> None:
        current = psutil.net_io_counters()
        bar = self.query_one("#traffic-bar", TrafficBar)
        bar.bytes_sent = current.bytes_sent - self._traffic_baseline.bytes_sent
        bar.bytes_recv = current.bytes_recv - self._traffic_baseline.bytes_recv
        bar.session_seconds = int(time.monotonic() - self._session_start)

    def _update_table(self) -> None:
        table = self.query_one("#conn-table", DataTable)
        cursor_row = table.cursor_row
        scroll_y = table.scroll_y
        table.clear()
        for conn in self._sorted_connections():
            table.add_row(
                conn.process_name,
                str(conn.pid) if conn.pid else "—",
                conn.protocol,
                conn.app_protocol or "—",
                conn.local_addr,
                conn.remote_addr,
                conn.status,
            )
        if self._connections:
            table.move_cursor(row=min(cursor_row, len(self._connections) - 1))
            table.scroll_y = scroll_y

    def _update_column_headers(self) -> None:
        table = self.query_one("#conn-table", DataTable)
        for idx, (col_key, (_, base_name)) in enumerate(zip(self._col_keys, SORT_COLUMNS)):
            num = idx + 1
            if self._sort.column == num:
                label = f"{base_name} {self._sort.arrow()}[{num}]"
            else:
                label = f"{base_name} [{num}]"
            table.columns[col_key].label = label

    # ------------------------------------------------------------------ status bar

    def _update_status_bar(self) -> None:
        bar = self.query_one("#status-bar", StatusBar)
        bar.count = len(self._connections)
        bar.last_update = datetime.now().strftime("%H:%M:%S")
        if self._sort.is_active:
            bar.sort_info = f"Сорт: {self._sort.column_name()} {self._sort.arrow()}"
        else:
            bar.sort_info = ""

    # ------------------------------------------------------------------ actions

    def action_refresh(self) -> None:
        self._refresh_connections()

    def action_sort(self, col: int) -> None:
        if col == 0:
            self._sort.reset()
        else:
            self._sort.apply(col)
        self._update_column_headers()
        self._update_table()
        self._update_status_bar()

    def action_analyze(self) -> None:
        self._run_ai_analysis()

    def action_clear_ai(self) -> None:
        self._clear_ai_panel()

    @on(Button.Pressed, "#btn-analyze")
    def on_analyze_pressed(self) -> None:
        self._run_ai_analysis()

    @on(Button.Pressed, "#btn-clear")
    def on_clear_pressed(self) -> None:
        self._clear_ai_panel()

    # ------------------------------------------------------------------ AI

    def _run_ai_analysis(self) -> None:
        recent = self._conn_logger.get_recent(limit=config.AI_MAX_CONNECTIONS)
        if not recent:
            self.notify("Нет данных для анализа. Подождите обновления.", severity="warning")
            return
        self._prepare_ai_panel()
        self._stream_analysis(recent)

    def _prepare_ai_panel(self) -> None:
        self.query_one("#ai-panel").add_class("visible")
        ai_log = self.query_one("#ai-log", RichLog)
        ai_log.clear()
        ai_log.write("[bold cyan]Анализирую трафик...[/bold cyan]\n")
        self.query_one("#status-bar", StatusBar).ai_status = "[yellow]AI: анализирует...[/yellow]"
        self.query_one("#btn-analyze", Button).disabled = True

    @work(exclusive=True, thread=False)
    async def _stream_analysis(self, data: list[dict]) -> None:
        ai_log = self.query_one("#ai-log", RichLog)
        bar = self.query_one("#status-bar", StatusBar)
        try:
            if self._ai_analyzer is None:
                self._ai_analyzer = AIAnalyzer()
            async for chunk in self._ai_analyzer.analyze_stream(data):
                ai_log.write(chunk, animate=False)
            bar.ai_status = "[green]AI: готово[/green]"
        except EnvironmentError as e:
            ai_log.write(f"\n[bold red]Ошибка:[/bold red] {e}")
            bar.ai_status = "[red]AI: ошибка[/red]"
        except Exception as e:
            ai_log.write(f"\n[bold red]Ошибка API:[/bold red] {e}")
            bar.ai_status = "[red]AI: ошибка[/red]"
        finally:
            self.query_one("#btn-analyze", Button).disabled = False

    def _clear_ai_panel(self) -> None:
        self.query_one("#ai-panel").remove_class("visible")
        self.query_one("#ai-log", RichLog).clear()
        self.query_one("#status-bar", StatusBar).ai_status = ""
