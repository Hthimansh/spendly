# Spec: Date Filter for Profile Page

## Overview
Step 6 adds a date-range filter to the profile page so users can narrow
the summary stats, transaction list, and category breakdown to a chosen
period. The filter is driven by two query-string parameters (`from` and
`to`) on the existing `GET /profile` route. Preset shortcuts (This Month,
Last Month, Last 3 Months, All Time) are rendered as buttons alongside
optional manual date inputs. All three data sections — stats, transactions,
and category breakdown — respect the active filter. When no filter is
supplied the page defaults to showing all expenses (All Time behaviour).

## Depends on
- Step 1: Database setup (`expenses` table with `date` column exists)
- Step 3: Login / Logout (`session["user_id"]` is set on login)
- Step 4: Profile page static UI (template already renders all three sections)
- Step 5: Backend routes wired to live DB queries (`database/queries.py` exists)

## Routes
No new routes. The existing `GET /profile` route is extended to read two
optional query-string parameters:
- `?from=YYYY-MM-DD` — inclusive start date
- `?to=YYYY-MM-DD`   — inclusive end date

Both parameters are optional. If either is absent the corresponding bound
is treated as unbounded (i.e. no lower/upper date limit applied).

## Database changes
No database changes. The `expenses` table already has a `date TEXT` column
stored as `YYYY-MM-DD`.

## Templates
- **Modify**: `templates/profile.html`
  - Add a filter bar above the stats section containing:
    - Four preset buttons: **This Month**, **Last Month**, **Last 3 Months**, **All Time**
    - Two `<input type="date">` fields labeled **From** and **To**
    - An **Apply** button that submits the custom date range
  - The active preset (or custom range) should be visually highlighted
  - A small label below the filter bar shows the currently active range,
    e.g. "Showing: Oct 2026" or "Showing: all time"
  - All three data sections (stats, transactions, category breakdown) already
    use Jinja variables — no structural changes needed beyond ensuring the
    filter state is passed through correctly

## Files to change
- `app.py`
  - In the `profile()` view: read `request.args.get("from")` and
    `request.args.get("to")`, validate they are either empty or valid
    `YYYY-MM-DD` strings, then pass them as `date_from` / `date_to`
    keyword arguments to all three query helpers.
  - Pass `date_from`, `date_to` back to the template as `filter_from` and
    `filter_to` so the filter UI can reflect the active state.
- `database/queries.py`
  - `get_recent_transactions(user_id, date_from=None, date_to=None)`
    — add optional `WHERE date >= ?` and/or `WHERE date <= ?` clauses
  - `get_summary_stats(user_id, date_from=None, date_to=None)`
    — same date bounds applied to the SELECT
  - `get_category_breakdown(user_id, date_from=None, date_to=None)`
    — same date bounds applied to the SELECT
- `templates/profile.html`
  - Add filter bar UI (see Templates section above)

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format values into SQL
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles
- Date validation in `app.py` must use `datetime.strptime` with `"%Y-%m-%d"`;
  silently ignore malformed dates (treat as unset) rather than raising 400
- Preset buttons must build their date range in Python-style terms relative
  to today's date and pass them as query params via `url_for("profile", **{...})`
  links or a small JS snippet that sets the form inputs — use JS only for
  the preset shortcuts, not for any server-side logic
- The "All Time" preset clears both bounds (links to `/profile` with no params)
- Currency must always display as ₹ — never £ or $
- If the filtered result is empty, all three sections must show zero/empty
  gracefully (no exceptions) — same behaviour as a new user with no expenses

## Definition of done
- [ ] Visiting `/profile` with no query params shows all expenses (unchanged behaviour from Step 5)
- [ ] Clicking **This Month** reloads the page and stats/transactions/category breakdown
      reflect only expenses whose `date` falls in the current calendar month
- [ ] Clicking **Last Month** shows only last calendar month's expenses
- [ ] Clicking **Last 3 Months** shows the rolling 90-day window
- [ ] Clicking **All Time** removes the filter and shows all expenses
- [ ] Entering a custom `from` and `to` date and clicking **Apply** shows only
      expenses within that inclusive date range
- [ ] The active filter label ("Showing: …") updates to reflect the current range
- [ ] A date range that matches no expenses shows ₹0.00 total, 0 transactions,
      and an empty category breakdown — no server errors
- [ ] A malformed `?from=` or `?to=` value in the URL is silently ignored and
      the page renders as if that bound were unset
- [ ] All amounts still display the ₹ symbol under every filter state
