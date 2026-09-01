"""QWebEngineView application shell hosting the local HTML/CSS/JS UI.

``adudu.exe -> PySide6 shell -> QWebEngineView -> bundled local HTML/CSS/JS``. It wires
the ``Bridge`` (QWebChannel) so JS talks to the existing services. The window keeps the
tray/hotkey-friendly lifecycle (hide-on-close, ``winId`` availability).

Global-hotkey lookup now runs in a separate frameless always-on-top popup
(``LookupPopupWindow``), not in this main window.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QMainWindow, QWidget

from cyberglossary import APP_NAME
from cyberglossary.ui.web.bridge import Bridge

_REQUIRED_FILES = ("index.html", "app.js", "qwebchannel.js")


class WebMainWindow(QMainWindow):
    def __init__(
        self,
        bridge: Bridge,
        web_dir: Path,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._exiting = False
        self.setWindowTitle(APP_NAME)
        self.resize(1440, 900)
        self.setMinimumSize(1024, 640)

        self.bridge = bridge

        self._index_path = (web_dir / "index.html").resolve()
        missing = [name for name in _REQUIRED_FILES if not (web_dir / name).is_file()]
        if missing:
            raise RuntimeError(
                f"Missing frontend resources in '{web_dir.resolve()}': {', '.join(missing)}"
            )

        self.view = QWebEngineView(self)
        self.view.setPage(QWebEnginePage(self))
        self.setCentralWidget(self.view)

        settings = self.view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)

        self.channel = QWebChannel(self.view.page())
        self.channel.registerObject("bridge", bridge)
        self.view.page().setWebChannel(self.channel)

        self.view.load(QUrl.fromLocalFile(str(self._index_path)))

    # --- lifecycle (tray-friendly) ---------------------------------------

    def show_window(self) -> None:
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()

    def exit_application(self) -> None:
        self._exiting = True
        self.close()

    def is_exiting(self) -> bool:
        return self._exiting

    def closeEvent(self, event) -> None:
        if self._exiting:
            event.accept()
            return
        event.ignore()
        self.hide()

    # --- push helpers ------------------------------------------------------

    def notify(self, message: str) -> None:
        self.bridge.toast.emit(message)
