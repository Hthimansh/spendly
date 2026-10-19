from flask import Flask, render_template, request, flash, redirect, url_for, abort, session
from werkzeug.security import check_password_hash
from database.db import get_db, init_db, seed_db, create_user, get_user_by_email
import sqlite3

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

    name = session.get("user_name", "User")
    initials = "".join(p[0].upper() for p in name.split()[:2])
    user_info = {
        "name": name,
        "initials": initials,
        "email": "demo@spendly.com",
        "member_since": "October 2026",
    }
    stats = {
        "total_spent": "₹269.24",
        "transaction_count": 8,
        "top_category": "Bills",
    }
    transactions = [
        {"date": "Oct 17", "description": "Stationery",           "category": "Other",         "amount": "₹8.50"},
        {"date": "Oct 15", "description": "Lunch at café",        "category": "Food",          "amount": "₹12.00"},
        {"date": "Oct 13", "description": "New sneakers",         "category": "Shopping",      "amount": "₹65.00"},
        {"date": "Oct 10", "description": "Netflix subscription", "category": "Entertainment", "amount": "₹15.49"},
        {"date": "Oct 08", "description": "Pharmacy",             "category": "Health",        "amount": "₹22.75"},
        {"date": "Oct 05", "description": "Electric bill",        "category": "Bills",         "amount": "₹95.00"},
        {"date": "Oct 03", "description": "Uber to office",       "category": "Transport",     "amount": "₹18.00"},
        {"date": "Oct 01", "description": "Grocery run",          "category": "Food",          "amount": "₹32.50"},
    ]
    categories = [
        {"name": "Bills",         "amount": "₹95.00", "pct": 35},
        {"name": "Shopping",      "amount": "₹65.00", "pct": 24},
        {"name": "Food",          "amount": "₹44.50", "pct": 17},
        {"name": "Health",        "amount": "₹22.75", "pct":  8},
        {"name": "Transport",     "amount": "₹18.00", "pct":  7},
        {"name": "Entertainment", "amount": "₹15.49", "pct":  6},
        {"name": "Other",         "amount": "₹8.50",  "pct":  3},
    ]
    return render_template("profile.html",
                           user_info=user_info,
                           stats=stats,
                           transactions=transactions,
                           categories=categories)


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
