(() => {
    const storageKey = "recipe-box-theme";
    const defaultPalette = "sage";
    const palettes = ["sage", "ocean", "lavender", "terracotta", "midnight"];
    const root = document.documentElement;
    let selected = defaultPalette;

    try {
        const saved = localStorage.getItem(storageKey);
        if (palettes.includes(saved)) selected = saved;
    } catch {
        // The picker still works when storage is unavailable.
    }
    root.dataset.palette = selected;

    document.addEventListener("DOMContentLoaded", () => {
        const picker = document.querySelector(".theme-picker");
        if (!picker) return;
        const toggle = picker.querySelector("#theme-toggle");
        const menu = picker.querySelector("#theme-palettes");
        const options = menu.querySelectorAll("[data-theme-choice]");

        function setExpanded(expanded) {
            menu.hidden = !expanded;
            toggle.setAttribute("aria-expanded", String(expanded));
        }

        function showSelection() {
            options.forEach(option => {
                option.setAttribute("aria-pressed", String(option.dataset.themeChoice === selected));
            });
        }

        toggle.addEventListener("click", () => setExpanded(menu.hidden));
        options.forEach(option => {
            option.addEventListener("click", () => {
                selected = option.dataset.themeChoice;
                root.dataset.palette = selected;
                showSelection();
                setExpanded(false);
                toggle.focus();
                try {
                    localStorage.setItem(storageKey, selected);
                } catch {
                    // The applied palette remains active for this page.
                }
            });
        });
        picker.addEventListener("keydown", event => {
            if (event.key === "Escape" && !menu.hidden) {
                setExpanded(false);
                toggle.focus();
            }
        });
        picker.addEventListener("focusout", event => {
            if (!picker.contains(event.relatedTarget)) setExpanded(false);
        });
        document.addEventListener("click", event => {
            if (!picker.contains(event.target)) setExpanded(false);
        });

        showSelection();
        picker.hidden = false;
    });
})();
