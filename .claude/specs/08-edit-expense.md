# Spec: Edit Expense

## Overview
Step 8 lets logged-in users edit an existing expense they own. A
`GET /expenses/<id>/edit` route fetches the expense, verifies ownership,
and renders a pre-filled form. A `POST /expenses/<id>/edit` route validates
the updated values and writes them back to the database, then redirects to
the profile page. This step also adds an "Edit" action link to each row in
the profile page's Recent Transactions table, and updates the query helper to
expose the expense `id` so the link can be built.

## Depends on
- Step 1: Database setup (`expenses` table with all required columns)
- Step 3: Login / Logout (`session["user_id"]` is set on login)
- Step 7: Add Expense (establishes the add-expense form pattern this step mirrors)

## Routes
- `GET /expenses/<int:id>/edit` — render the pre-filled edit form — logged-in only
- `POST /expenses/<int:id>/edit` — validate and update the expense, then redirect — logged-in only

## Database changes
No schema changes. Two new query helpers are needed in `database/db.py`:

- `get_expense_by_id(expense_id)` — fetches a single expense row by primary key
- `update_expense(expense_id, amount, category, date, description)` — updates the
  four editable columns for the given expense

## Templates
- **Create:** `templates/edit_expense.html`
  - Extends `base.html`
  - Identical layout to `add_expense.html` but:
    - Page title and heading read "Edit Expense"
    - Form `action` points to `url_for('edit_expense', id=expense.id)`
    - All fields pre-filled from the `expense` dict passed by the route
    - Submit button labeled "Save Changes"
    - Cancel link returns to `/profile`

- **Modify:** `templates/profile.html`
  - Add an "Actions" `<th>` column to the `<thead>` of the transactions table
  - For each transaction row, add a `<td>` with an Edit link:
    `<a href="{{ url_for('edit_expense', id=t.id) }}">Edit</a>`

## Files to change
- `app.py`
  - Replace the stub `edit_expense` route with a full handler:
    - Add `methods=["GET", "POST"]` to the route decorator
    - Redirect to `/login` with a flash if `session["user_id"]` is not set
    - Call `get_expense_by_id(id)`; `abort(404)` if `None`
    - Verify `expense["user_id"] == session["user_id"]`; `abort(403)` if not
    - On GET: render `edit_expense.html` with the expense row and categories list
    - On POST: validate using the same rules as add_expense; on success call
      `update_expense(...)`, flash "Expense updated.", redirect to `/profile`
    - On validation failure: re-render `edit_expense.html` with the original
      `expense` row (for pre-filling) and `form` data (for preserving edits)
  - Import `get_expense_by_id` and `update_expense` from `database.db`

- `database/db.py`
  - Add `get_expense_by_id(expense_id)` — fetches one row by `id`
  - Add `update_expense(expense_id, amount, category, date, description)` —
    updates `amount`, `category`, `date`, `description` for the given `id`

- `database/queries.py`
  - Update `get_recent_transactions` to also `SELECT id` from expenses
  - Include `"id": r["id"]` in the dict built for each transaction row

## Files to create
- `templates/edit_expense.html` — the pre-filled edit form (see Templates section)

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
  `url_for("login")` with a flash message "Please sign in."
- Ownership check: if `expense["user_id"] != session["user_id"]`, call
  `abort(403)` — never silently redirect or skip the check
- Amount validation: must be a positive float greater than 0
- Category validation: must be one of the seven allowed values in `CATEGORIES`
- Date validation: use `datetime.strptime(date_str, "%Y-%m-%d")` — reject
  malformed dates with a flash error
- Description: strip whitespace; store `None` if blank after stripping
- On any validation failure: re-render the form; preserve the edited form
  values (not the stale DB values) so the user does not lose their changes
- After a successful update: `flash("Expense updated.")` and
  `redirect(url_for("profile"))`
- Currency display must use ₹ — never £ or $

## Definition of done
- [ ] Visiting `/expenses/1/edit` while logged out redirects to `/login` with a
      flash message
- [ ] Visiting `/expenses/1/edit` while logged in as a different user returns 403
- [ ] Visiting `/expenses/999/edit` (non-existent id) returns 404
- [ ] Visiting `/expenses/1/edit` while logged in as the owner renders the form
      with all four fields pre-filled with the expense's current values
- [ ] Submitting the form with valid changes updates the row in the database and
      redirects to `/profile` with "Expense updated." flashed
- [ ] The updated values appear in the Recent Transactions table on the profile page
- [ ] Submitting with a blank amount shows a validation error and re-renders the
      form without losing the other edited field values
- [ ] Submitting with amount `0` or a negative number shows a validation error
- [ ] Submitting with an invalid date string shows a validation error
- [ ] Submitting with a category not in the allowed list is rejected with a flash error
- [ ] An "Edit" link appears on every row in the Recent Transactions table on the
      profile page and navigates to the correct `/expenses/<id>/edit` URL
