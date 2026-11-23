import '../static/style.css';
import '../static/chef-chat.css';
import '../static/theme.js';
import '../static/install.js';
import { api } from './api.js';
import { prepareCollection, renderCollection } from './collection.js';
import { renderEditor, renderRecipe } from './recipe.js';

const content = document.getElementById('content');

window.addEventListener('error', event => {
    if (!(event.target instanceof HTMLImageElement) || !event.target.hasAttribute('data-recipe-photo')) return;
    event.target.hidden = true;
    event.target.nextElementSibling.hidden = false;
}, true);

async function start() {
    const path = location.pathname.replace(/\/$/, '') || '/';
    const results = path === '/' ? prepareCollection(content) : content;
    try {
        const session = await api('/api/session');
        window.csrfHeaders = { 'X-CSRF-Token': session.csrf_token };
        document.getElementById('favorites-link').hidden = false;
        document.getElementById('shopping-link').hidden = false;
        document.getElementById('api-docs-link').hidden = false;
        document.getElementById('add-link').hidden = false;
        document.getElementById('editor-sign-in').hidden = !session.editor_available || session.editor_signed_in;
        const signOut = document.querySelector('.nav-signout');
        signOut.hidden = !session.signed_in && !session.editor_signed_in;
        if (session.editor_signed_in) signOut.action = '/auth/editor/sign-out';
        signOut.elements.csrf_token.value = session.csrf_token;

        const detail = path.match(/^\/(recipe|edit)\/(\d+)$/);
        if (detail) {
            const recipe = await api(`/api/recipes/${detail[2]}`);
            if (detail[1] === 'edit') renderEditor(content, recipe);
            else renderRecipe(content, recipe);
        } else if (path === '/add') {
            renderEditor(content);
        } else if (path === '/shopping-list') {
            const { mountShoppingList } = await import('../static/shopping-list.js');
            await mountShoppingList(content, session.csrf_token);
        } else if (path === '/') {
            await renderCollection(results);
        } else {
            throw new Error('This page could not be found.');
        }
        await import('../static/chef-chat.js');
    } catch (error) {
        const message = document.createElement('p');
        message.setAttribute('role', 'alert');
        message.textContent = error.message;
        results.replaceChildren(message);
        const link = document.createElement('a');
        link.href = error.status === 401 ? '/auth/sign-in' : '/';
        link.textContent = error.status === 401 ? 'Sign in' : path === '/' ? 'Try again' : 'Go to your recipe box';
        if (path === '/' && error.status !== 401) link.href = location.href;
        results.append(link);
    } finally {
        content.setAttribute('aria-busy', 'false');
    }
}

start();
