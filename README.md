# 🍲 Recipe Box

A personal recipe manager built with Flask, with SQLite for local development and Supabase PostgreSQL on Render. Store recipes with photos, structured ingredients, and tags, and use optional Gemini helpers for dish origins, nutrition estimates, and recipe suggestions.

For individual accounts, Render environments, background processing, backup drills, and the iOS and Android app, see [Operations](docs/operations.md).

## Features

- **Full recipe CRUD** — add, edit, view, and delete recipes
- **✨ Recipe auto-fill** — on the Add page, enter a dish title to draft an AI-generated recipe with servings, ingredients, instructions, and tags. Review the suggestion before saving.
- **Photo uploads** — PNG / JPG / JPEG / GIF / WebP (max 5 MB)
- **Structured ingredients** — parallel amount / unit / name rows with an "Add ingredient" slot
- **Servings scaler** — change the serving count to rescale ingredients. Estimated nutrition stays per serving.
- **Search & filtering** — search by partial text across title, instructions, ingredients, and tags; filter by tag and bookmark favorites
- **Swipeable recipe deck** — swipe, drag, or use the arrow controls to browse recipe cards. Select a card to open it, or switch to List to browse the page at a glance.
- **Project-aware chef chat** — ask how Recipe Box works, get references to source files, and ask follow-up questions within the same session.
- **Rating** — compact single-star display with a 1–5 dropdown to rate
- **Pagination** — 9 recipes per page
- **✨ Dish origin** — one click asks Gemini for the cultural origin and history of a dish
- **🥗 Nutrition estimates** — one click asks Gemini for per-serving calories / protein / carbs / fat
- **AI results are cached** in the DB, so they're only fetched once per recipe

## Tech Stack

- **Backend:** Python · Flask · Flask-SQLAlchemy · Flask-Migrate (Alembic)
- **Database:** SQLite (`instance/recipes.db`) or PostgreSQL via `DATABASE_URL`
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

Create a local `.env` as needed:

```bash
# Optional locally. Use a stable, randomly generated key in production.
SECRET_KEY=
GEMINI_API_KEY=
```

The app runs locally without either setting. Without `SECRET_KEY`, sessions reset when the app restarts. Photos are stored under `instance/uploads/` locally. The app also serves existing photos from `static/uploads/` in local mode.

### 3. Run locally

```bash
# Development
.venv\Scripts\python.exe app.py
# -> http://127.0.0.1:5000
```

Running `app.py` directly upgrades and uses `instance/recipes.db` and local uploads. This keeps local development separate even when `.env` contains a Render or Supabase configuration. Use `--port 5001` if port 5000 is occupied.

To use Flask's debug runner on Windows, first select the local database and apply its migrations:

```powershell
$env:RECIPE_BOX_LOCAL="1"
.venv\Scripts\python.exe -m flask --app app db upgrade
.venv\Scripts\python.exe -m flask --app app run --debug
```

Use `python app.py --configured-services` to test against the services configured in `.env`. A configured PostgreSQL database must be migrated separately before starting that way.

### Render and Supabase

Use `bash scripts/start_web.sh` as the Render start command, `bash scripts/migrate.sh` as the pre-deploy command, and `/readyz` as the HTTP health check path.

Set these variables in the Render service:

| Variable | What to set |
| --- | --- |
| `DATABASE_URL` | The existing Supabase PostgreSQL connection string for the app. |
| `SECRET_KEY` | A stable random key shared by all workers. Generate one with `python -c "import secrets; print(secrets.token_hex(32))"`. |
| `RECIPE_BOX_PASSWORD` | Legacy single-user mode only. Use a strong password for username `recipebox`. Account mode uses Supabase Auth instead. |
| `S3_ENDPOINT`, `S3_REGION`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` | The existing Supabase Storage S3-compatible configuration. |
| `S3_BUCKET`, `S3_PREFIX` | The existing photo bucket (default `uploads`) and optional folder. |
| `IMAGE_BASE_URL` | Optional public bucket URL used as a photo fallback. Private recipe access does not make a public bucket private. |
| `GEMINI_API_KEY` | Optional key for recipe suggestions, origin and nutrition. |
| `CHEF_RAG_PROVIDER` | Defaults to `local`. Set to `gemini` only if you want the chef to send filtered questions and selected project excerpts to the configured Gemini API for synthesis. |

Keep the existing database and photo-storage settings when updating an already deployed service. The SQLite import script is only for moving data into an empty PostgreSQL database. It does not copy photos.

The app loads deployed recipe photos from Supabase using the S3 settings. It can also serve photos present in `instance/uploads/` or the legacy `static/uploads/` folder. If a deployed photo is missing, check that the stored recipe filename matches an object in the configured bucket.

In Add Recipe or Edit Recipe, enter a dish title and choose **Generate Photo**. Recipe Box searches Wikimedia Commons for reference titles and a public-domain or CC0 reference image, then asks Gemini to generate a new photo. The editor indicates when Gemini used the title alone. A paid Gemini API project is required. Use `GEMINI_API_KEY` to enable generation and `GEMINI_IMAGE_MODEL` to override the default `gemini-nano-banana-2.1` model. Saving the recipe stores the photo through the usual upload flow and keeps its file key as a string in PostgreSQL.

Browser forms and Swagger UI include a session-bound CSRF token. Custom API consumers should keep the session cookie from a page request and send the page's `csrf-token` meta value as `X-CSRF-Token` on POST requests.

Run the local regression checks with `python -m unittest discover -s tests -v`.

## Chef chat and session memory

The chef answers site questions and looks up saved recipe data the current account can access. It calculates ingredient quantities and nutrition totals from saved values and explains the arithmetic. Recipe answers run on the server without sending recipe records to Gemini. For site help, optional Gemini mode uses only vetted project excerpts.

The session cache stores up to eight turns of context under a hashed browser session key. Recipe turns keep the recipe ID and any serving target. The app checks access again before reading the recipe. The cache does not store transcripts, recipe text, or raw questions and answers. Entries expire after 30 minutes of inactivity.

Run `flask --app app db upgrade` before serving the new chat on an existing database. On Supabase, the chat cache table has row-level security enabled. Apply the migration using the same database role the app uses so the server can access its own table.

## AI Features

The AI features call the Gemini API:

- **✨ Auto-fill recipe** (Add page) — type a dish title and Gemini drafts a recipe that auto-fills the form. An exact title already in the recipe box is flagged before the request reaches Gemini.
- **✨ Where does this dish come from?** (recipe detail) — returns 3–4 sentences on the dish's likely cultural origin and history.
- **🥗 Estimate nutrition** (recipe detail) — returns a per-serving estimate for calories, protein, carbs, and fat based on the structured ingredient list.

Successful origin and nutrition results are cached. Changing the title clears the origin. Changing the ingredients or servings clears the nutrition estimate so it can be requested again.

## Project Structure

```
recipie-box/
├── app.py                 # Flask app, routes, helpers, file uploads
├── model.py               # SQLAlchemy models (Recipe, Ingredient, Tag)
├── ai_helper.py           # Gemini calls: origin, nutrition, recipe auto-fill
├── requirements.txt
├── .env                   # secrets (gitignored)
├── static/
│   ├── style.css
│   └── uploads/           # bundled recipe photos
├── templates/
│   ├── base.html
│   ├── index.html         # recipe list / filmstrip + search / filtering
│   ├── recipe.html        # recipe detail + AI features
│   └── add.html           # add / edit form + auto-fill
├── migrations/            # Alembic migration scripts
└── instance/              # local SQLite database and uploads
```

## Migrations

After changing `model.py`, generate and apply a new migration:

```bash
flask db migrate -m "description of change"
flask db upgrade
```

## License

Personal use project.
