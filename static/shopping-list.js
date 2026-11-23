const unitAliases = new Map(Object.entries({
    cups: 'cup', teaspoons: 'tsp', teaspoon: 'tsp', tablespoons: 'tbsp', tablespoon: 'tbsp',
    grams: 'g', gram: 'g', kilograms: 'kg', kilogram: 'kg', milliliters: 'ml', milliliter: 'ml',
    liters: 'l', liter: 'l', ounces: 'oz', ounce: 'oz', pounds: 'lb', pound: 'lb',
}));
const storageKey = 'recipe-box-shopping-list';
const quantities = new Intl.NumberFormat(undefined, { maximumSignificantDigits: 8 });

function clean(value = '') {
    return (value || '').normalize('NFKC').trim().replace(/\s+/g, ' ');
}

function ingredientsFor(selection) {
    const totals = new Map();
    for (const { recipe, servings } of selection) {
        const scale = servings / recipe.servings;
        for (const ingredient of recipe.ingredients) {
            const name = clean(ingredient.name);
            const rawUnit = clean(ingredient.unit).toLowerCase();
            const unit = unitAliases.get(rawUnit) || rawUnit;
            if (!name) continue;

            const amount = ingredient.amount * scale;
            const measured = Number.isFinite(amount) && amount > 0;
            const key = JSON.stringify([name.toLowerCase(), unit, measured]);
            const item = totals.get(key) || { key, name, unit, measured, amount: 0 };
            if (measured) item.amount += amount;
            totals.set(key, item);
        }
    }
    return [...totals.values()].sort((a, b) => a.name.localeCompare(b.name) || a.unit.localeCompare(b.unit));
}

async function sessionStorageScope(sessionToken) {
    if (!sessionToken || !globalThis.crypto?.subtle) return null;
    const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(sessionToken));
    return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
}

function savedList(scope) {
    try {
        const saved = JSON.parse(sessionStorage.getItem(storageKey));
        return scope && saved?.scope === scope && Array.isArray(saved.selection) && Array.isArray(saved.checked)
            ? saved : null;
    } catch {
        return null;
    }
}

function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text) node.textContent = text;
    if (className) node.className = className;
    return node;
}

async function load(path, signal) {
    const response = await fetch(path, { signal });
    if (!response.ok) throw new Error('Could not load recipes. Please try again.');
    return response.json();
}

export async function mountShoppingList(container, sessionToken) {
    document.title = 'Shopping List · Recipe Box';
    container.innerHTML = `
        <section class="form-page shopping-list" aria-labelledby="shopping-title">
            <h1 id="shopping-title" class="form-title">Shopping List</h1>
            <div class="shopping-grid">
                <section class="shopping-card" aria-labelledby="shopping-recipes">
                    <h2 id="shopping-recipes" class="form-heading">Choose recipes</h2>
                    <form class="shopping-search" role="search" aria-label="Find recipes for your shopping list">
                        <input type="search" aria-label="Search recipes" placeholder="Search recipes">
                        <button type="submit" class="action-btn">Search</button>
                    </form>
                    <ul class="shopping-options" aria-label="Available recipes"></ul>
                    <nav class="shopping-pagination" aria-label="Recipe results pages" hidden>
                        <button type="button" class="action-btn" data-previous>Previous</button>
                        <span></span>
                        <button type="button" class="action-btn" data-next>Next</button>
                    </nav>
                    <h2 class="form-heading">Selected recipes</h2>
                    <ul class="shopping-selection"></ul>
                    <p class="shopping-selection-empty">Add a recipe to set its servings.</p>
                    <p class="shopping-status" role="status"></p>
                </section>
                <section class="shopping-card" aria-labelledby="shopping-ingredients">
                    <h2 id="shopping-ingredients" class="form-heading">Ingredient checklist</h2>
                    <p class="shopping-empty">Ingredients will appear here when you add a recipe.</p>
                    <p class="shopping-progress" role="status" hidden></p>
                    <ul class="shopping-checklist"></ul>
                </section>
            </div>
        </section>`;

    const form = container.querySelector('.shopping-search');
    const options = container.querySelector('.shopping-options');
    const selectedList = container.querySelector('.shopping-selection');
    const selectionEmpty = container.querySelector('.shopping-selection-empty');
    const status = container.querySelector('.shopping-status');
    const checklist = container.querySelector('.shopping-checklist');
    const empty = container.querySelector('.shopping-empty');
    const emptyMessage = empty.textContent;
    const progress = container.querySelector('.shopping-progress');
    const pagination = container.querySelector('.shopping-pagination');
    const previous = pagination.querySelector('[data-previous]');
    const next = pagination.querySelector('[data-next]');
    const picked = new Set();
    const selected = new Map();
    let page = 1;
    let search = '';
    let catalogRequest;
    const scope = await sessionStorageScope(sessionToken);
    const pending = new Set();

    function save() {
        if (!scope) return;
        const selection = [...selected.values()].map(({ recipe, servings }) => ({ id: recipe.id, servings }));
        try {
            sessionStorage.setItem(storageKey, JSON.stringify({ scope, selection, checked: [...picked] }));
        } catch {
            // Some browsing modes disable session storage.
        }
    }

    function clearCheckedIngredients(selection) {
        for (const ingredient of ingredientsFor([selection])) picked.delete(ingredient.key);
    }

    function renderChecklist() {
        const ingredients = ingredientsFor(selected.values());
        empty.hidden = ingredients.length > 0;
        empty.textContent = selected.size ? 'The selected recipes have no ingredients.' : emptyMessage;
        progress.hidden = ingredients.length === 0;
        function updateProgress() {
            const checked = ingredients.filter(({ key }) => picked.has(key)).length;
            progress.textContent = `${checked} of ${ingredients.length} checked`;
        }
        checklist.replaceChildren(...ingredients.map(item => {
            const row = element('li');
            const label = element('label');
            const box = element('input');
            box.type = 'checkbox';
            box.checked = picked.has(item.key);
            const unit = item.amount !== 1 && item.unit === 'cup' ? 'cups' : item.unit;
            const quantity = item.measured ? quantities.format(item.amount) : '';
            label.append(box, element('span', [quantity, unit, item.name].filter(Boolean).join(' ')));
            box.addEventListener('change', () => {
                if (box.checked) picked.add(item.key);
                else picked.delete(item.key);
                updateProgress();
                save();
            });
            row.append(label);
            return row;
        }));
        updateProgress();
    }

    function renderSelection(focusOptions = false) {
        selectionEmpty.hidden = selected.size > 0;
        selectedList.replaceChildren(...[...selected.values()].map(selection => {
            const { recipe, servings } = selection;
            const row = element('li');
            const name = element('a', recipe.title);
            name.href = `/recipe/${recipe.id}`;
            const label = element('label', 'Servings ');
            const count = element('input');
            count.type = 'number';
            count.min = '1';
            count.max = '2147483647';
            count.required = true;
            count.value = servings;
            count.setAttribute('aria-label', `Servings for ${recipe.title}`);
            count.addEventListener('change', () => {
                if (!count.checkValidity()) {
                    count.reportValidity();
                    count.value = selection.servings;
                    return;
                }
                if (count.valueAsNumber === selection.servings) return;
                clearCheckedIngredients(selection);
                selection.servings = count.valueAsNumber;
                renderChecklist();
                save();
            });
            label.append(count);
            const remove = element('button', 'Remove', 'action-btn');
            remove.type = 'button';
            remove.setAttribute('aria-label', `Remove ${recipe.title}`);
            remove.addEventListener('click', () => {
                clearCheckedIngredients(selection);
                selected.delete(recipe.id);
                renderSelection(true);
                save();
            });
            const actions = element('div', '', 'shopping-selection-actions');
            actions.append(label, remove);
            row.append(name, actions);
            return row;
        }));
        for (const button of options.querySelectorAll('button[data-recipe]')) {
            const id = Number(button.dataset.recipe);
            button.disabled = selected.has(id) || pending.has(id);
            button.textContent = selected.has(id) ? 'Added' : 'Add';
        }
        if (focusOptions) form.querySelector('input').focus();
        renderChecklist();
    }

    async function browse() {
        catalogRequest?.abort();
        const request = new AbortController();
        catalogRequest = request;
        options.setAttribute('aria-busy', 'true');
        previous.disabled = true;
        next.disabled = true;
        try {
            const params = new URLSearchParams({ q: search, page });
            const data = await load(`/api/recipes?${params}`, request.signal);
            options.replaceChildren(...data.recipes.map(summary => {
                const row = element('li');
                const add = element('button', 'Add', 'action-btn');
                add.type = 'button';
                add.dataset.recipe = summary.id;
                add.setAttribute('aria-label', `Add ${summary.title}`);
                add.addEventListener('click', async () => {
                    pending.add(summary.id);
                    add.disabled = true;
                    status.textContent = '';
                    try {
                        const recipe = await load(`/api/recipes/${summary.id}`);
                        const selection = { recipe, servings: recipe.servings };
                        clearCheckedIngredients(selection);
                        selected.set(recipe.id, selection);
                        save();
                    } catch (error) {
                        status.textContent = error.message;
                    } finally {
                        pending.delete(summary.id);
                        renderSelection();
                    }
                });
                row.append(element('span', summary.title), add);
                return row;
            }));
            if (!data.recipes.length) options.append(element('li', 'No matching recipes.'));
            pagination.hidden = data.pages < 2;
            previous.disabled = data.page <= 1;
            next.disabled = data.page >= data.pages;
            pagination.querySelector('span').textContent = `${data.page} / ${data.pages}`;
            renderSelection();
        } catch (error) {
            if (error.name !== 'AbortError') status.textContent = 'Could not load recipes. Use Search to try again.';
        } finally {
            if (catalogRequest === request) options.removeAttribute('aria-busy');
        }
    }

    form.addEventListener('submit', event => {
        event.preventDefault();
        status.textContent = '';
        search = form.querySelector('input').value.trim();
        page = 1;
        browse();
    });
    previous.addEventListener('click', () => { page--; browse(); });
    next.addEventListener('click', () => { page++; browse(); });

    const saved = savedList(scope);
    if (saved) {
        const entries = saved.selection.filter(({ id, servings }) => Number.isInteger(id) && id > 0 &&
            Number.isInteger(servings) && servings > 0 && servings <= 2147483647);
        const recovered = await Promise.allSettled(entries.map(async ({ id, servings }) => ({
            recipe: await load(`/api/recipes/${id}`), servings,
        })));
        for (const entry of recovered) if (entry.status === 'fulfilled') selected.set(entry.value.recipe.id, entry.value);
        for (const { key } of ingredientsFor(selected.values())) if (saved.checked.includes(key)) picked.add(key);
        if (recovered.some(entry => entry.status === 'rejected')) status.textContent = 'Some saved recipes are unavailable.';
    }
    renderSelection();
    await browse();
}

const shoppingPage = document.getElementById('shopping-list');
if (shoppingPage) {
    const sessionToken = document.querySelector('meta[name="csrf-token"]')?.content;
    mountShoppingList(shoppingPage, sessionToken);
}
