"""
tests/test_edit_expense.py
==========================
Pytest tests for Step 08: Edit Expense (GET/POST /expenses/<int:id>/edit).

Coverage:
  - Unauthenticated GET and POST redirect to /login
  - GET with valid id owned by logged-in user → 200, form pre-filled with expense values
  - GET with non-existent id → 404
  - GET with id belonging to a different user → 403
  - Valid POST → 302 redirect to /profile, "Expense updated." flashed, DB row updated
  - Valid POST with blank description → 302, description stored as None
  - POST with blank amount → 200 re-render, flash error, no DB change
  - POST with amount = 0 → 200 re-render, flash error, no DB change
  - POST with negative amount → 200 re-render, no DB change
  - POST with invalid date string → 200 re-render, flash error, no DB change
  - POST with unknown category → 200 re-render, flash error, no DB change
  - Parametrized invalid amounts, dates, and categories all rejected
  - After a validation failure the original DB row is unchanged
  - POST from a different user against another user's expense id → 403
"""

import sys
import os
import tempfile
import pytest
from werkzeug.security import generate_password_hash

# Ensure the project root is importable
sys.path.insert(0, r"F:\LANGGRAPH\expense-tracker")

# Redirect DATABASE_PATH to a temp file BEFORE importing any code that
# opens the DB. This must happen before any database.* import.
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()

import database.db as _db
_db.DATABASE_PATH = _tmp.name

from database.db import get_db, init_db

# Import the Flask app after the DB redirect is in place.
import app as flask_module


# ------------------------------------------------------------------ #
# Fixtures                                                             #
# ------------------------------------------------------------------ #

@pytest.fixture(autouse=True)
def fresh_db():
    """Drop and recreate the schema before each test, ensuring isolation."""
    with get_db() as conn:
        conn.executescript("DROP TABLE IF EXISTS expenses; DROP TABLE IF EXISTS users;")
    init_db()
    yield
    with get_db() as conn:
        conn.executescript("DROP TABLE IF EXISTS expenses; DROP TABLE IF EXISTS users;")


def _make_user(name="Test User", email="test@example.com", password="testpass"):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password)),
        )
        return conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()["id"]


def _insert_expense(user_id, amount=50.00, category="Food", date="2026-10-01",
                    description="Test expense"):
    """Insert an expense row directly and return its id."""
    with get_db() as conn:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, date, description),
        )
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _get_expense(expense_id):
    """Fetch an expense row by id."""
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()


@pytest.fixture
def client():
    flask_module.app.config["TESTING"] = True
    flask_module.app.config["SECRET_KEY"] = "test-secret"
    with flask_module.app.test_client() as c:
        yield c


@pytest.fixture
def logged_in_client(client):
    """A client with an authenticated session already injected."""
    uid = _make_user("Alice", "alice@example.com")
    with client.session_transaction() as sess:
        sess["user_id"] = uid
        sess["user_name"] = "Alice"
    return client, uid


@pytest.fixture
def other_user_client(client):
    """A separate client logged in as a second user (Bob)."""
    uid = _make_user("Bob", "bob@example.com")
    with client.session_transaction() as sess:
        sess["user_id"] = uid
        sess["user_name"] = "Bob"
    return client, uid


# ------------------------------------------------------------------ #
# Auth guard tests                                                     #
# ------------------------------------------------------------------ #

class TestEditExpenseAuthGuard:

    def test_unauthenticated_get_redirects_to_login(self, client):
        resp = client.get("/expenses/1/edit")
        assert resp.status_code == 302, "Unauthenticated GET must redirect (302)"
        assert "/login" in resp.headers["Location"], "Must redirect to /login"

    def test_unauthenticated_post_redirects_to_login(self, client):
        resp = client.post("/expenses/1/edit", data={
            "amount": "50.00",
            "category": "Food",
            "date": "2026-10-01",
            "description": "test",
        })
        assert resp.status_code == 302, "Unauthenticated POST must redirect (302)"
        assert "/login" in resp.headers["Location"], "Must redirect to /login"

    def test_unauthenticated_get_does_not_expose_expense_data(self, client):
        resp = client.get("/expenses/1/edit", follow_redirects=True)
        body = resp.data.decode("utf-8")
        # Should show the login page, not an edit form
        assert "sign in" in body.lower() or "login" in body.lower(), (
            "Unauthenticated redirect must show a sign-in page"
        )


# ------------------------------------------------------------------ #
# GET /expenses/<id>/edit — error cases                               #
# ------------------------------------------------------------------ #

class TestEditExpenseGetErrors:

    def test_get_nonexistent_id_returns_404(self, logged_in_client):
        client, uid = logged_in_client
        resp = client.get("/expenses/99999/edit")
        assert resp.status_code == 404, "Non-existent expense id must return 404"

    def test_get_other_users_expense_returns_403(self, client):
        # Create two separate users
        alice_id = _make_user("Alice", "alice@example.com")
        bob_id   = _make_user("Bob",   "bob@example.com")

        # Alice owns this expense
        expense_id = _insert_expense(alice_id, amount=25.00, category="Food",
                                     date="2026-10-01", description="Alice's lunch")

        # Log in as Bob and try to access Alice's expense
        with client.session_transaction() as sess:
            sess["user_id"]   = bob_id
            sess["user_name"] = "Bob"

        resp = client.get(f"/expenses/{expense_id}/edit")
        assert resp.status_code == 403, (
            "Accessing another user's expense must return 403"
        )


# ------------------------------------------------------------------ #
# GET /expenses/<id>/edit — authenticated, owns expense               #
# ------------------------------------------------------------------ #

class TestEditExpenseGetHappyPath:

    def test_authenticated_get_returns_200(self, logged_in_client):
        client, uid = logged_in_client
        expense_id = _insert_expense(uid)
        resp = client.get(f"/expenses/{expense_id}/edit")
        assert resp.status_code == 200, "Authenticated GET for own expense must return 200"

    def test_form_prefilled_with_amount(self, logged_in_client):
        client, uid = logged_in_client
        expense_id = _insert_expense(uid, amount=123.45, category="Transport",
                                     date="2026-09-15", description="Bus pass")
        resp = client.get(f"/expenses/{expense_id}/edit")
        body = resp.data.decode("utf-8")
        assert "123.45" in body, "Form must pre-fill the expense amount"

    def test_form_prefilled_with_date(self, logged_in_client):
        client, uid = logged_in_client
        expense_id = _insert_expense(uid, amount=40.00, category="Food",
                                     date="2026-09-20", description="Dinner")
        resp = client.get(f"/expenses/{expense_id}/edit")
        body = resp.data.decode("utf-8")
        assert "2026-09-20" in body, "Form must pre-fill the expense date"

    def test_form_prefilled_with_description(self, logged_in_client):
        client, uid = logged_in_client
        expense_id = _insert_expense(uid, amount=30.00, category="Health",
                                     date="2026-10-05", description="Pharmacy visit")
        resp = client.get(f"/expenses/{expense_id}/edit")
        body = resp.data.decode("utf-8")
        assert "Pharmacy visit" in body, "Form must pre-fill the expense description"

    def test_form_renders_all_valid_categories(self, logged_in_client):
        client, uid = logged_in_client
        expense_id = _insert_expense(uid)
        resp = client.get(f"/expenses/{expense_id}/edit")
        body = resp.data.decode("utf-8")
        for category in ["Food", "Transport", "Bills", "Health",
                         "Entertainment", "Shopping", "Other"]:
            assert category in body, (
                f"Edit form must render category option '{category}'"
            )

    def test_form_prefilled_with_category(self, logged_in_client):
        client, uid = logged_in_client
        expense_id = _insert_expense(uid, amount=55.00, category="Bills",
                                     date="2026-10-10", description="Electric")
        resp = client.get(f"/expenses/{expense_id}/edit")
        body = resp.data.decode("utf-8")
        # The selected category must appear in the form
        assert "Bills" in body, "Form must pre-fill the selected category"


# ------------------------------------------------------------------ #
# POST /expenses/<id>/edit — happy path                               #
# ------------------------------------------------------------------ #

class TestEditExpensePostHappyPath:

    def test_valid_post_redirects_to_profile(self, logged_in_client):
        client, uid = logged_in_client
        expense_id = _insert_expense(uid)
        resp = client.post(f"/expenses/{expense_id}/edit", data={
            "amount": "99.99",
            "category": "Transport",
            "date": "2026-10-15",
            "description": "Updated description",
        })
        assert resp.status_code == 302, "Valid POST must redirect (302)"
        assert "/profile" in resp.headers["Location"], (
            "Must redirect to /profile after successful update"
        )

    def test_valid_post_flashes_expense_updated(self, logged_in_client):
        client, uid = logged_in_client
        expense_id = _insert_expense(uid)
        resp = client.post(f"/expenses/{expense_id}/edit", data={
            "amount": "99.99",
            "category": "Transport",
            "date": "2026-10-15",
            "description": "Updated description",
        }, follow_redirects=True)
        body = resp.data.decode("utf-8")
        assert "Expense updated." in body, (
            "Must flash 'Expense updated.' after a successful update"
        )

    def test_valid_post_updates_db_amount(self, logged_in_client):
        client, uid = logged_in_client
        expense_id = _insert_expense(uid, amount=50.00, category="Food",
                                     date="2026-10-01", description="Old")
        client.post(f"/expenses/{expense_id}/edit", data={
            "amount": "75.00",
            "category": "Food",
            "date": "2026-10-01",
            "description": "Old",
        })
        row = _get_expense(expense_id)
        assert row["amount"] == 75.00, "DB amount must be updated to the new value"

    def test_valid_post_updates_db_category(self, logged_in_client):
        client, uid = logged_in_client
        expense_id = _insert_expense(uid, amount=50.00, category="Food",
                                     date="2026-10-01", description="Test")
        client.post(f"/expenses/{expense_id}/edit", data={
            "amount": "50.00",
            "category": "Shopping",
            "date": "2026-10-01",
            "description": "Test",
        })
        row = _get_expense(expense_id)
        assert row["category"] == "Shopping", "DB category must be updated"

    def test_valid_post_updates_db_date(self, logged_in_client):
        client, uid = logged_in_client
        expense_id = _insert_expense(uid, amount=50.00, category="Food",
                                     date="2026-10-01", description="Test")
        client.post(f"/expenses/{expense_id}/edit", data={
            "amount": "50.00",
            "category": "Food",
            "date": "2026-11-15",
            "description": "Test",
        })
        row = _get_expense(expense_id)
        assert row["date"] == "2026-11-15", "DB date must be updated"

    def test_valid_post_updates_db_description(self, logged_in_client):
        client, uid = logged_in_client
        expense_id = _insert_expense(uid, amount=50.00, category="Food",
                                     date="2026-10-01", description="Old note")
        client.post(f"/expenses/{expense_id}/edit", data={
            "amount": "50.00",
            "category": "Food",
            "date": "2026-10-01",
            "description": "New note",
        })
        row = _get_expense(expense_id)
        assert row["description"] == "New note", "DB description must be updated"

    def test_valid_post_stores_all_fields_correctly(self, logged_in_client):
        client, uid = logged_in_client
        expense_id = _insert_expense(uid)
        client.post(f"/expenses/{expense_id}/edit", data={
            "amount": "88.88",
            "category": "Health",
            "date": "2026-12-01",
            "description": "Doctor visit",
        })
        row = _get_expense(expense_id)
        assert row["amount"] == 88.88, "Updated amount must match submitted value"
        assert row["category"] == "Health", "Updated category must match submitted value"
        assert row["date"] == "2026-12-01", "Updated date must match submitted value"
        assert row["description"] == "Doctor visit", "Updated description must match"
        assert row["user_id"] == uid, "user_id must remain unchanged after update"

    def test_valid_post_blank_description_stores_null(self, logged_in_client):
        client, uid = logged_in_client
        expense_id = _insert_expense(uid, description="Old note")
        resp = client.post(f"/expenses/{expense_id}/edit", data={
            "amount": "50.00",
            "category": "Food",
            "date": "2026-10-01",
            "description": "",
        })
        assert resp.status_code == 302, "Blank description must still succeed (302)"
        row = _get_expense(expense_id)
        assert row["description"] is None, (
            "Blank description must be stored as NULL"
        )

    def test_valid_post_whitespace_only_description_stores_null(self, logged_in_client):
        client, uid = logged_in_client
        expense_id = _insert_expense(uid, description="Old note")
        client.post(f"/expenses/{expense_id}/edit", data={
            "amount": "50.00",
            "category": "Food",
            "date": "2026-10-01",
            "description": "   ",
        })
        row = _get_expense(expense_id)
        assert row["description"] is None, (
            "Whitespace-only description must be stored as NULL after stripping"
        )

    def test_valid_post_each_allowed_category(self, logged_in_client):
        client, uid = logged_in_client
        for cat in ["Food", "Transport", "Bills", "Health",
                    "Entertainment", "Shopping", "Other"]:
            expense_id = _insert_expense(uid, category="Food")
            resp = client.post(f"/expenses/{expense_id}/edit", data={
                "amount": "10.00",
                "category": cat,
                "date": "2026-10-01",
                "description": "",
            })
            assert resp.status_code == 302, (
                f"Valid category '{cat}' must be accepted and redirect"
            )


# ------------------------------------------------------------------ #
# POST /expenses/<id>/edit — validation errors                        #
# ------------------------------------------------------------------ #

class TestEditExpensePostValidation:

    def test_amount_zero_is_rejected(self, logged_in_client):
        client, uid = logged_in_client
        expense_id = _insert_expense(uid, amount=50.00)
        resp = client.post(f"/expenses/{expense_id}/edit", data={
            "amount": "0",
            "category": "Food",
            "date": "2026-10-10",
            "description": "",
        })
        assert resp.status_code == 200, "amount=0 must re-render form (200)"
        row = _get_expense(expense_id)
        assert row["amount"] == 50.00, "amount=0 must not update the DB row"

    def test_amount_zero_shows_flash_error(self, logged_in_client):
        client, uid = logged_in_client
        expense_id = _insert_expense(uid)
        resp = client.post(f"/expenses/{expense_id}/edit", data={
            "amount": "0",
            "category": "Food",
            "date": "2026-10-10",
            "description": "",
        })
        body = resp.data.decode("utf-8")
        assert "amount" in body.lower() or "positive" in body.lower(), (
            "Flash error must mention amount or positive for amount=0"
        )

    def test_blank_amount_is_rejected(self, logged_in_client):
        client, uid = logged_in_client
        expense_id = _insert_expense(uid, amount=50.00)
        resp = client.post(f"/expenses/{expense_id}/edit", data={
            "amount": "",
            "category": "Food",
            "date": "2026-10-10",
            "description": "",
        })
        assert resp.status_code == 200, "Blank amount must re-render form (200)"
        row = _get_expense(expense_id)
        assert row["amount"] == 50.00, "Blank amount must not update DB row"

    def test_negative_amount_is_rejected(self, logged_in_client):
        client, uid = logged_in_client
        expense_id = _insert_expense(uid, amount=50.00)
        resp = client.post(f"/expenses/{expense_id}/edit", data={
            "amount": "-10.00",
            "category": "Food",
            "date": "2026-10-10",
            "description": "",
        })
        assert resp.status_code == 200, "Negative amount must re-render form (200)"
        row = _get_expense(expense_id)
        assert row["amount"] == 50.00, "Negative amount must not update DB row"

    def test_non_numeric_amount_is_rejected(self, logged_in_client):
        client, uid = logged_in_client
        expense_id = _insert_expense(uid, amount=50.00)
        resp = client.post(f"/expenses/{expense_id}/edit", data={
            "amount": "abc",
            "category": "Food",
            "date": "2026-10-10",
            "description": "",
        })
        assert resp.status_code == 200, "Non-numeric amount must re-render form (200)"
        row = _get_expense(expense_id)
        assert row["amount"] == 50.00, "Non-numeric amount must not update DB row"

    @pytest.mark.parametrize("bad_amount", ["0", "-1", "-0.01", "abc", "", "0.00"])
    def test_invalid_amounts_rejected(self, logged_in_client, bad_amount):
        client, uid = logged_in_client
        expense_id = _insert_expense(uid, amount=50.00)
        resp = client.post(f"/expenses/{expense_id}/edit", data={
            "amount": bad_amount,
            "category": "Food",
            "date": "2026-10-10",
            "description": "",
        })
        assert resp.status_code == 200, (
            f"Invalid amount '{bad_amount}' must re-render form (200)"
        )
        row = _get_expense(expense_id)
        assert row["amount"] == 50.00, (
            f"Invalid amount '{bad_amount}' must not update DB row"
        )

    def test_invalid_date_string_is_rejected(self, logged_in_client):
        client, uid = logged_in_client
        expense_id = _insert_expense(uid, date="2026-10-01")
        resp = client.post(f"/expenses/{expense_id}/edit", data={
            "amount": "50.00",
            "category": "Food",
            "date": "not-a-date",
            "description": "",
        })
        assert resp.status_code == 200, "Invalid date must re-render form (200)"
        row = _get_expense(expense_id)
        assert row["date"] == "2026-10-01", "Invalid date must not update DB row"

    def test_invalid_date_shows_flash_error(self, logged_in_client):
        client, uid = logged_in_client
        expense_id = _insert_expense(uid)
        resp = client.post(f"/expenses/{expense_id}/edit", data={
            "amount": "50.00",
            "category": "Food",
            "date": "not-a-date",
            "description": "",
        })
        body = resp.data.decode("utf-8")
        assert "date" in body.lower(), (
            "Flash error must mention date for invalid date input"
        )

    @pytest.mark.parametrize("bad_date", [
        "not-a-date", "32-13-2026", "2026/10/01", "10-01-2026", ""
    ])
    def test_invalid_dates_rejected(self, logged_in_client, bad_date):
        client, uid = logged_in_client
        expense_id = _insert_expense(uid, date="2026-10-01")
        resp = client.post(f"/expenses/{expense_id}/edit", data={
            "amount": "50.00",
            "category": "Food",
            "date": bad_date,
            "description": "",
        })
        assert resp.status_code == 200, (
            f"Invalid date '{bad_date}' must re-render form (200)"
        )
        row = _get_expense(expense_id)
        assert row["date"] == "2026-10-01", (
            f"Invalid date '{bad_date}' must not update DB row"
        )

    def test_unknown_category_is_rejected(self, logged_in_client):
        client, uid = logged_in_client
        expense_id = _insert_expense(uid, category="Food")
        resp = client.post(f"/expenses/{expense_id}/edit", data={
            "amount": "50.00",
            "category": "Vacation",
            "date": "2026-10-10",
            "description": "",
        })
        assert resp.status_code == 200, "Unknown category must re-render form (200)"
        row = _get_expense(expense_id)
        assert row["category"] == "Food", "Unknown category must not update DB row"

    def test_unknown_category_shows_flash_error(self, logged_in_client):
        client, uid = logged_in_client
        expense_id = _insert_expense(uid)
        resp = client.post(f"/expenses/{expense_id}/edit", data={
            "amount": "50.00",
            "category": "Vacation",
            "date": "2026-10-10",
            "description": "",
        })
        body = resp.data.decode("utf-8")
        assert "category" in body.lower(), (
            "Flash error must mention category for unknown category input"
        )

    @pytest.mark.parametrize("bad_category", [
        "Vacation", "Rent", "Gym", "", "food", "<script>alert(1)</script>",
    ])
    def test_invalid_categories_rejected(self, logged_in_client, bad_category):
        client, uid = logged_in_client
        expense_id = _insert_expense(uid, category="Food")
        resp = client.post(f"/expenses/{expense_id}/edit", data={
            "amount": "50.00",
            "category": bad_category,
            "date": "2026-10-10",
            "description": "",
        })
        assert resp.status_code == 200, (
            f"Invalid category '{bad_category}' must re-render form (200)"
        )
        row = _get_expense(expense_id)
        assert row["category"] == "Food", (
            f"Invalid category '{bad_category}' must not update DB row"
        )

    def test_validation_failure_leaves_db_row_unchanged(self, logged_in_client):
        """All original values must be preserved in DB after a validation failure."""
        client, uid = logged_in_client
        expense_id = _insert_expense(uid, amount=50.00, category="Food",
                                     date="2026-10-01", description="Original")
        client.post(f"/expenses/{expense_id}/edit", data={
            "amount": "-99",       # invalid
            "category": "INVALID", # invalid
            "date": "bad-date",    # invalid
            "description": "Should not be saved",
        })
        row = _get_expense(expense_id)
        assert row["amount"] == 50.00, "Original amount must be unchanged after failure"
        assert row["category"] == "Food", "Original category must be unchanged after failure"
        assert row["date"] == "2026-10-01", "Original date must be unchanged after failure"
        assert row["description"] == "Original", "Original description must be unchanged"


# ------------------------------------------------------------------ #
# Cross-user ownership enforcement on POST                            #
# ------------------------------------------------------------------ #

class TestEditExpenseOwnershipOnPost:

    def test_post_to_other_users_expense_returns_403(self, client):
        """A POST from Bob targeting Alice's expense must be rejected with 403."""
        alice_id = _make_user("Alice", "alice@example.com")
        bob_id   = _make_user("Bob",   "bob@example.com")

        expense_id = _insert_expense(alice_id, amount=50.00, category="Food",
                                     date="2026-10-01", description="Alice's")

        # Log in as Bob
        with client.session_transaction() as sess:
            sess["user_id"]   = bob_id
            sess["user_name"] = "Bob"

        resp = client.post(f"/expenses/{expense_id}/edit", data={
            "amount": "1.00",
            "category": "Food",
            "date": "2026-10-01",
            "description": "Bob trying to hijack",
        })
        assert resp.status_code == 403, (
            "POST from a non-owner must return 403"
        )

    def test_post_to_other_users_expense_does_not_modify_db(self, client):
        """Bob's failed POST must leave Alice's expense row untouched."""
        alice_id = _make_user("Alice", "alice@example.com")
        bob_id   = _make_user("Bob",   "bob@example.com")

        expense_id = _insert_expense(alice_id, amount=50.00, category="Food",
                                     date="2026-10-01", description="Alice's")

        with client.session_transaction() as sess:
            sess["user_id"]   = bob_id
            sess["user_name"] = "Bob"

        client.post(f"/expenses/{expense_id}/edit", data={
            "amount": "1.00",
            "category": "Food",
            "date": "2026-10-01",
            "description": "Bob trying to hijack",
        })
        row = _get_expense(expense_id)
        assert row["amount"] == 50.00, "Alice's expense amount must be untouched"
        assert row["description"] == "Alice's", "Alice's expense description must be untouched"

    def test_post_to_nonexistent_expense_returns_404(self, logged_in_client):
        client, uid = logged_in_client
        resp = client.post("/expenses/99999/edit", data={
            "amount": "50.00",
            "category": "Food",
            "date": "2026-10-01",
            "description": "Ghost",
        })
        assert resp.status_code == 404, "POST to non-existent expense id must return 404"
