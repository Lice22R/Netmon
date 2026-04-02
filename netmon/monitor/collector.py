from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import psutil


# Маппинг well-known портов → протокол приложения (L7 heuristic)
_WELL_KNOWN_PORTS: dict[int, str] = {
    21: "FTP",
    22: "SSH",
    25: "SMTP",
    53: "DNS",
    80: "HTTP",
    110: "POP3",
    143: "IMAP",
    443: "HTTPS",
    465: "SMTP",
    587: "SMTP",
    993: "IMAP",
    995: "POP3",
    3306: "MySQL",
    5432: "PostgreSQL",
    6379: "Redis",
    8008: "HTTP",
    8080: "HTTP",
    8443: "HTTPS",
    27017: "MongoDB",
}


@dataclass
class Connection:
    pid: Optional[int]
    process_name: str
    process_path: str
    local_addr: str
    remote_addr: str
    status: str
    protocol: str
    app_protocol: str
    raw_laddr: tuple
    raw_raddr: tuple

    def to_dict(self) -> dict:
        return {
            "pid": self.pid,
            "process": self.process_name,
            "local": self.local_addr,
            "remote": self.remote_addr,
            "status": self.status,
            "protocol": self.protocol,
            "app_protocol": self.app_protocol,
        }


def _format_addr(addr) -> str:
    if not addr:
        return "-"
    host = addr.ip if hasattr(addr, "ip") else str(addr[0])
    port = addr.port if hasattr(addr, "port") else addr[1]
    if host in ("", "0.0.0.0", "::"):
        host = "*"
    return f"{host}:{port}"


def _get_process_path(proc: psutil.Process) -> str:
    try:
        return proc.exe()
    except (psutil.AccessDenied, psutil.ZombieProcess):
        return ""


def _get_process_info(pid: Optional[int]) -> tuple[str, str]:
    """Return (name, path) for a process. Returns safe fallbacks on permission errors."""
    if pid is None:
        return "[unknown]", ""
    try:
        proc = psutil.Process(pid)
        return proc.name(), _get_process_path(proc)
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return f"[pid:{pid}]", ""


def _determine_protocol(raw_conn) -> str:
    return "TCP" if raw_conn.type.name == "SOCK_STREAM" else "UDP"


def _detect_app_protocol(local_port: int, remote_port: int) -> str:
    """Определяет протокол приложения по well-known портам.
    Сначала проверяет remote port (исходящие), потом local (входящие/ожидающие).
    Возвращает пустую строку если порт неизвестен.
    """
    return _WELL_KNOWN_PORTS.get(remote_port) or _WELL_KNOWN_PORTS.get(local_port) or ""


def _fetch_raw_connections() -> list:
    """Fetch raw connections from psutil, falling back to IPv4-only on permission errors."""
    try:
        return psutil.net_connections(kind="inet")
    except psutil.AccessDenied:
        try:
            return psutil.net_connections(kind="inet4")
        except psutil.AccessDenied:
            return []


def _build_connection(raw_conn) -> Connection:
    name, path = _get_process_info(raw_conn.pid)
    local_port = raw_conn.laddr.port if raw_conn.laddr else 0
    remote_port = raw_conn.raddr.port if raw_conn.raddr else 0
    return Connection(
        pid=raw_conn.pid,
        process_name=name,
        process_path=path,
        local_addr=_format_addr(raw_conn.laddr),
        remote_addr=_format_addr(raw_conn.raddr) if raw_conn.raddr else "-",
        status=raw_conn.status if raw_conn.status else "-",
        protocol=_determine_protocol(raw_conn),
        app_protocol=_detect_app_protocol(local_port, remote_port),
        raw_laddr=raw_conn.laddr,
        raw_raddr=raw_conn.raddr or (),
    )


def _default_sort_key(conn: Connection) -> tuple[str, str]:
    return (conn.process_name.lower(), conn.local_addr)


def collect() -> list[Connection]:
    """Return all active network connections sorted by process name and local address."""
    raw_connections = _fetch_raw_connections()
    connections = [_build_connection(raw) for raw in raw_connections]
    return sorted(connections, key=_default_sort_key)
