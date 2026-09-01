# Adudu

**Adudu** is a personal, **offline-first** knowledge-management application for building your own glossary of terms, commands, and concepts. You own and control all of your knowledge — it lives in a local database on your machine.

adudu is **not** an AI dictionary. It makes no LLM/API calls, needs no API key or account, and works entirely offline.

> **Beta status:** adudu is in **public beta** (v0.1.0-beta). You can use it for free on Windows 10/11 x64.

---

## Why adudu exists

Most reference tools push accounts, clouds, and AI-generated answers at you. adudu is the opposite:

- It is **yours** — everything is stored locally in a single SQLite file.
- It is **offline** — no internet connection is required, ever.
- It is **your structure** — you decide the categories, terms, and sections.
- It is **fast** — local full-text search and instant global lookup.

---

## Main features

- **Profiles** — multiple knowledge scopes (e.g. Cyber Security, Networking, English, Accounting).
- **Categories** — first-class grouping: create, rename, reorder, delete, and browse terms per category.
- **Terms** — name + full name + optional category + aliases.
- **Dynamic sections** — every term has its own user-defined, reorderable sections (no hard-coded "Definition"/"Notes" fields).
- **Offline search** — fast SQLite **FTS5** full-text search across titles, full names, aliases, categories, and section content.
- **Global lookup hotkey** — press **`Ctrl+Shift+D`** anywhere (browser, Word, VS Code, PDF, terminal…) to look up the selected text in your active profile, in a floating, draggable, resizable popup.
- **Global launcher hotkey** — press **`Ctrl+Shift+Space`** to open a floating global search launcher. Search categories first, then terms/commands; expand results, copy details, pin/recent items, and minimize the launcher to a floating bar.
- **System tray** — run in the background; pause the lookup hotkey at any time; open/exit from the tray.
- **Import / export & backup / restore** — JSON, Markdown, and database backups.

> Templates and Tags are no longer part of the active v1 product. Their tables remain in the database for backward compatibility but are not shown in the UI.

---

## Architecture: local, offline, SQLite

- All data is stored in a **local SQLite database** (with FTS5 for full-text search).
- The database is created automatically on first launch under `%APPDATA%\CyberGlossary\` (never inside the application folder).
- Downloads: **none**. adudu does **not** send anything over the network. It contains **no telemetry, analytics, account system, or cloud sync**.
- The database location can be overridden with the `CYBERGLOSSARY_DATA_DIR` environment variable.

See `ARCHITECTURE.md` and `SPEC.md` for full technical detail.

---

## Installation (Windows 10 / 11 x64)

**No Python, Qt, Node.js, or development tools are required.** adudu ships as a self-contained application.

1. Download the latest release: `adudu-<version>-windows-x64.zip`.
2. Extract the ZIP to a folder of your choice (e.g. `C:\Programs\adudu\`).
3. Run **`adudu.exe`**.
4. That's it — the database is created on first launch. Use the system tray icon to keep it running in the background.

> On first launch Windows SmartScreen may warn about an unsigned app (there is currently no code-signing). Select **More info → Run anyway** if you trust the source.

---

## Basic usage

1. **Set up a home** — create a Profile, then Categories, and add Terms.
2. **Organize** — add dynamic Sections to a term (purpose, examples, commands, notes…).
3. **Lookup anywhere** — highlight text in any app and press **`Ctrl+Shift+D`**. The floating popup shows the matching term.
4. **Launch & search** — press **`Ctrl+Shift+Space`** anywhere to search the whole knowledge base from a floating launcher.
5. **Find** — use the search box (top-right) or `Ctrl+K`.
6. **Back up** — use File → Backup (or the tray) to protect your data.

---

## Beta status & known limitations

- **Platform:** Windows 10/11 **x64** only, for now.
- **GPU:** on some systems you may need to launch with `--disable-gpu --no-sandbox` (used automatically in CI).
- **Global hotkeys:** `Ctrl+Shift+D` and `Ctrl+Shift+Space` can conflict with other applications; both are changeable in Settings.
- **Signing:** the app is **not** code-signed yet, so SmartScreen will show a warning.
- **No installer:** the release is a portable ZIP (onedir build), not an installer.
- **Data safety:** your data is local and yours, but adudu does not auto-sync anywhere. Use Backup/Export to guard against data loss.

---

## Privacy & security

- **Local-only.** All content is stored in a local SQLite file under your Windows profile.
- **No network.** We verified the application source makes no network calls and includes no telemetry/analytics SDKs.
- **No accounts, no cloud.** Nothing is uploaded, and no personal data leaves your machine.
- **No clipboard leakage.** The lookup hotkey reads selected text only to look it up inside your profile; it is not logged or sent anywhere.

---

## Feedback

Found a bug or want a feature? Use the **GitHub Issues**:

- **[Bug Report](.github/ISSUE_TEMPLATE/bug_report.md)** — include steps to reproduce, expected vs. actual behavior, and your OS/build.
- **[Feature Request](.github/ISSUE_TEMPLATE/feature_request.md)** — describe the problem and the solution you'd like.

Please redact personal info from any screenshots/logs. Do **not** upload your database file.

---

## Licensing

- **adudu** is licensed under the **MIT License** — see [LICENSE](LICENSE).
- **Third-party software** (Qt/PySide6/WebEngine, Python, pywin32, icons, and more) is listed in [THIRD-PARTY-NOTICES](THIRD-PARTY-NOTICES), with the relevant license texts bundled in `QtLicenses\` inside the application.
- Icons are from **Feather (MIT)** and **Lucide (ISC)**.

---

## Roadmap (Free → Pro)

A future **Free → Pro** model is planned but **not implemented**. The current beta is entirely free:

- **Free** — the full offline knowledge base, global lookup, and launcher (as today).
- **Pro (planned)** — optional, likely value-adds such as advanced sync/backups, extra import formats, or priority support. **No payments or licensing are implemented in the beta**, and no Free features are gated.

---

## Tech stack & development

- Python 3.12+ · PySide6 (Qt for Python) · SQLite (FTS5) · pywin32 / Windows APIs · PyInstaller · pytest

### Getting started (development)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
python -m cyberglossary
```

### Build a Windows executable

```powershell
.\scripts\build.ps1        # installs deps, tests + ruff, then builds
# or, after `pip install -e ".[dev,build]"`:
pyinstaller packaging\CyberGlossary.spec
```

Produces a **onedir** distribution:

```
dist\adudu\
├── adudu.exe
└── _internal\        # bundled Python, Qt, and app resources
```

The end user does **not** need Python, PySide6, pywin32, or SQLite installed.

### CI (GitHub Actions)

`.github/workflows/build-windows.yml` runs on `windows-latest` (Python 3.12) on every push/PR: installs deps → pytest → ruff → builds → verifies → headless smoke test → uploads the `adudu-windows` artifact. `.github/workflows/release.yml` builds a tagged release and uploads `adudu-<version>-windows-x64.zip` **and** `SHA256SUMS.txt` as GitHub **Pre-release**.

---

## Project layout

```
src/cyberglossary/
├── ui/             # PySide6 windows and widgets (incl. web popup/launcher)
├── database/       # sqlite3 connection, migrations, repositories, FTS
├── services/       # business logic (glossary, search, templates, backup…)
├── windows/        # Windows integration (hotkey, clipboard, tray, single-instance)
├── import_export/  # JSON + Markdown import/export
└── config/         # settings + app-data paths
```

---

## Notes

- The user-facing product name is **adudu**; the internal Python package (`cyberglossary`) and the default data path (`%APPDATA%\CyberGlossary\`) are unchanged for backward compatibility.
- No telemetry, analytics, cloud services, or network calls. No LLM/API integration — any LLM tooling is used only by the development environment, never by the shipped application.
- **Windows 10 / Windows 11 (x64) only.**
