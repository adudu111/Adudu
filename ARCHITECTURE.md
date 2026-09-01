# CyberGlossary — Architecture

> Status: **Draft for approval** (Phase 1 not started)
> Stack: **Python / PySide6 / SQLite** (replaces the earlier C#/.NET/WinUI 3 draft)

## 1. Vision and governing principles

CyberGlossary is a **personal, offline-first, local knowledge-management system** for studying
subjects (Cyber Security, Networking, Programming, Accounting, English, …) by hand-building a
glossary of terms.

Non-negotiable principles:

1. **The user owns all knowledge.** Every profile, term, category, tag, alias, template, and
   section is authored manually. Nothing is auto-generated or fetched.
2. **Not an AI dictionary.** No LLM/API integration of any kind. No API key. No outbound network
   call. Normal use works fully offline.
3. **No hard-coded fields.** There are no mandatory "Definition / Example / Notes" columns.
   Terms carry dynamically created sections.
4. **Two UIs, one source of truth.** The main window is the "web-like" knowledge manager; the
   system-tray/global-hotkey popup is a lightweight read-only viewer + entry point.

### 1.1 DeepSeek boundary (explicit)

```
OpenCode  ──►  DeepSeek API          (development only, external to the app)
CyberGlossary.exe ──► PySide6 ──► SQLite ──► Windows APIs   (no AI, no network)
```

The shipped application **must not** call DeepSeek, OpenAI, or any LLM API; must not require a key;
must not send selected text anywhere; must not auto-fetch definitions. This is enforced by review,
not just convention.

---

## 2. Final technology stack

| Concern | Choice | Rationale |
|---|---|---|
| Language | **Python 3.12+** | Required; mature ecosystem for desktop + Windows interop. |
| GUI | **PySide6** (Qt for Python) | Native desktop widgets, modern styling (QSS), dark/light themes, `QSystemTrayIcon`, frameless popups. |
| Database | **SQLite** (built-in `sqlite3`) | Single-file, embedded, offline, WAL, FTS5. |
| DB abstraction | **stdlib `sqlite3` + thin repositories** (SQLAlchemy **not** used) | Dynamic rows-as-sections + FTS5 virtual tables are simplest with raw SQL. See §3. |
| Windows integration | **pywin32** + **ctypes** | Clipboard, global hotkey (`RegisterHotKey`), `SendInput`, foreground window. |
| Packaging | **PyInstaller** | Standalone `CyberGlossary.exe`; no Python/Qt/SQLite install required by end user. |
| Tests | **pytest** | Unit + integration. |
| Config/deps | **pyproject.toml** + virtualenv | Reproducible builds. |

### 2.1 Explicitly excluded

- C#, .NET, WinUI 3, WPF, Electron, Tauri, Rust.
- Any HTTP client / network library in the shipped app.
- Any LLM/AI SDK, API key, or secret.
- Docker (not required; see §24).

---

## 3. Why SQLAlchemy is not used (design decision)

The spec allows SQLAlchemy "if useful". Here it is **not**, for three reasons:

1. **Dynamic sections.** The core data model is "a term has N rows of `(title, content, order)`".
   There is no benefit to an ORM mapping of a schema that is deliberately free-form.
2. **FTS5.** Full-text search uses a `fts5` virtual table and `MATCH` queries; these require raw
   SQL and ORM models add friction without value.
3. **Control over SQLite internals.** WAL mode, `PRAGMA foreign_keys`, `ON DELETE CASCADE`, and a
   tiny migration runner are clearer and more testable with `sqlite3` + plain SQL.

We still keep a **clean abstraction boundary**: the UI never touches SQLite; it calls service
classes, which call repository classes. Swapping in SQLAlchemy later (if ever needed) would not
change the services/UI layers.

---

## 4. Project structure

```
CyberGlossary/
├── pyproject.toml
├── README.md
├── ARCHITECTURE.md
├── SPEC.md
├── LICENSE
├── .gitignore
├── .github/workflows/build-windows.yml
├── packaging/
│   └── CyberGlossary.spec          # PyInstaller spec
├── scripts/
│   ├── seed_sample_data.py         # optional sample profile
│   └── build.ps1                   # venv + test + build helper
├── src/cyberglossary/
│   ├── __init__.py
│   ├── main.py                     # entrypoint
│   ├── app.py                      # QApplication bootstrap + single instance
│   ├── ui/
│   │   ├── main_window.py
│   │   ├── dashboard.py
│   │   ├── term_list.py
│   │   ├── term_editor.py
│   │   ├── section_editor.py
│   │   ├── popup.py
│   │   ├── profile_selector.py
│   │   ├── template_editor.py
│   │   ├── settings_dialog.py
│   │   └── theme.py                # QSS / palette (dark + light)
│   ├── database/
│   │   ├── connection.py           # path, PRAGMA, WAL, foreign keys
│   │   ├── migrations.py           # versioned schema runner
│   │   ├── schema.sql              # canonical schema (or per-version scripts)
│   │   ├── models.py               # dataclasses (not ORM entities)
│   │   └── repositories.py         # profile/term/section/tag/template repos
│   ├── services/
│   │   ├── profile_service.py
│   │   ├── glossary_service.py     # term + section orchestration
│   │   ├── template_service.py
│   │   ├── search_service.py       # FTS query building + lookup
│   │   ├── lookup_service.py       # normalize -> search -> result
│   │   ├── backup_service.py
│   │   └── seed_service.py         # sample data
│   ├── windows/                    # Windows-specific integration (thin)
│   │   ├── hotkey.py               # RegisterHotKey + native event filter
│   │   ├── clipboard.py            # capture + restore
│   │   ├── text_capture.py         # Ctrl+C pipeline
│   │   ├── tray.py                 # QSystemTrayIcon + menu
│   │   └── single_instance.py      # mutex-based single instance
│   ├── import_export/
│   │   ├── json_export.py
│   │   ├── json_import.py
│   │   └── markdown_export.py
│   └── config/
│       ├── settings.py             # dataclass + persistence (QSettings)
│       └── paths.py                # app-data directory resolution
└── tests/
    ├── conftest.py
    ├── test_profiles.py
    ├── test_terms.py
    ├── test_sections.py
    ├── test_aliases.py
    ├── test_templates.py
    ├── test_search.py
    ├── test_import_export.py
    └── test_backup_restore.py
```

Notes on structure vs. the suggested layout:

- Added `app.py` (QApplication bootstrap + single instance) so `main.py` stays minimal.
- Added `config/paths.py` to centralize the `%APPDATA%` directory logic.
- Added `windows/` as a thin integration layer so tests can mock the OS boundary.
- Added `packaging/CyberGlossary.spec` for the PyInstaller config.

### 4.1 Layering rules

```
ui ──► services ──► repositories ──► sqlite3
ui ──► windows (thin OS integration)
services ──► repositories / models
import_export ──► services / repositories
config ──► (used everywhere, no reverse deps)
```

- `ui/` depends on `services/`, never on `database/` directly.
- `windows/` knows Qt + Windows APIs but no business logic.
- `database/` knows only SQLite + `models.py` dataclasses.
- Business rules live in `services/` and are unit-testable without a GUI or real clipboard.

---

## 5. Database schema (SQLite)

File: `%APPDATA%\CyberGlossary\cyberglossary.db` (see §18). `PRAGMA journal_mode=WAL`,
`PRAGMA foreign_keys=ON`. Timestamps are ISO-8601 UTC strings.

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- migration/bookkeeping
CREATE TABLE app_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

-- 5.1 Profiles (top-level knowledge scopes)
CREATE TABLE profiles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL COLLATE NOCASE UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    color       TEXT,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- 5.2 Categories (per profile)
CREATE TABLE categories (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    name       TEXT NOT NULL COLLATE NOCASE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    UNIQUE (profile_id, name)
);

-- 5.3 Tags (per profile)
CREATE TABLE tags (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    name       TEXT NOT NULL COLLATE NOCASE,
    UNIQUE (profile_id, name)
);

-- 5.4 Terms
CREATE TABLE terms (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id  INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    term        TEXT NOT NULL COLLATE NOCASE,     -- short name (e.g. "LDAP")
    full_name   TEXT NOT NULL DEFAULT '',          -- e.g. "Lightweight Directory Access Protocol"
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    UNIQUE (profile_id, term)
);
CREATE INDEX idx_terms_profile ON terms(profile_id, sort_order);
CREATE INDEX idx_terms_category ON terms(category_id);

-- 5.5 Aliases / misspellings (user-controlled)
CREATE TABLE aliases (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    term_id    INTEGER NOT NULL REFERENCES terms(id) ON DELETE CASCADE,
    alias      TEXT NOT NULL COLLATE NOCASE,
    created_at TEXT NOT NULL,
    UNIQUE (term_id, alias)
);
CREATE INDEX idx_aliases_alias ON aliases(alias);

-- 5.6 Term <-> Tag join
CREATE TABLE term_tags (
    term_id INTEGER NOT NULL REFERENCES terms(id) ON DELETE CASCADE,
    tag_id  INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (term_id, tag_id)
);

-- 5.7 Dynamic sections (user-defined, ordered)
CREATE TABLE sections (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    term_id    INTEGER NOT NULL REFERENCES terms(id) ON DELETE CASCADE,
    title      TEXT NOT NULL,                     -- user-defined ("Ports", "AS-REQ", "My Notes")
    content    TEXT NOT NULL DEFAULT '',           -- plain text / Markdown
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_sections_term ON sections(term_id, sort_order);

-- 5.8 Templates (per profile)
CREATE TABLE templates (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id  INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    name        TEXT NOT NULL COLLATE NOCASE,
    description TEXT NOT NULL DEFAULT '',
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    UNIQUE (profile_id, name)
);

CREATE TABLE template_sections (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id INTEGER NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    placeholder TEXT NOT NULL DEFAULT '',
    sort_order  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_tmpl_sections ON template_sections(template_id, sort_order);

-- 5.9 Settings (key/value)
CREATE TABLE settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
-- keys: active_profile_id, hotkey_modifiers, hotkey_key, search_scope, theme, backup_path, auto_backup, ...
-- hotkey is stored structured (hotkey_modifiers = bitmask int, hotkey_key = virtual-key code int)

-- 5.10 Full-text index (FTS5). rowid == terms.id.
CREATE VIRTUAL TABLE terms_fts USING fts5(
    term, full_name, aliases, tags, category, body, profile_id UNINDEXED,
    tokenize = 'unicode61 remove_diacritics 2'
);
```

### 5.1 Schema design notes

- **Sections are rows, not columns** — the single most important decision. It lets LDAP have
  "Ports" while Kerberos has "AS-REQ/AS-REP/TGS" and ROA has "Formula/Interpretation", with zero
  schema change.
- **Profile isolation via cascade.** Deleting a profile removes its categories, tags, terms,
  sections, aliases, and templates.
- **Term identity** is `(profile_id, term)` (case-insensitive unique). The same abbreviation can
  exist in different profiles.
- **`category_id` nullable** and `ON DELETE SET NULL` — category is optional metadata, never a
  required field.
- **Aliases** are separate rows owned by the user; the app never auto-adds them.
- **FTS sync is done in the repository layer, transactionally.** Any change to a term, its
  aliases, tags, category, or sections recomputes that term's single FTS row (rowid = term id),
  aggregating all searchable text. This avoids brittle SQL triggers and keeps the logic testable.

---

## 6. Profile architecture

- A **profile** is a top-level scope (e.g. "Cyber Security", "Accounting", "Networking", "English").
- Each profile owns its own **terms, categories, tags, templates** (all scoped by `profile_id`).
- One **active profile** is persisted (in `settings`) and controls which glossary the global
  lookup searches. Switching profiles is a one-click action in the sidebar/tray.
- Deleting the active profile automatically promotes another remaining profile (first by
  `sort_order`); the active setting is cleared only when no profiles remain.
- Same abbreviation can resolve differently per profile (e.g. `SPN` = Service Principal Name in
  Cyber Security; something else elsewhere).

---

## 7. Term architecture

- Term fields: `term` (short name), `full_name`, optional `category_id`, optional tags, optional
  aliases, `sort_order`, timestamps.
- No required knowledge fields. A term may exist with zero sections.
- Operations: create, edit, delete, duplicate (copies sections), reorder, assign/clear category
  and tags, manage aliases.

---

## 8. Dynamic section architecture

- Each section = `title` + `content` + `sort_order` + timestamps, scoped to a term.
- Full lifecycle: **add, edit (title + content), delete, rename, reorder, collapse** (collapse is
  UI-only state, optionally persisted per user preference).
- Order is persisted (`sort_order`); reorder is an ordered-list move recomputed in one transaction.
- No hard-coded section names anywhere in UI or logic.

---

## 9. Aliases / misspellings

- Stored as rows in `aliases` (`term_id`, `alias`), fully user-controlled.
- Lookup consults aliases **after** the exact term title and **before** full-text best match.
- The app never writes aliases automatically; the user explicitly adds them (e.g. `LDPA` → LDAP).

---

## 10. Templates (removed from v1)

Templates are **removed from the active v1 product**. The `templates`/`template_sections`
tables and the `TemplateService`/`TemplateRepository` remain in the schema and code for backward
compatibility and legacy import/export, but they are not exposed in the UI. The same applies to
**Tags** (`tags`/`term_tags` + `TagRepository`): no tag UI, no tag filtering.

---

## 11. Search architecture

Two paths share the FTS5 index:

1. **In-app search** (main window): matches across `term`, `full_name`, `aliases`, `tags`,
   `category`, and section `title`/`content` (the aggregated `body`).
2. **Lookup** (hotkey): normalize selected text → resolve within the **active profile**.

Query semantics (kept simple, deterministic):

| Syntax | Meaning |
|---|---|
| `ldap` | token match (AND across tokens by default) |
| `"ldap injection"` | phrase |
| `kerb*` | prefix |
| `ports OR 389` | boolean OR |
| `-tgt` | negate |

A `SearchQueryBuilder` sanitizes input (strips FTS reserved characters: `: ( ) " -` etc.) and
builds the `MATCH` string. Results are filtered by `profile_id`; highlighting uses FTS5 `snippet()`.

Implementation notes (Phase 6):

- **Negation** (`-tgt`): FTS5 supports only binary `NOT` (`a NOT b`), not unary negation. The
  builder therefore separates negated terms via `negated_terms()` and the `SearchService` excludes
  them at the service layer (a pure-negation query lists all in-scope terms, then subtracts the
  negated matches by rowid — no full-content load, only ids).
- **Sync**: every searchable write (term rename/full-name/category/tags, section
  add/rename/content/delete/reorder, alias add/delete, term create/duplicate/apply/delete, profile
  delete) recomputes the term's FTS row (`database/fts.py`) *before* its commit, so a source change
  and its index update share one transaction.
- **Backfill**: `fts.ensure_index()` runs after migration and rebuilds the index only when the
  row counts of `terms` and `terms_fts` differ; `fts.rebuild()` provides a deterministic full rebuild.

**Lookup algorithm** (active profile only):

1. Normalize selected text (§14.1).
2. Exact case-insensitive match on `terms.term` → return term.
3. Exact match on `aliases.alias` → return owning term.
4. Else FTS best match above a relevance threshold → return term.
5. Else → "Term not found" (no AI, no network).

---

## 12. Global hotkey (Ctrl + Shift + D — configurable)

### 12.1 Mechanism and isolation

- Mechanism: Win32 **`RegisterHotKey`** (system-wide, no keyboard hook) via **ctypes**
  (`user32.RegisterHotKey(hwnd, id, MOD_CONTROL|MOD_SHIFT, vk)`).
- Integration with Qt: a **`QAbstractNativeEventFilter`** is installed on the `QApplication`; when
  `WM_HOTKEY` (0x0312) arrives for our registered id, the filter emits a Qt signal consumed by the
  app, which runs the capture→lookup→popup pipeline.
- **All hotkey logic lives in `windows/hotkey.py`.** The Win32 `RegisterHotKey`/`UnregisterHotKey`
  calls and the native event handling never appear inside PySide6 widgets. The UI talks to a clean
  `HotkeyService` interface.

### 12.2 Structured representation (not just a display string)

The hotkey is stored **structured**, suitable for `RegisterHotKey`, and formatted only for display:

```python
# internal representation
Hotkey(modifiers=Modifier.CTRL | Modifier.SHIFT, key=VK.D)   # VK = virtual-key code
# formatted for UI
"Ctrl + Shift + D"
```

- `modifiers` = bitmask of `CTRL`, `SHIFT`, `ALT`, `WIN`.
- `key` = a non-modifier virtual-key code (letter, digit, `F1`–`F24`, etc.).
- Parsing (string → `Hotkey`) and formatting (`Hotkey` → string) are pure functions in
  `windows/hotkey.py`, fully unit-testable without any OS call.

### 12.3 Validity rules

- A valid hotkey must contain **at least one non-modifier key**.
- **Modifier-only combinations are rejected** (`Ctrl`, `Shift`, `Alt`, `Ctrl+Shift`, …).

### 12.4 Change flow (validation before commit)

When the user chooses a new hotkey:

1. Validate the combination (non-empty, at least one non-modifier key).
2. **Unregister** the current global hotkey.
3. Attempt to **register** the new hotkey via `RegisterHotKey`.
4. **Success** → persist to settings, activate immediately, show success.
5. **Failure** → **keep the old hotkey active** (re-register it), do **not** save the new one,
   explain that the shortcut may be in use by another app, and let the user pick another.

### 12.5 Reset to default

- `[ Reset to Default ]` restores `Ctrl + Shift + D`, immediately attempting registration.
- If the default is unavailable (in use), **keep the previous working hotkey** and report it.

### 12.6 Lifecycle

- Register on application start; unregister on exit.
- Unregister when changing the shortcut; register the replacement.
- Re-register when lookup is **resumed** after **Pause Lookup**.
- Remain active while minimized to tray.
- If **startup registration fails**, do not crash — show a clear warning and let the user configure
  another hotkey.

### 12.7 Pause Lookup

- `Pause Lookup` **unregisters/disable** the global hotkey without closing the app.
- The configured hotkey value is **not lost** while paused.
- Resuming registers the configured hotkey again.

### 12.8 Settings UI (Settings → General / Lookup)

- Displays `Global Lookup Hotkey` with the current shortcut and a `[ Change ]` button.
- `Change` opens a **hotkey capture dialog**: "Press the key combination you want to use", showing
  current vs. a live "Waiting for key combination…" field, with `Cancel` / `Save`.
- The dialog **detects the actual pressed combination** (native key events), never asks the user to
  type a string.
- Supported examples: `Ctrl+Shift+D`, `Ctrl+Alt+L`, `Alt+Shift+G`, `Ctrl+F8`, `F9`.
- On conflict, shows: "Could not register … This shortcut may already be in use by another
  application." with `[ Try Another ]`.

---

## 13. Selected-text capture + clipboard handling

**Strategy: clipboard-first (Ctrl+C), with careful save/restore.** This matches the spec's
preferred workflow and is deterministic across Chrome/Edge/Firefox/Word/PDF readers/VS Code/Notepad.

Pipeline:

1. User selects text in the foreground app and presses the hotkey.
2. **Save current clipboard state** — record `GetClipboardSequenceNumber()` and, where practical,
   the existing content (text + image/format presence).
3. **Send `Ctrl+C`** via `SendInput` to the foreground window.
4. **Read clipboard text** (poll briefly, e.g. up to ~250 ms) for the selected text.
5. **Restore** the previous clipboard content (best-effort).
6. Normalize and look up locally.

Safety rules:

- Never read the clipboard unless a user-initiated hotkey triggered it.
- Use the sequence number to detect whether another app changed the clipboard mid-capture.
- If restore is impossible (locked clipboard, async/cloud clipboard, external change), degrade
  gracefully — never crash, never clobber permanently.
- Captured text is used **only** for the local DB lookup; it is never logged or persisted.

*Future option (not v1):* UI Automation (`UIAutomation` via `comtypes`/`pywin32`) as a
non-destructive first attempt before falling back to clipboard. Deferred; clipboard-first is the
shipped default.

Implemented in Phase 8: `windows/clipboard.py` (`ClipboardProvider` + `WindowsClipboard`),
`windows/text_capture.py` (`TextCapture`), `windows/hotkey.py` (`HotkeyService`), and
`services/lookup_service.py` (`normalize_selected_text` + `LookupService`). The restore step only
re-writes text when prior text existed and the sequence number is unchanged since capture (never
clobbers a newer write; never destroys non-text clipboard content).

### 13.1 Lookup normalization

Apply deterministic cleanup to the captured text:

- Trim leading/trailing whitespace; collapse internal line breaks to spaces.
- Strip surrounding quotes (`"LDAP"`, `'LDAP'`).
- Strip trailing punctuation (`. , ; :`).
- If the selection is a longer phrase (e.g. `LDAP (Lightweight Directory Access Protocol)`),
  extract a candidate token — initially a simple, deterministic heuristic (e.g. the first
  "word-like" token before a parenthesis); configurable later. No AI.

---

## 14. Lookup popup

- A floating, frameless, always-on-top panel (`Tool` + `FramelessWindowHint` +
  `WindowStaysOnTopHint`), rendered as a rounded card (`QFrame#popupCard`) with a subtle drop shadow.
- **Draggable** by its title bar (`startSystemMove`) and **resizable** from all four edges and four
  corners (`startSystemResize`), with a minimum size and scrollable body.
- Positioned near the cursor (`QCursor.pos()`) and clamped to the cursor's screen
  `availableGeometry`; a new lookup positions near the cursor, while a re-used popup keeps the
  user's manual position/size.
- **Found**: title bar (term + full name/category) and **all** sections in `sort_order` (read-only),
  with **Open Full Page**, **Edit**, **Close** in the action bar.
- **Not found**: `Term not found in current profile.` with **[ + Add Term ]** and **[ Close ]**.
- `Esc` / focus-out dismisses the popup; a new lookup reuses the single popup (no duplicates).
- The popup renders whatever sections exist; it hard-codes nothing.

**Focus limitation (documented):** to keep `Esc`, the action buttons, dragging, and resizing usable,
the popup takes focus when shown (a plain `Tool` window). This is an accepted Qt/Windows windowing
trade-off.

---

## 15. Add-term flow (from popup)

1. User clicks **[ + Add Term ]**.
2. A creation dialog opens pre-filled with the captured text as `term`, plus fields for
   `full_name` and `category`.
3. On save, the term is created and the **main window** opens the new term editor so the user can
   add arbitrary sections manually.

---

## 16. Main window (knowledge manager)

A header + sidebar + stacked-content layout in PySide6:

```
┌──────────────────────────────────────────────────────┐
│ CyberGlossary                            Search...    │
├────────────┬─────────────────────────────────────────┤
│ Sidebar    │ Content (stack)                          │
│  Profile ▾ │  Terms view      |  Categories page      │
│  LIBRARY   │  [term list |      |  [list + terms]    │
│   Terms    │   term editor]     |                     │
│   Categ.   │                   |                     │
│  SYSTEM    │                   |                     │
│   Settings │                   |                     │
│  Theme     │                   |                     │
└────────────┴─────────────────────────────────────────┘
```

- **Header**: app title (left) + the main search field (right). Typing switches to the Terms view
  and filters via `SearchService` (FTS5, active profile).
- **Sidebar**: profile selector + `LIBRARY` (Terms, Categories) + `SYSTEM` (Settings) + theme toggle.
  Templates and Tags are not shown.
- **Term editor**: editable term/full-name/category, plus dynamic sections with add/rename/edit/
  reorder/delete/collapse.
- **Categories page**: a three-column layout — categories (search + counts + reorder) | category
  details (rename/delete) | terms in the category. Assign terms via **Add Existing Term** (never
  creates duplicates); a right-click context menu offers Open/Edit/Remove from Category/Delete Term.
- Clean QSS styling; **dark and light modes**; resizable; keyboard friendly.

---

## 17. System tray

- `QSystemTrayIcon` with a context menu:
  `Open CyberGlossary`, `Active Profile ▸` (submenu), `Lookup Selected Text`, `Pause Lookup`
  (toggle), `Settings`, `Exit`.
- `Pause Lookup` disables the global hotkey without closing the app.
- Closing the main window hides to tray (configurable); `Exit` fully quits.

---

## 18. Database location

- Stored under the Windows per-user app-data directory: **`%APPDATA%\CyberGlossary\`**
  (`os.environ['APPDATA']` → `...\CyberGlossary\cyberglossary.db`), created automatically on first
  run via `config/paths.py`.
- Never stored in the source repository at runtime; `.gitignore` excludes any local DB.
- Backups default to `%APPDATA%\CyberGlossary\backups\` (user-overridable).

---

## 19. Import / export

- **Export Profile → JSON**: profile + terms + metadata + categories + tags + aliases + sections
  (with order) + templates. Versioned schema (`schema_version`, `app_version`, timestamp).
- **Export Profile → Markdown**: one `.md` per term (title + sections as headings). Portable, no
  lock-in.
- **Import Profile → JSON**: validates schema/version/integrity first; supports **merge** or
  **replace**. Malformed input is rejected safely (no partial writes).
- All serialization via the stdlib `json` module (or Pydantic if added; stdlib is sufficient).

---

## 20. Backup / restore

- **Backup**: consistent snapshot via SQLite's **backup API** (`Connection.backup`), never a raw
  `.db` copy (unsafe under WAL). Timestamped filename in a user-chosen directory; never silently
  overwrites. After writing, `verify_database` runs `PRAGMA integrity_check`, checks `user_version`,
  and confirms all required tables before reporting success (`services/backup_service.py`).
- **Restore** (no data-loss guarantee): validate the candidate (`integrity_check` == ok,
  `user_version` >= 1, all required tables present) **before** touching the current DB → create a
  `pre-restore-<timestamp>.db` **safety backup** (if this fails, STOP) → `wal_checkpoint(TRUNCATE)`
  + close the current connection → atomically replace the db file (temp copy + `os.replace`, delete
  stale `-wal`/`-shm`) → reopen a fresh connection, re-migrate, `fts.ensure_index`, and return it.
- A failed restore never modifies the current database; a successful restore always leaves a safety
  backup. The app rebuilds services/window/tray/hotkey from the new connection after restore.

---

## 21. Privacy & security

- **Offline-first**: no telemetry, analytics, cloud, uploads, or auto-lookup. No network code.
- **No AI**: no LLM SDK, no API key, no DeepSeek/OpenAI credentials anywhere in the repo or binary.
- **Local only**: knowledge lives in the user's own `%APPDATA%` SQLite file.
- **No logging of secrets**: selected text, clipboard content, passwords, and keys are never
  logged or persisted.
- **Import validation**: imported JSON is validated before touching the DB; malformed DB data is
  handled gracefully (see §23).
- **No hard-coded secrets** anywhere.

---

## 22. Packaging (PyInstaller)

- Target: a standalone **`CyberGlossary.exe`**; end user does **not** install Python, PySide6, or
  SQLite.
- Build via a `packaging/CyberGlossary.spec`:
  - Entrypoint `src/cyberglossary/main.py`.
  - Collect PySide6 Qt plugins; exclude unused Qt modules (QtWebEngine, QtMultimedia, etc.) to cut
    size.
  - Include app icon and version metadata.
- Format choice:
  - **`onedir`** (recommended default): a folder with the exe + DLLs — faster startup, fewer AV
    false positives; distribute as a zip.
  - **`onefile`**: single exe — simplest UX but slower first launch (extracts to temp) and more
    prone to AV heuristics.
- The SQLite DB is created on first launch (not bundled).
- The packaged exe is smoke-tested on Windows before release.

---

## 23. GitHub Actions strategy

`windows-latest` runner workflow (`.github/workflows/build-windows.yml`):

```
push / PR ──► windows-latest ──► setup-python 3.12 ──► install deps ──► pytest ──►
             PyInstaller build ──► upload artifact (actions/upload-artifact)
```

- No DeepSeek API, no Docker.
- Optional matrix across Python 3.12.

---

## 24. Docker

**Not required** and **not used** for the GUI. The app needs direct Windows access for global
hotkey, clipboard, system tray, and popups — containerization provides no benefit for the product.
Docker may be added later only for CI convenience and must never become a requirement.

---

## 25. Testing strategy (pytest)

- **Unit tests** (no GUI, no real OS): profile create/switch, term CRUD + duplicate handling,
  aliases, section CRUD + ordering, template create/apply, search query building, lookup
  normalization, JSON import/export round-trip, malformed import rejection, backup/restore
  pre-validation logic.
- **Hotkey tests** (pure logic, mocked Win32 boundary): default hotkey, parse/format round-trips,
  modifier validation, modifier-only rejection, change flow, failed registration keeping the old
  hotkey, reset-to-default, pause/unpause, and startup-registration-failure handling.
- **Integration tests**: run against a temporary SQLite file (or `:memory:` with a shared
  connection) — verify migrations, cascades, uniqueness, FTS sync, and profile isolation.
- **Windows integration** (where practical): hotkey registration result, clipboard save/restore,
  and text-capture seams are tested behind thin interfaces; real system-wide behavior is validated
  via a manual checklist (real hotkey in Chrome/Word/VS Code/Notepad, tray, popup).

---

## 26. Error handling

Gracefully handle: empty selection, clipboard unavailable/locked, hotkey conflict, DB open/write
failure, malformed DB, invalid imported JSON, missing term, duplicate term, and startup errors.
A failed lookup must never crash the app — it degrades to "not found" or a silent no-op.

---

## 27. Performance

- Lookup is a local SQLite query (exact → alias → FTS) with no network, targeting < ~200 ms.
- Proper indexes (`profile_id`, `sort_order`, aliases, category); FTS5 for full-text.
- Load only needed data (pagination/limit for lists); do not load the whole knowledge base into
  memory.

---

## 28. Future extensibility

Clean interfaces (services/repositories) so these can be added later without rework: OCR, browser
extension, Markdown editor, backlinks, graph view, flashcards, spaced repetition, quiz mode,
sync, mobile client, optional AI integration. **None are implemented now**, and none are allowed
to complicate the current design.

---

## 29. Development phases

All phases are **complete** (Phase 14 — final testing, audit, and polish — is the last):

1. Project skeleton + config + SQLite schema/migrations.
2. Profiles.
3. Terms + dynamic sections.
4. Templates.
5. Main PySide6 UI.
6. Search + FTS5.
7. System tray.
8. Global hotkey + clipboard capture.
9. Lookup popup.
10. Import/export (JSON + Markdown).
11. Backup/restore.
12. PyInstaller packaging (onedir).
13. GitHub Actions (Windows CI).
14. Testing + polish.

Each phase: explain plan → list files → implement → run tests → run/build → fix → update docs →
summarize.

---

## 30. Major technical risks

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| 1 | **Selected-text capture reliability** varies by app (browsers, PDF, VS Code, UWP). | High | Clipboard-first per spec; sequence-number tracking; graceful restore; optional UIA fallback later. |
| 2 | **Hotkey conflict** — `Ctrl+Shift+D` = VS Code "Run & Debug". | Medium | Configurable hotkey; detect `RegisterHotKey` failure and prompt. |
| 3 | **Clipboard restore races** (async/cloud clipboard, other clipboard tools). | Medium | Save/restore with sequence check; never persist; allow disabling capture. |
| 4 | **PyInstaller + PySide6 packaging** (missing Qt plugins/DLLs, size, AV false positives). | Medium | Use `.spec`, exclude unused Qt modules, prefer `onedir`, smoke-test the exe. |
| 5 | **FTS5 sync drift** if writes don't update the index. | Medium | Centralize writes in repositories; recompute FTS in the same transaction; integration tests. |
| 6 | **Hotkey delivery into the Qt loop** (WM_HOTKEY vs Qt native event filter). | Medium | Isolate in `windows/hotkey.py`; verify early (Phase 8) with a real build. |
| 7 | **System-tray behavior differences** across Windows 10/11. | Low-Medium | `QSystemTrayIcon` + fallback to hide-to-taskbar. |
| 8 | **Backup consistency under WAL** (naive file copy). | Low-Medium | `VACUUM INTO` / backup API; integrity check before restore. |
| 9 | **Scope creep toward AI/network features** violating principles. | Low | Explicit review gate; no network/AI dependencies allowed. |
| 10 | **Search UX with FTS reserved chars** typed by the user. | Low | `SearchQueryBuilder` sanitizes; unit-tested. |

---

## 31. Decisions (resolved)

1. **DB access**: stdlib `sqlite3` + thin repositories (SQLAlchemy not used).
2. **Packaging format**: `onedir` (via `packaging/CyberGlossary.spec`); `onefile` documented as a future
   option.
3. **Content format in sections**: plain text.
4. **Hotkey lookup scope**: active profile only.
5. **Single instance**: deferred (not implemented in v1).

*This document reflects the final implemented architecture.*
