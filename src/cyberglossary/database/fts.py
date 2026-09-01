"""FTS5 index maintenance.

The ``terms_fts`` virtual table (rowid == terms.id) is kept in sync from the source
tables. Any write that changes searchable data must call ``sync_term`` (or
``delete_term``) *before* committing, so a source-data change and its index update share
a single transaction. Never leave a committed source change with a stale FTS row.
"""

from __future__ import annotations

import sqlite3

_SYNC_SQL = """
INSERT INTO terms_fts (rowid, term, full_name, aliases, tags, category, body, profile_id)
SELECT
    t.id,
    COALESCE(t.term, ''),
    COALESCE(t.full_name, ''),
    COALESCE((SELECT group_concat(a.alias, ' ') FROM aliases a WHERE a.term_id = t.id), ''),
    COALESCE((SELECT group_concat(g.name, ' ')
              FROM term_tags tt JOIN tags g ON g.id = tt.tag_id
              WHERE tt.term_id = t.id), ''),
    COALESCE((SELECT c.name FROM categories c WHERE c.id = t.category_id), ''),
    COALESCE((SELECT group_concat(s.title || ' ' || s.content, ' ')
              FROM (SELECT title, content FROM sections
                    WHERE term_id = t.id ORDER BY sort_order, id) s), ''),
    t.profile_id
FROM terms t
WHERE t.id = ?
"""


def sync_term(conn: sqlite3.Connection, term_id: int) -> None:
    """Recompute the FTS row for one term (no commit; caller owns the transaction)."""
    conn.execute("DELETE FROM terms_fts WHERE rowid = ?", (term_id,))
    conn.execute(_SYNC_SQL, (term_id,))


def delete_term(conn: sqlite3.Connection, term_id: int) -> None:
    """Remove a term's FTS row (call when the term itself is deleted)."""
    conn.execute("DELETE FROM terms_fts WHERE rowid = ?", (term_id,))


def sync_terms_for_category(conn: sqlite3.Connection, category_id: int) -> None:
    term_ids = [
        row[0]
        for row in conn.execute(
            "SELECT id FROM terms WHERE category_id = ?", (category_id,)
        ).fetchall()
    ]
    for term_id in term_ids:
        sync_term(conn, term_id)


def sync_terms_for_tag(conn: sqlite3.Connection, tag_id: int) -> None:
    term_ids = [
        row[0]
        for row in conn.execute(
            "SELECT term_id FROM term_tags WHERE tag_id = ?", (tag_id,)
        ).fetchall()
    ]
    for term_id in term_ids:
        sync_term(conn, term_id)


def delete_profile_terms(conn: sqlite3.Connection, profile_id: int) -> None:
    """Remove FTS rows for every term in a profile (call before deleting the profile)."""
    conn.execute(
        "DELETE FROM terms_fts WHERE rowid IN (SELECT id FROM terms WHERE profile_id = ?)",
        (profile_id,),
    )


def rebuild(conn: sqlite3.Connection) -> None:
    """Deterministically wipe and re-index all terms from the source tables."""
    conn.execute("DELETE FROM terms_fts")
    for (term_id,) in conn.execute("SELECT id FROM terms").fetchall():
        conn.execute(_SYNC_SQL, (term_id,))


def ensure_index(conn: sqlite3.Connection) -> None:
    """Backfill the index if it is missing (or has extra) rows.

    Called after migration/initialization. A mismatch between the number of terms and
    the number of indexed rows triggers a full, safe rebuild.
    """
    term_count = conn.execute("SELECT COUNT(*) FROM terms").fetchone()[0]
    fts_count = conn.execute("SELECT COUNT(*) FROM terms_fts").fetchone()[0]
    if fts_count != term_count:
        rebuild(conn)
