# adudu — UI Design System & Desktop Application Specification

**Platform:** PySide6 desktop application (Python, Qt Widgets + QSS), Windows-first, cross-platform ready
**Product:** Cybersecurity glossary & knowledge management tool
**Audience:** security analysts, researchers, engineers
**Version:** 2.0 — implementation-ready revision aligned with the current adudu application

This document is the **single source of truth for the presentation layer** of `adudu`. It defines the visual language, measurable design tokens, and the exact structure and behavior of every UI component. A coding agent (OpenCode + DeepSeek V4) implements it as-is against the existing application.

**Scope boundary — presentation layer only.** The UI sits on top of the existing services and never bypasses them. The architecture below is fixed and must not be changed:

```
UI  →  Services  →  Repositories  →  SQLite
```

No new backend services, no new database tables or columns, no new application modules beyond UI files, no fabricated sample data.

Implementation vehicle: **Qt Widgets + Qt Style Sheets (QSS)**. All values are pixel-exact at 96 DPI and scale with Qt's DPI handling.

---

## 1. Design Principles

1. **Calm, dense, pro-grade.** A cybersecurity tool should feel precise and trustworthy — dark, quiet surfaces, high information density, no decorative noise.
2. **Glossary first.** The term is the hero. Term List → Detail is the primary flow; every other surface serves quick lookup and knowledge maintenance.
3. **One accent, disciplined.** Blue is the single functional accent (actions, selection, focus, links). Purple is a secondary brand accent used only for the brand mark, active-nav glow, and the primary gradient. Each screen uses the blue accent at most twice.
4. **State feedback everywhere.** Every interactive element has distinct hover / pressed / focus / disabled pairs whose contrast never degrades.
5. **Keyboard-complete.** Every flow reachable by mouse is reachable by keyboard (`Ctrl+K` search, `↑/↓` in lists, `Esc` closes).
6. **Data-faithful rendering.** The UI renders exactly what the database contains. Section titles are user-defined; **never hard-code section names**. Never invent fields, rows, or sample content.

---

## 2. Existing adudu Capabilities This Spec Reflects

This specification is built strictly on the current adudu data model and feature set:

- **Profiles** (multiple glossaries)
- **Terms** with: name, full name, category, aliases, and **fully dynamic user-defined sections** (title + content)
- **Categories**
- **Search** via the existing SearchService / FTS5
- **Global hotkey** and **clipboard text capture** → open the lookup popup
- **Lookup popup**
- **Import / Export**
- **Backup / Restore**
- **Dark / Light theme switching**

Features **not** in the list above — favorites, recently viewed, references/sources, history/changelog, related terms, tags, templates, source URLs, category descriptions/colors, network features, AI — are out of scope and must **not** be required, rendered, or implemented.

---

## 3. Application Shell & Layout

### 3.1 Window

| Property | Value |
|---|---|
| Default size | 1440 × 900 |
| Minimum size | 1024 × 640 |
| Pane gap | 1px (shared border, no gap) |
| Content margin | 16px inside panes |

### 3.2 Three-pane layout

```
┌──────────────────────────────────────────────────────────────┐
│  Menu bar · 28px  [ File ▾ ]                                │
│  Header · 52px  [ breadcrumb ]          [  Global search  ]  │
├──────────┬──────────────────┬────────────────────────────────┤
│ Sidebar  │  Term List       │  Term Details (flex, ≥480)     │
│ ≈ 250px  │  ≈ 320px         │  (remaining width)             │
│          │                  │                                │
└──────────┴──────────────────┴────────────────────────────────┘
```

- **Sidebar** ≈ 250px (collapsible to a 64px rail), left pane.
- **Term List** ≈ 320px (resizable 260–420), **center pane**.
- **Term Details / Editor** = remaining width, **right pane**.
- **Menu bar** — a native `QMenuBar` row (28px) sits above the header and carries the **File** menu (File & Data Management, §13.1).
- **Global search is NOT part of these three panes.** It lives in the top header, pinned top-right (§13). It must never be placed in the sidebar, the term list, the center, or the left side.

### 3.3 Layout behavior

- Sidebar and Term List widths persist to `QSettings` (defaults 250 / 320).
- Sidebar collapses to the 64px rail (`Ctrl+B` or rail toggle). Term List can be hidden with `F`; the Detail pane then takes the full remaining width and a breadcrumb back link appears in the detail header.
- On windows narrower than 1100px the sidebar auto-collapses to the rail but remains toggleable.
- Below 900px the three panes degrade to a stacked layout with a segmented switcher (§24).

---

## 4. Color Tokens

Dark theme is the primary visual reference. Values are given as HEX with the RGB triplet used by `QColor(r, g, b)`. Neutrals are navy-tinted blacks, never pure gray. Derived tokens are generated from base tokens; do not hand-pick near-duplicates.

### 4.1 Base / neutrals (dark)

| Token | HEX | RGB | Usage |
|---|---|---|---|
| `bg-base` | `#0B0F16` | 11,15,22 | Window / term list / detail backgrounds |
| `bg-deep` | `#070A10` | 7,10,16 | Empty-state wells, code blocks, footer |
| `surface` | `#0F141D` | 15,20,29 | Sidebar, header, pane chrome |
| `surface-raised` | `#141B26` | 20,27,38 | Cards, list items, inputs, dropdowns |
| `surface-hover` | `#1A2230` | 26,34,48 | Hover fill |
| `surface-active` | `#1E2836` | 30,40,54 | Pressed fill, active handles |
| `overlay-scrim` | `rgba(4, 7, 12, 0.55)` | — | Dialog / popup backdrop |
| `overlay-popup` | `rgba(7, 10, 16, 0.85)` | — | Frosted popup fill (lookup, menus) |

### 4.2 Borders

| Token | HEX | Usage |
|---|---|---|
| `border-subtle` | `#1A222F` | Card, list, input resting borders |
| `border` | `#232E40` | Stronger dividers, popup edges |
| `border-strong` | `#2E3C52` | Hover borders, active segments |
| `border-accent` | `rgba(74, 127, 255, 0.45)` | Focus ring, active nav outline |

All borders are 1px (`border: 1px solid …`), except the focus ring which is 2px.

### 4.3 Text

| Token | HEX | Contrast on `surface-raised` | Usage |
|---|---|---|---|
| `text-primary` | `#E8EEF7` | ≥ 14:1 | Body, titles, term names |
| `text-secondary` | `#9AA7B8` | ≥ 7.4:1 | Descriptions, secondary labels |
| `text-muted` | `#7C8AA0` | ≥ 5.1:1 | Captions, metadata, placeholders |
| `text-disabled` | `#4A576D` | 2.8:1 (allowed) | Disabled controls only |
| `text-inverse` | `#FFFFFF` | — | Text on solid accent fills |
| `text-on-deep` | `#0B0F16` | — | Brand mark letter, active gradient chips |

### 4.4 Accents

| Token | HEX | Usage |
|---|---|---|
| `accent-blue` | `#4A7FFF` | Links, selection, focus ring, icons, active chip text |
| `accent-blue-strong` | `#3B6EE8` | Solid primary button fill (white 13px text passes 4.6:1) |
| `accent-blue-hover` | `#3362D8` | Primary button hover (contrast rises to 5.4:1) |
| `accent-blue-active` | `#2B55C2` | Primary button pressed |
| `accent-blue-soft` | `rgba(74, 127, 255, 0.14)` | Selected item / active nav background |
| `accent-blue-text` | `#8FB0FF` | Accent text on dark surfaces |
| `accent-purple` | `#8B7CF6` | Secondary accent: brand tile, active-nav glow, gradient |
| `accent-purple-soft` | `rgba(139, 124, 246, 0.14)` | Active-nav fill, category chip base |
| `gradient-brand` | `linear 135° #4A7FFF → #8B7CF6` | Brand tile, empty-state mark only |

Derivation note (for maintenance): blues and purples come from a fixed hue family with the OKLCh `L` channel moved ±0.06–0.12 for hover/pressed. **Never lighten a button's fill on hover** — darken it so white text contrast increases.

### 4.5 Status

| Token | HEX | Usage |
|---|---|---|
| `success` | `#2FBF71` | "Saved ✓" indicator, valid input |
| `warning` | `#F5A524` | Warning icon in confirm dialogs |
| `danger` | `#F05252` | Destructive buttons, errors (white text 4.7:1) |
| `danger-hover` | `#D94444` | Destructive button hover |
| `danger-soft` | `rgba(240, 82, 82, 0.12)` | Danger ghost hover, error rows |
| `info` | `#38BDF8` | Informational accents |

### 4.6 Category chip hue — derived, not stored

Categories have **no color field** in the database. The chip/tile hue is derived deterministically from the category name at render time (presentation-only; no DB change):

```
hue_index = zlib.crc32(name.lower().encode("utf-8")) % len(HUES)
```

Python's built-in `hash()` is not stable across runs — use `zlib.crc32` (or any fixed algorithm) so a category always gets the same hue. Chip fill = hue @ 16% alpha over `surface-raised`; chip text = light tint. Hover raises the fill to 26% alpha.

| Hue token | Chip fill (16% alpha) | Chip text |
|---|---|---|
| `cat-blue` | `rgba(74, 127, 255, 0.16)` | `#7FA8FF` |
| `cat-purple` | `rgba(139, 124, 246, 0.16)` | `#A99EFF` |
| `cat-cyan` | `rgba(56, 189, 248, 0.16)` | `#67D2FB` |
| `cat-green` | `rgba(47, 191, 113, 0.16)` | `#5EDC9A` |
| `cat-amber` | `rgba(245, 165, 36, 0.16)` | `#FFC45C` |
| `cat-pink` | `rgba(236, 106, 155, 0.16)` | `#F28FB4` |

### 4.7 Light theme mapping

The Dark/Light switch is preserved; the two themes share the **same component system** (same spacing, radii, typography, component structure). Only the neutral / text / border scale swaps. Accent, status, and chip hues are unchanged (deepen the blue/purple one OKLCh `L` step for light surfaces so contrast stays ≥ 4.5:1).

| Token | Light value |
|---|---|
| `bg-base` | `#F6F8FB` |
| `bg-deep` | `#EDF1F7` |
| `surface` | `#FFFFFF` |
| `surface-raised` | `#FFFFFF` |
| `surface-hover` | `#EEF2F8` |
| `surface-active` | `#E4EAF3` |
| `text-primary` | `#161C26` |
| `text-secondary` | `#4A5568` |
| `text-muted` | `#6B7688` |
| `text-disabled` | `#A8B0BE` |
| `border-subtle` | `#E3E8EF` |
| `border` | `#D3DBE6` |
| `border-strong` | `#B9C4D4` |
| `accent-blue-strong` | `#2E5BD0` |
| `accent-purple` | `#7B68E8` |

---

## 5. Typography

### 5.1 Families

| Role | Family | Notes |
|---|---|---|
| UI / body | `Segoe UI` (fallback `Cantarell` / `Noto Sans` on Linux, `.AppleSystemUIFont` on macOS) | Do not bundle; use the native stack |
| Mono | `Cascadia Mono` → `JetBrains Mono` (bundled optional) → `Consolas` | Metadata, keybind hints, code, numbers |

One family for UI (a data-dense tool: appropriate); mono reserved for technical metadata. Weights used: 400 and 600 only.

### 5.2 Type scale

Qt's `QFont` uses points; QSS accepts pixels. **Specify sizes in pixels in QSS** and set the app base font to `10pt` (≈13.3px) for non-QSS widgets.

| Token | Size / weight / tracking | Usage |
|---|---|---|
| `font-display` | 20px / 600 / 0 | Term name, page titles |
| `font-title` | 16px / 600 / 0 | Pane header titles |
| `font-h3` | 15px / 600 / 0 | Section card titles, dialog titles |
| `font-body` | 13px / 400 / 0 | Default UI text |
| `font-body-medium` | 13px / 600 / 0 | Term names in lists, emphasis |
| `font-sm` | 12px / 400 / 0 | Full-name lines, descriptions, secondary rows |
| `font-xs` | 11px / 500 / +0.08em | Eyebrows, section labels, keybind hints (uppercase) |
| `font-mono` | 12.5px / 400 / 0 | Metadata, code |
| `font-mono-xs` | 11px / 400 / 0 | Counts, kbd chips, version |

Line heights: body 1.45, titles 1.3, mono 1.4. Define line-height only on custom widgets that lay out text manually (`QTextDocument`), never via QSS.

---

## 6. Spacing

Base unit **4px**. No other step exists.

| Token | px | Typical use |
|---|---|---|
| `space-1` | 4 | Icon-to-text gaps inside tiny elements, chip padding |
| `space-2` | 8 | Button icon gap, small padding, list padding |
| `space-3` | 12 | Card padding (compact), input padding-x |
| `space-4` | 16 | Card padding, list item padding, header padding-x |
| `space-5` | 20 | Dialog body padding |
| `space-6` | 24 | Section rhythm inside detail, popup padding |
| `space-7` | 32 | Between major page blocks |
| `space-8` | 40 | Detail header to first card |
| `space-9` | 48 | Page bottom breathing room |

Fixed rules:
- Card padding: **16px** (body), **20px** for large cards.
- Dialog body padding: **20px**; dialog footer padding: **16px 20px**.
- Horizontal padding inside list/accordion rows: **12px**.
- Header horizontal padding: **16px**.
- Vertical rhythm between adjacent cards: **12px**; between blocks: **24px**.

---

## 7. Border Radius

| Token | px | Used on |
|---|---|---|
| `radius-xs` | 3 | Tiny tags, kbd chips |
| `radius-sm` | 4 | Compact buttons (28px), small inputs |
| `radius-md` | 6 | Default buttons (32px), inputs, selects, nav items, tiles |
| `radius-lg` | 8 | Cards, list items, popups, dialogs, term detail sections |
| `radius-xl` | 10 | Large category cards |
| `radius-full` | 999 | Global search pill, category pills, badges |

Inner corners: when an element sits flush inside a rounded container (e.g. an accordion body inside a card), match inner radius = outer radius − 1.

---

## 8. Shadows

QSS cannot paint shadows. Use `QGraphicsDropShadowEffect` (one per top-level surface; avoid stacking many).

| Token | Blur / offset / color | Used on |
|---|---|---|
| `shadow-sm` | 6px blur, y+1, `rgba(0,0,0,0.25)` | Cards on hover (interactive), buttons on hover |
| `shadow-md` | 14px blur, y+2, `rgba(0,0,0,0.35)` | Dropdowns, popovers, tooltips |
| `shadow-lg` | 28px blur, y+6, `rgba(0,0,0,0.50)` | Lookup popup, dialogs |
| `glow-accent` | 0 0 12px, `rgba(139, 124, 246, 0.25)` | Active nav indicator, brand tile |

Focus ring: 2px `border-accent` outline offset 2px from the widget edge (never a colored inset border that blends into the widget fill). Implement via a painted focus frame or `setProperty("focused", true)` in QSS.

---

## 9. Icons

- **Source:** bundled SVG set (loaded via `QtSvg` / `QIcon`). Geometry in 16px and 20px; stroke-based, 1.5px stroke, round caps and joins (Lucide-style, not filled glyphs). No emoji.
- **Sizes:** 16px default; 20px for detail-section icons; 24px max for the brand tile.
- **Tinting:** icons inherit the surrounding text color. Generate three variants at load time by substituting the SVG stroke color — `muted` (`#7C8AA0`), `primary` (`#E8EEF7`), `accent` (`#4A7FFF`); white (`#FFFFFF`) on solid primary buttons.
- **State rules:** resting icon = `muted`; hover/focus = `primary`; active/selected = `accent`.
- **Required icon inventory (maps to existing features only):** search, x (close/clear), chevron-down, chevron-right, book (term), folder (category), settings, plus, pencil (edit), trash (delete), more-horizontal (overflow), check, filter, sort, keyboard, sidebar-left (collapse rail), panel (list toggle), users (profile selector), chevrons-up-down (reorder), copy, command (global hotkey), clipboard (clipboard capture), upload, download (import/export), file-text (export markdown), archive (backup/restore), sun, moon (theme toggle).

Do not add icons for favorites, history, sources, or other non-existent features.

---

## 10. Component Heights & Sizing

Standard control heights (includes the 1px border):

| Token | px | Used on |
|---|---|---|
| `h-xs` | 28 | Compact buttons, small inputs, icon buttons (28×28), kbd chips |
| `h-sm` | 32 | Default buttons, text inputs, selects, search field, nav items |
| `h-md` | 36 | Large buttons, "New term" action, popup accordion headers |
| `h-lg` | 44 | Term list rows, section accordion headers, list items |
| `h-xl` | 52 | Header bar, dialog title bar, app brand row |
| `h-menu` | 28 | Menu bar row (`QMenuBar`), top-level menu items |

Touch/click targets: every interactive control is ≥ 28px tall and ≥ 28px wide; primary/medium actions are ≥ 32px. Icon-only buttons are square (28×28 or 32×32).

---

## 11. Buttons

### 11.1 Variants

| Variant | Resting | Hover | Pressed | Disabled |
|---|---|---|---|---|
| `btn-primary` | fill `accent-blue-strong`, text `#FFF`, border 1px `transparent` | fill `accent-blue-hover`, `shadow-sm` | fill `accent-blue-active` | fill `#232E40`, text `text-disabled` |
| `btn-secondary` | fill `surface-raised`, text `text-primary`, border `border` | fill `surface-hover`, border `border-strong` | fill `surface-active` | text `text-disabled`, border `border-subtle` |
| `btn-ghost` | transparent, text `text-secondary`, no border | fill `surface-hover`, text `text-primary` | fill `surface-active` | text `text-disabled` |
| `btn-danger` | fill `danger`, text `#FFF` | fill `danger-hover`, `shadow-sm` | fill `#B83A3A` | fill `#232E40`, text `text-disabled` |
| `btn-link` | transparent, text `accent-blue-text` | text `#BBD1FF` + underline | text `#7FA8FF` | text `text-disabled` |

Contrast invariant: hovering never reduces the contrast between label and fill. Primary/danger labels are always white on a fill that passes ≥ 4.5:1.

### 11.2 Sizes & metrics

| Size | Height | Horizontal padding | Radius | Icon | Font |
|---|---|---|---|---|---|
| Compact | 28 | 8–12 | `radius-sm` (4) | 14 | 12/500 |
| Default | 32 | 12–16 | `radius-md` (6) | 16 | 13/600 |
| Large | 36 | 16–20 | `radius-md` (6) | 16 | 13/600 |

Icon + text gap: **8px**. Icon-only buttons: square 28 or 32, icon centered. All buttons gain a visible 2px accent focus ring on keyboard focus (see §8).

### 11.3 Rules

- **One primary per function per viewport.** App-wide primary: "New term" in the term list bottom bar. Contextual primaries: "Save" in the editor, "Create" in dialogs, "Open Full Page" in the lookup popup footer. Never two solid blue buttons for the same action in one viewport.
- Destructive confirmations use `btn-danger` in the dialog footer; never a destructive primary in a pane header.
- Loading state (where the app already uses async work): swap the leading icon for a 14px spinner, keep the label, disable the button.

---

## 12. Inputs & Fields

### 12.1 Text input (`QLineEdit`)

- Height 32, `radius-md` (6), fill `surface-raised`, border `border-subtle`.
- Inner padding: 8px x; placeholder `text-muted`.
- Focus: border `border-accent` + 2px outer accent ring; text `text-primary`.
- Hover (unfocused): border `border-strong`.
- Disabled: fill `bg-base`, text `text-disabled`, no ring.
- With leading icon: 16px icon `muted` at left, 8px from edge. With trailing clear (×) button: 24×24 hit area, appears when text is non-empty, `muted` → `primary` on hover.

### 12.2 Multiline (`QPlainTextEdit` / `QTextEdit`)

- Same fill/border/radius rules as inputs; padding 10px; word wrap on; soft scrollbar (§27).
- Minimum heights: 88px for a section content editor; the editor grows with content up to the section-card max height.

### 12.3 Select / dropdown (`QComboBox`)

- Height 32, same surface/border rules. Popup list: `radius-lg` (8), `shadow-md`, item height 32, hover row `surface-hover`, selected row `accent-blue-soft`.
- Style the dropdown arrow (16px chevron, `muted`).

### 12.4 Search field (header global search + list filter share the same base)

- Height 32, `radius-full` (pill), fill `surface-raised`, border `border-subtle`; focus border `border-accent` + ring.
- Left: 16px search icon `muted` (8px inset). Right inset: clear (×) button + a `Ctrl K` kbd chip (11px mono, `radius-xs`, fill `bg-deep`, text `muted`) shown only when empty.

### 12.5 Chip input (aliases)

- A `QLineEdit` plus a flow/wrap row of tag chips. Type text + `Enter` commits a chip; `Backspace` on an empty field removes the last chip; each chip has an 18px × button.
- Existing aliases load as chips on open. Chip style: 22px, `radius-xs`, fill `bg-deep`, border `border-subtle`, text `text-secondary`, 11px.

---

## 13. Top Header

Height **52px**, fill `surface`, bottom border 1px `border-subtle`, horizontal padding 16px. Layout: left cluster → stretch → right cluster. **Global search is pinned top-right; it never moves.**

**Left cluster:**
- Back chevron button (28×28, `btn-ghost`) — visible only on sub-pages (e.g. categories view when opened from a breadcrumb).
- Breadcrumb: `text-secondary` 13px, segments joined by a 16px chevron-right `muted`; active segment `text-primary`. Example: `Glossary / Category`.

**Right cluster (fixed order):**
1. **Global search** — 320px pill (§12.4), **right-aligned, 8px from the header's right edge**. Height 32 (32–40 acceptable). Placeholder: "Search terms…". Typing opens the lookup popup (§20). **This position is a hard requirement — the field must never move to the sidebar, the term list, the center, or the left.**
2. Pane toggle cluster — only in frameless mode, on the far right: `sidebar-left` rail toggle, `panel` list toggle (28×28 ghost icon buttons).

Focus behavior: `Ctrl+K` anywhere focuses the global search; typing opens the lookup popup; `Esc` returns focus to the prior widget.

### 13.1 File & Data Management menu (menu bar)

Import / Export and Backup / Restore are **existing adudu capabilities** and are surfaced through the existing **File** menu. Their handlers and service logic are preserved unchanged — only the menu's visual presentation is restyled. **No large Import / Export buttons appear in the main header**; the File menu is the single surface for data management.

**Menu bar (`QMenuBar`, 28px):** sits above the header (§3.2), fill `bg-deep`, bottom border 1px `border-subtle`, height `h-menu` 28, horizontal padding 4. Top-level item: 28px, padding 0 10, `radius-md`, icon none, label 13/500 `text-secondary`; hover fill `surface-hover`, text `text-primary`; open (menu shown) fill `accent-blue-soft`, text `text-primary`. No icons on top-level items.

**File menu (`QMenu`):** popup 240px wide, padding 6, `radius-lg` (8), fill `surface-raised`, 1px `border`, `shadow-lg`, max-height 420 with scroll. Menu items: 28px, padding 0 12, `radius-md`, icon 16 `muted` + label 13 `text-secondary` (8px gap); hover fill `surface-hover`, icon + label `text-primary`; shortcut hints right-aligned `font-mono-xs` `text-muted`. Separators: 1px `border-subtle`, margin 4 8.

**Structure (exact order):**

```
File
├── Import JSON …
├── Export JSON …
├── Export Markdown …
├──────────────────────────
├── Backup Database …
├── Restore Database …
├──────────────────────────
└── Exit
```

- "…" items open the existing file dialogs (`QFileDialog`, existing handlers). **Exit** calls the existing close flow (`close()` / `QApplication.quit`).
- Menu items reuse the current handlers verbatim; only the `QMenuBar` / `QMenu` / `QAction` QSS and item geometry change.
- No Import / Export / Backup / Restore buttons in the header, sidebar, or pane headers. The Settings dialog may link to these actions, but the menu bar is the canonical entry point.
- Keyboard: `Alt+F` opens File (native menubar behavior); `↑/↓` navigates, `Enter` activates, `Esc` closes.

---

## 14. Sidebar

Width **250px** (collapsible to 64px), fill `surface`, right border 1px `border-subtle`, no scroll (its sections are short).

**Brand block (52px):**
- 28×28 brand tile: `radius-md` (6), fill `gradient-brand`, letter "A" 13/600 `text-on-deep` centered; `glow-accent` behind.
- Name "adudu" 15/600 `text-primary`, 8px gap; version `font-mono-xs` `text-muted` under it.

**PROFILE section** (section label `font-xs` uppercase `text-muted`, padding 12 16 6):
- **Profile selector** — 32px `QComboBox` (or styled dropdown) of existing profiles; switching loads that profile's glossary via existing services.
- Action row: New, Rename, Delete — three compact ghost buttons (28px) for profiles. Delete opens the Confirm dialog.

**LIBRARY section:**
- Terms (book icon)
- Categories (folder icon)

**SYSTEM section:**
- Settings (settings icon)

**Nav item metrics:** height 32, `radius-md` (6), padding-left 12, icon 16 `muted`, label 13 `text-secondary`. Hover: fill `surface-hover`, icon + label `text-primary`. **Active:** fill `accent-blue-soft`, icon `accent-blue`, label `text-primary`, plus a 3px `accent-purple` indicator bar on the left edge (radius 2). Icon-only state in the collapsed rail keeps the active tint.

**Bottom block (pinned):**
- 1px `border-subtle` divider, then the **Theme toggle**: full-width 32px row — 16px sun/moon icon (muted) + label "Dark / Light" 13px `text-secondary`. Hover: fill `surface-hover`, text `text-primary`. Toggles the existing theme switch; both themes use the same component system.

**Collapsed rail (64px):** brand tile centered; nav items become 32px icon-only (icons centered), tooltips on hover, labels hidden; the profile selector becomes a 28×28 avatar/initial tile; theme toggle becomes icon-only. `Ctrl+B` toggles.

**Explicitly NOT in the sidebar:** templates, tags, favorites, recently viewed.

---

## 15. Term List (Center Pane)

Width **320px** (resizable 260–420), fill `bg-base`, right border 1px `border-subtle`.

**Pane header (52px):** title "All Terms" 15/600 `text-primary` + count badge `font-mono-xs` `text-muted` in parentheses; right side: filter icon-button (28) and sort icon-button (28) opening a dropdown menu (A–Z, Z–A, Category, Default). The header swaps to the bulk bar when terms are multi-selected (§16).

**Filter input (below header):** pill search field (§12.4), full width minus 24px, placeholder "Filter terms…"; `Esc` clears and blurs. Filtering uses the existing search/filter path.

**List:** one scroll region; no row separators — rely on the 4px row gap + hover fill. Two-line rows:

```
┌──────────────────────────────────────────────┐
│ ▢[tile]  Command Injection         [Chip]    │  ← 44px
│          Exploits that run arbitrary code    │
└──────────────────────────────────────────────┘
```

**Term row (44px, `radius-lg` 8):**
- **Line 1:** term name 13/600 `text-primary`; trailing category chip (§23) when the term has a category.
- **Line 2:** full name 12/400 `text-muted`, single line, ellipsized.
- Leading tile: 28×28 `radius-md`, fill = category hue @ 16% (§4.6), initial letter 12/600 in the hue's light text; when the term has no category, fill `bg-deep` and letter `text-secondary`.

**Qt sizing requirements (hard):**
- Rows **fill the complete pane width**: horizontal size policy `Expanding`, no fixed small width; the row widget or delegate draws its background across the full viewport width.
- Correct `sizeHint`: height 44; width ≥ the pane's viewport width so the list never renders items at a tiny width.
- Padding: 12px horizontal, 8px to tile, 6px between lines.
- Long text: elide with `QFontMetrics.elidedText(..., Qt.ElideRight, available)`; when the elided text differs from the full text, `setToolTip(full text)`.

**Row states:**
- Resting: fill `surface-raised`, border 1px `border-subtle`.
- Hover: fill `surface-hover`, border `border-strong`, `shadow-sm`.
- Selected: fill `accent-blue-soft`, border `accent-blue` @ 40%, left 2px `accent-blue` indicator (radius 1); name stays `text-primary` (never dim).
- Multi-selected: same selected fill; a 16px checkbox replaces the tile.

**Interactions:** click selects and loads the detail pane; `Ctrl+Click` toggles; `Shift+Click` extends; drag draws a selection rectangle; `Ctrl+A` selects all visible; double-click switches the detail pane to edit mode.

**Empty states:**
- No terms: centered 40px faded brand tile + "No terms yet" 15/600 + "Use + New term below to add your first term" 13 `text-secondary`.
- Filter, no results: search icon + "No terms match *query*" + ghost "Clear filter" button.

**Bottom bar (pinned, 56px, top border `border-subtle`):** full-width **New term** `btn-primary` (Large, 36px), 12px side margins, 10px top/bottom, leading 16px plus icon. This is the app-wide primary action for creating a term.

---

## 16. Multi-Selection & Bulk Actions

Applies to the term list.

- **Selection model:** extended (`QAbstractItemView.ExtendedSelection`): `Ctrl+Click` toggles, `Shift+Click` extends, drag-selects, `Ctrl+A` selects all visible.
- **Visual:** when 2+ rows are selected, leading tiles switch to 16px checkboxes (checked = `accent-blue` fill + white check). Selected rows share the selected fill §15.
- **Bulk bar:** when selection ≥ 1, the pane header swaps its title/filter cluster for a compact bar: "**N terms selected**" 13/600 + **Delete Selected** (`btn-danger`, 32px). Delete opens the Confirm dialog ("Delete N terms?"); on confirm the selected terms are deleted through existing services.
- `Esc` clears the selection. While a multi-selection is active, the detail pane shows a neutral "N terms selected" placeholder in its header instead of a term.
- No bulk favorite, no bulk export, no "clear selection" button (Esc is the clear affordance).

---

## 17. Term Detail / Editor

Fill `bg-base`; vertically scrolling content column **max-width 860px, centered**, 40px horizontal padding, 32px top, 48px bottom. When the pane is narrower than the column, the column takes full width.

### 17.1 Read mode

**Header card** (`radius-lg` 8, fill `surface-raised`, border `border-subtle`, padding 20, `shadow-sm`):
- Row 1: term name `font-display` `text-primary`; right side actions: Edit (`btn-primary`, "Edit", 32px) + ⋯ (`btn-ghost` overflow menu: Export, Delete — reuse existing flows).
- Row 2 (8px gap): category chip (§23) when assigned + full name 13px `text-secondary`.
- Aliases row: one compact chip per alias (§23). Shown only if the term has aliases.

**Body — dynamic section cards (§18), 12px apart.** Render exactly the sections the database contains, in database order. **Never hard-code section titles.** No default sections are created; examples like "Definition", "Usage", "Ports", "Commands", "Detection", "Notes" are illustrations only — the UI must render whatever title/content exists in the data.

```
▼ Ports
  389 LDAP
  636 LDAPS
▶ Commands
▶ Notes
```

Each card:
- Header: chevron + dynamic title 15/600 + line-count badge `font-mono-xs` `text-muted`; hover fill; the entire header is the click target.
- Body: content 13/400 `text-primary`, line-height 1.45; long content scrolls within a max-height (~40vh) region; the card remains collapsible.
- Section actions (28×28 ghost icon buttons, revealed on header hover): reorder (chevrons-up-down), rename (pencil), delete (trash). These call existing section-management services.

**"Add section"** — below the last card: ghost button, plus icon, "Add section". Adds a new empty dynamic section; the user supplies the title (inline title edit or the New Section dialog). No fixed section names.

**No-selection:** centered 40px faded brand tile + "Select a term to view it" 15/600 + a `Ctrl+K` hint `font-mono-xs`.

### 17.2 Edit mode

Entered from Edit (double-click too). Same column; the header card becomes a form:
- **Name** — `QLineEdit` 32 (§12.1), auto-focused.
- **Full name** — `QLineEdit` 32.
- **Category** — `QComboBox` of existing categories plus a "(None)" entry to change or clear the assignment. Compact badge-style.
- **Aliases** — chip input (§12.5).
- **Sections** — the dynamic section cards remain fully manageable here with the same inline actions (rename, edit, delete, reorder, add), plus the content editor for the open section.

Footer row (24px below the form): Cancel (`btn-ghost`) + Save (`btn-primary`, disabled until a name is present). `Ctrl+Enter` saves; `Esc` cancels and discards only if the form is untouched (else confirm). Saving flips the Save button into a brief "Saved ✓" `success` ghost state.

---

## 18. Section Accordions (Dynamic Cards)

Used for detail-pane sections and the lookup popup content. Implementation: `QToolButton` header + animated body (`QPropertyAnimation` on `maximumHeight`, 160ms, `OutCubic`); the body is clipped, so its content never reflows during animation.

**Header (44px, `radius-lg` top):** 20px section icon `muted` → `primary` on hover; dynamic title 15/600, 8px gap; optional count badge `font-mono-xs` in parentheses; stretch; trailing 16px chevron-down rotating 180° when open. Hover: fill `surface-hover`. The entire header is the hit target (pointing hand cursor).

**Body:** padding 16px; bottom corners `radius-lg` minus 1 (inner-corner rule, §7). Border: 1px `border-subtle` around the whole card; card carries `shadow-sm`.

**Behavior:**
- Independent open/close; multiple sections may be open at once.
- Long sections: body max-height ~40vh with an internal soft scrollbar — a long open section must never prevent access to the other sections below it.
- Compact variant (lookup popup): header 36px, body padding 12px.

**Titles are user data — display only.** Never build logic or UI branches on a known section name.

---

## 19. Categories Page

Reached from the sidebar "Categories" nav. **Two main content areas only — Categories | Terms. There is no middle category-details column.**

```
┌─────────────────────────┬──────────────────────────────────────┐
│  Categories (280px)     │  Terms (flex, remaining width)      │
└─────────────────────────┴──────────────────────────────────────┘
```

**Left — Categories list (280px, fill `bg-base`, right border `border-subtle`):**
- Pane header (52): "Categories" 15/600 + count `font-mono-xs` `text-muted`; right: "+ New category" `btn-ghost` (32px, plus icon).
- Rows (40px, `radius-md`): folder icon 16 `muted`, name 13 `text-secondary`, term count `font-mono-xs` `text-muted` right-aligned. Hover: fill `surface-hover`, text `text-primary`.
- Reorder: internal drag-and-drop (plus optional up/down fallback) via existing reorder support.
- Right-click row: **Rename**, **Delete**. Delete opens the Confirm dialog stating that **its terms are kept** (the category assignment is cleared, terms are not deleted).
- Click selects the category → the right pane filters to its terms. Deselect (click empty space) → the right pane shows all terms.

**Right — Terms (flex):**
- Pane header (52): "Terms" 15/600 + count `font-mono-xs` (N of total when filtered); filter pill (§15 filter, scoped to the current view); sort dropdown reuse.
- Rows: two-line term rows, same design as §15 (name / full name), full width.
- Right-click row: **Open** (load the term in the detail pane), **Edit** (edit mode), **Remove from Category** (clears the term's category assignment; the term is not deleted), **Delete** (Confirm dialog).
- **Assign / change / clear category:** done in the term editor's category selector; "Remove from Category" is the in-context shortcut. If the current app already offers an "add existing term" picker in this view, keep it; otherwise assignment happens via the editor selector.
- Empty category: "No terms in this category" empty state.

**Rules:**
- Deleting a category never deletes its terms.
- No category description field and no category color field (hue is derived from the name, §4.6).
- New / Rename category dialogs contain the name field only.

---

## 20. Lookup Popup (Global Search / Hotkey / Clipboard)

Opens when the header search field gains focus or text is typed, and via the existing global hotkey and clipboard text capture. Same widget for all triggers.

**Surface:** frameless floating window, **480px** wide, max-height **520px**, `radius-lg` (8), fill `overlay-popup` (frosted, 0.85 alpha) over `shadow-lg`, 1px `border`, padding 12.
- **Position:** under the header search field, right edges aligned (when opened from the field); centered on screen (or last position) when opened from the hotkey/clipboard.
- **Draggable** by the header strip. **Resizable** from all edges and corners (custom edge/corner hit regions; `QSizeGrip` acceptable for the corner). Size/position may persist in `QSettings`.
- Content column is scrollable.

**Results state:** term rows (40px, `radius-md`): term name 13/600 with the matched substring highlighted `accent-blue-text` + full name 12 `text-muted` ellipsized + category chip. Hover `surface-hover`; active row shows a 2px left `accent-blue` indicator. Show ~8 rows; a trailing "See all results →" ghost row filters the term list and focuses it.

**No results:** search icon + "No results for *query*" 13/600 + ghost "Clear" action.

**Term content view:** opening a row (Enter or click) shows that term inside the popup: name, full name, category chip, aliases chips, then **all dynamic sections as compact collapsible accordions** (§18, header 36px). Long sections scroll within the popup and remain collapsible; the section heading is the hit target. **Never hard-code section names.**

**Fixed footer bar (48px, top border `border-subtle`):** actions right-aligned, 8px gap: Close (`btn-ghost` 32) · Edit (`btn-ghost` 32) · **Open Full Page** (`btn-primary` 32). Edit opens the term in the detail pane in edit mode; Open Full Page selects the term in the list and loads the detail pane. When no term row is active, the footer instead shows `font-mono-xs` hints: `↑↓ NAVIGATE · ↵ OPEN · ESC CLOSE`.

**Keyboard (live):** `↑/↓` move the active row, `Enter` opens it, `Esc` closes (restores focus to the search). Scroll the active row into view.

---

## 21. Dialogs

Frameless dialogs with a custom 52px title bar (`surface`, bottom border `border-subtle`, `shadow-lg`, `radius-lg` 8): title 13/600 `text-primary` at 16px left, close (×) ghost icon-button 28×28 far right. Body padding 20; footer 64px with top border `border-subtle`, actions right-aligned with 8px gap.

**Sizing:** small 420px, default 520px, large 680px; max-height 85vh with inner scroll. Modal scrim: `overlay-scrim` over the whole window. **Every dialog opens centered relative to its parent / the main window.** Entrance: 120ms fade + 4px upward slide (disabled under reduced motion).

**Keyboard & focus contract:** first focusable control focused on open; `Esc` = cancel; `Enter` = confirm (unless a multiline field has focus); `Tab`/`Shift+Tab` cycles within the dialog and never escapes it.

**Dialog inventory (existing features only):**

| Dialog | Size | Fields / content | Primary action |
|---|---|---|---|
| New Term | 420 | Name (autofocus), Full name, Category (combo, optional) | Create |
| New / Rename Category | 420 | Name | Create / Save |
| New / Rename Section | 420 | Section title | Create / Save |
| New / Rename Profile | 420 | Profile name | Create / Save |
| Confirm Delete | 420 | danger icon (20px) + message; category delete adds "Its terms will be kept." | Delete (`btn-danger`) |
| Settings | 520 | existing settings (theme, hotkey, clipboard capture, import/export, backup/restore) restyled to this system | Done |

Import / Export and Backup / Restore dialogs already exist in adudu; restyle them to the dialog contract without changing their logic.

Dialog footer rule: at most one solid button — the confirm. Other actions are `btn-ghost`.

---

## 22. Cards

Generic card = `surface-raised` fill, 1px `border-subtle`, `radius-lg` (8), padding 16, optional `shadow-sm`. Card paddings: 16 (default) / 20 (large). Non-interactive cards do not react to hover. Interactive cards (category rows, term rows as cards, chips) hover: fill `surface-hover`, border `border-strong`, `shadow-sm`; press: fill `surface-active`. Never use a hover fill that drops text contrast.

Empty-state card: centered content in `bg-deep`, dashed 1px `border-subtle`, `radius-lg`, padding 32.

---

## 23. Tags & Badges

- **Category chip:** height 22, pill `radius-full` (or `radius-xs` for dense rows), fill = category hue @ 16% (§4.6), text = hue light tint, 11/600, padding 6–8. Hover (interactive chips): fill @ 26%, text lightens.
- **Alias chip:** height 22, `radius-xs`, fill `bg-deep`, border `border-subtle`, text `text-secondary` 11/500.
- **Count badge:** `font-mono-xs` `text-muted`, no fill.
- **Kbd chip:** `font-mono-xs`, fill `bg-deep`, border `border-subtle`, `radius-xs`, padding 2 4.

---

## 24. Responsive & Window-Resize Behavior

Desktop-first; the app never scrolls horizontally.

| Window width | Behavior |
|---|---|
| ≥ 1280 | Full three panes (defaults 250 / 320 / flexible) |
| 1100 – 1280 | Sidebar auto-collapses to the 64px rail (toggleable); term list min 260 |
| 900 – 1100 | Term list collapses behind a `panel` toggle; detail full width with breadcrumb back |
| < 900 | Stacked layout: segmented switcher (Terms / Categories / Detail) in the header's left cluster; only one pane visible at a time |

- **Global search stays pinned top-right at every width.** On very narrow widths it may shrink to ~200px but remains right-aligned in the header.
- Detail column: collapses from 860px max to full width below 900px.
- Dialog/popup sizes are fixed but clamped to window height (85vh).
- All panes are `QSplitter`-resizable; splitter widths persist in `QSettings`.

---

## 25. Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+K` | Focus global search / open lookup popup |
| `Ctrl+N` | New term |
| `Ctrl+F` | Focus term-list filter |
| `Ctrl+E` | Edit current term |
| `Ctrl+Enter` | Save in editor / confirm dialog |
| `Ctrl+B` | Toggle sidebar rail |
| `F` | Toggle term list |
| `Ctrl+1` / `Ctrl+2` / `Ctrl+3` | Terms / Categories / Settings |
| `Esc` | Close popup/dialog, clear filter, clear selection, cancel edit |
| `Ctrl+A` | Select all visible terms (in list) |
| `Ctrl+Click` / `Shift+Click` / drag | Multi-select / range-select |
| `↑/↓`, `Enter` | Navigate lists and the lookup popup |
| Global hotkey | Open lookup popup (existing) |

Shortcuts are listed in the tooltips of their controls and in the popup footer.

---

## 26. Accessibility

- All text ≥ 4.5:1; large text and icons ≥ 3:1; state changes never reduce contrast (§11.1).
- Every focusable widget has a 2px accent focus ring visible on keyboard navigation only (`FocusReason`).
- Full keyboard path for every flow; visible focus always follows `Tab`.
- Notify state/selection changes to the screen reader via `QAccessible` roles (set on custom widgets).
- Respect `QApplication` font DPI scaling; all sizes are pixel tokens that scale with the OS DPI.
- Reduced-motion setting disables popup/dialog animations; popups prefer `Qt.Popup` (no window animation).
- Where long text is elided, always expose the full text via tooltip (list rows, chips, popup rows).

---

## 27. QSS Implementation Guide

QSS cannot express variables, shadows, or font tracking — so implement the system in Python and generate the stylesheet from centralized tokens.

### 27.1 Recommended UI module layout

```
adudu/ui/
├── theme.py           # all tokens as Python constants (single source of truth)
│   ├── COLOR, SPACING, RADIUS, TYPO, HEIGHT, WIDTH
│   ├── QSS  = build_stylesheet()   # f-string-generated global stylesheet
│   ├── category_hue(name)          # deterministic hue (§4.6)
│   └── icons()                     # loads SVG set, recolors variants
├── main_window.py     # MainWindow: header, sidebar, splitter, status wiring
├── header.py, sidebar.py, term_list.py, term_detail.py, categories.py
├── lookup.py          # popup + search field + hotkey/clipboard hooks
└── dialogs.py         # NewTerm, NewCategory, Rename, NewSection, Confirm, Settings, Profile dialogs
```

### 27.2 Token → Python → QSS

```python
# theme.py (excerpt — pattern to follow)
COLOR = {
    "bg_base": QColor(0x0B, 0x0F, 0x16),
    "accent_strong": QColor(0x3B, 0x6E, 0xE8),
    # … every token from §4 …
}
QSS = f"""
QLineEdit, QComboBox, QPlainTextEdit {{
  background: {hex(COLOR["surface_raised"])};
  border: 1px solid {hex(COLOR["border_subtle"])};
  border-radius: 6px; color: {hex(COLOR["text_primary"])};
  padding: 0 8px; min-height: 30px;
}}
QLineEdit:focus {{ border-color: {hex(COLOR["border_accent"])}; }}
QPushButton#btnPrimary {{
  background: {hex(COLOR["accent_strong"])}; color: #FFFFFF;
  border-radius: 6px; padding: 0 16px; min-height: 30px;
}}
QPushButton#btnPrimary:hover {{ background: {hex(COLOR["accent_hover"])}; }}
QPushButton#btnPrimary:pressed {{ background: {hex(COLOR["accent_active"])}; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{
  background: {hex(COLOR["border_strong"])}; border-radius: 5px; min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {hex(COLOR["text_muted"])}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QMenuBar {{
  background: {hex(COLOR["bg_deep"])};
  border-bottom: 1px solid {hex(COLOR["border_subtle"])};
  min-height: 28px; padding: 0 4px;
}}
QMenuBar::item {{
  background: transparent; color: {hex(COLOR["text_secondary"])};
  padding: 0 10px; border-radius: 6px;
}}
QMenuBar::item:selected {{ background: {hex(COLOR["surface_hover"])}; color: {hex(COLOR["text_primary"])}; }}
QMenuBar::item:open {{ background: {hex(COLOR["accent_soft"])}; color: {hex(COLOR["text_primary"])}; }}
QMenu {{
  background: {hex(COLOR["surface_raised"])};
  border: 1px solid {hex(COLOR["border"])};
  border-radius: 8px; padding: 6px;
}}
QMenu::item {{
  color: {hex(COLOR["text_secondary"])}; padding: 6px 12px;
  border-radius: 6px; min-width: 200px; min-height: 16px;
}}
QMenu::item:selected {{ background: {hex(COLOR["surface_hover"])}; color: {hex(COLOR["text_primary"])}; }}
QMenu::separator {{ height: 1px; background: {hex(COLOR["border_subtle"])}; margin: 4px 8px; }}
"""
```

### 27.3 Qt-specific implementation notes

- **Splitter:** use `QSplitter` for the three panes; set stretch factors 0 / 0 / 1 and persist `sizes()` in `QSettings`. Set minimum pane widths in code (sidebar 64, list 260).
- **Term list sizing:** `QListView` with a custom item widget or `QStyledItemDelegate`; rows use `QSizePolicy.Expanding` horizontally and a correct `sizeHint` so items always fill the pane width (see §15). Never leave items at a tiny width.
- **Accordion:** `QPropertyAnimation` on `maximumHeight` (160ms, `OutCubic`) with the body inside a clipping widget (§18).
- **Shadows:** `QGraphicsDropShadowEffect` on popups, dialogs, and hovered interactive cards. Use sparingly (one per surface) for performance.
- **SVG tinting:** loading the SVG and setting the icon color per state in code is preferred over QSS `setProperty` `image:` rules.
- **Focus ring:** draw it in a `FocusFrame.paintEvent` (2px `accent-blue`, radius+1, offset 2) rather than a border on the widget, so it reads against fills.
- **Tracking / line-height:** not supported in QSS — set `QFont.setLetterSpacing`/`setPixelSize` in code for eyebrow labels.
- **Category hue:** compute with `zlib.crc32` for run-to-run stability (§4.6).
- Set `HighDpiScaleFactorRoundingPolicy.PassThrough` and enable DPI scaling on the `QApplication` for consistent 96-DPI tokens.
- Apply the global `QSS` to the app; keep widget-level styles only for layout-internal geometry (spacing, padding) to avoid QSS cascade fights.

---

## 28. Verification Checklist for the Coding Agent

P0 (must pass before handoff):

- [ ] The three-pane shell matches §3 at 1440×900 and holds ≥ 1024×640.
- [ ] File menu shows exactly: Import JSON, Export JSON, Export Markdown, Backup Database, Restore Database, Exit — reusing existing handlers; no large Import/Export buttons in the main header (§13.1).
- [ ] Global search is pinned top-right of the header at every width (§13).
- [ ] Sidebar shows only PROFILE / LIBRARY / SYSTEM plus the theme toggle — no favorites, recent, templates, or tags (§14).
- [ ] Term list two-line rows fill the full pane width with correct `sizeHint`, `Expanding` policy, and tooltips on truncated text (§15).
- [ ] Every color used exists in `theme.py`; no stray hex in widget code.
- [ ] Hover/pressed/focus/disabled pairs defined for every button and input; contrast never drops on hover (§11.1).
- [ ] All interactive controls ≥ 28px; focus ring visible via keyboard.
- [ ] Dynamic sections render DB content only; no hard-coded titles; add/rename/edit/delete/reorder/collapse all work (§17/18).
- [ ] Lookup popup: draggable, resizable, keyboard nav, highlight, fixed footer, dynamic accordions (§20).
- [ ] Dialogs open centered on the parent, trap focus, and show a single solid confirm (§21).
- [ ] Multi-selection shows "N terms selected" + Delete Selected, clears on `Esc` (§16).
- [ ] Categories page has exactly two content areas; deleting a category keeps its terms (§19).
- [ ] No horizontal scroll at any window width (§24).
- [ ] Empty/loading/no-result states present for list, detail, lookup, categories (§15/17/19/20).

P1:

- [ ] All keyboard shortcuts in §25 wired; tooltips mention them.
- [ ] Pane widths persist across sessions (`QSettings`).
- [ ] Theme toggle flips both themes; both use the same component system (§4.7).
- [ ] Reduced-motion disables entrance animations (§26).
- [ ] Focused search opens the popup; `Esc` returns focus to the previous widget.

P2:

- [ ] Category hue is stable across runs (`zlib.crc32`, §4.6).
- [ ] `QAccessible` roles set on custom widgets.
- [ ] Every elided long text exposes its full value via tooltip (§15/23).

---

## 29. Out of Scope & Architecture Constraint

- **Presentation layer only.** `UI → Services → Repositories → SQLite` is fixed. No changes to the database, repositories, services, or application architecture.
- No new backend services; no new database tables or columns; no new network functionality; no AI functionality.
- No invented features: favorites, recently viewed, references/sources, history/changelog, related terms, tags, templates, source URLs, category descriptions/colors, reviewed/deprecated status fields.
- No hard-coded section names — sections render whatever exists in the database.
- No web technologies (no HTML/CSS/Tailwind, no React), no Tkinter, no replacement of PySide6.
- No fake or fabricated sample data.
- Dark and Light themes are both supported through the existing switch; the dark theme is the primary visual reference.
