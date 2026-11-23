import { api, escape, photoMarkup } from './api.js';

const desktopHero = new URL('../static/images/recipe-box-hero.webp', import.meta.url).href;
const mobileHero = new URL('../static/images/recipe-box-hero-mobile.webp', import.meta.url).href;

function collectionLink(params, updates) {
    const query = new URLSearchParams(params);
    Object.entries(updates).forEach(([key, value]) => value ? query.set(key, value) : query.delete(key));
    return query.size ? `/?${query}` : '/';
}

export function prepareCollection(content) {
    const params = new URLSearchParams(location.search);
    const favorites = params.get('favorites') === '1';
    const tag = params.get('tag');
    content.innerHTML = `
        <section class="collection-hero" aria-labelledby="collection-title">
            <picture class="collection-photo" aria-hidden="true">
                <source media="(max-width: 640px)" srcset="${mobileHero}">
                <img src="${desktopHero}" width="1672" height="941" alt="" fetchpriority="high">
            </picture>
            <div class="collection-intro"><h1 id="collection-title">${favorites ? 'Favorite recipes' : 'Your recipe box'}</h1>
                <div class="search-bar"><form role="search" action="/">
                    ${favorites ? '<input type="hidden" name="favorites" value="1">' : ''}
                    ${tag ? `<input type="hidden" name="tag" value="${escape(tag)}">` : ''}
                    <input type="search" name="q" aria-label="Search recipes" placeholder="Recipes, ingredients, tags" value="${escape(params.get('q'))}">
                    <button>Search</button>
                </form></div>
            </div>
        </section>
        <div id="collection-results"><p role="status">Loading recipes…</p></div>`;
    return content.querySelector('#collection-results');
}

export async function renderCollection(results) {
    const params = new URLSearchParams(location.search);
    const { recipes, page, pages, total } = await api(`/api/recipes?${params}`);
    const favorites = params.get('favorites') === '1';
    const tag = params.get('tag');
    results.innerHTML = `
        <div class="filter-bar">
            <a class="filter-pill${favorites ? '' : ' active'}" href="${escape(collectionLink(params, { favorites: '', page: '' }))}">All</a>
            <a class="filter-pill${favorites ? ' active' : ''}" href="${escape(collectionLink(params, { favorites: '1', page: '' }))}">★ Favorites</a>
            ${tag ? `<a class="filter-tag" href="${escape(collectionLink(params, { tag: '', page: '' }))}">${escape(tag)} &times;</a>` : ''}
            <span class="filter-count">${total} ${total === 1 ? 'recipe' : 'recipes'}</span>
        </div>
        ${recipes.length ? deckMarkup(recipes, params) : '<div class="empty-collection"><p>No recipes match this view.</p><a href="/">Browse all recipes</a></div>'}
        ${pages > 1 ? `<nav class="pagination" aria-label="Recipe pages">
            ${page > 1 ? `<a href="${escape(collectionLink(params, { page: page - 1 }))}">← Previous</a>` : ''}
            <span class="page-info">Page ${page} of ${pages}</span>
            ${page < pages ? `<a href="${escape(collectionLink(params, { page: page + 1 }))}">Next →</a>` : ''}
        </nav>` : ''}`;
    if (recipes.length) await import('../static/deck.js');
}

function deckMarkup(recipes, params) {
    return `
        <div class="view-controls" id="recipe-view-controls" role="group" aria-label="Recipe view" hidden>
            <button class="view-btn" id="view-deck" type="button">Deck</button>
            <button class="view-btn" id="view-list" type="button">List</button>
        </div>
        <section class="recipe-deck" id="recipe-deck" aria-label="Recipe deck" hidden>
            <div class="deck-stack" id="deck-stack">${recipes.map(recipe => `
                <a class="flashcard" draggable="false" href="/recipe/${recipe.id}">
                    <div class="flashcard-media">
                        ${photoMarkup(recipe.photo, '<div class="flashcard-placeholder">🍽️</div>')}
                        ${recipe.favorite ? '<span class="flashcard-fav" aria-label="Favorite">★</span>' : ''}
                    </div>
                    <div class="flashcard-body">
                        <h2 class="flashcard-title">${escape(recipe.title)}</h2>
                        <div class="flashcard-meta">${recipe.servings} servings <span class="flashcard-rating">${'★'.repeat(Math.max(0, Math.min(5, recipe.rating || 0)))}</span></div>
                        <div class="flashcard-tags">${recipe.tags.slice(0, 3).map(tag => `<span class="tag">${escape(tag)}</span>`).join('')}</div>
                    </div>
                </a>`).join('')}</div>
            <div class="deck-controls" id="deck-controls" hidden>
                <button class="deck-arrow" id="deck-prev" aria-label="Previous recipe" type="button">←</button>
                <p class="deck-progress"><span id="deck-position" aria-hidden="true"></span><span id="deck-announcement" class="visually-hidden" role="status"></span></p>
                <button class="deck-arrow" id="deck-next" aria-label="Next recipe" type="button">→</button>
            </div>
        </section>
        <ul id="recipe-list">${recipes.map(recipe => `
            <li>${recipe.favorite ? '<span class="star">★</span>' : ''}<a href="/recipe/${recipe.id}">${escape(recipe.title)}</a>
                ${recipe.tags.map(tag => `<a class="tag" href="${escape(collectionLink(params, { tag, page: '' }))}">${escape(tag)}</a>`).join('')}
            </li>`).join('')}
        </ul>`;
}
