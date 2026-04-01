"""
Тесты для netmon.monitor.logger

Покрываемые сценарии:
- Запись соединений в буфер
- Кольцевой буфер: переполнение до MEMORY_BUFFER_SIZE
- get_recent без лимита и с лимитом
- clear_buffer очищает буфер
- Файловый логгер создаёт директорию и файл
- Формат записи (JSON)
"""

from __future__ import annotations

import json
import os
import sys
import stat
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, "/home/lice/hdd/Projects/netmon")

from netmon.monitor.collector import Connection
from netmon.monitor import logger as logger_module


def _make_connection(pid: int, name: str, remote: str = "8.8.8.8:443") -> Connection:
    return Connection(
        pid=pid,
        process_name=name,
        process_path=f"/usr/bin/{name}",
        local_addr="127.0.0.1:5000",
        remote_addr=remote,
        status="ESTABLISHED",
        protocol="TCP",
        raw_laddr=MagicMock(),
        raw_raddr=MagicMock(),
    )


class TestConnectionLoggerBuffer:
    def setup_method(self):
        """Перед каждым тестом патчим путь логов во временную директорию."""
        self._tmpdir = tempfile.TemporaryDirectory()
        tmp = Path(self._tmpdir.name)
        self._patcher_log_dir = patch.object(logger_module.config, "LOG_DIR", tmp)
        self._patcher_log_file = patch.object(
            logger_module.config, "LOG_FILE", tmp / "netmon.log"
        )
        self._patcher_log_dir.start()
        self._patcher_log_file.start()
        # Сбрасываем кеш логгера Python чтобы каждый тест получал свежий handler
        import logging
        log = logging.getLogger("netmon.traffic")
        log.handlers.clear()

    def teardown_method(self):
        self._patcher_log_dir.stop()
        self._patcher_log_file.stop()
        self._tmpdir.cleanup()

    def _make_logger(self, buffer_size: int = 50):
        with patch.object(logger_module.config, "MEMORY_BUFFER_SIZE", buffer_size):
            from netmon.monitor.logger import ConnectionLogger
            return ConnectionLogger()

    def test_log_single_connection(self):
        cl = self._make_logger()
        cl.log([_make_connection(1, "curl")])
        assert len(cl.get_recent()) == 1

    def test_log_multiple_connections(self):
        cl = self._make_logger()
        conns = [_make_connection(i, f"proc{i}") for i in range(5)]
        cl.log(conns)
        assert len(cl.get_recent()) == 5

    def test_buffer_overflow(self):
        """Буфер не должен превышать MEMORY_BUFFER_SIZE."""
        cl = self._make_logger(buffer_size=10)
        for i in range(25):
            cl.log([_make_connection(i, f"proc{i}")])
        recent = cl.get_recent()
        assert len(recent) == 10

    def test_buffer_keeps_latest(self):
        """При переполнении должны оставаться последние записи."""
        cl = self._make_logger(buffer_size=3)
        for i in range(5):
            cl.log([_make_connection(i, f"proc{i}")])
        recent = cl.get_recent()
        names = [r["process"] for r in recent]
        assert "proc4" in names
        assert "proc0" not in names

    def test_get_recent_with_limit(self):
        cl = self._make_logger()
        conns = [_make_connection(i, f"proc{i}") for i in range(20)]
        cl.log(conns)
        recent = cl.get_recent(limit=5)
        assert len(recent) == 5

    def test_get_recent_limit_larger_than_buffer(self):
        cl = self._make_logger()
        cl.log([_make_connection(1, "curl")])
        recent = cl.get_recent(limit=100)
        assert len(recent) == 1

    def test_clear_buffer(self):
        cl = self._make_logger()
        cl.log([_make_connection(1, "curl")])
        cl.clear_buffer()
        assert cl.get_recent() == []

    def test_empty_log_call(self):
        cl = self._make_logger()
        cl.log([])
        assert cl.get_recent() == []

    def test_record_format_is_dict(self):
        cl = self._make_logger()
        cl.log([_make_connection(42, "firefox", "1.2.3.4:80")])
        record = cl.get_recent()[0]
        assert isinstance(record, dict)
        assert record["process"] == "firefox"
        assert record["remote"] == "1.2.3.4:80"
        assert record["pid"] == 42

    def test_file_created(self):
        cl = self._make_logger()
        cl.log([_make_connection(1, "test")])
        log_file = logger_module.config.LOG_FILE
        assert log_file.exists()

    def test_file_contains_json(self):
        cl = self._make_logger()
        cl.log([_make_connection(99, "myproc", "10.0.0.1:22")])
        log_file = logger_module.config.LOG_FILE
        content = log_file.read_text()
        # Каждая строка заканчивается JSON-объектом
        json_part = content.strip().split(" ", 2)[-1]  # убираем timestamp
        parsed = json.loads(json_part)
        assert parsed["process"] == "myproc"

    def test_multiple_log_calls_accumulate(self):
        cl = self._make_logger()
        cl.log([_make_connection(1, "a")])
        cl.log([_make_connection(2, "b")])
        cl.log([_make_connection(3, "c")])
        assert len(cl.get_recent()) == 3

    def test_get_recent_limit_zero_returns_empty(self):
        """get_recent(limit=0) должен возвращать пустой список, а не все записи."""
        cl = self._make_logger()
        cl.log([_make_connection(1, "curl")])
        cl.log([_make_connection(2, "firefox")])
        result = cl.get_recent(limit=0)
        assert result == []

    def test_log_file_permissions_are_0600(self):
        """Лог-файл должен быть доступен только владельцу (0o600)."""
        cl = self._make_logger()
        cl.log([_make_connection(1, "test")])
        log_file = logger_module.config.LOG_FILE
        mode = stat.S_IMODE(os.stat(log_file).st_mode)
        assert mode == 0o600, f"Ожидался 0o600, получен {oct(mode)}"

    def test_sudo_chown_called_when_sudo_env_set(self):
        """При запуске через sudo лог-файл должен переназначаться реальному пользователю."""
        with patch.dict(os.environ, {"SUDO_UID": "1000", "SUDO_GID": "1000"}):
            with patch("netmon.monitor.logger.os.chown") as mock_chown:
                cl = self._make_logger()
                cl.log([_make_connection(1, "test")])
                mock_chown.assert_called_once()
                args = mock_chown.call_args[0]
                assert args[1] == 1000  # uid
                assert args[2] == 1000  # gid
