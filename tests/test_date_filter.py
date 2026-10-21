"""
tests/test_date_filter.py
=========================
Pytest tests for Step 06: Date-range filter on GET /profile.

Coverage:
  - get_summary_stats(user_id, date_from, date_to)
  - get_recent_transactions(user_id, date_from, date_to)
  - get_category_breakdown(user_id, date_from, date_to)
  - GET /profile with from/to query params (integration via test client)
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
from database.queries import (
    get_recent_transactions,
    get_summary_stats,
    get_category_breakdown,
)

# Import app module at module level so its app-context init_db/seed_db
# fires once against the temp DB, before any test resets the schema.
import app as flask_module  # noqa: E402  (side-effect: init_db + seed_db)


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


def _make_user(name="Test User", email="test@example.com"):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash("pw")),
        )
        return conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()["id"]


def _add_expense(user_id, amount, category, date, description="desc"):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, date, description),
        )


@pytest.fixture
def seeded_user():
    """
    Create a test user with exactly the spec seed expenses.

    Date      Category       Amount   Description
    --------- -------------- -------- ---------------------
    2026-10-01 Food           32.50   Grocery run
    2026-10-03 Transport      18.00   Uber to office
    2026-10-05 Bills          95.00   Electric bill
    2026-10-08 Health         22.75   Pharmacy
    2026-10-10 Entertainment  15.49   Netflix subscription
    2026-10-13 Shopping       65.00   New sneakers
    2026-10-15 Food           12.00   Lunch at cafe
    2026-10-17 Other           8.50   Stationery
                        Total: 269.24  (8 transactions)
    """
    uid = _make_user("Demo User", "demo@spendly.com")
    expenses = [
        (uid, 32.50, "Food",          "2026-10-01", "Grocery run"),
        (uid, 18.00, "Transport",      "2026-10-03", "Uber to office"),
        (uid, 95.00, "Bills",          "2026-10-05", "Electric bill"),
        (uid, 22.75, "Health",         "2026-10-08", "Pharmacy"),
        (uid, 15.49, "Entertainment",  "2026-10-10", "Netflix subscription"),
        (uid, 65.00, "Shopping",       "2026-10-13", "New sneakers"),
        (uid, 12.00, "Food",           "2026-10-15", "Lunch at cafe"),
        (uid,  8.50, "Other",          "2026-10-17", "Stationery"),
    ]
    for e in expenses:
        _add_expense(*e)
    return uid


@pytest.fixture
def client():
    flask_module.app.config["TESTING"] = True
    flask_module.app.config["SECRET_KEY"] = "test-secret"
    with flask_module.app.test_client() as c:
        yield c


# ------------------------------------------------------------------ #
# get_summary_stats — date filter unit tests                          #
# ------------------------------------------------------------------ #

class TestGetSummaryStatsDateFilter:

    def test_no_filter_returns_all_8_transactions(self, seeded_user):
        stats = get_summary_stats(seeded_user)
        assert stats["total_spent"] == "₹269.24", "All-time total should be ₹269.24"
        assert stats["transaction_count"] == 8, "Should have 8 transactions"
        assert stats["top_category"] == "Bills", "Bills (₹95.00) is the top category"

    def test_from_and_to_inclusive_boundary(self, seeded_user):
        # Oct 01 (32.50) + Oct 03 (18.00) + Oct 05 (95.00) = 145.50
        stats = get_summary_stats(seeded_user, date_from="2026-10-01", date_to="2026-10-05")
        assert stats["total_spent"] == "₹145.50", "Three expenses sum to ₹145.50"
        assert stats["transaction_count"] == 3
        assert stats["top_category"] == "Bills"

    def test_from_only_returns_expenses_on_or_after_date(self, seeded_user):
        # Oct 08 onward: 22.75 + 15.49 + 65.00 + 12.00 + 8.50 = 123.74
        stats = get_summary_stats(seeded_user, date_from="2026-10-08")
        assert stats["total_spent"] == "₹123.74", "Expenses from Oct 08 onward sum to ₹123.74"
        assert stats["transaction_count"] == 5

    def test_to_only_returns_expenses_on_or_before_date(self, seeded_user):
        # Up to Oct 05: 32.50 + 18.00 + 95.00 = 145.50
        stats = get_summary_stats(seeded_user, date_to="2026-10-05")
        assert stats["total_spent"] == "₹145.50", "Expenses up to Oct 05 sum to ₹145.50"
        assert stats["transaction_count"] == 3

    def test_empty_range_returns_zero_stats(self, seeded_user):
        stats = get_summary_stats(seeded_user, date_from="2025-01-01", date_to="2025-01-31")
        assert stats["total_spent"] == "₹0.00"
        assert stats["transaction_count"] == 0
        assert stats["top_category"] == "—"

    def test_single_day_range_matches_boundary_record(self, seeded_user):
        # Only Oct 08 (Health, 22.75)
        stats = get_summary_stats(seeded_user, date_from="2026-10-08", date_to="2026-10-08")
        assert stats["total_spent"] == "₹22.75"
        assert stats["transaction_count"] == 1
        assert stats["top_category"] == "Health"

    def test_inverted_range_returns_empty(self, seeded_user):
        # from > to — SQL WHERE date >= 'later' AND date <= 'earlier' never matches
        stats = get_summary_stats(seeded_user, date_from="2026-10-15", date_to="2026-10-01")
        assert stats["transaction_count"] == 0
        assert stats["total_spent"] == "₹0.00"

    def test_user_isolation(self, seeded_user):
        # Expenses for a different user must not appear
        other_uid = _make_user("Other User", "other@example.com")
        _add_expense(other_uid, 500.00, "Rent", "2026-10-01", "Other user expense")
        stats = get_summary_stats(seeded_user)
        assert stats["transaction_count"] == 8, "Should only count expenses for seeded_user"
        assert stats["total_spent"] == "₹269.24"

    @pytest.mark.parametrize("date_from,date_to,expected_total,expected_count", [
        ("2026-10-01", "2026-10-05", "₹145.50", 3),
        ("2026-10-08", None,         "₹123.74", 5),
        (None,         "2026-10-05", "₹145.50", 3),
        ("2025-01-01", "2025-01-31", "₹0.00",   0),
        (None,         None,         "₹269.24", 8),
    ])
    def test_parametrized_summary_stats(self, seeded_user, date_from, date_to,
                                         expected_total, expected_count):
        kwargs = {}
        if date_from is not None:
            kwargs["date_from"] = date_from
        if date_to is not None:
            kwargs["date_to"] = date_to
        stats = get_summary_stats(seeded_user, **kwargs)
        assert stats["total_spent"] == expected_total, (
            f"date_from={date_from}, date_to={date_to}: "
            f"expected {expected_total}, got {stats['total_spent']}"
        )
        assert stats["transaction_count"] == expected_count


# ------------------------------------------------------------------ #
# get_recent_transactions — date filter unit tests                    #
# ------------------------------------------------------------------ #

class TestGetRecentTransactionsDateFilter:

    def test_no_filter_returns_all_8_newest_first(self, seeded_user):
        txns = get_recent_transactions(seeded_user)
        assert len(txns) == 8, "No filter should return all 8 transactions"
        assert txns[0]["date"] == "Oct 17", "Newest transaction should be first"
        assert txns[-1]["date"] == "Oct 01", "Oldest transaction should be last"

    def test_from_and_to_returns_correct_transactions(self, seeded_user):
        # Oct 01–05: Grocery run, Uber to office, Electric bill
        txns = get_recent_transactions(seeded_user, date_from="2026-10-01", date_to="2026-10-05")
        assert len(txns) == 3
        dates = {t["date"] for t in txns}
        assert dates == {"Oct 01", "Oct 03", "Oct 05"}

    def test_from_only_filters_correctly(self, seeded_user):
        txns = get_recent_transactions(seeded_user, date_from="2026-10-08")
        assert len(txns) == 5, "5 expenses on or after Oct 08"
        for t in txns:
            assert t["date"] in {"Oct 08", "Oct 10", "Oct 13", "Oct 15", "Oct 17"}, (
                f"Unexpected date {t['date']} before filter start"
            )

    def test_to_only_filters_correctly(self, seeded_user):
        txns = get_recent_transactions(seeded_user, date_to="2026-10-05")
        assert len(txns) == 3, "3 expenses on or before Oct 05"
        for t in txns:
            assert t["date"] in {"Oct 01", "Oct 03", "Oct 05"}, (
                f"Unexpected date {t['date']} after filter end"
            )

    def test_empty_range_returns_empty_list(self, seeded_user):
        txns = get_recent_transactions(seeded_user, date_from="2025-01-01", date_to="2025-01-31")
        assert txns == [], "No expenses in 2025 should return empty list"

    def test_single_day_range(self, seeded_user):
        txns = get_recent_transactions(seeded_user, date_from="2026-10-08", date_to="2026-10-08")
        assert len(txns) == 1
        assert txns[0]["date"] == "Oct 08"
        assert txns[0]["category"] == "Health"
        assert txns[0]["amount"] == "₹22.75"

    def test_results_ordered_newest_first_within_range(self, seeded_user):
        txns = get_recent_transactions(seeded_user, date_from="2026-10-01", date_to="2026-10-05")
        assert len(txns) == 3
        # Newest first within range: Oct 05, Oct 03, Oct 01
        assert txns[0]["date"] == "Oct 05"
        assert txns[1]["date"] == "Oct 03"
        assert txns[2]["date"] == "Oct 01"

    def test_transaction_keys_present(self, seeded_user):
        txns = get_recent_transactions(seeded_user, date_from="2026-10-01", date_to="2026-10-01")
        assert len(txns) == 1
        expected_keys = {"date", "description", "category", "amount"}
        assert set(txns[0].keys()) == expected_keys, "Transaction dict must have correct keys"

    def test_amount_formatted_with_rupee_sign(self, seeded_user):
        txns = get_recent_transactions(seeded_user, date_from="2026-10-01", date_to="2026-10-01")
        assert txns[0]["amount"] == "₹32.50"

    def test_user_isolation(self, seeded_user):
        other_uid = _make_user("Other User", "other@example.com")
        _add_expense(other_uid, 999.00, "Food", "2026-10-01", "Other")
        txns = get_recent_transactions(seeded_user)
        assert len(txns) == 8, "Should not return other user's transactions"


# ------------------------------------------------------------------ #
# get_category_breakdown — date filter unit tests                     #
# ------------------------------------------------------------------ #

class TestGetCategoryBreakdownDateFilter:

    def test_no_filter_returns_all_categories(self, seeded_user):
        breakdown = get_category_breakdown(seeded_user)
        # 8 expenses spanning 7 unique categories (Food appears twice but is one category)
        names = {c["name"] for c in breakdown}
        assert "Bills" in names
        assert "Food" in names
        assert "Transport" in names
        assert "Health" in names
        assert "Entertainment" in names
        assert "Shopping" in names
        assert "Other" in names

    def test_no_filter_sorted_descending_by_amount(self, seeded_user):
        breakdown = get_category_breakdown(seeded_user)
        # Bills (95.00) should be first
        assert breakdown[0]["name"] == "Bills"
        assert breakdown[0]["amount"] == "₹95.00"

    def test_no_filter_pcts_sum_to_100(self, seeded_user):
        breakdown = get_category_breakdown(seeded_user)
        assert sum(c["pct"] for c in breakdown) == 100

    def test_from_and_to_returns_3_categories(self, seeded_user):
        # Oct 01–05: Food(32.50), Transport(18.00), Bills(95.00)
        breakdown = get_category_breakdown(seeded_user, date_from="2026-10-01", date_to="2026-10-05")
        assert len(breakdown) == 3
        names = {c["name"] for c in breakdown}
        assert names == {"Food", "Transport", "Bills"}

    def test_from_and_to_sorted_descending(self, seeded_user):
        breakdown = get_category_breakdown(seeded_user, date_from="2026-10-01", date_to="2026-10-05")
        assert breakdown[0]["name"] == "Bills"
        assert breakdown[0]["amount"] == "₹95.00"

    def test_from_and_to_pcts_sum_to_100(self, seeded_user):
        breakdown = get_category_breakdown(seeded_user, date_from="2026-10-01", date_to="2026-10-05")
        assert sum(c["pct"] for c in breakdown) == 100

    def test_empty_range_returns_empty_list(self, seeded_user):
        breakdown = get_category_breakdown(seeded_user, date_from="2025-01-01", date_to="2025-01-31")
        assert breakdown == []

    def test_single_category_gets_100_pct(self, seeded_user):
        # Oct 08 only: Health (22.75)
        breakdown = get_category_breakdown(seeded_user, date_from="2026-10-08", date_to="2026-10-08")
        assert len(breakdown) == 1
        assert breakdown[0]["name"] == "Health"
        assert breakdown[0]["pct"] == 100

    def test_food_aggregates_two_expenses(self, seeded_user):
        # Food appears on Oct 01 (32.50) and Oct 15 (12.00) = 44.50 total
        breakdown = get_category_breakdown(seeded_user)
        food = next(c for c in breakdown if c["name"] == "Food")
        assert food["amount"] == "₹44.50", "Food total should aggregate both Food expenses"

    def test_from_only(self, seeded_user):
        # Oct 08 onward: Health(22.75), Entertainment(15.49), Shopping(65.00),
        #                Food(12.00), Other(8.50)
        breakdown = get_category_breakdown(seeded_user, date_from="2026-10-08")
        names = {c["name"] for c in breakdown}
        assert names == {"Health", "Entertainment", "Shopping", "Food", "Other"}
        assert sum(c["pct"] for c in breakdown) == 100

    def test_to_only(self, seeded_user):
        # Up to Oct 05: Food(32.50), Transport(18.00), Bills(95.00)
        breakdown = get_category_breakdown(seeded_user, date_to="2026-10-05")
        names = {c["name"] for c in breakdown}
        assert names == {"Food", "Transport", "Bills"}
        assert sum(c["pct"] for c in breakdown) == 100


# ------------------------------------------------------------------ #
# GET /profile — route integration tests with date filter              #
# ------------------------------------------------------------------ #

class TestProfileDateFilterRoute:

    def _set_session(self, client, uid, name="Demo User"):
        with client.session_transaction() as sess:
            sess["user_id"] = uid
            sess["user_name"] = name

    # -- Auth guard --------------------------------------------------

    def test_unauthenticated_redirects_to_login(self, client):
        resp = client.get("/profile?from=2026-10-01&to=2026-10-05")
        assert resp.status_code == 302, "Unauthenticated request must redirect"
        assert "/login" in resp.headers["Location"]

    def test_unauthenticated_no_params_redirects_to_login(self, client):
        resp = client.get("/profile")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    # -- No params: all-time view ------------------------------------

    def test_no_params_returns_200(self, client, seeded_user):
        self._set_session(client, seeded_user)
        resp = client.get("/profile")
        assert resp.status_code == 200

    def test_no_params_shows_all_time_label(self, client, seeded_user):
        self._set_session(client, seeded_user)
        resp = client.get("/profile")
        body = resp.data.decode("utf-8")
        assert "Showing: all time" in body, (
            "Profile with no filter params should display 'Showing: all time'"
        )

    def test_no_params_shows_total_269_24(self, client, seeded_user):
        self._set_session(client, seeded_user)
        resp = client.get("/profile")
        body = resp.data.decode("utf-8")
        assert "₹269.24" in body, "All-time total should be ₹269.24"

    def test_no_params_shows_transaction_count_8(self, client, seeded_user):
        self._set_session(client, seeded_user)
        resp = client.get("/profile")
        body = resp.data.decode("utf-8")
        assert "8" in body, "All-time view should show 8 transactions"

    # -- Exact date range: Oct 01–05 ---------------------------------

    def test_oct01_to_oct05_shows_145_50(self, client, seeded_user):
        self._set_session(client, seeded_user)
        resp = client.get("/profile?from=2026-10-01&to=2026-10-05")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        assert "₹145.50" in body, "Oct 01-05 range should total ₹145.50"

    def test_oct01_to_oct05_hides_later_expenses(self, client, seeded_user):
        self._set_session(client, seeded_user)
        resp = client.get("/profile?from=2026-10-01&to=2026-10-05")
        body = resp.data.decode("utf-8")
        # Expenses after Oct 05 should not appear as amounts in the breakdown
        # (₹123.74 is only produced by combining Oct 08+ expenses)
        assert "₹123.74" not in body

    def test_oct01_to_oct05_shows_filter_dates_in_response(self, client, seeded_user):
        self._set_session(client, seeded_user)
        resp = client.get("/profile?from=2026-10-01&to=2026-10-05")
        body = resp.data.decode("utf-8")
        assert "2026-10-01" in body, "Filter start date should appear in rendered HTML"
        assert "2026-10-05" in body, "Filter end date should appear in rendered HTML"

    # -- Empty range: 2025 dates -------------------------------------

    def test_2025_range_shows_zero_total(self, client, seeded_user):
        self._set_session(client, seeded_user)
        resp = client.get("/profile?from=2025-01-01&to=2025-01-31")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        assert "₹0.00" in body, "A range with no data should show ₹0.00"

    def test_2025_range_does_not_show_any_expense_amounts(self, client, seeded_user):
        self._set_session(client, seeded_user)
        resp = client.get("/profile?from=2025-01-01&to=2025-01-31")
        body = resp.data.decode("utf-8")
        assert "₹269.24" not in body
        assert "₹145.50" not in body

    # -- Malformed dates fall back to all-time -----------------------

    def test_malformed_dates_return_200(self, client, seeded_user):
        self._set_session(client, seeded_user)
        resp = client.get("/profile?from=notadate&to=bad")
        assert resp.status_code == 200

    def test_malformed_dates_show_all_time_label(self, client, seeded_user):
        self._set_session(client, seeded_user)
        resp = client.get("/profile?from=notadate&to=bad")
        body = resp.data.decode("utf-8")
        assert "Showing: all time" in body, (
            "Malformed date params should be silently ignored and show all-time view"
        )

    def test_malformed_dates_show_full_total(self, client, seeded_user):
        self._set_session(client, seeded_user)
        resp = client.get("/profile?from=notadate&to=bad")
        body = resp.data.decode("utf-8")
        assert "₹269.24" in body, "Fallback all-time view should show ₹269.24"

    def test_malformed_from_only_falls_back(self, client, seeded_user):
        # Invalid from + valid to: both should be treated as unset (all-time)
        # Actually per spec: each is validated independently; malformed ones become None.
        # If only `from` is malformed, `to` might still be valid.
        # Test the clearly invalid-both case matches all-time.
        self._set_session(client, seeded_user)
        resp = client.get("/profile?from=not-a-date")
        body = resp.data.decode("utf-8")
        assert resp.status_code == 200
        assert "₹269.24" in body, "Invalid from with no to should show all-time data"

    # -- from only (no to) -------------------------------------------

    def test_from_oct08_shows_123_74(self, client, seeded_user):
        self._set_session(client, seeded_user)
        resp = client.get("/profile?from=2026-10-08")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        assert "₹123.74" in body, "from=Oct 08 without to should total ₹123.74"

    def test_from_oct08_shows_5_transactions(self, client, seeded_user):
        self._set_session(client, seeded_user)
        resp = client.get("/profile?from=2026-10-08")
        body = resp.data.decode("utf-8")
        assert "5" in body, "from=Oct 08 without to should have 5 transactions"

    def test_from_oct08_shows_filter_date_in_response(self, client, seeded_user):
        self._set_session(client, seeded_user)
        resp = client.get("/profile?from=2026-10-08")
        body = resp.data.decode("utf-8")
        assert "2026-10-08" in body, "Filter start date should appear in rendered HTML"

    # -- to only (no from) -------------------------------------------

    def test_to_oct05_shows_145_50(self, client, seeded_user):
        self._set_session(client, seeded_user)
        resp = client.get("/profile?to=2026-10-05")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        assert "₹145.50" in body, "to=Oct 05 without from should total ₹145.50"

    def test_to_oct05_shows_3_transactions(self, client, seeded_user):
        self._set_session(client, seeded_user)
        resp = client.get("/profile?to=2026-10-05")
        body = resp.data.decode("utf-8")
        assert "3" in body, "to=Oct 05 without from should have 3 transactions"

    def test_to_oct05_shows_filter_date_in_response(self, client, seeded_user):
        self._set_session(client, seeded_user)
        resp = client.get("/profile?to=2026-10-05")
        body = resp.data.decode("utf-8")
        assert "2026-10-05" in body, "Filter end date should appear in rendered HTML"

    # -- Template rendering ------------------------------------------

    def test_profile_renders_user_name(self, client, seeded_user):
        self._set_session(client, seeded_user)
        resp = client.get("/profile")
        body = resp.data.decode("utf-8")
        assert "Demo User" in body

    def test_profile_renders_user_email(self, client, seeded_user):
        self._set_session(client, seeded_user)
        resp = client.get("/profile")
        body = resp.data.decode("utf-8")
        assert "demo@spendly.com" in body

    def test_all_time_does_not_show_range_label(self, client, seeded_user):
        # When no filter is active, the range label ("Showing: start – today" style)
        # should not appear; only "Showing: all time" should.
        self._set_session(client, seeded_user)
        resp = client.get("/profile")
        body = resp.data.decode("utf-8")
        assert "Showing: all time" in body
        # The range display uses " – " separator; that should NOT appear when all-time
        assert "Showing: 2026" not in body
