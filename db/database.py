from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path
from models import CategorizedTransaction

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        DATE NOT NULL,
    amount      INTEGER NOT NULL,
    description TEXT NOT NULL,
    place       TEXT NOT NULL DEFAULT '',
    category    TEXT NOT NULL DEFAULT '미분류',
    source      TEXT NOT NULL,
    raw_source  TEXT NOT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_edited   BOOLEAN DEFAULT 0,
    UNIQUE(date, amount, description, place, source)
);

CREATE TABLE IF NOT EXISTS crawl_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  DATETIME NOT NULL,
    finished_at DATETIME,
    status      TEXT NOT NULL,
    rows_added  INTEGER DEFAULT 0,
    error_msg   TEXT
);
"""


class Database:
    def __init__(self, path: str = "data/finance.db"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        self._migrate()

    def _migrate(self) -> None:
        # Migration 1: add place column if missing
        try:
            self._conn.execute("ALTER TABLE transactions ADD COLUMN place TEXT NOT NULL DEFAULT ''")
            self._conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists

        # Migration 2: expand UNIQUE constraint to include place
        # Detect by inspecting the existing unique index columns
        indexes = self._conn.execute("PRAGMA index_list(transactions)").fetchall()
        needs_migration = False
        for idx in indexes:
            if idx["unique"]:
                cols = [
                    r["name"]
                    for r in self._conn.execute(f"PRAGMA index_info({idx['name']})").fetchall()
                ]
                if "place" not in cols:
                    needs_migration = True
                    break
        if needs_migration:
            self._conn.executescript("""
                BEGIN;
                CREATE TABLE transactions_new (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    date        DATE NOT NULL,
                    amount      INTEGER NOT NULL,
                    description TEXT NOT NULL,
                    place       TEXT NOT NULL DEFAULT '',
                    category    TEXT NOT NULL DEFAULT '미분류',
                    source      TEXT NOT NULL,
                    raw_source  TEXT NOT NULL,
                    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                    is_edited   BOOLEAN DEFAULT 0,
                    UNIQUE(date, amount, description, place, source)
                );
                INSERT INTO transactions_new
                    SELECT id, date, amount, description, place, category,
                           source, raw_source, created_at, is_edited
                    FROM transactions;
                DROP TABLE transactions;
                ALTER TABLE transactions_new RENAME TO transactions;
                COMMIT;
            """)

    def insert_transactions(self, transactions: list[CategorizedTransaction]) -> int:
        inserted = 0
        try:
            for tx in transactions:
                existing = self._conn.execute(
                    "SELECT is_edited FROM transactions WHERE date=? AND amount=? AND description=? AND place=? AND source=?",
                    (tx.date.isoformat(), tx.amount, tx.description, tx.place, tx.source),
                ).fetchone()
                if existing:
                    if existing["is_edited"]:
                        # User has manually overridden the category — preserve it, skip re-insert
                        continue
                    else:
                        # Pure deduplication — row already exists, nothing to do
                        continue
                self._conn.execute(
                    """INSERT INTO transactions
                       (date, amount, description, place, category, source, raw_source)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (tx.date.isoformat(), tx.amount, tx.description,
                     tx.place, tx.category, tx.source, tx.raw_source),
                )
                inserted += 1
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        return inserted

    def update_category(self, *, date: date, amount: int, description: str,
                        source: str, category: str) -> None:
        cur = self._conn.execute(
            """UPDATE transactions SET category=?, is_edited=1
               WHERE date=? AND amount=? AND description=? AND source=?""",
            (category, date.isoformat(), amount, description, source),
        )
        self._conn.commit()
        if cur.rowcount == 0:
            raise LookupError(
                f"No transaction found for ({date}, {amount}, {description!r}, {source!r})"
            )

    def get_transactions(self, year: int = None, month: int = None) -> list[dict]:
        if month is not None and year is None:
            raise ValueError("year is required when month is specified")
        query = "SELECT * FROM transactions WHERE 1=1"
        params: list = []
        if year and month:
            query += " AND strftime('%Y', date)=? AND strftime('%m', date)=?"
            params.extend([str(year), f"{month:02d}"])
        elif year:
            query += " AND strftime('%Y', date)=?"
            params.append(str(year))
        query += " ORDER BY date DESC"
        rows = self._conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def start_crawl_log(self) -> int:
        cur = self._conn.execute(
            "INSERT INTO crawl_log (started_at, status) VALUES (datetime('now'), 'running')"
        )
        self._conn.commit()
        return cur.lastrowid

    def finish_crawl_log(self, log_id: int, *, status: str,
                         rows_added: int = 0, error_msg: str = None) -> None:
        self._conn.execute(
            """UPDATE crawl_log SET status=?, finished_at=datetime('now'),
               rows_added=?, error_msg=? WHERE id=?""",
            (status, rows_added, error_msg, log_id),
        )
        self._conn.commit()

    def delete_transactions(self, ids: list[int]) -> int:
        placeholders = ",".join("?" * len(ids))
        cur = self._conn.execute(
            f"DELETE FROM transactions WHERE id IN ({placeholders})", ids
        )
        self._conn.commit()
        return cur.rowcount

    def update_transaction(self, row_id: int, *, category: str = None,
                           place: str = None, description: str = None) -> None:
        updates, params = [], []
        if category is not None:
            updates.append("category=?, is_edited=1")
            params.append(category)
        if place is not None:
            updates.append("place=?")
            params.append(place)
        if description is not None:
            updates.append("description=?")
            params.append(description)
        if not updates:
            return
        params.append(row_id)
        self._conn.execute(
            f"UPDATE transactions SET {', '.join(updates)} WHERE id=?", params
        )
        self._conn.commit()

    def get_available_years(self) -> list[int]:
        rows = self._conn.execute(
            "SELECT DISTINCT CAST(strftime('%Y', date) AS INTEGER) AS yr "
            "FROM transactions ORDER BY yr DESC"
        ).fetchall()
        return [r["yr"] for r in rows]

    def close(self) -> None:
        self._conn.close()

    def get_latest_crawl_log(self) -> dict | None:
        row = self._conn.execute(
            """SELECT id, started_at, finished_at, rows_added, error_msg,
               CASE
                 WHEN status='running' AND
                      (julianday('now') - julianday(started_at)) * 24 * 60 > 30
                 THEN 'failed'
                 ELSE status
               END AS status
               FROM crawl_log ORDER BY id DESC LIMIT 1"""
        ).fetchone()
        return dict(row) if row else None
