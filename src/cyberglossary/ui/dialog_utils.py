"""Dialog positioning helpers and the shared frameless dialog shell (§21)."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from cyberglossary.ui.icons import alert_icon
from cyberglossary.ui.icons import close as close_icon


def centered_position(
    dialog_width: int,
    dialog_height: int,
    parent_geometry: tuple[int, int, int, int] | None,
    screen_geometry: tuple[int, int, int, int],
) -> tuple[int, int]:
    """Return a centered (x, y), preferring the parent, clamped to the screen.

    Geometries are ``(x, y, width, height)``. When ``parent_geometry`` is ``None``, the
    dialog is centered within ``screen_geometry`` (e.g. the screen under the cursor).
    """
    target = parent_geometry if parent_geometry is not None else screen_geometry
    x = target[0] + (target[2] - dialog_width) // 2
    y = target[1] + (target[3] - dialog_height) // 2
    x = max(screen_geometry[0], min(x, screen_geometry[0] + screen_geometry[2] - dialog_width))
    y = max(screen_geometry[1], min(y, screen_geometry[1] + screen_geometry[3] - dialog_height))
    return x, y


def _screen_geometry(screen) -> tuple[int, int, int, int]:
    geometry = screen.availableGeometry()
    return geometry.x(), geometry.y(), geometry.width(), geometry.height()


def _screen_of_parent(parent):
    handle = parent.window().windowHandle()
    if handle is not None:
        screen = handle.screen()
        if screen is not None:
            return screen
    return QGuiApplication.screenAt(parent.frameGeometry().center()) or QGuiApplication.primaryScreen()


def center_dialog(dialog: QDialog, parent=None) -> None:
    """Center ``dialog`` over ``parent`` (or the cursor's screen when parent is hidden)."""
    dialog.adjustSize()

    if parent is not None and parent.isVisible():
        screen = _screen_of_parent(parent)
        geometry = parent.frameGeometry()
        parent_geometry = (geometry.x(), geometry.y(), geometry.width(), geometry.height())
    else:
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        parent_geometry = None

    screen_geometry = _screen_geometry(screen)
    size = dialog.frameGeometry().size()
    x, y = centered_position(size.width(), size.height(), parent_geometry, screen_geometry)
    dialog.move(QPoint(x, y))


class _DialogTitleBar(QWidget):
    """A draggable custom title bar for frameless dialogs."""

    def __init__(self, title: str, dialog: QDialog, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("dialogTitleBar")
        self.setFixedHeight(52)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 8, 0)
        layout.setSpacing(8)

        label = QLabel(title)
        label.setObjectName("dialogTitle")
        layout.addWidget(label, 1)

        close_btn = QToolButton()
        close_btn.setIcon(close_icon())
        close_btn.setToolTip("Close")
        close_btn.clicked.connect(dialog.reject)
        layout.addWidget(close_btn)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if handle is not None:
                handle.startSystemMove()
                event.accept()
                return
        super().mousePressEvent(event)


class FramelessDialog(QDialog):
    """A frameless modal dialog with a custom 52px title bar, body, and footer.

    Subclasses add fields to ``self.body_layout`` and actions to ``self.footer_layout``.
    """

    def __init__(self, title: str, parent: QWidget | None = None, width: int = 420):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle(title)
        self.setFixedWidth(width)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(0)

        self._card = QFrame()
        self._card.setObjectName("dialogCard")
        card = QVBoxLayout(self._card)
        card.setContentsMargins(0, 0, 0, 0)
        card.setSpacing(0)

        self._title_bar = _DialogTitleBar(title, self)
        card.addWidget(self._title_bar)

        self.body_widget = QWidget()
        self.body_layout = QVBoxLayout(self.body_widget)
        self.body_layout.setContentsMargins(20, 20, 20, 20)
        self.body_layout.setSpacing(10)
        card.addWidget(self.body_widget, 1)

        self.footer_widget = QWidget()
        self.footer_widget.setObjectName("dialogFooter")
        self.footer_layout = QHBoxLayout(self.footer_widget)
        self.footer_layout.setContentsMargins(20, 12, 20, 16)
        self.footer_layout.setSpacing(8)
        self.footer_layout.addStretch(1)
        card.addWidget(self.footer_widget)

        outer.addWidget(self._card)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        center_dialog(self, self.parentWidget())


class ConfirmDialog(FramelessDialog):
    """A confirm dialog with a warning icon, message, and a single danger action (§21)."""

    def __init__(
        self,
        title: str,
        message: str,
        confirm_text: str = "Delete",
        parent: QWidget | None = None,
    ):
        super().__init__(title, parent, width=420)
        self._confirmed = False

        row = QHBoxLayout()
        row.setSpacing(12)
        warn = QLabel()
        warn.setPixmap(alert_icon("#F5A524").pixmap(20, 20))
        row.addWidget(warn, 0, Qt.AlignmentFlag.AlignTop)

        column = QVBoxLayout()
        column.setSpacing(4)
        heading = QLabel(title)
        heading.setObjectName("dialogTitle")
        column.addWidget(heading)
        body = QLabel(message)
        body.setObjectName("muted")
        body.setWordWrap(True)
        column.addWidget(body)
        row.addLayout(column, 1)
        self.body_layout.addLayout(row)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("ghost")
        self.cancel_btn.clicked.connect(self.reject)
        self.confirm_btn = QPushButton(confirm_text)
        self.confirm_btn.setObjectName("danger")
        self.confirm_btn.clicked.connect(self._confirm)
        self.footer_layout.addWidget(self.cancel_btn)
        self.footer_layout.addWidget(self.confirm_btn)

    def _confirm(self) -> None:
        self._confirmed = True
        self.accept()

    def was_confirmed(self) -> bool:
        return self._confirmed


class NameDialog(FramelessDialog):
    """A single-field name dialog (New/Rename category, section, profile) (§21)."""

    def __init__(
        self,
        title: str,
        label: str,
        placeholder: str = "",
        prefill: str = "",
        confirm_text: str = "Create",
        parent: QWidget | None = None,
    ):
        super().__init__(title, parent, width=420)

        field_label = QLabel(label)
        field_label.setObjectName("muted")
        self.body_layout.addWidget(field_label)

        self.name_edit = QLineEdit(prefill)
        self.name_edit.setPlaceholderText(placeholder)
        self.body_layout.addWidget(self.name_edit)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("ghost")
        self.cancel_btn.clicked.connect(self.reject)
        self.ok_btn = QPushButton(confirm_text)
        self.ok_btn.setObjectName("primary")
        self.ok_btn.clicked.connect(self._try_accept)
        self.footer_layout.addWidget(self.cancel_btn)
        self.footer_layout.addWidget(self.ok_btn)

    def _try_accept(self) -> None:
        if self.name_edit.text().strip():
            self.accept()

    def value(self) -> str:
        return self.name_edit.text().strip()
