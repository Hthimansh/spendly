import os
import tempfile
import pytest
from werkzeug.security import generate_password_hash

# Point the module at a temp DB before importing anything that opens it
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["SPENDLY_TEST_DB"] = _tmp.name

import database.db as _db
_db.DATABASE_PATH = _tmp.name

from database.db import get_db, init_db
from database.queries import (
    get_user_by_id,
    get_recent_transactions,
    get_summary_stats,
    get_category_breakdown,
)


@pytest.fixture(autouse=True)
def fresh_db():
    """Wipe and re-create the schema before each test."""
    with get_db() as conn:
        conn.executescript("DROP TABLE IF EXISTS expenses; DROP TABLE IF EXISTS users;")
    init_db()
    yield
    with get_db() as conn:
        conn.executescript("DROP TABLE IF EXISTS expenses; DROP TABLE IF EXISTS users;")


def _make_user(name="Test User", email="test@example.com"):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash("pw")),
        )
        return conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()["id"]


def _add_expense(user_id, amount, category, date, description="desc"):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, date, description),
        )


# ------------------------------------------------------------------ #
# get_user_by_id                                                       #
# ------------------------------------------------------------------ #

def test_get_user_by_id_valid():
    uid = _make_user("Alice", "alice@example.com")
    row = get_user_by_id(uid)
    assert row is not None
    assert row["name"] == "Alice"
    assert row["email"] == "alice@example.com"


def test_get_user_by_id_missing():
    assert get_user_by_id(99999) is None


# ------------------------------------------------------------------ #
# get_recent_transactions                                              #
# ------------------------------------------------------------------ #

def test_get_recent_transactions_with_data():
    uid = _make_user()
    _add_expense(uid, 10.00, "Food",  "2026-10-01", "Lunch")
    _add_expense(uid, 20.00, "Bills", "2026-10-05", "Electric")
    txns = get_recent_transactions(uid)
    assert len(txns) == 2
    # newest first
    assert txns[0]["date"] == "Oct 05"
    assert txns[1]["date"] == "Oct 01"
    assert txns[0]["amount"] == "₹20.00"
    assert set(txns[0].keys()) == {"date", "description", "category", "amount"}


def test_get_recent_transactions_empty():
    uid = _make_user()
    assert get_recent_transactions(uid) == []


# ------------------------------------------------------------------ #
# get_summary_stats                                                    #
# ------------------------------------------------------------------ #

def test_get_summary_stats_with_data():
    uid = _make_user()
    _add_expense(uid, 95.00, "Bills", "2026-10-05", "Electric")
    _add_expense(uid, 65.00, "Shopping", "2026-10-13", "Shoes")
    _add_expense(uid, 32.50, "Food", "2026-10-01", "Groceries")
    stats = get_summary_stats(uid)
    assert stats["total_spent"] == "₹192.50"
    assert stats["transaction_count"] == 3
    assert stats["top_category"] == "Bills"


def test_get_summary_stats_empty():
    uid = _make_user()
    stats = get_summary_stats(uid)
    assert stats == {"total_spent": "₹0.00", "transaction_count": 0, "top_category": "—"}


# ------------------------------------------------------------------ #
# get_category_breakdown                                               #
# ------------------------------------------------------------------ #

def test_get_category_breakdown_with_data():
    uid = _make_user()
    _add_expense(uid, 100.00, "Bills", "2026-10-01", "Rent")
    _add_expense(uid, 50.00, "Food", "2026-10-02", "Groceries")
    _add_expense(uid, 50.00, "Food", "2026-10-03", "Lunch")
    breakdown = get_category_breakdown(uid)
    assert len(breakdown) == 2
    names = [c["name"] for c in breakdown]
    assert "Food" in names and "Bills" in names
    assert all(c["pct"] >= 0 for c in breakdown)
    assert sum(c["pct"] for c in breakdown) == 100


def test_get_category_breakdown_pcts_sum_100():
    uid = _make_user()
    _add_expense(uid, 95.00, "Bills", "2026-10-05", "Electric")
    _add_expense(uid, 65.00, "Shopping", "2026-10-13", "Shoes")
    _add_expense(uid, 44.50, "Food", "2026-10-01", "Food")
    _add_expense(uid, 22.75, "Health", "2026-10-08", "Pharmacy")
    _add_expense(uid, 18.00, "Transport", "2026-10-03", "Uber")
    _add_expense(uid, 15.49, "Entertainment", "2026-10-10", "Netflix")
    _add_expense(uid, 8.50, "Other", "2026-10-17", "Misc")
    breakdown = get_category_breakdown(uid)
    assert sum(c["pct"] for c in breakdown) == 100
    assert breakdown[0]["name"] == "Bills"


def test_get_category_breakdown_empty():
    uid = _make_user()
    assert get_category_breakdown(uid) == []


# ------------------------------------------------------------------ #
# Route tests                                                          #
# ------------------------------------------------------------------ #

@pytest.fixture
def client():
    import app as flask_app
    flask_app.app.config["TESTING"] = True
    flask_app.app.config["SECRET_KEY"] = "test"
    with flask_app.app.test_client() as c:
        yield c


def test_profile_unauthenticated(client):
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_profile_authenticated(client):
    uid = _make_user("Demo User", "demo@example.com")
    _add_expense(uid, 95.00, "Bills", "2026-10-05", "Electric")

    with client.session_transaction() as sess:
        sess["user_id"] = uid
        sess["user_name"] = "Demo User"

    resp = client.get("/profile")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "Demo User" in body
    assert "demo@example.com" in body
    assert "₹" in body
