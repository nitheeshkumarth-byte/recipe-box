# 🍲 Recipe Box

A personal recipe manager built with Flask and SQLite. Store your recipes with photos, structured ingredients, and tags — plus a couple of AI-powered helpers (dish origin and nutrition estimates) powered by Google Gemini.

## Features

- **Full recipe CRUD** — add, edit, view, and delete recipes
- **Photo uploads** — PNG / JPG / JPEG / GIF / WebP (max 5 MB)
- **Structured ingredients** — parallel amount / unit / name rows
- **Servings scaler** — change the serving count on a recipe page and ingredient amounts (and nutrition) rescale client-side
- **Search & filtering** — search by title, filter by tag, and bookmark favorites
- **Rating** — 1–5 star ratings per recipe
- **Pagination** — 9 recipes per page
- **✨ Dish origin** — one click asks Gemini for the cultural origin and history of a dish
- **🥗 Nutrition estimates** — one click asks Gemini for per-serving calories / protein / carbs / fat
- **AI results are cached** in the DB, so they're only fetched once per recipe

## Tech Stack

- **Backend:** Python · Flask · Flask-SQLAlchemy · Flask-Migrate (Alembic)
- **Database:** SQLite (`instance/recipes.db`)
- **AI:** Google Generative AI (`google-genai`, Gemini `gemini-2.5-flash`)
- **Frontend:** Jinja2 templates · vanilla JS · custom CSS
- **Server:** `gunicorn` (production)

## Setup

### Prerequisites

- Python 3.10+
- A [Google AI](https://aistudio.google.com/) API key for the AI features

### 1. Clone and install

```bash
git clone <your-repo-url>
cd recipie-box

# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# macOS / Linux
# python -m venv .venv
# source .venv/bin/activate
# pip install -r requirements.txt
```

### 2. Configure secrets

Copy `.env` (or create one) with your keys:

```bash
SECRET_KEY=your-secret-key
GEMINI_API_KEY=your-google-ai-api-key
```

> `.env` is gitignored — never commit it. The `SECRET_KEY` falls back to a dev value if unset, and the app will start without a Gemini key, but the AI features won't work until `GEMINI_API_KEY` is set.

### 3. Set up the database

```bash
# Windows
$env:FLASK_APP="app.py"
.venv\Scripts\python.exe -m flask db upgrade

# macOS / Linux
# export FLASK_APP=app.py
# flask db upgrade
```

### 4. Run

```bash
# Development
.venv\Scripts\python.exe app.py
# -> http://127.0.0.1:5000
```

Or with a debug loopback server:

```bash
.venv\Scripts\python.exe -m flask run --debug
```

### Production (gunicorn)

```bash
gunicorn app:app
```

## AI Features

The two AI buttons on a recipe's detail page call the Gemini API:

- **✨ Where does this dish come from?** — returns 3–4 sentences on the dish's likely cultural origin and history.
- **🥗 Estimate nutrition** — returns a per-serving estimate for calories, protein, carbs, and fat based on the structured ingredient list.

Results are saved to the recipe, so subsequent visits don't re-call the API. Nutrition is recomputed automatically when ingredients change on edit.

## Project Structure

```
recipie-box/
├── app.py                 # Flask app, routes, helpers, file uploads
├── model.py               # SQLAlchemy models (Recipe, Ingredient, Tag)
├── ai_helper.py           # Gemini calls for origin & nutrition
├── requirements.txt
├── .env                   # secrets (gitignored)
├── static/
│   ├── style.css
│   └── uploads/           # uploaded recipe photos (gitignored)
├── templates/
│   ├── base.html
│   ├── index.html         # recipe list / search / pagination
│   ├── recipe.html        # recipe detail + AI features
│   └── add.html           # add / edit form
├── migrations/            # Alembic migration scripts
└── instance/              # SQLite database lives here
```

## Migrations

After changing `model.py`, generate and apply a new migration:

```bash
flask db migrate -m "description of change"
flask db upgrade
```

## License

Personal use project.
