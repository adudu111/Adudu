# CyberGlossary — Specification

> Status: **Draft for approval** (Phase 1 not started)
> Stack: **Python 3.12+ / PySide6 / SQLite**
> Companion to `ARCHITECTURE.md`.

## 1. Purpose

CyberGlossary is a **personal, offline, local knowledge-management application** for studying
subjects by hand-building a glossary of terms. The user owns and controls all content. It is
explicitly **not** an AI dictionary: no LLM API, no API key, no network lookup, fully offline.

---

## 2. Definitions

- **Profile** — a top-level scope (e.g. "Cyber Security", "Accounting", "Networking", "English").
- **Term** — a named entry within a profile (e.g. "LDAP", "Kerberos", "ROA").
- **Section** — a user-defined named block within a term (e.g. "Ports", "AS-REQ", "My Notes").
- **Category** — an optional grouping of terms within a profile.
- **Tag** — an optional label attached to a term.
- **Alias** — a user-defined alternate name or misspelling for a term.
- **Template** — a per-profile, named, ordered set of section titles applied to new terms.
- **Active profile** — the profile targeted by the global lookup.
- **Lookup popup** — a lightweight desktop viewer shown after hotkey + selected-text lookup.

---

## 3. Goals and non-goals

### Goals
- Own all knowledge locally and offline.
- Provide a fast, searchable, structured glossary across multiple subjects.
- Make sections fully dynamic and per-term (no hard-coded fields).
- Provide a global lookup from any application via a configurable hotkey.
- Preserve data via import/export and backup/restore.

### Non-goals (explicit)
- No AI/LLM integration of any kind in the shipped app.
- No cloud sync, telemetry, analytics, accounts, or uploads.
- No hard-coded mandatory fields.
- No network dependency to run.
- Not an Electron/Tauri/Web app; native PySide6 desktop.

---

## 4. Functional requirements

### 4.1 Profiles
- FR-01: Create a profile with a unique name.
- FR-02: Rename, describe, set an optional accent color, reorder, and delete a profile.
- FR-03: Deleting a profile removes its terms, categories, tags, templates, sections, and aliases.
- FR-04: Maintain one **active profile** persisted across sessions; if the active profile is
  deleted while other profiles remain, automatically select another valid profile as active
  (clear `active_profile_id` only when no profiles remain).
- FR-05: Switch the active profile easily from the sidebar and tray.

### 4.2 Terms
- FR-06: Create a term (`term` short name + optional `full_name`, category, tags).
- FR-07: Term short names are unique within a profile (case-insensitive).
- FR-08: Edit, delete, duplicate, and reorder terms; assign/clear category and tags.
- FR-09: A term requires **no** predefined fields; it may exist with zero sections.
- FR-10: A term may optionally be created from a template.

### 4.3 Dynamic sections
- FR-11: Add a section to a term with a user-defined title and content.
- FR-12: Edit a section's title and content.
- FR-13: Delete a section.
- FR-14: Rename a section.
- FR-15: Reorder sections (persisted).
- FR-16: Collapse/expand a section (UI).
- FR-17: The application must not reference hard-coded section names anywhere.

### 4.4 Categories
- FR-18: Create, rename, delete, and reorder categories within a profile.
- FR-19: List terms within a category and show the term count per category.
- FR-20: Assign a category to a term, change it, or clear it (terms have zero or one category).

### 4.5 Aliases
- FR-21: Add, edit, and delete aliases for a term (user-controlled only).
- FR-22: Lookup resolves aliases (e.g. `LDPA` → LDAP) after exact title, before best-match.

### 4.6 Templates — REMOVED from v1
- ~~FR-23–FR-25~~ Templates are no longer part of the active v1 product. Template tables remain in
  the schema for backward compatibility only.

### 4.7 Search (in-app)
- FR-26: Search across term, full name, aliases, category, and section title/content.
- FR-27: Support token AND, quoted phrases, prefix, boolean OR, and negation.
- FR-28: Highlight matching terms/sections in results.
- FR-29: The search field is located in the main window header (top-right).

### 4.8 Global hotkey (configurable)
- FR-30: Default `Ctrl+Shift+D`; fully **configurable** (modifiers + non-modifier key).
- FR-31: Works system-wide while the app runs (foreground or background, including minimized to tray).
- FR-32: Store the hotkey **structured** (`hotkey_modifiers` bitmask + `hotkey_key` virtual-key code),
  not merely a display string.
- FR-33: Provide a dedicated "Global Lookup Hotkey" section under **Settings → General / Lookup**
  showing the current shortcut and a `[ Change ]` button.
- FR-34: `Change` opens a **hotkey capture dialog** that detects the actual pressed combination
  (native key events), never requiring the user to type a string.
- FR-35: Support combinations such as `Ctrl+Shift+D`, `Ctrl+Alt+L`, `Alt+Shift+G`, `Ctrl+F8`, `F9`.
- FR-36: Reject modifier-only combinations (`Ctrl`, `Shift`, `Alt`); require ≥1 non-modifier key.
- FR-37: On change: validate → unregister old → try registering new. On success, persist and
  activate immediately; on failure, keep the old hotkey active, do not save, and explain that the
  shortcut may be in use by another application.
- FR-38: Provide `[ Reset to Default ]` (`Ctrl+Shift+D`); if unavailable, keep the previous working
  hotkey.
- FR-39: Report and allow remapping on registration failure at startup (do not crash).

### 4.9 Selected-text lookup
- FR-40: On hotkey press, capture the selected text from the foreground app.
- FR-41: Normalize the text (trim, collapse line breaks, strip quotes/punctuation).
- FR-42: Search the **active profile** only.
- FR-43: Resolve exact term → alias → best FTS match → not found.

### 4.10 Lookup popup
- FR-44: Lightweight, frameless, always-on-top, non-focus-stealing popup near the cursor.
- FR-45: Read-only render of the term's title, full name, and all sections in order.
- FR-46: Buttons: **Open Full Page**, **Edit**, **Close**; dismiss on `Esc`/focus-out.

### 4.11 Unknown term / add term
- FR-47: Show `Term not found in current profile.` with **[ + Add Term ]** and **[ Close ]**.
- FR-48: **Add Term** opens a creation dialog pre-filled with the captured text + fields for
  full name, category, tags.
- FR-49: After saving, open the new term in the editor for the user to add sections manually.

### 4.12 System tray
- FR-50: Run in the system tray with menu: Open, Active Profile, Lookup Selected Text,
  Pause Lookup, Settings, Exit.
- FR-51: `Pause Lookup` temporarily unregisters/disables the global hotkey without closing the app.
- FR-52: The configured hotkey is **not lost** while paused; resuming re-registers it.

### 4.13 Hotkey lifecycle
- FR-53: Register on startup; unregister on exit.
- FR-54: Unregister when changing the shortcut; register the replacement.
- FR-55: Re-register when lookup is resumed after pause.
- FR-56: Remain active while minimized to tray.
- FR-57: On startup registration failure, show a clear warning and allow reconfiguration.

### 4.14 Import / export
- FR-58: Export Profile → JSON (profile, terms, metadata, categories, tags, aliases, sections
  with order, templates).
- FR-59: Export Profile → Markdown (one `.md` per term).
- FR-60: Import Profile → JSON (merge or replace), with validation before apply.

### 4.15 Backup / restore
- FR-61: Backup the database to a user-chosen location (timestamped; no silent overwrite).
- FR-62: Restore a database after integrity validation; back up current DB first.
- FR-63: Handle invalid backup files safely.
- FR-67: Backup uses SQLite's backup API (WAL-safe) and is verified (`integrity_check`,
  schema version, required tables) before being reported as successful.
- FR-68: Restore always creates a `pre-restore` safety backup before replacing the database; if the
  safety backup fails, the restore aborts and the current database is left untouched.
- FR-69: Restore validates the candidate (integrity, schema version, required tables) before any
  change, closes/reopens the connection, and re-verifies FTS afterward.

### 4.16 Application / data
- FR-64: ~~Single-instance behavior (second launch activates the existing instance).~~ **Deferred**
  (not implemented in v1; a second launch starts an independent instance).
- FR-65: Database stored under `%APPDATA%\CyberGlossary\`, auto-created on first launch.
- FR-66: Runs fully offline.

---

## 5. Non-functional requirements

- **NFR-01 Offline-first**: no network I/O; works with no connectivity.
- **NFR-02 No AI**: no LLM/API integration, no key, no DeepSeek/OpenAI credentials.
- **NFR-03 Privacy**: all data local; no telemetry; no logging of clipboard/selected text/secrets.
- **NFR-04 Performance**: lookup < ~200 ms; in-app search near-instant via FTS5.
- **NFR-05 Data integrity**: transactional writes; FTS index never drifts.
- **NFR-06 Platform**: Windows 10 / Windows 11.
- **NFR-07 Usability**: clean, modern, fast UI; dark + light mode; resizable; keyboard-friendly.
- **NFR-08 Maintainability**: modular Python packages (ui/database/services/windows/…), tests.

---

## 6. Data model (summary)

See `ARCHITECTURE.md §5` for full SQL.

- `profiles` — id, name (unique), description, color, sort_order, timestamps.
- `categories` — id, profile_id, name, sort_order; UNIQUE(profile_id, name).
- `tags` — id, profile_id, name; UNIQUE(profile_id, name).
- `terms` — id, profile_id, term, full_name, category_id (nullable), sort_order, timestamps;
  UNIQUE(profile_id, term).
- `aliases` — id, term_id, alias, created_at; UNIQUE(term_id, alias).
- `term_tags` — (term_id, tag_id) composite PK.
- `sections` — id, term_id, title, content, sort_order, timestamps.
- `templates` — id, profile_id, name, description, sort_order, timestamps; UNIQUE(profile_id, name).
- `template_sections` — id, template_id, title, placeholder, sort_order.
- `settings` — key/value (active_profile_id, hotkey, theme, backup path, …).
- `terms_fts` — FTS5 virtual table (rowid = term id).

Rules: all references cascade on delete; timestamps ISO-8601 UTC; section titles and content are
entirely user-defined.

---

## 7. UI specification (high level)

### Main window (three-pane, "web-like")
- **Sidebar**: profile selector; navigation (Dashboard, Terms, Categories, Templates, Tags,
  Settings).
- **Middle**: search box + term list; "+ New" and "Create from Template".
- **Content**: editable term/full-name/category/tags; ordered, collapsible sections with
  add/rename/edit/reorder/delete; `[ + Add Section ]`.

### Lookup popup
- Frameless, always-on-top, dismissable.
- Found → title + full name + all sections (read-only) + Open Full Page / Edit / Close.
- Not found → message + Add Term / Close.

---

## 8. Acceptance criteria (summary)

1. Create a profile; add terms with **no** predefined fields.
2. Two terms can have completely different section sets, freely reordered/edited/deleted.
3. Create and apply a template to produce a term with the template's sections.
4. `Ctrl+Shift+D` in an external app (browser/PDF/Word/VS Code) opens the popup with the correct
   term from the active profile, or "Term not found".
5. **Add Term** opens a pre-filled dialog, then the term editor.
6. Runs offline; no network or AI code path.
7. Search returns correct, highlighted results across title/full name/aliases/tags/category/
   section content.
8. JSON export→import round-trips preserve all data; Markdown export works; backup→restore works
   and validates integrity.
9. Hotkey: default `Ctrl+Shift+D` works; change to another combination saves and works immediately;
   the old hotkey no longer triggers; a conflicting shortcut is reported and the previous working
   shortcut stays active; Pause/Resume Lookup disables/restores the configured shortcut; restart
   keeps the configured shortcut.

### 8.1 Manual acceptance test (hotkey)

1. Start CyberGlossary — default `Ctrl+Shift+D` works.
2. Open Settings → General / Lookup.
3. Change hotkey to another combination via the capture dialog.
4. Save — new hotkey works immediately; old hotkey no longer triggers lookup.
5. Choose a conflicting shortcut — application reports the conflict; previous shortcut stays active.
6. Pause Lookup disables the shortcut; Resume Lookup restores the configured shortcut.
7. Restart the application — the configured shortcut remains active.

### 8.2 Hotkey tests (automated)

- default hotkey; parse/format round-trip; modifier validation; modifier-only rejection; change
  flow; failed registration keeps old hotkey; reset-to-default; pause/resume lookup; startup
  registration failure.

---

## 9. Out of scope (v1)

- OCR, browser extension, backlinks, graph view, flashcards, spaced repetition, quiz, sync, mobile,
  optional AI (future only).
- UI Automation text capture (deferred; clipboard-first ships).
- Docker (not used).

---

## 10. Phase plan

All phases are **complete**:

- **Phase 0** — Architecture + spec + README (this document set).
- **Phase 1** — Skeleton + config + SQLite.
- **Phase 2** — Profiles. **Phase 3** — Terms + dynamic sections. **Phase 4** — Templates.
- **Phase 5** — Main PySide6 UI. **Phase 6** — Search + FTS5. **Phase 7** — System tray.
- **Phase 8** — Global hotkey + clipboard capture. **Phase 9** — Lookup popup.
- **Phase 10** — Import/export. **Phase 11** — Backup/restore.
- **Phase 12** — PyInstaller packaging. **Phase 13** — GitHub Actions. **Phase 14** — Testing + polish.

Known deferred items (not in v1): single-instance, UI Automation text capture, DB encryption,
system-tray "start with Windows", Markdown-editor UI, and all §9 future work.
