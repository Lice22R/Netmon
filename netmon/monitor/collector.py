from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import psutil


@dataclass
class Connection:
    pid: Optional[int]
    process_name: str
    process_path: str
    local_addr: str
    remote_addr: str
    status: str
    protocol: str
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
    return Connection(
        pid=raw_conn.pid,
        process_name=name,
        process_path=path,
        local_addr=_format_addr(raw_conn.laddr),
        remote_addr=_format_addr(raw_conn.raddr) if raw_conn.raddr else "-",
        status=raw_conn.status if raw_conn.status else "-",
        protocol=_determine_protocol(raw_conn),
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
