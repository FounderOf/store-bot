"""
Lapisan database SQLite.
Menyediakan helper untuk semua tabel: products, transactions, stock,
settings, premium_users.

Semua fungsi sinkron (sqlite3 standar) supaya simple.
Discord.py menjalankannya di event loop, jadi untuk skala kecil ini cukup.
"""

from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from typing import Any, Iterable, Iterator, Optional

from config import DB_PATH


# ---------------------------------------------------------------------------
# koneksi
# ---------------------------------------------------------------------------


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# inisialisasi schema
# ---------------------------------------------------------------------------


def init_db() -> None:
    with get_conn() as conn:
        c = conn.cursor()

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL UNIQUE,
                description TEXT    NOT NULL DEFAULT '',
                price       INTEGER NOT NULL DEFAULT 0,
                type        TEXT    NOT NULL DEFAULT 'manual',
                image_url   TEXT    NOT NULL DEFAULT '',
                discount    INTEGER NOT NULL DEFAULT 0,
                created_at  INTEGER NOT NULL
            )
            """
        )

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                product_id  INTEGER NOT NULL,
                price       INTEGER NOT NULL,
                final_price INTEGER NOT NULL,
                status      TEXT    NOT NULL DEFAULT 'pending',
                kind        TEXT    NOT NULL DEFAULT 'product',
                created_at  INTEGER NOT NULL,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            )
            """
        )

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS stock (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                content    TEXT    NOT NULL,
                used       INTEGER NOT NULL DEFAULT 0,
                used_by    INTEGER,
                used_at    INTEGER,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            )
            """
        )

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS premium_users (
                user_id    INTEGER PRIMARY KEY,
                status     TEXT    NOT NULL DEFAULT 'pending',
                created_at INTEGER NOT NULL,
                approved_at INTEGER
            )
            """
        )


# ---------------------------------------------------------------------------
# settings (key/value)
# ---------------------------------------------------------------------------


def set_setting(key: str, value: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )


def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default


# ---------------------------------------------------------------------------
# products
# ---------------------------------------------------------------------------


def add_product(
    name: str,
    description: str,
    price: int,
    ptype: str,
    image_url: str,
    discount: int,
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO products
                (name, description, price, type, image_url, discount, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (name, description, price, ptype, image_url, discount, int(time.time())),
        )
        return int(cur.lastrowid)


def update_product(product_id: int, **fields: Any) -> bool:
    if not fields:
        return False
    allowed = {"name", "description", "price", "type", "image_url", "discount"}
    sets = []
    values: list[Any] = []
    for k, v in fields.items():
        if k in allowed and v is not None:
            sets.append(f"{k} = ?")
            values.append(v)
    if not sets:
        return False
    values.append(product_id)
    with get_conn() as conn:
        cur = conn.execute(
            f"UPDATE products SET {', '.join(sets)} WHERE id = ?", values
        )
        return cur.rowcount > 0


def delete_product(product_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
        return cur.rowcount > 0


def get_product(product_id: int) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        ).fetchone()


def get_product_by_name(name: str) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM products WHERE name = ?", (name,)
        ).fetchone()


def list_products() -> list[sqlite3.Row]:
    with get_conn() as conn:
        return list(
            conn.execute("SELECT * FROM products ORDER BY id ASC").fetchall()
        )


# ---------------------------------------------------------------------------
# stock
# ---------------------------------------------------------------------------


def add_stock_items(product_id: int, items: Iterable[str]) -> int:
    items = [i.strip() for i in items if i and i.strip()]
    if not items:
        return 0
    with get_conn() as conn:
        conn.executemany(
            "INSERT INTO stock (product_id, content) VALUES (?, ?)",
            [(product_id, i) for i in items],
        )
    return len(items)


def count_stock(product_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM stock WHERE product_id = ? AND used = 0",
            (product_id,),
        ).fetchone()
        return int(row["c"]) if row else 0


def take_stock(product_id: int, user_id: int) -> Optional[str]:
    """Ambil 1 stock yang belum dipakai, tandai sebagai used."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, content FROM stock WHERE product_id = ? AND used = 0 LIMIT 1",
            (product_id,),
        ).fetchone()
        if not row:
            return None
        conn.execute(
            "UPDATE stock SET used = 1, used_by = ?, used_at = ? WHERE id = ?",
            (user_id, int(time.time()), row["id"]),
        )
        return str(row["content"])


# ---------------------------------------------------------------------------
# transactions
# ---------------------------------------------------------------------------


def create_transaction(
    user_id: int,
    product_id: int,
    price: int,
    final_price: int,
    kind: str = "product",
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO transactions
                (user_id, product_id, price, final_price, status, kind, created_at)
            VALUES (?, ?, ?, ?, 'pending', ?, ?)
            """,
            (user_id, product_id, price, final_price, kind, int(time.time())),
        )
        return int(cur.lastrowid)


def set_transaction_status(tx_id: int, status: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE transactions SET status = ? WHERE id = ?", (status, tx_id)
        )
        return cur.rowcount > 0


def get_transaction(tx_id: int) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM transactions WHERE id = ?", (tx_id,)
        ).fetchone()


# ---------------------------------------------------------------------------
# premium users
# ---------------------------------------------------------------------------


def create_premium_request(user_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO premium_users (user_id, status, created_at)
            VALUES (?, 'pending', ?)
            ON CONFLICT(user_id) DO UPDATE SET
                status     = CASE WHEN premium_users.status = 'paid'
                                  THEN premium_users.status
                                  ELSE 'pending' END,
                created_at = excluded.created_at
            """,
            (user_id, int(time.time())),
        )


def approve_premium(user_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO premium_users (user_id, status, created_at, approved_at)
            VALUES (?, 'paid', ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                status      = 'paid',
                approved_at = excluded.approved_at
            """,
            (user_id, int(time.time()), int(time.time())),
        )
        return cur.rowcount > 0


def revoke_premium(user_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM premium_users WHERE user_id = ?", (user_id,)
        )
        return cur.rowcount > 0


def is_premium(user_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT status FROM premium_users WHERE user_id = ?", (user_id,)
        ).fetchone()
        return bool(row and row["status"] == "paid")


def get_premium_status(user_id: int) -> Optional[str]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT status FROM premium_users WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row["status"] if row else None


def list_premium_users() -> list[sqlite3.Row]:
    with get_conn() as conn:
        return list(
            conn.execute(
                "SELECT * FROM premium_users ORDER BY created_at DESC"
            ).fetchall()
        )
