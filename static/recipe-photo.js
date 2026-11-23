export function mountRecipePhoto(form, csrfToken) {
    const input = form.elements.image;
    const title = form.elements.title;
    const fileName = form.querySelector('#file-name');
    const button = form.querySelector('[data-generate-photo]');
    const status = form.querySelector('[data-photo-status]');
    const preview = form.querySelector('[data-photo-preview]');
    const discard = form.querySelector('[data-discard-photo]');
    const saved = form.querySelector('[data-saved-photo]');
    const extensions = { 'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp', 'image/gif': 'gif' };
    let previewUrl;
    let selection = 0;
    button.hidden = false;

    function showSelection() {
        selection += 1;
        if (previewUrl) URL.revokeObjectURL(previewUrl);
        const file = input.files[0];
        fileName.textContent = file?.name || '';
        previewUrl = file && Object.hasOwn(extensions, file.type) && file.size <= 5 * 1024 * 1024
            ? URL.createObjectURL(file)
            : null;
        if (previewUrl) preview.src = previewUrl;
        else preview.removeAttribute('src');
        preview.hidden = !previewUrl;
        discard.hidden = !file;
        if (saved) saved.hidden = Boolean(previewUrl);
        status.textContent = '';
        status.classList.remove('error');
    }

    input.addEventListener('change', showSelection);
    discard.addEventListener('click', () => {
        input.value = '';
        showSelection();
        button.focus();
    });

    button.addEventListener('click', async () => {
        const dish = title.value.trim();
        if (!dish || dish.length > 120) {
            status.textContent = 'Enter a recipe title of 120 characters or fewer.';
            status.classList.add('error');
            title.focus();
            return;
        }
        const currentSelection = selection;
        button.disabled = true;
        status.classList.remove('error');
        status.textContent = 'Looking for a web reference and generating a photo…';
        try {
            const response = await fetch('/api/recipe/photo', {
                method: 'POST',
                headers: { 'X-CSRF-Token': csrfToken, 'Content-Type': 'application/json' },
                body: JSON.stringify({ title: dish }),
            });
            if (!response.ok) {
                const error = response.headers.get('Content-Type')?.includes('application/json')
                    ? (await response.json()).error
                    : null;
                throw new Error(error || 'Couldn’t generate a photo. Try again or upload one.');
            }
            const blob = await response.blob();
            if (selection !== currentSelection) return;
            if (title.value.trim() !== dish) {
                status.textContent = 'The title changed. Generate a photo for the new title.';
                return;
            }
            if (!Object.hasOwn(extensions, blob.type) || !blob.size || blob.size > 5 * 1024 * 1024) {
                throw new Error('The generated photo could not be opened. Try again or upload one.');
            }
            const transfer = new DataTransfer();
            transfer.items.add(new File([blob], `generated-recipe.${extensions[blob.type]}`, { type: blob.type }));
            input.files = transfer.files;
            showSelection();
            status.textContent = response.headers.get('X-Recipe-Photo-Reference') === 'commons'
                ? 'AI-generated photo ready. Save the recipe to keep it.'
                : 'AI-generated photo ready. No web reference was available. Save the recipe to keep it.';
        } catch (error) {
            if (selection === currentSelection) {
                status.textContent = error instanceof TypeError
                    ? 'Couldn’t generate a photo. Try again or upload one.'
                    : error.message;
                status.classList.add('error');
            }
        } finally {
            button.disabled = false;
        }
    });
}
