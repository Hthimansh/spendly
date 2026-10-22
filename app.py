from flask import Flask, render_template, request, flash, redirect, url_for, abort, session
from werkzeug.security import check_password_hash
from database.db import get_db, init_db, seed_db, create_user, get_user_by_email, add_expense as db_add_expense
from database.queries import get_user_by_id, get_summary_stats, get_recent_transactions, get_category_breakdown
import sqlite3
from datetime import datetime, date, timedelta


def _parse_date(s):
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return s
    except (ValueError, TypeError):
        return None

CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]

app = Flask(__name__)
app.secret_key = "dev-secret-change-in-prod"

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    if request.method != "POST":
        abort(405)

    name             = request.form.get("name", "").strip()
    email            = request.form.get("email", "").strip()
    password         = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not name or not email or not password or not confirm_password:
        flash("All fields are required.")
        return render_template("register.html")
    if password != confirm_password:
        flash("Passwords do not match.")
        return render_template("register.html")

    try:
        create_user(name, email, password)
    except sqlite3.IntegrityError:
        flash("Email already registered.")
        return render_template("register.html")

    flash("Account created! Please sign in.")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email    = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not email or not password:
        flash("All fields are required.")
        return render_template("login.html")

    user = get_user_by_email(email)
    if user is None or not check_password_hash(user["password_hash"], password):
        flash("Invalid email or password.")
        return render_template("login.html")

    session["user_id"]   = user["id"]
    session["user_name"] = user["name"]
    flash(f"Welcome back, {user['name']}!")
    return redirect(url_for("profile"))


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        flash("Please sign in to view your profile.")
        return redirect(url_for("login"))

    user_id = session["user_id"]
    user = get_user_by_id(user_id)
    if user is None:
        abort(404)

    created = datetime.strptime(user["created_at"][:10], "%Y-%m-%d")
    name = user["name"]
    initials = "".join(p[0].upper() for p in name.split()[:2])
    user_info = {
        "name":         name,
        "initials":     initials,
        "email":        user["email"],
        "member_since": created.strftime("%B %Y"),
    }

    date_from = _parse_date(request.args.get("from", "").strip())
    date_to   = _parse_date(request.args.get("to", "").strip())

    today          = date.today()
    month_start    = today.replace(day=1)
    last_month_end = month_start - timedelta(days=1)

    date_presets = [
        {"label": "This Month",    "date_from": month_start.isoformat(),                   "date_to": today.isoformat()},
        {"label": "Last Month",    "date_from": last_month_end.replace(day=1).isoformat(),  "date_to": last_month_end.isoformat()},
        {"label": "Last 3 Months", "date_from": (today - timedelta(days=90)).isoformat(),   "date_to": today.isoformat()},
    ]

    return render_template(
        "profile.html",
        user_info=user_info,
        stats=get_summary_stats(user_id, date_from=date_from, date_to=date_to),
        transactions=get_recent_transactions(user_id, date_from=date_from, date_to=date_to),
        categories=get_category_breakdown(user_id, date_from=date_from, date_to=date_to),
        filter_from=date_from or "",
        filter_to=date_to or "",
        date_presets=date_presets,
    )


@app.route("/analytics")
def analytics():
    if not session.get("user_id"):
        flash("Please sign in to view Analytics.")
        return redirect(url_for("login"))
    return render_template("analytics.html")


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    if not session.get("user_id"):
        flash("Please sign in to add an expense.")
        return redirect(url_for("login"))

    if request.method == "GET":
        return render_template("add_expense.html",
                               categories=CATEGORIES,
                               today=date.today().isoformat())

    amount_raw  = request.form.get("amount", "").strip()
    category    = request.form.get("category", "").strip()
    date_raw    = request.form.get("date", "").strip()
    description = request.form.get("description", "").strip()

    errors = []
    amount = None
    try:
        amount = float(amount_raw)
        if amount <= 0:
            raise ValueError
    except (ValueError, TypeError):
        errors.append("Amount must be a positive number.")

    if category not in CATEGORIES:
        errors.append("Please select a valid category.")

    parsed_date = None
    try:
        datetime.strptime(date_raw, "%Y-%m-%d")
        parsed_date = date_raw
    except (ValueError, TypeError):
        errors.append("Date must be a valid YYYY-MM-DD value.")

    if errors:
        for e in errors:
            flash(e)
        return render_template("add_expense.html",
                               categories=CATEGORIES,
                               today=date.today().isoformat(),
                               form=request.form)

    db_add_expense(session["user_id"], amount, category, parsed_date,
                   description or None)
    flash("Expense added.")
    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
