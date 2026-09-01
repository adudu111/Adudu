-- CyberGlossary canonical schema (migration v1).
-- See ARCHITECTURE.md §5 for rationale. All timestamps are ISO-8601 UTC strings.

-- Metadata / bookkeeping. NOTE: schema version is tracked via PRAGMA user_version
-- (see migrations.py); this table is reserved for other key/value app metadata.
CREATE TABLE app_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Profiles: top-level knowledge scopes.
CREATE TABLE profiles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL COLLATE NOCASE UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    color       TEXT,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- Categories (per profile).
CREATE TABLE categories (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    name       TEXT NOT NULL COLLATE NOCASE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    UNIQUE (profile_id, name)
);

-- Tags (per profile).
CREATE TABLE tags (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    name       TEXT NOT NULL COLLATE NOCASE,
    UNIQUE (profile_id, name)
);

-- Terms. Identity is (profile_id, term).
CREATE TABLE terms (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id  INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    term        TEXT NOT NULL COLLATE NOCASE,
    full_name   TEXT NOT NULL DEFAULT '',
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    UNIQUE (profile_id, term)
);
CREATE INDEX idx_terms_profile ON terms(profile_id, sort_order);
CREATE INDEX idx_terms_category ON terms(category_id);

-- Aliases / misspellings (user-controlled).
CREATE TABLE aliases (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    term_id    INTEGER NOT NULL REFERENCES terms(id) ON DELETE CASCADE,
    alias      TEXT NOT NULL COLLATE NOCASE,
    created_at TEXT NOT NULL,
    UNIQUE (term_id, alias)
);
CREATE INDEX idx_aliases_alias ON aliases(alias);

-- Term <-> Tag join.
CREATE TABLE term_tags (
    term_id INTEGER NOT NULL REFERENCES terms(id) ON DELETE CASCADE,
    tag_id  INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (term_id, tag_id)
);

-- Dynamic sections (user-defined, ordered).
CREATE TABLE sections (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    term_id    INTEGER NOT NULL REFERENCES terms(id) ON DELETE CASCADE,
    title      TEXT NOT NULL,
    content    TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_sections_term ON sections(term_id, sort_order);

-- Templates (per profile).
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

-- Application data-adjacent settings (key/value). E.g. active_profile_id.
CREATE TABLE settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Full-text index (FTS5). rowid == terms.id.
CREATE VIRTUAL TABLE terms_fts USING fts5(
    term,
    full_name,
    aliases,
    tags,
    category,
    body,
    profile_id UNINDEXED,
    tokenize = 'unicode61 remove_diacritics 2'
);
