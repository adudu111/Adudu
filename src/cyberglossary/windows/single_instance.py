"""Single-instance guard for adudu.

Uses a ``QLocalServer``/``QLocalSocket`` channel. The first instance listens on a
per-user named pipe; a later instance connects, sends an ``activate`` request, and exits.
The running instance receives the request and brings its window to the foreground.
"""

from __future__ import annotations

import getpass
import os
import re
from collections.abc import Callable

from PySide6.QtCore import QObject
from PySide6.QtNetwork import QLocalServer, QLocalSocket

_ACTIVATE = b"activate"


def server_name() -> str:
    """A per-user, stable name for the single-instance pipe."""
    user = os.environ.get("USERNAME") or os.environ.get("USER") or getpass.getuser() or "user"
    safe = re.sub(r"[^A-Za-z0-9_]", "_", user)
    return f"adudu_single_{safe}"


def notify_running_instance(name: str) -> bool:
    """Ask an already-running instance to come to the foreground.

    Returns ``True`` if another instance is running (and was told to activate), so the
    caller should exit. Returns ``False`` when no other instance answered.
    """
    sock = QLocalSocket()
    sock.connectToServer(name)
    if sock.waitForConnected(300):
        sock.write(_ACTIVATE)
        sock.flush()
        sock.waitForBytesWritten(300)
        sock.close()
        return True
    return False


class SingleInstanceServer(QObject):
    """Listens for ``activate`` requests from a second launch of adudu."""

    def __init__(self, name: str, on_activate: Callable[[], None], parent: QObject | None = None):
        super().__init__(parent)
        self._server = QLocalServer(parent or self)
        self._server.listen(name)
        self._server.newConnection.connect(self._on_new_connection)
        self._on_activate = on_activate

    def _on_new_connection(self) -> None:
        conn = self._server.nextPendingConnection()
        if conn is None:
            return
        conn.readyRead.connect(lambda: self._read(conn))

    def _read(self, conn) -> None:
        data = bytes(conn.readAll())
        if _ACTIVATE in data:
            self._on_activate()
