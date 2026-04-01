"""
Tests for netmon.ui.widgets

Covered scenarios:
- StatusBar.render(): connection count, last update time
- StatusBar.render(): sort_info shown only when non-empty
- StatusBar.render(): ai_status shown only when non-empty
- StatusBar.render(): both sort and AI shown together
- StatusBar.render(): order of parts (count → update → sort → AI)
"""

from __future__ import annotations

import sys

sys.path.insert(0, "/home/lice/hdd/Projects/netmon")

from netmon.ui.widgets import StatusBar


def _make_status_bar(
    count: int = 0,
    last_update: str = "—",
    sort_info: str = "",
    ai_status: str = "",
) -> StatusBar:
    """Instantiate StatusBar and inject reactive values directly."""
    bar = StatusBar.__new__(StatusBar)
    bar._reactive_count = count
    bar._reactive_last_update = last_update
    bar._reactive_sort_info = sort_info
    bar._reactive_ai_status = ai_status
    return bar


class TestStatusBarRender:
    def test_shows_connection_count(self):
        bar = _make_status_bar(count=42)
        result = bar.render()
        assert "42" in result

    def test_shows_last_update_time(self):
        bar = _make_status_bar(last_update="14:32:01")
        result = bar.render()
        assert "14:32:01" in result

    def test_sort_info_shown_when_set(self):
        bar = _make_status_bar(sort_info="Сорт: PID ▲")
        result = bar.render()
        assert "Сорт: PID ▲" in result

    def test_sort_info_hidden_when_empty(self):
        bar = _make_status_bar(sort_info="")
        result = bar.render()
        assert "Сорт" not in result

    def test_ai_status_shown_when_set(self):
        bar = _make_status_bar(ai_status="AI: готово")
        result = bar.render()
        assert "AI: готово" in result

    def test_ai_status_hidden_when_empty(self):
        bar = _make_status_bar(ai_status="")
        result = bar.render()
        assert "AI" not in result

    def test_both_sort_and_ai_shown_together(self):
        bar = _make_status_bar(sort_info="Сорт: Статус ▼", ai_status="AI: анализирует...")
        result = bar.render()
        assert "Сорт: Статус ▼" in result
        assert "AI: анализирует..." in result

    def test_sort_appears_before_ai(self):
        bar = _make_status_bar(sort_info="SORT", ai_status="AISTATUS")
        result = bar.render()
        assert result.index("SORT") < result.index("AISTATUS")

    def test_count_appears_first(self):
        bar = _make_status_bar(count=7, last_update="10:00:00", sort_info="SORT", ai_status="AI")
        result = bar.render()
        count_pos = result.index("7")
        sort_pos = result.index("SORT")
        ai_pos = result.index("AI")
        assert count_pos < sort_pos < ai_pos

    def test_zero_count(self):
        bar = _make_status_bar(count=0)
        result = bar.render()
        assert "0" in result

    def test_large_count(self):
        bar = _make_status_bar(count=9999)
        result = bar.render()
        assert "9999" in result

    def test_default_last_update_placeholder(self):
        bar = _make_status_bar(last_update="—")
        result = bar.render()
        assert "—" in result
