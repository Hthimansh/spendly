import sqlite3
import os

DATABASE_PATH = os.path.join(os.path.dirname(__file__), "..", "spendly.db")


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT    NOT NULL,
                email         TEXT    NOT NULL UNIQUE,
                password_hash TEXT    NOT NULL,
                created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS expenses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                amount      REAL    NOT NULL,
                category    TEXT    NOT NULL,
                date        TEXT    NOT NULL,
                description TEXT,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
        """)


def seed_db():
    with get_db() as conn:
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
            return

        from werkzeug.security import generate_password_hash

        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Demo User", "demo@spendly.com", generate_password_hash("demo123")),
        )
        user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        expenses = [
            (user_id, 32.50, "Food",          "2026-10-01", "Grocery run"),
            (user_id, 18.00, "Transport",      "2026-10-03", "Uber to office"),
            (user_id, 95.00, "Bills",          "2026-10-05", "Electric bill"),
            (user_id, 22.75, "Health",         "2026-10-08", "Pharmacy"),
            (user_id, 15.49, "Entertainment",  "2026-10-10", "Netflix subscription"),
            (user_id, 65.00, "Shopping",       "2026-10-13", "New sneakers"),
            (user_id, 12.00, "Food",           "2026-10-15", "Lunch at café"),
            (user_id,  8.50, "Other",          "2026-10-17", "Stationery"),
        ]
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            expenses,
        )


def get_user_by_email(email):
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()


def create_user(name, email, password):
    from werkzeug.security import generate_password_hash
    password_hash = generate_password_hash(password)
    with get_db() as conn:
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, password_hash),
        )
        row = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()
    return row["id"]


def add_expense(user_id, amount, category, date, description):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, date, description or None),
        )


def get_expense_by_id(expense_id):
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()


def update_expense(expense_id, amount, category, date, description):
    with get_db() as conn:
        conn.execute(
            "UPDATE expenses SET amount=?, category=?, date=?, description=?"
            " WHERE id=?",
            (amount, category, date, description or None, expense_id),
        )
