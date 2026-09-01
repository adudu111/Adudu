# Changelog

All notable changes to adudu are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

- Placeholder for upcoming changes.

## [v0.1.0-beta] - 2026-09-01

Initial public beta release for Windows 10/11 x64.

### Added

- **Profiles** — multiple, independent knowledge scopes.
- **Categories** — create, rename, reorder, delete; browse terms per category; assign a term's category.
- **Terms** — name + full name + optional category + aliases.
- **Dynamic sections** — per-term, user-defined, reorderable sections.
- **Offline search** — SQLite FTS5 full-text search over names, full names, aliases, categories, and section content.
- **Global lookup hotkey** — select text anywhere (`Ctrl+Shift+D`) and view the matching term in a floating, draggable, resizable popup.
- **Global launcher hotkey** — `Ctrl+Shift+Space` opens a floating global search launcher (categories-first results, expandable terms, copy/pin, minimize-to-bar).
- **System tray** — background operation with pause/open/exit; global-hotkey capture toggling.
- **Import / Export** (JSON, Markdown) and **Backup / Restore**.
- **Settings** — theme (dark/light), global + launcher hotkey configuration, licenses viewer.
- **Single-instance guard** — launching adudu again focuses the running instance.
- **Multi-select** — click-and-drag / Ctrl / Shift selection and bulk delete.

### Changed

- Transitioned entirely to a PySide6 + QWebEngine (local HTML/CSS/JS + QWebChannel) UI.
- Readme, docs, and third-party notices prepared for public release.

### Packaging / licensing

- Standalone **onedir** PyInstaller build (`adudu.exe` + `_internal\`).
- Bundled `LICENSE` (MIT), `THIRD-PARTY-NOTICES`, `lgpl-3.0.txt`, `gpl-2.0.txt`, and a `QtLicenses\` directory with the QtWebEngine/Chromium/ICU/NSS/BoringSSL/ANGLE/libvpx/FFmpeg/OpenSSL/Mesa/MSVC/Python license texts.
- Excluded the GPL-only Qt `QtVirtualKeyboard` module from the build.
- GitHub Actions CI + a tag-triggered GitHub Release workflow.

### Fixed

- Global hotkey display now reflects the actual saved hotkey.
- Section editing via double-click inline edit (title + content).
- Multi-select un-check no longer clears the whole selection.
- Save on edit no longer clears a term's category.
- Popup/launcher now opaque (no see-through) with a consistent blue border.

### Security

- Confirmed fully offline: no network calls, no telemetry/analytics, no cloud/accounts.

### Known limitations

- Windows 10/11 **x64 only**.
- Not code-signed (SmartScreen warning expected).
- Portable ZIP release, not an installer.
- Global hotkeys can conflict with other applications; both are configurable in Settings.
- Some systems may benefit from `--disable-gpu --no-sandbox`.
