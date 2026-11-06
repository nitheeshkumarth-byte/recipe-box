import os
import json
import time
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

MODEL = "gemini-2.5-flash"

TRANSIENT_STATUS_CODES = (429, 500, 503)


def _generate(prompt):
    """Call Gemini with retries for transient API errors."""
    last_error = None
    for attempt in range(3):
        try:
            return client.models.generate_content(
                model=MODEL,
                contents=prompt
            )
        except Exception as e:
            last_error = e
            status = getattr(e, "code", None)
            if status not in TRANSIENT_STATUS_CODES:
                raise
            time.sleep(2 * (attempt + 1))
    raise last_error


def _extract_json(raw_text):
    """Try to pull a JSON object out of Gemini's text response."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("json", "", 1).strip()

    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(cleaned[start:end + 1])
        except (json.JSONDecodeError, ValueError):
            pass

    return None


def get_recipe_origin(title):
    """Ask Gemini about the likely cultural origin and history of a dish."""
    prompt = (
        f"In 3-4 sentences, describe the likely cultural origin and brief "
        f"history of the dish '{title}'. Be concise and factual. If the "
        f"dish is generic or you're unsure of its exact origin, say so "
        f"honestly rather than inventing details."
    )

    try:
        response = _generate(prompt)
    except Exception:
        return "Unknown origin."
    return response.text


def get_nutrition_estimate(ingredient_lines, servings):
    """Ask Gemini to estimate nutrition per serving, given structured ingredients.
    Returns a dict like {"calories": 320, "protein_g": 12, "carbs_g": 40, "fat_g": 10}
    or None if the response couldn't be parsed."""

    ingredients_text = "\n".join(
        f"- {ing.amount} {ing.unit or ''} {ing.name}".strip()
        for ing in ingredient_lines
    )

    prompt = (
        f"Estimate the nutrition facts PER SERVING for a recipe that makes "
        f"{servings} servings, using this ingredient list:\n\n"
        f"{ingredients_text}\n\n"
        f"Respond with ONLY a JSON object, no other text, no markdown formatting, "
        f"in exactly this shape:\n"
        f'{{"calories": <number>, "protein_g": <number>, "carbs_g": <number>, "fat_g": <number>}}\n'
        f"These are estimates — round to whole numbers. If you cannot reasonably "
        f"estimate, use 0 for all values."
    )

    try:
        response = _generate(prompt)
    except Exception:
        return None

    return _extract_json(response.text)


def get_recipe_from_web(title):
    """Ask Gemini to return a well-known online recipe for a dish title.
    Returns a dict like:
      {"title": "...", "servings": 4, "ingredients": [
         {"amount": 2, "unit": "cups", "name": "rice"}, ...
       ], "instructions": "...", "tags": ["dinner"]}
    or None if the response couldn't be parsed."""

    prompt = (
        f"Find a well-known, genuine published recipe for the dish '{title}'. "
        f"Use your knowledge of real online recipes.\n\n"
        f"Respond with ONLY a JSON object, no other text, no markdown formatting, "
        f"in exactly this shape:\n"
        f'{{\n'
        f'  "title": "<recipe title>",\n'
        f'  "servings": <integer>,\n'
        f'  "ingredients": [{{"amount": <number>, "unit": "<unit or empty string>", "name": "<ingredient>"}}],\n'
        f'  "instructions": "<complete step-by-step instructions as a single string>",\n'
        f'  "tags": ["<one or two relevant tags>"]\n'
        f'}}\n\n'
        f"Rules:\n"
        f"- Use real ingredient quantities and units.\n"
        f"- Amount can be 0 if there is no sensible numeric amount.\n"
        f"- Keep tags short single words (e.g. dinner, dessert, quick).\n"
        f"- Provide complete, usable cooking instructions."
    )

    try:
        response = _generate(prompt)
    except Exception:
        return None

    data = _extract_json(response.text)

    if data is None:
        return None

    data.setdefault("title", title)
    data.setdefault("servings", 4)
    data.setdefault("ingredients", [])
    data.setdefault("instructions", "")
    data.setdefault("tags", [])
    return data