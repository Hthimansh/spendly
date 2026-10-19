# Spec: Login and Logout

## Overview
Implement session-based login and logout so registered users can authenticate with Spendly. This step upgrades the stub `GET /login` route into a fully functional form that accepts a POST, validates credentials against the `users` table, starts a Flask session on success, and redirects to the dashboard (or a placeholder). The `GET /logout` stub is replaced with a route that clears the session and redirects to the landing page. Together these gates protect all future authenticated routes.

## Depends on
- Step 01 — Database setup (`users` table, `get_db()`)
- Step 02 — Registration (`create_user()`, hashed passwords in DB)

## Routes
- `GET /login` — render login form — public (already exists as stub, upgrade it)
- `POST /login` — validate credentials, start session, redirect — public
- `GET /logout` — clear session, redirect to `/` — public (already exists as placeholder, implement it)

## Database changes
No new tables or columns.

A new DB helper must be added to `database/db.py`:
- `get_user_by_email(email)` — looks up a single row from `users` by email, returns the row as a `sqlite3.Row` or `None` if not found. Used by the login route to fetch the stored `password_hash` for verification.

## Templates
- **Modify**: `templates/login.html`
  - Change the form `action` to `url_for('login')` with `method="post"`
  - Add `name` attributes to all inputs: `email`, `password`
  - Add a block to display a flash error message (e.g. "Invalid email or password")
  - Keep all existing visual design

## Files to change
- `app.py` — upgrade `login()` to handle `GET` and `POST`; add session logic; implement `logout()`; import `session` from Flask
- `database/db.py` — add `get_user_by_email()` helper
- `templates/login.html` — wire up form action/method and flash message display

## Files to create
None.

## New dependencies
No new dependencies. Uses `werkzeug.security.check_password_hash` (already installed) and Flask's built-in `session`, `flash`, `redirect`, `url_for`.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never use f-strings in SQL
- Verify passwords with `werkzeug.security.check_password_hash` — never compare plaintext
- Use Flask's `session` dict to store the logged-in user: store `session["user_id"]` and `session["user_name"]` on successful login
- `app.secret_key` is already set in `app.py` — do not change it
- Server-side validation must check:
  1. Both fields are non-empty
  2. A user row exists for the submitted email
  3. `check_password_hash` returns `True` for the submitted password
- On any validation failure, re-render the form with a single generic flash message: "Invalid email or password" (do not reveal which field failed)
- On success, `flash` a welcome message and `redirect` to `url_for('profile')` (which is still a placeholder — that is fine)
- `logout()` must call `session.clear()` then redirect to `url_for('landing')`
- All templates extend `base.html`
- Use CSS variables — never hardcode hex values
- Use `url_for()` for every internal link — never hardcode URLs

## Definition of done
- [ ] `GET /login` renders the login form without errors
- [ ] Submitting valid credentials starts a session (`session["user_id"]` is set) and redirects to `/profile`
- [ ] Submitting an unregistered email re-renders the form with "Invalid email or password" — no session started
- [ ] Submitting the correct email but wrong password re-renders the form with "Invalid email or password" — no session started
- [ ] Submitting with any empty field re-renders the form with a validation error
- [ ] `GET /logout` clears the session and redirects to `/`
- [ ] After logout, `session["user_id"]` is no longer present
- [ ] The demo user (`demo@spendly.com` / `demo123`) can log in successfully
