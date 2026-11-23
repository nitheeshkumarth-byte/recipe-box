const escapeCharacters = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

export function escape(value) {
    return String(value ?? '').replace(/[&<>"']/g, character => escapeCharacters[character]);
}

export async function api(path, { method = 'GET', body } = {}) {
    const response = await fetch(path, { method, body, headers: method === 'GET' ? {} : window.csrfHeaders });
    const data = await response.json().catch(() => null);
    if (!response.ok || !data) {
        const error = new Error(data?.error || (response.status === 413 ? 'This upload is too large.' : 'Recipe Box could not complete this request.'));
        error.status = response.status;
        throw error;
    }
    return data;
}

export function photoMarkup(path, { placeholder = '', className = '', alt = '' } = {}) {
    if (!path?.startsWith('/photos/')) return placeholder;
    return `<img src="${escape(path)}" class="${escape(className)}" alt="${escape(alt)}" loading="lazy" draggable="false" data-recipe-photo>
        <div class="${placeholder ? 'flashcard-placeholder ' : ''}photo-unavailable" hidden>Photo unavailable</div>`;
}
