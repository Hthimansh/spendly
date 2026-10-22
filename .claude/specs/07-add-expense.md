# Spec: Add Expense

## Overview
Step 7 lets logged-in users submit a new expense through a dedicated form page.
A `GET /expenses/add` route renders a form with fields for amount, category,
date, and an optional description. A `POST /expenses/add` route validates the
input and inserts a row into the `expenses` table, then redirects the user to
their profile page with a success flash message. This is the first write
operation available to regular users and is the foundation for the edit and
delete steps that follow.

## Depends on
- Step 1: Database setup (`expenses` table exists with `user_id`, `amount`,
  `category`, `date`, `description` columns)
- Step 3: Login / Logout (`session["user_id"]` is set on login; unauthenticated
  users must be redirected)

## Routes
- `GET /expenses/add` — render the add-expense form — logged-in only
- `POST /expenses/add` — validate and insert the new expense, then redirect — logged-in only

## Database changes
No database changes. The `expenses` table already has all required columns:
- `user_id INTEGER NOT NULL`
- `amount REAL NOT NULL`
- `category TEXT NOT NULL`
- `date TEXT NOT NULL` (stored as `YYYY-MM-DD`)
- `description TEXT` (optional)

## Templates
- **Create:** `templates/add_expense.html`
  - Extends `base.html`
  - A single-column form card with:
    - Amount input (`type="number"`, `step="0.01"`, `min="0.01"`, required)
    - Category select (options: Food, Transport, Bills, Health, Entertainment, Shopping, Other)
    - Date input (`type="date"`, defaults to today's date, required)
    - Description textarea (optional, max 200 characters)
    - Submit button labeled "Add Expense"
  - Flash messages displayed at the top of the form on validation errors
  - A cancel link back to `/profile`

## Files to change
- `app.py`
  - Replace the stub `GET /expenses/add` route with a full handler:
    - Redirect to `/login` if `session["user_id"]` is not set
    - On GET: render `add_expense.html` with today's date pre-filled
    - On POST: validate input, insert row via `add_expense()` DB helper,
      flash success, redirect to `/profile`
  - Add `methods=["GET", "POST"]` to the route decorator

- `database/db.py`
  - Add `add_expense(user_id, amount, category, date, description)` helper
    that inserts one row into `expenses` using a parameterised query

## Files to create
- `templates/add_expense.html` — the form template (see Templates section)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format user values into SQL
- Passwords hashed with werkzeug (not applicable here, but keep the pattern)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles
- Authentication check: if `session.get("user_id")` is falsy, redirect to
  `url_for("login")` with a flash message "Please sign in to add an expense."
- Amount validation: must be a positive float greater than 0; reject with flash
  on invalid or missing value
- Category validation: must be one of the seven allowed values; reject unknown
  categories (prevents injection of arbitrary strings into the DB)
- Date validation: use `datetime.strptime(date_str, "%Y-%m-%d")` — reject
  malformed dates with a flash error; do not silently ignore them (unlike the
  profile filter, this is user-submitted write data)
- Description: strip whitespace; store `None` if blank after stripping
- On any validation failure: re-render the form with the original input values
  preserved and flash messages shown — do not lose what the user typed
- After a successful insert: `flash("Expense added.")` and
  `redirect(url_for("profile"))`
- Currency display in flash messages or UI must use ₹ — never £ or $

## Definition of done
- [ ] Visiting `/expenses/add` while logged out redirects to `/login` with a
      flash message
- [ ] Visiting `/expenses/add` while logged in renders the form with today's
      date pre-filled in the date field
- [ ] Submitting the form with all valid fields inserts a row in `expenses` and
      redirects to `/profile` with "Expense added." flashed
- [ ] The new expense appears in the transactions list on the profile page
- [ ] Submitting with a blank amount shows a validation error and re-renders
      the form without losing the other field values
- [ ] Submitting with amount `0` or a negative number shows a validation error
- [ ] Submitting with an invalid date string (e.g. `"not-a-date"`) shows a
      validation error
- [ ] Submitting with a category not in the allowed list is rejected with a
      flash error
- [ ] Submitting with no description stores `NULL` / `None` in the DB (no error)
- [ ] The cancel link returns the user to `/profile` without inserting any data
