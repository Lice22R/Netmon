from __future__ import annotations

import json
import logging
import os
from collections import deque
from logging.handlers import RotatingFileHandler
from typing import TYPE_CHECKING

from netmon import config

if TYPE_CHECKING:
    from netmon.monitor.collector import Connection


def _ensure_log_directory() -> None:
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)


def _create_rotating_handler() -> RotatingFileHandler:
    handler = RotatingFileHandler(
        config.LOG_FILE,
        maxBytes=config.LOG_MAX_BYTES,
        backupCount=config.LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    return handler


def _fix_log_file_ownership() -> None:
    """Set restrictive permissions and return ownership to the real user when running via sudo."""
    os.chmod(config.LOG_FILE, 0o600)
    sudo_uid = os.environ.get("SUDO_UID")
    sudo_gid = os.environ.get("SUDO_GID")
    if sudo_uid and sudo_gid:
        os.chown(config.LOG_FILE, int(sudo_uid), int(sudo_gid))


def _setup_file_logger() -> logging.Logger:
    _ensure_log_directory()

    logger = logging.getLogger("netmon.traffic")
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    logger.addHandler(_create_rotating_handler())
    logger.propagate = False

    _fix_log_file_ownership()
    return logger


class ConnectionLogger:
    """Logs connections to a rotating file and maintains an in-memory buffer for AI analysis."""

    def __init__(self) -> None:
        self._logger = _setup_file_logger()
        self._buffer: deque[dict] = deque(maxlen=config.MEMORY_BUFFER_SIZE)

    def log(self, connections: list[Connection]) -> None:
        """Record a snapshot of connections to both the file and in-memory buffer."""
        for conn in connections:
            self._write_entry(conn.to_dict())

    def _write_entry(self, entry: dict) -> None:
        self._buffer.append(entry)
        self._logger.info(json.dumps(entry, ensure_ascii=False))

    def get_recent(self, limit: int | None = None) -> list[dict]:
        """Return recent entries from the buffer, optionally capped at limit."""
        data = list(self._buffer)
        if limit is not None:
            data = data[-limit:] if limit > 0 else []
        return data

    def clear_buffer(self) -> None:
        self._buffer.clear()
