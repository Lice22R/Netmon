"""
Тесты для netmon.monitor.collector

Покрываемые сценарии:
- _format_addr: нормальный адрес, пустой хост, отсутствующий адрес
- _get_process_info: нормальный процесс, нет процесса, нет прав
- collect: нормальные данные, AccessDenied, пустой список, сортировка
- Connection.to_dict: корректный формат словаря
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest
import psutil

# Добавляем корень проекта в путь
sys.path.insert(0, "/home/lice/hdd/Projects/netmon")

from netmon.monitor.collector import (
    Connection,
    _format_addr,
    _get_process_info,
    collect,
)


# ─────────────────────────────────────────────────────────────── _format_addr

class TestFormatAddr:
    def test_normal_ipv4(self):
        addr = MagicMock()
        addr.ip = "192.168.1.1"
        addr.port = 8080
        assert _format_addr(addr) == "192.168.1.1:8080"

    def test_wildcard_host(self):
        addr = MagicMock()
        addr.ip = "0.0.0.0"
        addr.port = 22
        assert _format_addr(addr) == "*:22"

    def test_empty_host(self):
        addr = MagicMock()
        addr.ip = ""
        addr.port = 443
        assert _format_addr(addr) == "*:443"

    def test_ipv6_wildcard(self):
        addr = MagicMock()
        addr.ip = "::"
        addr.port = 80
        assert _format_addr(addr) == "*:80"

    def test_none_returns_dash(self):
        assert _format_addr(None) == "-"

    def test_tuple_fallback(self):
        # psutil иногда возвращает простой tuple (ip, port) без атрибутов .ip/.port
        result = _format_addr(("10.0.0.1", 9000))
        assert result == "10.0.0.1:9000"

    def test_ipv6_non_wildcard(self):
        addr = MagicMock()
        addr.ip = "::1"
        addr.port = 443
        result = _format_addr(addr)
        # ::1 — не wildcard, должен передаваться как есть
        assert "443" in result
        assert "::1" in result

    def test_addr_with_none_ip(self):
        addr = MagicMock()
        addr.ip = None
        addr.port = 80
        # None не в списке wildcard, но str(None) не вызовет исключение
        result = _format_addr(addr)
        assert "80" in result


# ─────────────────────────────────────────────────────────────── _get_process_info

class TestGetProcessInfo:
    def test_valid_process(self):
        mock_proc = MagicMock()
        mock_proc.name.return_value = "firefox"
        mock_proc.exe.return_value = "/usr/bin/firefox"

        with patch("netmon.monitor.collector.psutil.Process", return_value=mock_proc):
            name, path = _get_process_info(1234)

        assert name == "firefox"
        assert path == "/usr/bin/firefox"

    def test_no_such_process(self):
        with patch("netmon.monitor.collector.psutil.Process",
                   side_effect=psutil.NoSuchProcess(9999)):
            name, path = _get_process_info(9999)

        assert "9999" in name
        assert path == ""

    def test_access_denied_on_exe(self):
        mock_proc = MagicMock()
        mock_proc.name.return_value = "systemd"
        mock_proc.exe.side_effect = psutil.AccessDenied(1)

        with patch("netmon.monitor.collector.psutil.Process", return_value=mock_proc):
            name, path = _get_process_info(1)

        assert name == "systemd"
        assert path == ""

    def test_access_denied_on_process(self):
        with patch("netmon.monitor.collector.psutil.Process",
                   side_effect=psutil.AccessDenied(1)):
            name, path = _get_process_info(1)

        assert name.startswith("[")
        assert path == ""

    def test_none_pid(self):
        name, path = _get_process_info(None)
        assert name == "[unknown]"
        assert path == ""

    def test_zombie_process_on_name(self):
        """Зомби-процесс может кинуть ZombieProcess при вызове .name()."""
        with patch("netmon.monitor.collector.psutil.Process",
                   side_effect=psutil.ZombieProcess(1234)):
            name, path = _get_process_info(1234)

        assert "1234" in name
        assert path == ""


# ─────────────────────────────────────────────────────────────── collect

def _make_mock_conn(pid, laddr_ip, laddr_port, raddr_ip=None, raddr_port=None,
                    status="ESTABLISHED", kind="SOCK_STREAM"):
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
    sock_type.name = kind
    conn.type = sock_type

    return conn


class TestCollect:
    def test_basic_tcp_connection(self):
        mock_conn = _make_mock_conn(1234, "127.0.0.1", 5000, "8.8.8.8", 443)

        mock_proc = MagicMock()
        mock_proc.name.return_value = "curl"
        mock_proc.exe.return_value = "/usr/bin/curl"

        with patch("netmon.monitor.collector.psutil.net_connections", return_value=[mock_conn]), \
             patch("netmon.monitor.collector.psutil.Process", return_value=mock_proc):
            result = collect()

        assert len(result) == 1
        assert result[0].process_name == "curl"
        assert result[0].protocol == "TCP"
        assert result[0].remote_addr == "8.8.8.8:443"

    def test_udp_connection(self):
        mock_conn = _make_mock_conn(5678, "0.0.0.0", 53, kind="SOCK_DGRAM")

        mock_proc = MagicMock()
        mock_proc.name.return_value = "dnsmasq"
        mock_proc.exe.return_value = "/usr/sbin/dnsmasq"

        with patch("netmon.monitor.collector.psutil.net_connections", return_value=[mock_conn]), \
             patch("netmon.monitor.collector.psutil.Process", return_value=mock_proc):
            result = collect()

        assert result[0].protocol == "UDP"

    def test_listen_socket_no_remote(self):
        mock_conn = _make_mock_conn(80, "0.0.0.0", 8080, status="LISTEN")

        mock_proc = MagicMock()
        mock_proc.name.return_value = "nginx"
        mock_proc.exe.return_value = "/usr/sbin/nginx"

        with patch("netmon.monitor.collector.psutil.net_connections", return_value=[mock_conn]), \
             patch("netmon.monitor.collector.psutil.Process", return_value=mock_proc):
            result = collect()

        assert result[0].remote_addr == "-"
        assert result[0].status == "LISTEN"

    def test_access_denied_fallback(self):
        """При AccessDenied на inet — fallback на inet4."""
        mock_conn = _make_mock_conn(1, "127.0.0.1", 22)
        mock_proc = MagicMock()
        mock_proc.name.return_value = "sshd"
        mock_proc.exe.return_value = "/usr/sbin/sshd"

        def net_connections_side_effect(kind):
            if kind == "inet":
                raise psutil.AccessDenied(0)
            return [mock_conn]

        with patch("netmon.monitor.collector.psutil.net_connections",
                   side_effect=net_connections_side_effect), \
             patch("netmon.monitor.collector.psutil.Process", return_value=mock_proc):
            result = collect()

        assert len(result) == 1

    def test_empty_connections(self):
        with patch("netmon.monitor.collector.psutil.net_connections", return_value=[]):
            result = collect()
        assert result == []

    def test_both_inet_and_inet4_access_denied(self):
        """Если оба fallback кидают AccessDenied — возвращаем пустой список, не крашим."""
        with patch("netmon.monitor.collector.psutil.net_connections",
                   side_effect=psutil.AccessDenied(0)):
            result = collect()
        assert result == []

    def test_unknown_socket_type(self):
        """Неизвестный тип сокета (SOCK_RAW и т.п.) классифицируется как UDP."""
        conn = _make_mock_conn(1, "127.0.0.1", 9999, kind="SOCK_RAW")
        mock_proc = MagicMock()
        mock_proc.name.return_value = "rawproc"
        mock_proc.exe.return_value = "/usr/bin/rawproc"

        with patch("netmon.monitor.collector.psutil.net_connections", return_value=[conn]), \
             patch("netmon.monitor.collector.psutil.Process", return_value=mock_proc):
            result = collect()

        assert len(result) == 1
        assert result[0].protocol == "UDP"  # не TCP → всё остальное идёт как UDP

    def test_sorting_by_process_name(self):
        conns = [
            _make_mock_conn(3, "127.0.0.1", 3000, "1.1.1.1", 80),
            _make_mock_conn(1, "127.0.0.1", 1000, "1.1.1.1", 80),
            _make_mock_conn(2, "127.0.0.1", 2000, "1.1.1.1", 80),
        ]

        def make_proc(name):
            p = MagicMock()
            p.name.return_value = name
            p.exe.return_value = f"/usr/bin/{name}"
            return p

        proc_map = {3: make_proc("zsh"), 1: make_proc("apt"), 2: make_proc("curl")}

        with patch("netmon.monitor.collector.psutil.net_connections", return_value=conns), \
             patch("netmon.monitor.collector.psutil.Process",
                   side_effect=lambda pid: proc_map[pid]):
            result = collect()

        names = [c.process_name for c in result]
        assert names == sorted(names, key=str.lower)

    def test_multiple_connections_same_process(self):
        conns = [
            _make_mock_conn(100, "127.0.0.1", 5000, "8.8.8.8", 443),
            _make_mock_conn(100, "127.0.0.1", 5001, "1.1.1.1", 80),
        ]
        mock_proc = MagicMock()
        mock_proc.name.return_value = "firefox"
        mock_proc.exe.return_value = "/usr/bin/firefox"

        with patch("netmon.monitor.collector.psutil.net_connections", return_value=conns), \
             patch("netmon.monitor.collector.psutil.Process", return_value=mock_proc):
            result = collect()

        assert len(result) == 2
        assert all(c.process_name == "firefox" for c in result)


# ─────────────────────────────────────────────────────────────── Connection.to_dict

class TestConnectionToDict:
    def test_to_dict_keys(self):
        conn = Connection(
            pid=1234,
            process_name="test",
            process_path="/usr/bin/test",
            local_addr="127.0.0.1:5000",
            remote_addr="8.8.8.8:443",
            status="ESTABLISHED",
            protocol="TCP",
            raw_laddr=MagicMock(),
            raw_raddr=MagicMock(),
        )
        d = conn.to_dict()
        assert set(d.keys()) == {"pid", "process", "local", "remote", "status", "protocol"}

    def test_to_dict_values(self):
        conn = Connection(
            pid=42,
            process_name="myapp",
            process_path="/opt/myapp",
            local_addr="0.0.0.0:8080",
            remote_addr="-",
            status="LISTEN",
            protocol="TCP",
            raw_laddr=MagicMock(),
            raw_raddr=(),
        )
        d = conn.to_dict()
        assert d["pid"] == 42
        assert d["process"] == "myapp"
        assert d["status"] == "LISTEN"

    def test_to_dict_none_pid(self):
        conn = Connection(
            pid=None,
            process_name="[unknown]",
            process_path="",
            local_addr="*:22",
            remote_addr="-",
            status="LISTEN",
            protocol="TCP",
            raw_laddr=MagicMock(),
            raw_raddr=(),
        )
        d = conn.to_dict()
        assert d["pid"] is None
