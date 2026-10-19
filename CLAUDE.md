# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Activate virtual environment (Windows)
venv\Scripts\activate

# Run the dev server (port 5001)
python app.py

# Run tests
pytest

# Run a single test file
pytest tests/test_foo.py

# Install dependencies
pip install -r requirements.txt
```

## Architecture

**Spendly** is a Flask expense-tracker web app. The Python backend is in `app.py`; Jinja2 templates live in `templates/`; CSS and JS assets in `static/`.

### Template hierarchy

`base.html` defines the shared shell (navbar, footer, CSS/JS links). All other templates extend it via `{% extends "base.html" %}`. The landing page uses an extra stylesheet (`landing.css`) loaded in its `{% block head %}`.

### Route map (current)

| Route | Template | Status |
|---|---|---|
| `/` | `landing.html` | Done |
| `/register` | `register.html` | Done (stub) |
| `/login` | `login.html` | Done (stub) |
| `/terms` | `terms.html` | Done |
| `/privacy` | `privacy.html` | Done |
| `/logout` | — | Placeholder |
| `/profile` | — | Placeholder |
| `/expenses/add` | — | Placeholder |
| `/expenses/<id>/edit` | — | Placeholder |
| `/expenses/<id>/delete` | — | Placeholder |

### Database (`database/db.py`)

Not yet implemented. The file contains comments describing what to build in Step 1:
- `get_db()` — SQLite connection with `row_factory` and foreign keys enabled
- `init_db()` — `CREATE TABLE IF NOT EXISTS` for all tables
- `seed_db()` — sample data for development

### Vanilla JS

No framework is used. JavaScript is vanilla; the only global script is `static/js/main.js`. Page-specific JS goes in `{% block scripts %}` at the bottom of the template (see the YouTube modal in `landing.html` as the pattern to follow).

### Styling

Two stylesheets: `style.css` (global) and `landing.css` (landing page only). Font family is DM Sans / DM Serif Display from Google Fonts, loaded in `base.html`.
