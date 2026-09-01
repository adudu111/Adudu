# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build configuration for CyberGlossary (onedir, windowed).

Build from the project root with:  pyinstaller packaging/CyberGlossary.spec
"""

from pathlib import Path

project_root = Path(SPECPATH).parent  # noqa: F821  (SPECPATH provided by PyInstaller)

a = Analysis(
    [str(project_root / "src" / "cyberglossary" / "main.py")],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=[
        (str(project_root / "src" / "cyberglossary" / "database" / "schema.sql"),
         "cyberglossary/database"),
        (str(project_root / "resources" / "icon.ico"), "resources"),
        (str(project_root / "src" / "cyberglossary" / "ui" / "web" / "index.html"), "web"),
        (str(project_root / "src" / "cyberglossary" / "ui" / "web" / "app.js"), "web"),
        (str(project_root / "src" / "cyberglossary" / "ui" / "web" / "qwebchannel.js"), "web"),
        (str(project_root / "src" / "cyberglossary" / "ui" / "web" / "popup.html"), "web"),
        (str(project_root / "src" / "cyberglossary" / "ui" / "web" / "popup.js"), "web"),
        (str(project_root / "src" / "cyberglossary" / "ui" / "web" / "launcher.html"), "web"),
        (str(project_root / "src" / "cyberglossary" / "ui" / "web" / "launcher.js"), "web"),
        (str(project_root / "THIRD-PARTY-NOTICES"), "."),
        (str(project_root / "lgpl-3.0.txt"), "."),
        (str(project_root / "gpl-2.0.txt"), "."),
    ] + [
        (str(project_root / "packaging" / "third_party_notices" / name), "QtLicenses")
        for name in (
            "INDEX.txt",
            "QtWebEngine-CHROMIUM-LICENSE.txt",
            "ICU-LICENSE.txt",
            "NSS-MPL-2.0.txt",
            "BoringSSL-LICENSE.txt",
            "ANGLE-LICENSE.txt",
            "libvpx-LICENSE.txt",
            "FFmpeg-LICENSE.txt",
            "LGPL-2.1.txt",
            "OpenSSL-LICENSE.txt",
            "Mesa-LICENSE.txt",
            "MSVC-RUNTIME-NOTICE.txt",
            "Python-3.12.10-LICENSE.txt",
        )
    ],
    hiddenimports=["PySide6.QtWebChannel", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineCore"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Development/test tooling that must never ship.
        "pytest",
        "ruff",
        "tkinter",
        # Unused Qt modules (correctness first: only well-understood exclusions).
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuickWidgets",
        "PySide6.QtVirtualKeyboard",  # GPL-3.0-only (no LGPL option) — never ship it
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtPdf",
        "PySide6.QtPdfWidgets",
        "PySide6.QtWebSockets",
        "PySide6.QtSql",
        "PySide6.QtTest",
        "PySide6.QtDesigner",
        "PySide6.QtUiTools",
        "PySide6.QtXml",
        "PySide6.QtOpenGL",
        "PySide6.QtOpenGLWidgets",
        "PySide6.QtSensors",
        "PySide6.QtPositioning",
        "PySide6.QtLocation",
        "PySide6.Qt3DCore",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtBluetooth",
        "PySide6.QtNfc",
        "PySide6.QtRemoteObjects",
        "PySide6.QtSerialPort",
        "PySide6.QtScxml",
        "PySide6.QtStateMachine",
    ],
    noarchive=False,
)

# Compliance: drop the GPL-3.0-only Qt Virtual Keyboard library + its input
# plugin. QtWebEngine may pull them in transitively, but Adudu never uses an
# on-screen virtual keyboard, so they are safe to remove.
def _drop_banned(collection):
    kept = []
    for entry in collection:
        name = entry[0].lower()
        if "virtualkeyboard" in name:
            continue
        kept.append(entry)
    return kept

a.binaries = _drop_banned(a.binaries)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="adudu",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / "resources" / "icon.ico"),
    version=str(project_root / "packaging" / "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="adudu",
)
