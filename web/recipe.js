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
        ${photoMarkup(recipe.photo, { className: 'recipe-photo', alt: recipe.title })}
        <article class="recipe-card">
            <h1><span class="star" id="recipe-favorite-star" aria-hidden="true"${recipe.favorite ? '' : ' hidden'}>★</span> ${escape(recipe.title)}</h1>
            ${recipe.tags.length ? `<div class="tags">${recipe.tags.map(tag => `<a class="tag" href="/?${escape(new URLSearchParams({ tag }))}">${escape(tag)}</a>`).join('')}</div>` : ''}
            <div class="rating">
                <div class="rating-display"><span class="single-star" aria-hidden="true">★</span><span class="rating-value">${recipe.rating ? `${recipe.rating} / 5` : 'Not rated yet'}</span></div>
                <form id="rating-form" class="rating-form">
                    <label for="rating-select">Rate:</label>
                    <select name="rating" id="rating-select" required>
                        <option value="" disabled${recipe.rating ? '' : ' selected'}>Choose…</option>
                        ${[1, 2, 3, 4, 5].map(rating => `<option value="${rating}"${rating === recipe.rating ? ' selected' : ''}>${rating} ${rating === 1 ? 'star' : 'stars'}</option>`).join('')}
                    </select>
                    <button class="rate-btn" type="submit">Rate</button>
                </form>
            </div>
            <div id="origin-section">
                <button type="button" id="origin-btn">✨ Where does this dish come from?</button>
                <p id="origin-text" role="status" hidden></p>
            </div>
            <h2>Ingredients</h2>
            <p><label for="servings-input">Servings:</label>
                <input id="servings-input" type="number" min="1" max="2147483647" value="${recipe.servings}">
                <span id="servings-note">(original recipe: ${recipe.servings})</span>
            </p>
            <ul id="ingredient-list"></ul>
            <div id="nutrition-section">
                <div class="nutrition-facts" id="nutrition-facts" hidden>
                    <strong>Nutrition (estimated per serving)</strong>
                    <ul><li><span data-nutrition="calories"></span> calories</li><li><span data-nutrition="protein_g"></span> g protein</li><li><span data-nutrition="carbs_g"></span> g carbs</li><li><span data-nutrition="fat_g"></span> g fat</li></ul>
                </div>
                <button type="button" id="nutrition-btn"${recipe.ingredients.length ? '' : ' hidden'}>Estimate nutrition</button>
            </div>
            <h2>Instructions</h2>
            <p class="recipe-instructions">${escape(recipe.instructions)}</p>
            <p role="status" id="recipe-status"></p>
            <div class="actions-bar">
                <a class="action-btn edit-btn" href="/edit/${recipe.id}">Edit</a>
                <button type="button" class="action-btn favorite-btn" id="favorite"></button>
                <button type="button" class="action-btn delete-action-btn" id="delete">Delete</button>
            </div>
        </article>`;

    const status = content.querySelector('#recipe-status');
    const servings = content.querySelector('#servings-input');
    const amounts = content.querySelector('#ingredient-list');
    const number = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 });
    function updateAmounts() {
        if (!servings.value || !servings.checkValidity()) return;
        amounts.innerHTML = recipe.ingredients.map(ingredient => `<li>
            <span class="ing-amount">${escape(number.format(ingredient.amount * Number(servings.value) / recipe.servings))}</span>
            <span class="ing-unit">${escape(ingredient.unit)}</span><span class="ing-name">${escape(ingredient.name)}</span></li>`).join('');
    }
    servings.addEventListener('input', updateAmounts);
    updateAmounts();

    const favorite = content.querySelector('#favorite');
    const favoriteStar = content.querySelector('#recipe-favorite-star');
    function showFavorite(value) {
        favorite.textContent = value ? '★ Remove from Favorites' : '☆ Add to Favorites';
        favorite.setAttribute('aria-pressed', String(value));
        favoriteStar.hidden = !value;
    }
    showFavorite(recipe.favorite);
    favorite.addEventListener('click', recipeAction(favorite, status, async () => {
        const result = await api(`/api/recipes/${recipe.id}/favorite`, { method: 'POST' });
        showFavorite(result.favorite);
    }));

    const ratingForm = content.querySelector('#rating-form');
    ratingForm.addEventListener('submit', recipeAction(ratingForm.querySelector('button'), status, async () => {
        const result = await api(`/api/recipes/${recipe.id}/rating`, { method: 'POST', body: new FormData(ratingForm) });
        content.querySelector('.rating-value').textContent = `${result.rating} / 5`;
        status.textContent = 'Rating saved.';
    }));

    const deleteButton = content.querySelector('#delete');
    deleteButton.addEventListener('click', recipeAction(deleteButton, status, async () => {
        if (!window.confirm('Delete this recipe?')) return;
        await api(`/api/delete/${recipe.id}`, { method: 'POST' });
        location.assign('/');
    }));

    const origin = content.querySelector('#origin-text');
    const originButton = content.querySelector('#origin-btn');
    function showOrigin(value) {
        const hasOrigin = Boolean(value && value !== 'Unknown origin.');
        origin.hidden = !hasOrigin;
        originButton.hidden = hasOrigin;
        origin.textContent = hasOrigin ? value : '';
    }
    showOrigin(recipe.origin);
    originButton.addEventListener('click', recipeAction(originButton, status, async () => {
        const { origin: value } = await api(`/api/origin/${recipe.id}`, { method: 'POST' });
        showOrigin(value);
        if (origin.hidden) status.textContent = value;
    }));

    const nutrition = content.querySelector('#nutrition-facts');
    const nutritionButton = content.querySelector('#nutrition-btn');
    function showNutrition(data) {
        nutrition.hidden = data.calories == null;
        nutritionButton.hidden = recipe.ingredients.length === 0 || !nutrition.hidden;
        nutrition.querySelectorAll('[data-nutrition]').forEach(value => {
            value.textContent = data[value.dataset.nutrition] ?? '—';
        });
    }
    showNutrition(recipe.nutrition);
    nutritionButton.addEventListener('click', recipeAction(nutritionButton, status, async () => {
        showNutrition(await api(`/api/nutrition/${recipe.id}`, { method: 'POST' }));
    }));
}

function ingredientRow(ingredient = {}) {
    return `<div class="ingredient-row">
        <input type="number" min="0" step="any" name="ing_amount" aria-label="Amount" placeholder="Amount" value="${escape(ingredient.amount)}">
        <input name="ing_unit" maxlength="20" aria-label="Unit" placeholder="Unit" value="${escape(ingredient.unit)}">
        <input name="ing_name" maxlength="120" aria-label="Ingredient name" placeholder="Ingredient name" value="${escape(ingredient.name)}">
        <button type="button" class="remove-row-btn" data-remove-ingredient aria-label="Remove ingredient">×</button>
    </div>`;
}

export function renderEditor(content, recipe) {
    const defaultServings = recipe?.servings ?? 4;
    content.innerHTML = `
        <div class="form-page">
            <a href="${recipe ? `/recipe/${recipe.id}` : '/'}" class="back-link">← Back</a>
            <h1 class="form-title">${recipe ? 'Edit Recipe' : 'Add a New Recipe'}</h1>
            <form id="recipe-editor" class="recipe-form">
                <div class="form-card">
                    <div class="form-section">
                        <h2 class="form-heading">🧾 Basics</h2>
                        <div class="field">
                            <label for="f-title">Title</label>
                            <div class="title-input-group">
                                <input type="text" id="f-title" name="title" required maxlength="120" value="${escape(recipe?.title)}" placeholder="e.g. Creamy Mushroom Pasta">
                                ${recipe ? '' : '<button type="button" class="suggest-btn" id="auto-fill">✨ Auto-fill</button>'}
                            </div>
                            <p class="suggest-status" role="status" id="suggest-status"></p>
                        </div>
                        <div class="field-row">
                            <div class="field"><label for="f-servings">Servings</label><input id="f-servings" name="servings" type="number" min="1" max="2147483647" required value="${defaultServings}"></div>
                            <div class="field"><label for="f-tags">Tags <span class="field-hint">(comma-separated)</span></label><input type="text" id="f-tags" name="tags" placeholder="dinner, quick, veg" value="${escape(recipe?.tags.join(', '))}"></div>
                        </div>
                    </div>
                    <div class="form-section">
                        <h2 class="form-heading">📷 Photo</h2>
                        <div class="field">
                            <label class="file-label">
                                <input type="file" name="image" aria-label="Recipe photo" accept="image/png,image/jpeg,image/gif,image/webp" class="visually-hidden">
                                <span class="file-drop">${recipe?.photo ? '🖼️ Change photo' : '📤 Upload a photo'}</span>
                                <span class="file-name" id="file-name"></span>
                            </label>
                            <p class="hint">PNG, JPEG, GIF, or WebP up to 5 MB.</p>
                            ${photoMarkup(recipe?.photo, { className: 'form-photo-preview', alt: recipe?.title })}
                        </div>
                    </div>
                </div>
                <div class="form-card">
                    <div class="form-section">
                        <h2 class="form-heading">🥄 Ingredients</h2>
                        <div id="editor-ingredients">${(recipe?.ingredients.length ? recipe.ingredients : [{}]).map(ingredientRow).join('')}</div>
                        <div class="add-row-wrap"><button type="button" id="add-row-btn">+ Add ingredient</button></div>
                    </div>
                    <div class="form-section">
                        <h2 class="form-heading">📝 Instructions</h2>
                        <div class="field"><label for="f-instructions">Step by step</label><textarea id="f-instructions" name="instructions" required rows="8" placeholder="Describe how to make this dish…">${escape(recipe?.instructions)}</textarea></div>
                    </div>
                </div>
                <p role="status" id="editor-status" class="suggest-status"></p>
                <div class="form-actions"><button type="submit" class="save-btn">${recipe ? 'Save Changes' : 'Save Recipe'}</button></div>
            </form>
        </div>`;
    const form = content.querySelector('form');
    const rows = form.querySelector('#editor-ingredients');
    const status = form.querySelector('#editor-status');
    form.querySelector('#add-row-btn').addEventListener('click', () => {
        rows.insertAdjacentHTML('beforeend', ingredientRow());
        rows.lastElementChild.querySelector('input').focus();
    });
    rows.addEventListener('click', event => {
        if (event.target.matches('[data-remove-ingredient]')) event.target.closest('.ingredient-row').remove();
    });
    const fileName = form.querySelector('#file-name');
    form.elements.image.addEventListener('change', () => {
        fileName.textContent = form.elements.image.files[0]?.name || '';
    });
    const autoFill = form.querySelector('#auto-fill');
    const suggestionStatus = form.querySelector('#suggest-status');
    autoFill?.addEventListener('click', recipeAction(autoFill, suggestionStatus, async () => {
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
        suggestionStatus.textContent = 'Review the suggested recipe before saving.';
    }));
    form.addEventListener('submit', recipeAction(form.querySelector('button[type="submit"]'), status, async () => {
        if (form.elements.image.files[0]?.size > 5 * 1024 * 1024) throw new Error('Choose a photo up to 5 MB.');
        const target = recipe ? `/api/recipes/${recipe.id}` : '/api/recipes';
        const result = await api(target, { method: recipe ? 'PATCH' : 'POST', body: new FormData(form) });
        location.assign(`/recipe/${result.id}`);
    }));
}
