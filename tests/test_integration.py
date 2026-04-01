"""
Интеграционные тесты: collector → logger → analyzer

Покрываемые сценарии:
- Полный пайплайн: сбор → лог → AI анализ
- Данные из collector корректно сериализуются через logger для AI
- Подозрительные процессы (nc, bash, python) присутствуют в данных
- Лог-файл создаётся при первом запуске пайплайна
- Буфер не превышает лимит при длительной работе
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import psutil

sys.path.insert(0, "/home/lice/hdd/Projects/netmon")

from netmon.monitor.collector import Connection, collect
from netmon.monitor import logger as logger_module


def _make_conn_mock(pid, name, laddr_ip, laddr_port,
                    raddr_ip=None, raddr_port=None, status="ESTABLISHED"):
    conn = MagicMock()
    conn.pid = pid
    conn.status = status

    laddr = MagicMock()
    laddr.ip = laddr_ip
    laddr.port = laddr_port
    conn.laddr = laddr

    if raddr_ip:
        raddr = MagicMock()
        raddr.ip = raddr_ip
        raddr.port = raddr_port
        conn.raddr = raddr
    else:
        conn.raddr = None

    sock_type = MagicMock()
    sock_type.name = "SOCK_STREAM"
    conn.type = sock_type

    proc = MagicMock()
    proc.name.return_value = name
    proc.exe.return_value = f"/usr/bin/{name}"

    return conn, proc


class TestCollectorToLogger:
    def setup_method(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        tmp = Path(self._tmpdir.name)
        self._p1 = patch.object(logger_module.config, "LOG_DIR", tmp)
        self._p2 = patch.object(logger_module.config, "LOG_FILE", tmp / "netmon.log")
        self._p1.start()
        self._p2.start()
        import logging
        logging.getLogger("netmon.traffic").handlers.clear()

    def teardown_method(self):
        self._p1.stop()
        self._p2.stop()
        self._tmpdir.cleanup()

    def _make_logger(self):
        from netmon.monitor.logger import ConnectionLogger
        return ConnectionLogger()

    def test_pipeline_collect_and_log(self):
        """Соединения из collect корректно записываются в logger."""
        conn_mock, proc_mock = _make_conn_mock(
            1234, "curl", "127.0.0.1", 5000, "8.8.8.8", 443
        )

        with patch("netmon.monitor.collector.psutil.net_connections", return_value=[conn_mock]), \
             patch("netmon.monitor.collector.psutil.Process", return_value=proc_mock):
            connections = collect()

        cl = self._make_logger()
        cl.log(connections)

        recent = cl.get_recent()
        assert len(recent) == 1
        assert recent[0]["process"] == "curl"
        assert recent[0]["remote"] == "8.8.8.8:443"

    def test_suspicious_process_in_pipeline(self):
        """nc (netcat) должен попасть в данные для AI."""
        conn_mock, proc_mock = _make_conn_mock(
            666, "nc", "0.0.0.0", 4444
        )

        with patch("netmon.monitor.collector.psutil.net_connections", return_value=[conn_mock]), \
             patch("netmon.monitor.collector.psutil.Process", return_value=proc_mock):
            connections = collect()

        cl = self._make_logger()
        cl.log(connections)

        recent = cl.get_recent()
        nc_conns = [r for r in recent if r["process"] == "nc"]
        assert len(nc_conns) == 1
        assert nc_conns[0]["local"] == "*:4444"

    def test_multiple_snapshots_accumulate(self):
        """Несколько снапшотов должны накапливаться в буфере."""
        cl = self._make_logger()

        for i in range(5):
            conn_mock, proc_mock = _make_conn_mock(
                i, f"proc{i}", "127.0.0.1", 5000 + i, "1.1.1.1", 80
            )
            with patch("netmon.monitor.collector.psutil.net_connections",
                       return_value=[conn_mock]), \
                 patch("netmon.monitor.collector.psutil.Process", return_value=proc_mock):
                connections = collect()
            cl.log(connections)

        assert len(cl.get_recent()) == 5

    def test_data_survives_serialization(self):
        """Данные из буфера должны быть сериализуемы в JSON (для передачи в AI)."""
        conn_mock, proc_mock = _make_conn_mock(
            99, "python3", "127.0.0.1", 8888, "185.34.21.10", 4444
        )

        with patch("netmon.monitor.collector.psutil.net_connections", return_value=[conn_mock]), \
             patch("netmon.monitor.collector.psutil.Process", return_value=proc_mock):
            connections = collect()

        cl = self._make_logger()
        cl.log(connections)

        recent = cl.get_recent()
        # Должно сериализоваться без ошибок
        serialized = json.dumps(recent, ensure_ascii=False)
        parsed = json.loads(serialized)
        assert parsed[0]["process"] == "python3"

    def test_buffer_limit_across_many_snapshots(self):
        """Буфер не должен расти бесконечно при длительной работе."""
        cl = self._make_logger()
        buffer_size = logger_module.config.MEMORY_BUFFER_SIZE

        # Симулируем 3x больше снапшотов чем размер буфера
        for i in range(buffer_size * 3):
            conn_mock, proc_mock = _make_conn_mock(
                i % 100, f"proc{i % 10}", "127.0.0.1", 5000, "1.1.1.1", 80
            )
            with patch("netmon.monitor.collector.psutil.net_connections",
                       return_value=[conn_mock]), \
                 patch("netmon.monitor.collector.psutil.Process", return_value=proc_mock):
                connections = collect()
            cl.log(connections)

        assert len(cl.get_recent()) <= buffer_size

    def test_log_file_created_after_pipeline(self):
        """Лог-файл должен создаться после первого запуска пайплайна."""
        conn_mock, proc_mock = _make_conn_mock(
            1, "sshd", "0.0.0.0", 22, status="LISTEN"
        )

        with patch("netmon.monitor.collector.psutil.net_connections", return_value=[conn_mock]), \
             patch("netmon.monitor.collector.psutil.Process", return_value=proc_mock):
            connections = collect()

        cl = self._make_logger()
        cl.log(connections)

        assert logger_module.config.LOG_FILE.exists()


class TestLoggerToAnalyzerData:
    """Проверяем что данные из логгера совместимы с форматом ожидаемым анализатором."""

    def setup_method(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        tmp = Path(self._tmpdir.name)
        self._p1 = patch.object(logger_module.config, "LOG_DIR", tmp)
        self._p2 = patch.object(logger_module.config, "LOG_FILE", tmp / "netmon.log")
        self._p1.start()
        self._p2.start()
        import logging
        logging.getLogger("netmon.traffic").handlers.clear()

    def teardown_method(self):
        self._p1.stop()
        self._p2.stop()
        self._tmpdir.cleanup()

    def _make_logger(self):
        from netmon.monitor.logger import ConnectionLogger
        return ConnectionLogger()

    def test_get_recent_returns_list_of_dicts(self):
        cl = self._make_logger()
        conn_mock, proc_mock = _make_conn_mock(
            1, "test", "127.0.0.1", 9000, "2.2.2.2", 80
        )
        with patch("netmon.monitor.collector.psutil.net_connections",
                   return_value=[conn_mock]), \
             patch("netmon.monitor.collector.psutil.Process", return_value=proc_mock):
            connections = collect()
        cl.log(connections)

        recent = cl.get_recent()
        assert isinstance(recent, list)
        assert all(isinstance(r, dict) for r in recent)

    def test_each_record_has_required_fields(self):
        """Каждая запись должна содержать поля нужные AI-анализатору."""
        cl = self._make_logger()
        conn_mock, proc_mock = _make_conn_mock(
            1, "firefox", "127.0.0.1", 9000, "3.3.3.3", 443
        )
        with patch("netmon.monitor.collector.psutil.net_connections",
                   return_value=[conn_mock]), \
             patch("netmon.monitor.collector.psutil.Process", return_value=proc_mock):
            connections = collect()
        cl.log(connections)

        record = cl.get_recent()[0]
        required_fields = {"pid", "process", "local", "remote", "status", "protocol"}
        assert required_fields.issubset(record.keys())
