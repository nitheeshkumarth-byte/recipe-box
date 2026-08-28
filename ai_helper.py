import os
import json
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))


def get_recipe_origin(title):
    """Ask Gemini about the likely cultural origin and history of a dish."""
    prompt = (
        f"In 3-4 sentences, describe the likely cultural origin and brief "
        f"history of the dish '{title}'. Be concise and factual. If the "
        f"dish is generic or you're unsure of its exact origin, say so "
        f"honestly rather than inventing details."
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

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

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    raw_text = response.text.strip()

    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        raw_text = raw_text.replace("json", "", 1).strip()

    try:
        return json.loads(raw_text)
    except (json.JSONDecodeError, ValueError):
        return None