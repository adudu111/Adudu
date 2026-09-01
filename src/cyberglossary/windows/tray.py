"""System tray integration.

``TrayController`` owns the ``QSystemTrayIcon`` and its menu. It depends only on the
``ProfileService`` and a paused-flag, never on repositories or SQLite. It emits signals that
the application composes (open window, settings, exit, profile selection, pause state).

Global-hotkey registration is intentionally *not* here — Phase 8 integrates it with the
pause state managed below.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from cyberglossary import APP_NAME
from cyberglossary.database.models import Profile
from cyberglossary.services.profile_service import ProfileService


@dataclass(frozen=True)
class ProfileActionSpec:
    """Pure data describing a profile entry in the tray menu."""

    profile_id: int
    name: str
    checked: bool


def build_profile_specs(profiles: list[Profile], active_id: int | None) -> list[ProfileActionSpec]:
    """Map profiles to menu specs, marking the active one."""
    return [ProfileActionSpec(p.id, p.name, p.id == active_id) for p in profiles]


class TrayController(QObject):
    open_requested = Signal()
    settings_requested = Signal()
    exit_requested = Signal()
    profile_selected = Signal(int)
    pause_toggled = Signal(bool)

    def __init__(
        self,
        profile_service: ProfileService,
        initial_paused: bool = False,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._service = profile_service
        self._paused = initial_paused
        self.tray = QSystemTrayIcon(self)
        self.tray.setToolTip(APP_NAME)
        self.tray.setIcon(self._make_icon())

        self.menu = QMenu()
        self.tray.setContextMenu(self.menu)
        # Left-click / double-click opens adudu; right-click still shows the menu.
        self.tray.activated.connect(self._on_activated)
        self._build_menu()
        self._rebuild_profile_menu()

    # --- construction -----------------------------------------------------

    @staticmethod
    def _make_icon() -> QIcon:
        from cyberglossary.config.resources import resource_path

        icon_path = resource_path("resources/icon.ico")
        if icon_path.exists():
            return QIcon(str(icon_path))

        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#4f8cff"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(4, 4, 24, 24)
        painter.end()
        return QIcon(pixmap)

    def _build_menu(self) -> None:
        self.open_action = self.menu.addAction(f"Open {APP_NAME}")
        self.open_action.triggered.connect(self.open_requested.emit)

        self.profile_menu = self.menu.addMenu("Active Profile")
        self.menu.aboutToShow.connect(self.refresh_profiles)

        self.menu.addSeparator()

        self.pause_action = self.menu.addAction("Pause Lookup")
        self.pause_action.setCheckable(True)
        self.pause_action.setChecked(self._paused)
        self.pause_action.toggled.connect(self._on_pause_toggled)

        self.settings_action = self.menu.addAction("Settings")
        self.settings_action.triggered.connect(self.settings_requested.emit)

        self.menu.addSeparator()

        self.exit_action = self.menu.addAction("Exit")
        self.exit_action.triggered.connect(self.exit_requested.emit)

    # --- profiles ---------------------------------------------------------

    def refresh_profiles(self) -> None:
        self._rebuild_profile_menu()

    def _rebuild_profile_menu(self) -> None:
        self.profile_menu.clear()
        profiles = self._service.list_profiles()
        active_id = self._service.get_active_profile_id()
        for spec in build_profile_specs(profiles, active_id):
            action: QAction = self.profile_menu.addAction(spec.name)
            action.setCheckable(True)
            action.setChecked(spec.checked)
            action.setData(spec.profile_id)
            action.triggered.connect(
                lambda _checked=False, pid=spec.profile_id: self._on_profile_selected(pid)
            )
        self.profile_menu.setEnabled(bool(profiles))

    def _on_profile_selected(self, profile_id: int) -> None:
        self._service.set_active_profile(profile_id)
        self.refresh_profiles()
        self.profile_selected.emit(profile_id)

    # --- pause state ------------------------------------------------------

    def is_paused(self) -> bool:
        return self._paused

    def set_paused(self, paused: bool) -> None:
        self._paused = paused
        self.pause_action.setChecked(paused)

    def _on_pause_toggled(self, checked: bool) -> None:
        self._paused = checked
        self.pause_toggled.emit(checked)

    # --- lifecycle --------------------------------------------------------

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.open_requested.emit()

    def show(self) -> None:
        self.tray.show()

    def hide(self) -> None:
        self.tray.hide()

    def notify(self, title: str, message: str) -> None:
        if self.tray.isSystemTrayAvailable():
            self.tray.showMessage(title, message)
