"""Read the current account's recipe data and calculate with the saved values."""

import re
import unicodedata
from decimal import Decimal

from model import Recipe, RecipeIngredient, Tag
from recipe_access import recipe_query

NUMBER = r"(?:[0-9]{1,8} [0-9]{1,6}/[0-9]{1,6}|[0-9]{1,8}/[0-9]{1,6}|[0-9]{1,8}(?:\.[0-9]{1,6})?)"
SERVING_NUMBER = r"-?[0-9]{1,8}(?:\.[0-9]{1,3})?"
SERVINGS = re.compile(
    rf"(?<![\w.-])({SERVING_NUMBER})\s+(?:servings?|people|persons?|portions?|guests?)\b"
    rf"|\b(?:for|to|feed)\s+({SERVING_NUMBER})\s*(?=[?.,!]*$)", re.I,
)
HAVE = re.compile(rf"\b(?:with|have|using)\s+({NUMBER})\s+([a-z]+)\s+(?:of\s+)?([^?,;]+)", re.I)
SITE_HELP = re.compile(
    r"\b(?:offline|dark mode|theme|chatbot|swagger|sign in|log in|password|render|supabase)\b"
    r"|\bhow (?:do|can) i (?:add|create|upload|edit|delete|favorite|rate|search|filter|estimate)\b",
    re.I,
)
COLLECTION = re.compile(
    r"\b(?:how many|number of|count(?: of)?|list|show(?: me)?|which|search(?: for)?|find|do i have|all)\b"
    r".*\b(?:recipes|favorites|favourites)\b|\b(?:what|which|my|saved) (?:recipes|favorites|favourites)\b"
)
TOP_RATED = re.compile(r"\b(?:best rated|top rated|highest rated|highest rating)\b")
USES = re.compile(r"\b(?:recipes (?:that )?(?:use|using|contain|include|with)|(?:use|contain|include)) (.+)")
TAGGED = re.compile(r"\b(?:tagged|tag) (.+)")
TITLE_SEARCH = re.compile(r"\b(?:find|search(?: for)?) recipes? (?:for|called|named) (.+)")
SERVING_MATH = re.compile(r"\b(?:ingredients?|nutrition|calories|protein|carbs|fat|how much|scale|double|halve|triple)\b")
CONTEXT = re.compile(r"\b(?:this|that|it|its|same|the recipe)\b|^(?:and|what about|how about)\b")
NUTRIENTS = (
    ("calories", "calories", r"\b(?:calorie|calories|kcal)\b"),
    ("protein_g", "g protein", r"\bprotein\b"),
    ("carbs_g", "g carbs", r"\b(?:carbs?|carbohydrates?)\b"),
    ("fat_g", "g fat", r"\bfat\b"),
)
COMMON_WORDS = set("""
    a an and are about at be can compare could do does for from give have how in is it its many
    make me much of on or people please recipe recipes serving servings show tell that the this to
    use using what which with you your my ingredient ingredients nutrition calories calorie
    protein carbs fat rating stars rated origin instructions steps tag tags favorite favorites photo
    picture image scale list details data total amount amounts quantity need
""".split())
UNITS = {
    "g": ("mass", 1), "gram": ("mass", 1), "grams": ("mass", 1),
    "kg": ("mass", 1000), "kilogram": ("mass", 1000), "kilograms": ("mass", 1000),
    "ml": ("volume", 1), "milliliter": ("volume", 1), "milliliters": ("volume", 1),
    "l": ("volume", 1000), "liter": ("volume", 1000), "liters": ("volume", 1000),
    "tsp": ("spoon", 1), "teaspoon": ("spoon", 1), "teaspoons": ("spoon", 1),
    "tbsp": ("spoon", 3), "tablespoon": ("spoon", 3), "tablespoons": ("spoon", 3),
}


def normalize(value):
    return " ".join(re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", value).casefold()))


def phrase(value, text):
    return bool(value and f" {value} " in f" {text} ")


def search_pattern(value):
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def format_amount(value):
    if abs(value) >= Decimal("1000000000"):
        return f"{value:.4g}"
    formatted = f"{value:.3f}".rstrip("0").rstrip(".")
    if value and formatted in {"0", "-0"}:
        return f"{value:.3g}"
    return formatted


def recipe_matches(question, titles):
    exact = [(recipe_id, title, normalize(title)) for recipe_id, title in titles if phrase(normalize(title), question)]
    return [
        (recipe_id, title) for recipe_id, title, name in exact
        if not any(name != longer and phrase(name, longer) for _, _, longer in exact)
    ]


def collection_answer(question):
    recipes = recipe_query()
    if re.search(r"\bfavou?rites?\b", question):
        recipes = recipes.filter(Recipe.is_favorite.is_(True))
    if TOP_RATED.search(question) or re.search(r"\b(?:rated recipes|recipes (?:have been )?rated)\b", question):
        recipes = recipes.filter(Recipe.rating.is_not(None))
    tag = TAGGED.search(question)
    ingredient = USES.search(question)
    title = TITLE_SEARCH.search(question)
    if tag:
        recipes = recipes.filter(Recipe.tags.any(Tag.name.ilike(search_pattern(tag[1]), escape="\\")))
    elif ingredient:
        recipes = recipes.filter(Recipe.ingredient_lines.any(
            RecipeIngredient.name.ilike(search_pattern(ingredient[1]), escape="\\")
        ))
    elif title:
        recipes = recipes.filter(Recipe.title.ilike(search_pattern(title[1]), escape="\\"))
    if re.search(r"\b(?:total servings|how many servings)\b", question):
        portions = [row.servings for row in recipes.filter(Recipe.servings > 0).with_entities(Recipe.servings)]
        if not portions:
            return "I don't have any matching recipes with a saved serving count."
        return f"One batch of each of the {len(portions)} matching recipes makes {sum(portions)} servings. I added their saved serving counts."
    if re.search(r"\baverage rating\b", question):
        ratings = [row.rating for row in recipes.filter(Recipe.rating.is_not(None)).with_entities(Recipe.rating)]
        if not ratings:
            return "None of those recipes has a saved rating yet."
        average = format_amount(Decimal(sum(ratings)) / len(ratings))
        return f"The average rating is {average}/5 across {len(ratings)} rated recipes."
    metric = next(((field, unit) for field, unit, pattern in NUTRIENTS if re.search(pattern, question)), None)
    if metric:
        field, unit = metric
        column = getattr(Recipe, field)
        threshold = re.search(r"\b(more than|over|at least|less than|under|at most) ([0-9]{1,8})\b", question)
        if threshold:
            value = int(threshold[2])
            operator = {"more than": column.__gt__, "over": column.__gt__,
                        "at least": column.__ge__, "less than": column.__lt__,
                        "under": column.__lt__, "at most": column.__le__}
            recipes = recipes.filter(operator[threshold[1]](value))
        if re.search(r"\b(?:average|total)\b", question) and not threshold:
            values = recipes.filter(column.is_not(None)).with_entities(column, Recipe.servings).all()
            if not values:
                return "I don't have saved estimates for that nutrient in these recipes."
            if "average" in question.split():
                result = sum(value for value, _ in values) / Decimal(len(values))
                return f"The estimated average is {format_amount(result)} {unit} per serving. I averaged the saved values from {len(values)} recipes."
            batches = [(value, servings) for value, servings in values if servings > 0]
            if not batches:
                return "I need saved serving counts to calculate that total."
            total = sum(value * servings for value, servings in batches)
            return f"One full batch of each of the {len(batches)} recipes with saved values totals an estimated {format_amount(total)} {unit}. I multiplied by each recipe's serving count before adding them."
    count = recipes.count()
    if not count:
        return "I couldn't find any matching recipes in your box."
    if re.search(r"\b(?:how many|number of|count)\b", question):
        return f"You have {count} matching {'recipe' if count == 1 else 'recipes'}."
    if metric and re.search(r"\b(?:most|least|highest|lowest)\b", question):
        column = getattr(Recipe, metric[0])
        sorted_recipes = recipes.filter(column.is_not(None)).with_entities(Recipe.title, column)
        sort = column.asc() if re.search(r"\b(?:least|lowest)\b", question) else column.desc()
        row = sorted_recipes.order_by(sort, Recipe.title, Recipe.id).first()
        if not row:
            return "I don't have saved estimates for that nutrient in these recipes."
        return f"{row[0]} has an estimated {row[1]} {metric[1]} per serving."
    if TOP_RATED.search(question):
        recipes = recipes.order_by(Recipe.rating.desc(), Recipe.title, Recipe.id)
    else:
        recipes = recipes.order_by(Recipe.title, Recipe.id)
    rows = recipes.with_entities(Recipe.title, Recipe.rating).limit(12).all()
    lines = [f"- {title}" + (f" ({rating}/5)" if TOP_RATED.search(question) else "") for title, rating in rows]
    return f"Found {count} {'recipe' if count == 1 else 'recipes'}" + (" (first 12)" if count > 12 else "") + ":\n" + "\n".join(lines)


def requested_servings(question, base, remembered=None):
    match = SERVINGS.search(question)
    if match:
        return Decimal(match[1] or match[2])
    if re.search(r"\b(?:double|twice)\b", question, re.I):
        return base * 2
    if re.search(r"\b(?:halve|half (?:a|the|batch|recipe)|(?:make|scale) half)\b", question, re.I):
        return Decimal(base) / 2
    if re.search(r"\b(?:triple|three times)\b", question, re.I):
        return base * 3
    if remembered and not re.search(r"\b(?:original|usual|default)\b", question, re.I):
        return Decimal(str(remembered))
    return None


def ingredient_row(ingredient, multiplier=1):
    amount = Decimal(str(ingredient.amount))
    if not amount.is_finite() or amount <= 0:
        return f"{ingredient.name} (amount not specified)"
    unit = f"{ingredient.unit} " if ingredient.unit else ""
    return f"{format_amount(amount * multiplier)} {unit}{ingredient.name}"


def find_ingredients(recipe, question):
    terms = set(question.split()) - COMMON_WORDS
    return [
        item for item in recipe.ingredient_lines
        if terms & set(normalize(item.name).split())
    ]


def parse_number(value):
    parts = value.split()
    if "/" not in parts[-1]:
        return Decimal(value)
    numerator, denominator = map(Decimal, parts[-1].split("/"))
    return (Decimal(parts[0]) if len(parts) > 1 else 0) + numerator / denominator if denominator else None


def yield_answer(recipe, match):
    available = parse_number(match[1])
    available_unit = normalize(match[2])
    requested = normalize(match[3])
    matches = [
        item for item in recipe.ingredient_lines
        if phrase(normalize(item.name), requested) or phrase(requested, normalize(item.name))
    ]
    if len(matches) != 1:
        return f"Which single ingredient in {recipe.title} should I use for that calculation?"
    ingredient = matches[0]
    saved = Decimal(str(ingredient.amount))
    saved_unit = normalize(ingredient.unit or "")
    if available is None or not saved.is_finite() or saved <= 0 or recipe.servings <= 0:
        return f"I need valid, measured quantities to calculate servings for {recipe.title}."
    if available_unit.rstrip("s") != saved_unit.rstrip("s"):
        source = UNITS.get(available_unit)
        target = UNITS.get(saved_unit)
        if not source or not target or source[0] != target[0]:
            return f"{recipe.title} measures {ingredient.name} in {ingredient.unit or 'whole units'}. Give me your amount in that unit."
        available = available * source[1] / target[1]
    prepared = available * recipe.servings / saved
    return (
        f"About {format_amount(prepared)} servings of {recipe.title}, assuming you have enough of the other ingredients. "
        f"I divided {format_amount(available)} by the saved {format_amount(saved)} {ingredient.unit or 'units'} "
        f"of {ingredient.name}, then multiplied by {recipe.servings} servings."
    )


def nutrition_answer(recipe, question, target):
    selected = [(field, unit) for field, unit, pattern in NUTRIENTS if re.search(pattern, question)]
    selected = selected or [(field, unit) for field, unit, _ in NUTRIENTS]
    if re.search(r"\b(?:per serving|each serving)\b", question):
        target = None
    elif target is None and re.search(r"\b(?:whole|entire|batch|total)\b", question):
        target = recipe.servings
    values = [(getattr(recipe, field), unit) for field, unit in selected]
    if all(value is None for value, _ in values):
        return f"I don't have those nutrition estimates for {recipe.title} yet. Open the recipe and choose Estimate nutrition."
    if target is None:
        data = [f"{value} {unit}" for value, unit in values if value is not None]
        answer = f"{recipe.title} has an estimated {', '.join(data)} per serving."
    else:
        data = [f"{format_amount(value * target)} {unit}" for value, unit in values if value is not None]
        answer = f"For {format_amount(target)} servings of {recipe.title}, the estimated total is {', '.join(data)}. I multiplied each per-serving value by {format_amount(target)}."
    if any(value is None for value, _ in values):
        answer += " The other requested values aren't saved."
    return answer


def recipe_details(recipe, question, target):
    if re.search(r"\b(?:full recipe|whole recipe|all(?: the)? details|everything)\b", question) and target is None:
        tags = ", ".join(tag.name for tag in recipe.tags) or "No tags"
        rating = f"{recipe.rating}/5" if recipe.rating is not None else "Unrated"
        favorite = "Favorited" if recipe.is_favorite else "Outside favorites"
        info = [
            f"{recipe.title} • {recipe.servings} servings • {rating} • {favorite}",
            f"Tags: {tags}. {'Photo saved.' if recipe.image_filename else 'No photo saved.'}",
        ]
        if recipe.ingredient_lines:
            ingredients = "\n".join(f"- {ingredient_row(item)}" for item in recipe.ingredient_lines)
            info.append("Ingredients:\n" + ingredients)
        info.append("Instructions:\n" + recipe.instructions.strip()[:2500])
        if any(getattr(recipe, field) is not None for field, _, _ in NUTRIENTS):
            info.append(nutrition_answer(recipe, "", None))
        if recipe.origin and recipe.origin != "Unknown origin.":
            info.append("Saved origin: " + recipe.origin[:1000])
        return "\n\n".join(info)
    if any(re.search(pattern, question) for _, _, pattern in NUTRIENTS) or re.search(r"\b(?:nutrition|macros)\b", question):
        return nutrition_answer(recipe, question, target)
    if re.search(r"\b(?:how long|how many minutes|(?:prep|cook|cooking) time)\b", question):
        return f"{recipe.title} has no separate cooking-time field. Its saved instructions say:\n{recipe.instructions.strip()[:1200]}"
    if re.search(r"\b(?:instructions?|steps?|method|how (?:do i|to) (?:make|cook|prepare))\b", question) and target is None:
        instructions = recipe.instructions.strip()
        return f"How to make {recipe.title}:\n{instructions[:2500]}" + ("… Open the recipe for the rest." if len(instructions) > 2500 else "")
    if re.search(r"\bhow many (?:servings|portions)\b", question) and target is None:
        return f"{recipe.title} makes {recipe.servings} servings."
    if re.search(r"\b(?:ingredients?|how much|scale|adjust|double|halve|triple|amount|quantity)\b", question) or target is not None:
        if not recipe.ingredient_lines:
            return f"{recipe.title} doesn't have any saved ingredients."
        matches = find_ingredients(recipe, question)
        wanted = re.search(r"\bhow much (?!of |do |will |is |in |for |ingredient|amount)(\w+)", question)
        if wanted and not matches:
            return f"I couldn't find {wanted[1]} in the saved ingredients for {recipe.title}."
        if target is not None and recipe.servings <= 0:
            return f"{recipe.title} has no valid starting serving count, so I can't scale its ingredients."
        multiplier = Decimal(target) / recipe.servings if target is not None else 1
        lines = "\n".join(f"- {ingredient_row(item, multiplier)}" for item in matches or recipe.ingredient_lines)
        if target is None:
            return f"Ingredients for {recipe.title} ({recipe.servings} servings):\n{lines}"
        return (
            f"For {format_amount(target)} servings of {recipe.title}:\n{lines}\n"
            f"I multiplied the saved amounts by {format_amount(target)} ÷ {recipe.servings}."
        )
    if re.search(r"\b(?:origin|history|come from)\b", question):
        if not recipe.origin or recipe.origin == "Unknown origin.":
            return f"I don't have a saved origin for {recipe.title}."
        return f"Saved origin for {recipe.title}: {recipe.origin[:1000]}"
    if re.search(r"\b(?:rating|rated|stars?)\b", question):
        return f"{recipe.title} is rated {recipe.rating}/5." if recipe.rating is not None else f"{recipe.title} hasn't been rated yet."
    if re.search(r"\bfavou?rites?\b", question):
        return f"{recipe.title} is {'in' if recipe.is_favorite else 'not in'} your favorites."
    if re.search(r"\btags?\b", question):
        tags = ", ".join(tag.name for tag in recipe.tags)
        return f"Tags for {recipe.title}: {tags}." if tags else f"{recipe.title} has no saved tags."
    if re.search(r"\b(?:photo|image|picture)\b", question):
        return f"{recipe.title} has a photo on its recipe page." if recipe.image_filename else f"{recipe.title} has no saved photo."
    if re.search(r"\b(?:servings?|portions?)\b", question):
        return f"{recipe.title} makes {recipe.servings} servings."
    return (
        f"{recipe.title} makes {recipe.servings} servings and has {len(recipe.ingredient_lines)} saved ingredients."
        f"{f' You rated it {recipe.rating}/5.' if recipe.rating is not None else ''} Ask me for its ingredients, steps, or nutrition."
    )


def compare_recipes(recipes, question):
    metric = next(((field, unit) for field, unit, pattern in NUTRIENTS if re.search(pattern, question)), None)
    if metric is None and re.search(r"\b(?:rating|rated|stars?)\b", question):
        metric = ("rating", "/5")
    if metric is None:
        if re.search(r"\b(?:nutrition|macros)\b", question):
            return "\n".join(nutrition_answer(recipe, "", None) for recipe in recipes)
        return "\n".join(f"{recipe.title}: {recipe.servings} servings, {len(recipe.ingredient_lines)} ingredients" +
                         (f", {recipe.rating}/5" if recipe.rating is not None else "") + "." for recipe in recipes)
    field, unit = metric
    values = [getattr(recipe, field) for recipe in recipes]
    lines = [f"{recipe.title}: {f'{value} {unit}' if value is not None else 'no saved value'}" for recipe, value in zip(recipes, values)]
    if None not in values:
        gap = abs(values[0] - values[1])
        lines.append(f"Difference: {gap} {unit}" + (" per serving." if field != "rating" else "."))
    if field != "rating":
        lines.insert(0, "Saved estimates per serving:")
    return "\n".join(lines)


def answer_recipe_question(question, memory, page_recipe_id=None):
    """Return (reply, context) or None so normal site-help chat can answer."""
    if SITE_HELP.search(question):
        return None
    normalized = normalize(question)
    named_favorite_question = re.match(r"^is\b.+\b(?:a favorite|in my favou?rites)\b", normalized)
    if (COLLECTION.search(normalized) or TOP_RATED.search(normalized)) and not named_favorite_question:
        return collection_answer(normalized), None
    titles = recipe_query().with_entities(Recipe.id, Recipe.title).all()
    chosen = recipe_matches(normalized, titles)
    remaining = normalized
    for _, title in chosen:
        before, _, after = f" {remaining} ".rpartition(f" {normalize(title)} ")
        remaining = f"{before} {after}".strip()
    if len(chosen) > 1:
        if len(chosen) == 2 and len({normalize(title) for _, title in chosen}) == 2 and re.search(r"\b(?:compare|versus|vs|difference|higher|more|fewer)\b", remaining):
            compared = [recipe_query().filter_by(id=recipe_id).first() for recipe_id, _ in chosen]
            if all(compared):
                return compare_recipes(compared, remaining), None
        labels = ", ".join(title for _, title in chosen[:6])
        return f"I found multiple matches: {labels}. Which recipe should I use?", None
    if not chosen:
        context = memory[-1] if memory and "recipe_id" in memory[-1] else {}
        topic = re.search(r"\b(?:ingredients?|calories|nutrition|protein|carbs|fat|servings?|portions?|instructions?|steps?|origin|tags?|rating|stars?|favou?rites?|photo|image|scale|double|halve|triple|how much|how many|cook|how long)\b", normalized)
        if not topic and not (context and phrase("tell me more", normalized)):
            return None
        title_words = (set(normalized.split()) - COMMON_WORDS)
        partial = [(recipe_id, title) for recipe_id, title in titles
                   if title_words & (set(normalize(title).split()) - COMMON_WORDS)]
        use_page = phrase("this recipe", normalized) or phrase("this dish", normalized)
        match_context = (CONTEXT.search(normalized) or not title_words
                         or (SERVING_MATH.search(normalized) and not re.search(r"\b(?:in|about|named|called)\b", normalized)
                             and not re.search(r"\bfor (?![0-9]|the same\b|that\b|it\b)", normalized)))
        if partial and not use_page and not match_context:
            if len(partial) > 1:
                labels = ", ".join(title for _, title in partial[:6])
                return f"I found several matches: {labels}. Which recipe should I use?", None
            chosen = partial
        elif use_page and page_recipe_id:
            chosen = [(page_recipe_id, "")]
        elif context and match_context:
            chosen = [(context["recipe_id"], "")]
        elif page_recipe_id and not re.search(r"\b(?:of|about|named|called)\b", normalized):
            chosen = [(page_recipe_id, "")]
        elif not re.search(r"\b(?:recipe|dish|of|called|named)\b", normalized) and not match_context:
            return None
        else:
            return "Which recipe should I use? Tell me its title or open its recipe page.", None
    recipe = recipe_query().filter_by(id=chosen[0][0]).first()
    if recipe is None:
        return "I couldn't find that recipe in your box.", None
    context = memory[-1] if memory and memory[-1].get("recipe_id") == recipe.id else {}
    available = HAVE.search(question) if re.search(r"\bhow many (?:servings|portions)\b", remaining) else None
    if available:
        return yield_answer(recipe, available), {"recipe_id": recipe.id}
    remembered = context.get("servings") if SERVING_MATH.search(remaining) else None
    scaling_question = re.sub(re.escape(recipe.title), "", question, flags=re.I).strip()
    target = requested_servings(scaling_question, recipe.servings, remembered)
    if target is not None and not 0 < target <= 100_000:
        return "Enter a serving amount above zero and no more than 100,000.", None
    turn = {"recipe_id": recipe.id}
    if target is not None:
        turn["servings"] = str(target)
    return recipe_details(recipe, remaining, target), turn
