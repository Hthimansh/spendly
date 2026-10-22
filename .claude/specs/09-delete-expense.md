# Spec: Delete Expense

## Overview
This feature lets a logged-in user permanently delete one of their own expenses. A
confirmation step (a POST-only route) prevents accidental deletion via a link or
prefetch. After a successful delete the user is redirected back to the profile page
with a flash message. The route already exists as a stub in `app.py`; this step
replaces that stub with a working implementation and adds a `delete_expense` helper
to `database/db.py`.

## Depends on
- Step 01 — Database setup (`expenses` table with `user_id` FK)
- Step 05 — Backend routes / profile page (session handling pattern)
- Step 07 — Add expense (profile page transaction list where the Delete button lives)
- Step 08 — Edit expense (`get_expense_by_id` ownership check pattern)

## Routes
- `POST /expenses/<id>/delete` — delete the expense owned by the current user and
  redirect to `/profile` — **logged-in only**

The existing `GET /expenses/<id>/delete` stub must be converted to `POST` only.
No standalone confirmation page is needed; the confirmation is a small inline modal
triggered from the profile page.

## Database changes
No new tables or columns.

A new helper is needed in `database/db.py`:

```python
def delete_expense(expense_id):
    """Delete one expense row by primary key."""
```

## Templates
- **Modify:** `templates/profile.html` — add a delete button/form next to each
  transaction row; the button triggers a confirmation modal; on confirm it submits
  the hidden `<form method="POST">` for that expense id.

No new templates required.

## Files to change
- `app.py` — replace the stub `delete_expense` route with a POST-only handler that:
  1. Requires login
  2. Fetches the expense by id (404 if missing)
  3. Checks ownership (403 if not the current user)
  4. Calls `db_delete_expense(id)`
  5. Flashes "Expense deleted." and redirects to `profile`
- `database/db.py` — add `delete_expense(expense_id)` function
- `templates/profile.html` — add delete button + confirmation modal per row

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only (`DELETE FROM expenses WHERE id = ?`)
- Passwords hashed with werkzeug (not relevant here but keep existing usage)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Delete route must be **POST only** — return 405 on GET
- Ownership check is mandatory: `expense["user_id"] != session["user_id"]` → 403
- Confirmation modal must be pure HTML/CSS/vanilla JS (no external libraries)
- The form for deletion must include the expense id in the URL, not a hidden field
- Import `delete_expense as db_delete_expense` in `app.py` alongside the existing imports

## Definition of done
- [ ] `POST /expenses/<id>/delete` deletes the row and redirects to `/profile` with
      flash "Expense deleted."
- [ ] `GET /expenses/<id>/delete` returns 405 (Method Not Allowed)
- [ ] Attempting to delete another user's expense returns 403
- [ ] Attempting to delete a non-existent expense id returns 404
- [ ] The profile page shows a Delete button on each transaction row
- [ ] Clicking Delete opens a confirmation modal ("Are you sure?")
- [ ] Confirming in the modal submits the POST form and removes the expense
- [ ] Cancelling the modal leaves the expense intact
- [ ] After deletion the profile page statistics update to exclude the deleted expense
