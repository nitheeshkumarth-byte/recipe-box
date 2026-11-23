import { api, escape, photoMarkup } from './api.js';

function recipeAction(button, status, action) {
    return async event => {
        event.preventDefault();
        button.disabled = true;
        status.textContent = '';
        try {
            await action();
        } catch (error) {
            status.textContent = error.message;
        } finally {
            button.disabled = false;
        }
    };
}

export function renderRecipe(content, recipe) {
    document.title = `${recipe.title} · Recipe Box`;
    const chat = document.getElementById('chef-chat');
    chat.dataset.recipeId = recipe.id;
    const [ingredients, scale] = chat.querySelectorAll('[data-question]');
    ingredients.dataset.question = 'What are the ingredients for this recipe?';
    ingredients.textContent = 'Ingredients';
    scale.dataset.question = 'Scale this recipe for 8 servings';
    scale.textContent = 'Scale to 8 servings';
    content.innerHTML = `
        <a class="back-link" href="/">← Back to all recipes</a>
        ${photoMarkup(recipe.photo).replace('<img ', '<img class="recipe-photo" ')}
        <article class="recipe-card">
            <h1>${escape(recipe.title)}</h1>
            <div class="tags">${recipe.tags.map(tag => `<a class="tag" href="/?${escape(new URLSearchParams({ tag }))}">${escape(tag)}</a>`).join('')}</div>
            <p id="recipe-origin">${escape(recipe.origin)}</p>
            <button type="button" id="find-origin">Find recipe origin</button>
            <h2>Ingredients</h2>
            <label>Servings <input id="servings" type="number" min="1" max="2147483647" value="${recipe.servings}"></label>
            <ul id="ingredients"></ul>
            <h2>Instructions</h2>
            <p class="recipe-instructions">${escape(recipe.instructions)}</p>
            <h2>Nutrition</h2>
            <p id="nutrition-facts"></p>
            <button type="button" id="estimate-nutrition">Estimate nutrition</button>
            <form id="rating-form" class="rating-form">
                <label>Rating <select name="rating" required>
                    <option value="">Rate this recipe</option>
                    ${[1, 2, 3, 4, 5].map(rating => `<option value="${rating}"${rating === recipe.rating ? ' selected' : ''}>${rating} ${rating === 1 ? 'star' : 'stars'}</option>`).join('')}
                </select></label>
                <button>Rate</button>
            </form>
            <p role="status" id="recipe-status"></p>
            <div class="actions-bar">
                <a class="btn" href="/edit/${recipe.id}">Edit</a>
                <button type="button" id="favorite"></button>
                <button type="button" class="delete-action-btn" id="delete">Delete</button>
            </div>
        </article>`;

    const status = content.querySelector('#recipe-status');
    const servings = content.querySelector('#servings');
    const amounts = content.querySelector('#ingredients');
    const number = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 });
    function updateAmounts() {
        if (!servings.value || !servings.checkValidity()) return;
        amounts.innerHTML = recipe.ingredients.map(ingredient => `<li>${escape(number.format(ingredient.amount * Number(servings.value) / recipe.servings))} ${escape(ingredient.unit)} ${escape(ingredient.name)}</li>`).join('');
    }
    servings.addEventListener('input', updateAmounts);
    updateAmounts();

    const favorite = content.querySelector('#favorite');
    function showFavorite(value) {
        favorite.textContent = value ? 'Remove from Favorites' : 'Add to Favorites';
        favorite.setAttribute('aria-pressed', String(value));
    }
    showFavorite(recipe.favorite);
    favorite.addEventListener('click', recipeAction(favorite, status, async () => {
        const result = await api(`/api/recipes/${recipe.id}/favorite`, { method: 'POST' });
        showFavorite(result.favorite);
    }));

    const ratingForm = content.querySelector('#rating-form');
    ratingForm.addEventListener('submit', recipeAction(ratingForm.querySelector('button'), status, async () => {
        await api(`/api/recipes/${recipe.id}/rating`, { method: 'POST', body: new FormData(ratingForm) });
        status.textContent = 'Rating saved.';
    }));

    const deleteButton = content.querySelector('#delete');
    deleteButton.addEventListener('click', recipeAction(deleteButton, status, async () => {
        if (!window.confirm('Delete this recipe?')) return;
        await api(`/api/delete/${recipe.id}`, { method: 'POST' });
        location.assign('/');
    }));

    const origin = content.querySelector('#recipe-origin');
    const originButton = content.querySelector('#find-origin');
    originButton.addEventListener('click', recipeAction(originButton, status, async () => {
        origin.textContent = (await api(`/api/origin/${recipe.id}`, { method: 'POST' })).origin;
    }));

    const nutrition = content.querySelector('#nutrition-facts');
    function showNutrition(data) {
        nutrition.textContent = data.calories == null ? 'No nutrition estimate saved.' :
            `Per serving: ${data.calories} kcal · Protein ${data.protein_g ?? '—'} g · Carbs ${data.carbs_g ?? '—'} g · Fat ${data.fat_g ?? '—'} g`;
    }
    showNutrition(recipe.nutrition);
    const nutritionButton = content.querySelector('#estimate-nutrition');
    nutritionButton.addEventListener('click', recipeAction(nutritionButton, status, async () => {
        showNutrition(await api(`/api/nutrition/${recipe.id}`, { method: 'POST' }));
    }));
}

function ingredientRow(ingredient = {}) {
    return `<div class="ingredient-row">
        <input type="number" min="0" step="any" name="ing_amount" aria-label="Amount" placeholder="Amount" value="${escape(ingredient.amount)}">
        <input name="ing_unit" maxlength="20" aria-label="Unit" placeholder="Unit" value="${escape(ingredient.unit)}">
        <input name="ing_name" maxlength="120" aria-label="Ingredient name" placeholder="Ingredient name" value="${escape(ingredient.name)}">
        <button type="button" data-remove-ingredient aria-label="Remove ingredient">×</button>
    </div>`;
}

export function renderEditor(content, recipe) {
    const defaultServings = recipe?.servings ?? 4;
    content.innerHTML = `
        <a href="${recipe ? `/recipe/${recipe.id}` : '/'}" class="back-link">← Back</a>
        <h1>${recipe ? 'Edit recipe' : 'Add recipe'}</h1>
        <form id="recipe-editor" class="recipe-card">
            <label>Title <input name="title" required maxlength="120" value="${escape(recipe?.title)}"></label>
            ${recipe ? '' : '<button type="button" id="auto-fill">Auto-fill from title</button>'}
            <label>Servings <input name="servings" type="number" min="1" max="2147483647" required value="${defaultServings}"></label>
            <label>Tags <input name="tags" placeholder="Dinner, easy" value="${escape(recipe?.tags.join(', '))}"></label>
            <h2>Ingredients</h2>
            <div id="editor-ingredients">${(recipe?.ingredients.length ? recipe.ingredients : [{}]).map(ingredientRow).join('')}</div>
            <button type="button" id="add-ingredient">Add ingredient</button>
            <label>Step by step <textarea name="instructions" required rows="8">${escape(recipe?.instructions)}</textarea></label>
            <label>Recipe photo <input type="file" name="image" accept="image/png,image/jpeg,image/gif,image/webp"></label>
            <p role="status" id="editor-status"></p>
            <button type="submit">Save Recipe</button>
        </form>`;
    const form = content.querySelector('form');
    const rows = form.querySelector('#editor-ingredients');
    const status = form.querySelector('#editor-status');
    form.querySelector('#add-ingredient').addEventListener('click', () => {
        rows.insertAdjacentHTML('beforeend', ingredientRow());
        rows.lastElementChild.querySelector('input').focus();
    });
    rows.addEventListener('click', event => {
        if (event.target.matches('[data-remove-ingredient]')) event.target.closest('.ingredient-row').remove();
    });
    const autoFill = form.querySelector('#auto-fill');
    autoFill?.addEventListener('click', recipeAction(autoFill, status, async () => {
        const title = form.elements.title;
        if (!title.reportValidity()) return;
        if (form.elements.instructions.value && !window.confirm('Replace the current recipe draft with the suggestion?')) return;
        const response = await fetch('/api/recipe/suggest', {
            method: 'POST', headers: { ...window.csrfHeaders, 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: title.value }),
        });
        const suggestion = await response.json();
        if (!response.ok) throw new Error(suggestion.error || suggestion.message);
        form.elements.servings.value = suggestion.recipe.servings || 4;
        form.elements.instructions.value = suggestion.recipe.instructions || '';
        form.elements.tags.value = suggestion.recipe.tags.join(', ');
        rows.innerHTML = suggestion.recipe.ingredients.map(ingredientRow).join('');
        status.textContent = 'Review the suggested recipe before saving.';
    }));
    form.addEventListener('submit', recipeAction(form.querySelector('button[type="submit"]'), status, async () => {
        if (form.elements.image.files[0]?.size > 5 * 1024 * 1024) throw new Error('Choose a photo up to 5 MB.');
        const target = recipe ? `/api/recipes/${recipe.id}` : '/api/recipes';
        const result = await api(target, { method: recipe ? 'PATCH' : 'POST', body: new FormData(form) });
        location.assign(`/recipe/${result.id}`);
    }));
}
