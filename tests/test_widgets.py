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

from netmon.ui.widgets import (
    _format_duration,
    format_bytes,
    format_status_bar,
    format_traffic_bar,
)


class TestStatusBarRender:
    """Тестируем чистую функцию format_status_bar напрямую."""

    def test_shows_connection_count(self):
        result = format_status_bar(count=42, last_update="—", sort_info="", ai_status="")
        assert "42" in result

    def test_shows_last_update_time(self):
        result = format_status_bar(count=0, last_update="14:32:01", sort_info="", ai_status="")
        assert "14:32:01" in result

    def test_sort_info_shown_when_set(self):
        result = format_status_bar(count=0, last_update="—", sort_info="Сорт: PID ▲", ai_status="")
        assert "Сорт: PID ▲" in result

    def test_sort_info_hidden_when_empty(self):
        result = format_status_bar(count=0, last_update="—", sort_info="", ai_status="")
        assert "Сорт" not in result

    def test_ai_status_shown_when_set(self):
        result = format_status_bar(count=0, last_update="—", sort_info="", ai_status="AI: готово")
        assert "AI: готово" in result

    def test_ai_status_hidden_when_empty(self):
        result = format_status_bar(count=0, last_update="—", sort_info="", ai_status="")
        assert "AI" not in result

    def test_both_sort_and_ai_shown_together(self):
        result = format_status_bar(count=0, last_update="—", sort_info="Сорт: Статус ▼", ai_status="AI: анализирует...")
        assert "Сорт: Статус ▼" in result
        assert "AI: анализирует..." in result

    def test_sort_appears_before_ai(self):
        result = format_status_bar(count=0, last_update="—", sort_info="SORT", ai_status="AISTATUS")
        assert result.index("SORT") < result.index("AISTATUS")

    def test_count_appears_first(self):
        result = format_status_bar(count=7, last_update="10:00:00", sort_info="SORT", ai_status="AI")
        count_pos = result.index("7")
        sort_pos = result.index("SORT")
        ai_pos = result.index("AI")
        assert count_pos < sort_pos < ai_pos

    def test_zero_count(self):
        result = format_status_bar(count=0, last_update="—", sort_info="", ai_status="")
        assert "0" in result

    def test_large_count(self):
        result = format_status_bar(count=9999, last_update="—", sort_info="", ai_status="")
        assert "9999" in result

    def test_default_last_update_placeholder(self):
        result = format_status_bar(count=0, last_update="—", sort_info="", ai_status="")
        assert "—" in result


# ─────────────────────────────────────────────────────────────── format_bytes

class TestFormatBytes:
    def test_bytes(self):
        assert format_bytes(512) == "512 B"

    def test_zero_bytes(self):
        assert format_bytes(0) == "0 B"

    def test_exactly_1kb(self):
        assert format_bytes(1024) == "1.0 KB"

    def test_kilobytes(self):
        assert format_bytes(2048) == "2.0 KB"

    def test_megabytes(self):
        assert format_bytes(1024 ** 2) == "1.0 MB"

    def test_megabytes_fractional(self):
        result = format_bytes(int(1.5 * 1024 ** 2))
        assert "1.5 MB" in result

    def test_gigabytes(self):
        assert format_bytes(1024 ** 3) == "1.00 GB"

    def test_just_below_1kb(self):
        assert format_bytes(1023) == "1023 B"

    def test_just_below_1mb(self):
        result = format_bytes(1024 ** 2 - 1)
        assert "KB" in result


# ─────────────────────────────────────────────────────────────── _format_duration

class TestFormatDuration:
    def test_zero(self):
        assert _format_duration(0) == "00:00:00"

    def test_seconds_only(self):
        assert _format_duration(45) == "00:00:45"

    def test_minutes(self):
        assert _format_duration(90) == "00:01:30"

    def test_hours(self):
        assert _format_duration(3661) == "01:01:01"

    def test_large_hours(self):
        assert _format_duration(36000) == "10:00:00"

    def test_format_padding(self):
        result = _format_duration(65)
        assert result == "00:01:05"


# ─────────────────────────────────────────────────────────────── format_traffic_bar

class TestFormatTrafficBar:
    def test_shows_sent(self):
        result = format_traffic_bar(sent=1024, recv=0, seconds=0)
        assert "↑" in result
        assert "1.0 KB" in result

    def test_shows_recv(self):
        result = format_traffic_bar(sent=0, recv=2048, seconds=0)
        assert "↓" in result
        assert "2.0 KB" in result

    def test_shows_session_time(self):
        result = format_traffic_bar(sent=0, recv=0, seconds=125)
        assert "00:02:05" in result

    def test_sent_before_recv(self):
        result = format_traffic_bar(sent=1024, recv=2048, seconds=0)
        assert result.index("↑") < result.index("↓")

    def test_zero_traffic(self):
        result = format_traffic_bar(sent=0, recv=0, seconds=0)
        assert "0 B" in result
        assert "00:00:00" in result


# ─────────────────────────────────────────────────────────────── TrafficBar

class TestTrafficBar:
    """Тестируем чистую функцию format_traffic_bar напрямую."""

    def test_render_shows_sent(self):
        result = format_traffic_bar(sent=1024 ** 2, recv=0, seconds=0)
        assert "1.0 MB" in result

    def test_render_shows_recv(self):
        result = format_traffic_bar(sent=0, recv=512, seconds=0)
        assert "512 B" in result

    def test_render_shows_session(self):
        result = format_traffic_bar(sent=0, recv=0, seconds=3600)
        assert "01:00:00" in result

    def test_render_zero_state(self):
        result = format_traffic_bar(sent=0, recv=0, seconds=0)
        assert "↑" in result
        assert "↓" in result
        assert "00:00:00" in result
