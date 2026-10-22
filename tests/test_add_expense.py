"""
tests/test_add_expense.py
=========================
Pytest tests for Step 07: Add Expense (GET/POST /expenses/add).

Coverage:
  - Unauthenticated GET and POST redirect to /login
  - Authenticated GET renders form with today's date pre-filled
  - Authenticated GET renders all seven valid category options
  - Valid POST inserts DB row, redirects to /profile, flashes "Expense added."
  - Valid POST with blank description stores NULL in DB
  - Invalid amounts (0, negative, blank, non-numeric) rejected with flash
  - Invalid date string rejected with flash
  - Unknown category rejected with flash
  - Validation failure re-renders form (does not lose submitted values)
  - Cancel link href points to /profile
"""

import sys
import os
import tempfile
import pytest
from datetime import date
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

# Import the Flask app after DB redirect is in place.
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


def _get_expenses_for_user(user_id):
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchall()


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


# ------------------------------------------------------------------ #
# Auth guard tests                                                     #
# ------------------------------------------------------------------ #

class TestAddExpenseAuthGuard:

    def test_unauthenticated_get_redirects_to_login(self, client):
        resp = client.get("/expenses/add")
        assert resp.status_code == 302, "Unauthenticated GET must redirect (302)"
        assert "/login" in resp.headers["Location"], "Must redirect to /login"

    def test_unauthenticated_post_redirects_to_login(self, client):
        resp = client.post("/expenses/add", data={
            "amount": "50.00",
            "category": "Food",
            "date": "2026-10-01",
            "description": "test",
        })
        assert resp.status_code == 302, "Unauthenticated POST must redirect (302)"
        assert "/login" in resp.headers["Location"], "Must redirect to /login"

    def test_unauthenticated_get_flashes_sign_in_message(self, client):
        client.get("/expenses/add", follow_redirects=True)
        # After following the redirect to /login, the flash message should appear
        resp = client.get("/expenses/add", follow_redirects=True)
        body = resp.data.decode("utf-8")
        assert "sign in" in body.lower(), (
            "Flash message should prompt user to sign in"
        )


# ------------------------------------------------------------------ #
# GET /expenses/add — authenticated                                    #
# ------------------------------------------------------------------ #

class TestAddExpenseGet:

    def test_authenticated_get_returns_200(self, logged_in_client):
        client, uid = logged_in_client
        resp = client.get("/expenses/add")
        assert resp.status_code == 200, "Authenticated GET must return 200"

    def test_form_renders_today_date_prefilled(self, logged_in_client):
        client, uid = logged_in_client
        resp = client.get("/expenses/add")
        body = resp.data.decode("utf-8")
        today = date.today().isoformat()
        assert today in body, (
            f"Form must pre-fill today's date ({today}) in the date field"
        )

    def test_form_renders_all_valid_categories(self, logged_in_client):
        client, uid = logged_in_client
        resp = client.get("/expenses/add")
        body = resp.data.decode("utf-8")
        for category in ["Food", "Transport", "Bills", "Health",
                         "Entertainment", "Shopping", "Other"]:
            assert category in body, (
                f"Form must render category option '{category}'"
            )

    def test_cancel_link_points_to_profile(self, logged_in_client):
        client, uid = logged_in_client
        resp = client.get("/expenses/add")
        body = resp.data.decode("utf-8")
        assert 'href="/profile"' in body, (
            "Cancel link must have href pointing to /profile"
        )

    def test_form_renders_amount_input(self, logged_in_client):
        client, uid = logged_in_client
        resp = client.get("/expenses/add")
        body = resp.data.decode("utf-8")
        assert 'name="amount"' in body, "Form must contain an amount input field"

    def test_form_renders_submit_button(self, logged_in_client):
        client, uid = logged_in_client
        resp = client.get("/expenses/add")
        body = resp.data.decode("utf-8")
        assert "Add Expense" in body, "Form must have an 'Add Expense' submit button"


# ------------------------------------------------------------------ #
# POST /expenses/add — happy path                                      #
# ------------------------------------------------------------------ #

class TestAddExpensePostHappyPath:

    def test_valid_post_redirects_to_profile(self, logged_in_client):
        client, uid = logged_in_client
        resp = client.post("/expenses/add", data={
            "amount": "75.50",
            "category": "Food",
            "date": "2026-10-10",
            "description": "Grocery run",
        })
        assert resp.status_code == 302, "Valid POST must redirect (302)"
        assert "/profile" in resp.headers["Location"], (
            "Must redirect to /profile after success"
        )

    def test_valid_post_inserts_db_row(self, logged_in_client):
        client, uid = logged_in_client
        client.post("/expenses/add", data={
            "amount": "75.50",
            "category": "Food",
            "date": "2026-10-10",
            "description": "Grocery run",
        })
        expenses = _get_expenses_for_user(uid)
        assert len(expenses) == 1, "Valid POST must insert exactly one row in expenses"

    def test_valid_post_stores_correct_values(self, logged_in_client):
        client, uid = logged_in_client
        client.post("/expenses/add", data={
            "amount": "75.50",
            "category": "Food",
            "date": "2026-10-10",
            "description": "Grocery run",
        })
        expenses = _get_expenses_for_user(uid)
        row = expenses[0]
        assert row["amount"] == 75.50, "Stored amount must match submitted value"
        assert row["category"] == "Food", "Stored category must match submitted value"
        assert row["date"] == "2026-10-10", "Stored date must match submitted value"
        assert row["description"] == "Grocery run", "Stored description must match"
        assert row["user_id"] == uid, "Stored user_id must match the session user"

    def test_valid_post_flashes_expense_added(self, logged_in_client):
        client, uid = logged_in_client
        resp = client.post("/expenses/add", data={
            "amount": "75.50",
            "category": "Food",
            "date": "2026-10-10",
            "description": "Grocery run",
        }, follow_redirects=True)
        body = resp.data.decode("utf-8")
        assert "Expense added." in body, (
            "Must flash 'Expense added.' after a successful insert"
        )

    def test_valid_post_blank_description_stores_null(self, logged_in_client):
        client, uid = logged_in_client
        client.post("/expenses/add", data={
            "amount": "20.00",
            "category": "Transport",
            "date": "2026-10-05",
            "description": "",
        })
        expenses = _get_expenses_for_user(uid)
        assert len(expenses) == 1, "Must insert expense even when description is blank"
        assert expenses[0]["description"] is None, (
            "Blank description must be stored as NULL, not empty string"
        )

    def test_valid_post_whitespace_only_description_stores_null(self, logged_in_client):
        client, uid = logged_in_client
        client.post("/expenses/add", data={
            "amount": "20.00",
            "category": "Transport",
            "date": "2026-10-05",
            "description": "   ",
        })
        expenses = _get_expenses_for_user(uid)
        assert len(expenses) == 1, "Must insert expense even with whitespace-only description"
        assert expenses[0]["description"] is None, (
            "Whitespace-only description must be stored as NULL after stripping"
        )

    def test_valid_post_each_allowed_category(self, logged_in_client):
        client, uid = logged_in_client
        categories = ["Food", "Transport", "Bills", "Health",
                      "Entertainment", "Shopping", "Other"]
        for i, cat in enumerate(categories):
            resp = client.post("/expenses/add", data={
                "amount": "10.00",
                "category": cat,
                "date": "2026-10-01",
                "description": "",
            })
            assert resp.status_code == 302, (
                f"Valid category '{cat}' must be accepted and redirect"
            )

    def test_expense_appears_on_profile_after_insert(self, logged_in_client):
        client, uid = logged_in_client
        client.post("/expenses/add", data={
            "amount": "55.00",
            "category": "Bills",
            "date": "2026-10-15",
            "description": "Electric bill",
        })
        resp = client.get("/profile")
        body = resp.data.decode("utf-8")
        assert "₹55.00" in body, (
            "Newly added expense amount must appear in profile transactions"
        )


# ------------------------------------------------------------------ #
# POST /expenses/add — validation errors                              #
# ------------------------------------------------------------------ #

class TestAddExpensePostValidation:

    def test_amount_zero_is_rejected(self, logged_in_client):
        client, uid = logged_in_client
        resp = client.post("/expenses/add", data={
            "amount": "0",
            "category": "Food",
            "date": "2026-10-10",
            "description": "",
        })
        assert resp.status_code == 200, "Validation error must re-render form (200)"
        expenses = _get_expenses_for_user(uid)
        assert len(expenses) == 0, "amount=0 must not insert any row"

    def test_amount_zero_shows_flash_error(self, logged_in_client):
        client, uid = logged_in_client
        resp = client.post("/expenses/add", data={
            "amount": "0",
            "category": "Food",
            "date": "2026-10-10",
            "description": "",
        })
        body = resp.data.decode("utf-8")
        assert "amount" in body.lower() or "positive" in body.lower(), (
            "Flash error must mention amount or positive number for amount=0"
        )

    def test_negative_amount_is_rejected(self, logged_in_client):
        client, uid = logged_in_client
        resp = client.post("/expenses/add", data={
            "amount": "-10.00",
            "category": "Food",
            "date": "2026-10-10",
            "description": "",
        })
        assert resp.status_code == 200, "Validation error must re-render form (200)"
        expenses = _get_expenses_for_user(uid)
        assert len(expenses) == 0, "Negative amount must not insert any row"

    def test_blank_amount_is_rejected(self, logged_in_client):
        client, uid = logged_in_client
        resp = client.post("/expenses/add", data={
            "amount": "",
            "category": "Food",
            "date": "2026-10-10",
            "description": "",
        })
        assert resp.status_code == 200, "Blank amount must re-render form (200)"
        expenses = _get_expenses_for_user(uid)
        assert len(expenses) == 0, "Blank amount must not insert any row"

    def test_non_numeric_amount_is_rejected(self, logged_in_client):
        client, uid = logged_in_client
        resp = client.post("/expenses/add", data={
            "amount": "abc",
            "category": "Food",
            "date": "2026-10-10",
            "description": "",
        })
        assert resp.status_code == 200, "Non-numeric amount must re-render form (200)"
        expenses = _get_expenses_for_user(uid)
        assert len(expenses) == 0, "Non-numeric amount must not insert any row"

    @pytest.mark.parametrize("bad_amount", ["0", "-1", "-0.01", "abc", "", "0.00"])
    def test_invalid_amounts_rejected(self, logged_in_client, bad_amount):
        client, uid = logged_in_client
        resp = client.post("/expenses/add", data={
            "amount": bad_amount,
            "category": "Food",
            "date": "2026-10-10",
            "description": "",
        })
        assert resp.status_code == 200, (
            f"Invalid amount '{bad_amount}' must re-render form (200)"
        )
        expenses = _get_expenses_for_user(uid)
        assert len(expenses) == 0, (
            f"Invalid amount '{bad_amount}' must not insert any row"
        )

    def test_invalid_date_string_is_rejected(self, logged_in_client):
        client, uid = logged_in_client
        resp = client.post("/expenses/add", data={
            "amount": "50.00",
            "category": "Food",
            "date": "not-a-date",
            "description": "",
        })
        assert resp.status_code == 200, "Invalid date must re-render form (200)"
        expenses = _get_expenses_for_user(uid)
        assert len(expenses) == 0, "Invalid date must not insert any row"

    def test_invalid_date_shows_flash_error(self, logged_in_client):
        client, uid = logged_in_client
        resp = client.post("/expenses/add", data={
            "amount": "50.00",
            "category": "Food",
            "date": "not-a-date",
            "description": "",
        })
        body = resp.data.decode("utf-8")
        assert "date" in body.lower(), (
            "Flash error must mention date for invalid date input"
        )

    @pytest.mark.parametrize("bad_date", ["not-a-date", "32-13-2026", "2026/10/01",
                                           "10-01-2026", ""])
    def test_invalid_dates_rejected(self, logged_in_client, bad_date):
        client, uid = logged_in_client
        resp = client.post("/expenses/add", data={
            "amount": "50.00",
            "category": "Food",
            "date": bad_date,
            "description": "",
        })
        assert resp.status_code == 200, (
            f"Invalid date '{bad_date}' must re-render form (200)"
        )
        expenses = _get_expenses_for_user(uid)
        assert len(expenses) == 0, (
            f"Invalid date '{bad_date}' must not insert any row"
        )

    def test_unknown_category_is_rejected(self, logged_in_client):
        client, uid = logged_in_client
        resp = client.post("/expenses/add", data={
            "amount": "50.00",
            "category": "Vacation",
            "date": "2026-10-10",
            "description": "",
        })
        assert resp.status_code == 200, "Unknown category must re-render form (200)"
        expenses = _get_expenses_for_user(uid)
        assert len(expenses) == 0, "Unknown category must not insert any row"

    def test_unknown_category_shows_flash_error(self, logged_in_client):
        client, uid = logged_in_client
        resp = client.post("/expenses/add", data={
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
        "Vacation", "Rent", "Gym", "", "food",  # lowercase should also be rejected
        "<script>alert(1)</script>",
    ])
    def test_invalid_categories_rejected(self, logged_in_client, bad_category):
        client, uid = logged_in_client
        resp = client.post("/expenses/add", data={
            "amount": "50.00",
            "category": bad_category,
            "date": "2026-10-10",
            "description": "",
        })
        assert resp.status_code == 200, (
            f"Invalid category '{bad_category}' must re-render form (200)"
        )
        expenses = _get_expenses_for_user(uid)
        assert len(expenses) == 0, (
            f"Invalid category '{bad_category}' must not insert any row"
        )

    def test_validation_error_preserves_submitted_amount(self, logged_in_client):
        """On a validation failure, re-rendered form must retain submitted values."""
        client, uid = logged_in_client
        resp = client.post("/expenses/add", data={
            "amount": "123.45",
            "category": "Food",
            "date": "not-a-date",  # invalid date triggers error
            "description": "my note",
        })
        body = resp.data.decode("utf-8")
        assert "123.45" in body, (
            "Re-rendered form must preserve the submitted amount value"
        )

    def test_validation_error_preserves_submitted_description(self, logged_in_client):
        """On a validation failure, description value should be preserved."""
        client, uid = logged_in_client
        resp = client.post("/expenses/add", data={
            "amount": "0",  # invalid amount triggers error
            "category": "Food",
            "date": "2026-10-10",
            "description": "preserved note",
        })
        body = resp.data.decode("utf-8")
        assert "preserved note" in body, (
            "Re-rendered form must preserve the submitted description value"
        )

    def test_validation_error_does_not_insert_row(self, logged_in_client):
        """Any combination of invalid fields must not insert a partial row."""
        client, uid = logged_in_client
        client.post("/expenses/add", data={
            "amount": "-5",
            "category": "UnknownCat",
            "date": "bad-date",
            "description": "should not be saved",
        })
        expenses = _get_expenses_for_user(uid)
        assert len(expenses) == 0, (
            "Multiple validation errors must not insert any partial row"
        )
