import ipaddress
import os
import socket

import httpx
import psycopg2
import pytest
import requests


# Sanitize SSL_CERT_FILE on Windows if Anaconda sets it to a non-existent path
ssl_cert = os.environ.get("SSL_CERT_FILE")
if ssl_cert and not os.path.exists(ssl_cert):
    os.environ.pop("SSL_CERT_FILE", None)


def _is_loopback(address: object) -> bool:
    if not isinstance(address, tuple) or not address:
        return False
    try:
        return ipaddress.ip_address(str(address[0])).is_loopback
    except ValueError:
        return False


@pytest.fixture(autouse=True)
def forbid_live_services(monkeypatch):
    """Block external I/O while allowing Starlette's in-process loopback socket."""

    def blocked(*args, **kwargs):
        pytest.fail("Live I/O is disabled in tests; mock the service explicitly.")

    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_httpx_send = httpx.Client.send

    def guarded_connect(sock, address):
        if _is_loopback(address):
            return original_connect(sock, address)
        return blocked(sock, address)

    def guarded_connect_ex(sock, address):
        if _is_loopback(address):
            return original_connect_ex(sock, address)
        return blocked(sock, address)

    def guarded_httpx_send(client, request, *args, **kwargs):
        if client.__class__.__module__ == "starlette.testclient":
            return original_httpx_send(client, request, *args, **kwargs)
        return blocked(client, request, *args, **kwargs)

    monkeypatch.setattr(requests.sessions.Session, "request", blocked)
    monkeypatch.setattr(httpx.Client, "send", guarded_httpx_send)
    monkeypatch.setattr(psycopg2, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
