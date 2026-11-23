(() => {
    const deck = document.getElementById("recipe-deck");
    const stack = document.getElementById("deck-stack");
    const list = document.getElementById("recipe-list");
    const viewControls = document.getElementById("recipe-view-controls");
    const deckView = document.getElementById("view-deck");
    const listView = document.getElementById("view-list");
    const controls = document.getElementById("deck-controls");
    const position = document.getElementById("deck-position");
    const announcement = document.getElementById("deck-announcement");
    const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");

    let cards = Array.from(stack.children);
    let index = 0;
    let drag = null;
    let animating = false;
    let suppressClick = false;

    function wrap(value) {
        return (value + cards.length) % cards.length;
    }

    function layerCards(direction = 1) {
        cards.forEach((card, current) => {
            const depth = wrap((current - index) * direction);
            card.dataset.depth = depth;
            card.inert = depth !== 0;
        });
    }

    function renderDeck() {
        layerCards();
        controls.hidden = cards.length < 2;
        stack.classList.toggle("can-swipe", cards.length > 1);
        if (!cards.length) return;
        position.textContent = `${index + 1} / ${cards.length}`;
        const title = cards[index].querySelector(".flashcard-title").textContent;
        announcement.textContent = `Recipe ${index + 1} of ${cards.length}: ${title}`;
    }

    function selectView(showDeck) {
        deck.hidden = !showDeck;
        list.hidden = showDeck;
        deckView.classList.toggle("active", showDeck);
        listView.classList.toggle("active", !showDeck);
        deckView.setAttribute("aria-pressed", String(showDeck));
        listView.setAttribute("aria-pressed", String(!showDeck));
    }

    function rotation(offset) {
        return Math.max(-20, Math.min(20, offset / 10));
    }

    async function move(direction, offset = 0) {
        if (cards.length < 2 || animating) return;
        const outgoing = cards[index];
        const incoming = cards[wrap(index + direction)];
        layerCards(direction);
        animating = true;
        if (!reducedMotion.matches && outgoing.animate) {
            const exit = -direction * (stack.clientWidth + outgoing.offsetWidth) / 2;
            const animation = outgoing.animate([
                { transform: `translateX(${offset}px) rotate(${rotation(offset)}deg)`, opacity: 1 },
                { transform: `translateX(${exit}px) rotate(${-direction * 24}deg)`, opacity: 0 },
            ], { duration: 270, easing: "cubic-bezier(.22,.61,.36,1)" });
            await animation.finished.catch(() => {});
        }
        const hadFocus = document.activeElement === outgoing;
        index = Math.max(0, cards.indexOf(incoming));
        renderDeck();
        animating = false;
        if (hadFocus) cards[index]?.focus({ preventScroll: true });
    }

    function finishDrag(event, canceled) {
        if (!drag || event.pointerId !== drag.pointerId) return;
        const { card, offset, horizontal } = drag;
        drag = null;
        if (!horizontal) return;
        const threshold = Math.min(110, card.offsetWidth * 0.24);
        const committed = !canceled && Math.abs(offset) >= threshold;
        card.classList.remove("is-dragging");
        card.style.removeProperty("--drag-x");
        card.style.removeProperty("--drag-angle");
        suppressClick = true;
        if (committed) move(offset < 0 ? 1 : -1, offset);
        else layerCards();
    }

    stack.addEventListener("pointerdown", event => {
        if (!event.isPrimary || event.button !== 0) return;
        suppressClick = false;
        const card = cards[index];
        if (animating || cards.length < 2 || !card?.contains(event.target)) return;
        drag = { card, pointerId: event.pointerId, x: event.clientX, y: event.clientY, offset: 0 };
    });

    window.addEventListener("pointermove", event => {
        if (!drag || event.pointerId !== drag.pointerId) return;
        const offset = event.clientX - drag.x;
        if (!drag.horizontal) {
            const vertical = Math.abs(event.clientY - drag.y);
            if (vertical > 8 && vertical >= Math.abs(offset)) {
                drag = null;
                return;
            }
            if (Math.abs(offset) < 8) return;
            drag.horizontal = true;
            stack.setPointerCapture(event.pointerId);
            drag.card.classList.add("is-dragging");
        }
        if (Math.sign(offset) !== Math.sign(drag.offset)) layerCards(offset > 0 ? -1 : 1);
        drag.offset = offset;
        drag.card.style.setProperty("--drag-x", `${offset}px`);
        drag.card.style.setProperty("--drag-angle", `${rotation(offset)}deg`);
    });

    window.addEventListener("pointerup", event => finishDrag(event, false));
    window.addEventListener("pointercancel", event => finishDrag(event, true));
    stack.addEventListener("lostpointercapture", event => finishDrag(event, true));
    stack.addEventListener("click", event => {
        if (event.detail && (suppressClick || animating)) {
            event.preventDefault();
            suppressClick = false;
        }
    }, true);

    deck.addEventListener("keydown", event => {
        if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
        event.preventDefault();
        move(event.key === "ArrowRight" ? 1 : -1);
    });

    document.getElementById("deck-prev").addEventListener("click", () => move(-1));
    document.getElementById("deck-next").addEventListener("click", () => move(1));
    deckView.addEventListener("click", () => selectView(true));
    listView.addEventListener("click", () => selectView(false));
    list.addEventListener("recipe-removed", () => {
        const previous = cards[index];
        cards = Array.from(stack.children);
        const kept = cards.indexOf(previous);
        index = kept < 0 ? Math.max(0, Math.min(index, cards.length - 1)) : kept;
        renderDeck();
    });

    renderDeck();
    selectView(true);
    viewControls.hidden = false;
})();
