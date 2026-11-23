import os
import json
import logging
import math
import time
from dotenv import load_dotenv
from google import genai

load_dotenv()

logger = logging.getLogger(__name__)


class AIUnavailable(RuntimeError):
    pass

DEFAULT_MODEL = "gemini-3.5-flash-lite"

TRANSIENT_STATUS_CODES = (429, 500, 503)


def _generate(prompt):
    """Call Gemini with retries for transient API errors."""
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise AIUnavailable("AI features are unavailable until Gemini is configured.")
    model = os.getenv("GEMINI_MODEL") or DEFAULT_MODEL
    with genai.Client(api_key=key) as client:
        for attempt in range(3):
            try:
                return client.models.generate_content(model=model, contents=prompt).text
            except Exception as error:
                status = getattr(error, "code", None)
                if status in TRANSIENT_STATUS_CODES and attempt < 2:
                    time.sleep(2 * (attempt + 1))
                    continue
                logger.warning("Gemini request failed (%s)", type(error).__name__)
                raise AIUnavailable("Gemini is unavailable right now. Please try again.") from error


def _extract_json(raw_text):
    """Try to pull a JSON object out of Gemini's text response."""
    if not raw_text:
        raise AIUnavailable("Gemini returned an empty response. Please try again.")
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("json", "", 1).strip()

    try:
        data = json.loads(cleaned)
    except ValueError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        try:
            data = json.loads(cleaned[start:end + 1]) if start != -1 and end > start else None
        except ValueError:
            data = None
    if not isinstance(data, dict):
        raise AIUnavailable("Gemini returned an unexpected response. Please try again.")
    return data


def get_recipe_origin(title):
    """Ask Gemini about the likely cultural origin and history of a dish."""
    prompt = (
        f"In 3-4 sentences, describe the likely cultural origin and brief "
        f"history of the dish '{title}'. Be concise and factual. If the "
        f"dish is generic or you're unsure of its exact origin, say so "
        f"honestly rather than inventing details."
    )

    text = _generate(prompt)
    if not text or not text.strip():
        raise AIUnavailable("Gemini returned no origin information. Please try again.")
    return text.strip()


def get_nutrition_estimate(ingredient_lines, servings):
    """Ask Gemini to estimate nutrition per serving, given structured ingredients.
    Return a validated dictionary of integer values."""

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
        f"estimate, respond with an empty JSON object."
    )

    data = _extract_json(_generate(prompt))
    fields = ("calories", "protein_g", "carbs_g", "fat_g")
    if not all(type(data.get(field)) is int and 0 <= data[field] <= 2_147_483_647 for field in fields):
        raise AIUnavailable("Gemini could not provide a complete nutrition estimate.")
    return {field: data[field] for field in fields}


def get_recipe_suggestion(title):
    """Ask Gemini to suggest a recipe for a dish title.
    Returns a dict like:
      {"title": "...", "servings": 4, "ingredients": [
         {"amount": 2, "unit": "cups", "name": "rice"}, ...
       ], "instructions": "...", "tags": ["dinner"]}
    """

    prompt = (
        f"Suggest a recipe for the dish '{title}'.\n\n"
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

    data = _extract_json(_generate(prompt))
    servings = data.get("servings")
    ingredients = data.get("ingredients")
    instructions = data.get("instructions")
    tags = data.get("tags")
    suggested_title = data.get("title")
    if (
        not valid_text(suggested_title, 120)
        or type(servings) is not int or not 1 <= servings <= 2_147_483_647
        or not isinstance(ingredients, list) or not ingredients
        or not all(valid_ingredient(row) for row in ingredients)
        or not valid_text(instructions, 24_000)
        or not isinstance(tags, list)
        or not all(valid_text(tag, 50) and "," not in tag for tag in tags)
    ):
        raise AIUnavailable("Gemini returned an incomplete recipe. Please try again.")
    return {
        "title": suggested_title, "servings": servings, "ingredients": ingredients,
        "instructions": instructions, "tags": tags,
    }


def valid_text(value, max_length):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= max_length


def valid_ingredient(row):
    if not isinstance(row, dict):
        return False
    amount = row.get("amount")
    unit = row.get("unit")
    return (
        type(amount) in (int, float) and 0 <= amount <= 1e12 and math.isfinite(amount)
        and isinstance(unit, str) and len(unit) <= 20
        and valid_text(row.get("name"), 120)
    )
