(() => {
    const chat = document.getElementById("chef-chat");
    if (!chat) return;

    const launcher = chat.querySelector(".chef-launcher");
    const panel = chat.querySelector(".chef-panel");
    const close = chat.querySelector(".chef-close");
    const transcript = chat.querySelector(".chef-transcript");
    const form = chat.querySelector(".chef-form");
    const input = chat.querySelector("#chef-question");
    const viewport = window.visualViewport;

    const quickReplies = chat.querySelectorAll("[data-question]");
    const send = form.querySelector('button[type="submit"]');
    let pending = false;
    function addMessage(text, user = false) {
        const message = document.createElement("div");
        message.className = `chef-message ${user ? "chef-user" : "chef-reply"}`;
        const speaker = document.createElement("span");
        speaker.className = "visually-hidden";
        speaker.textContent = user ? "You: " : "Chef: ";
        const body = document.createElement("p");
        body.className = "chef-message-text";
        body.append(speaker, text);
        message.append(body);

        transcript.append(message);
        transcript.scrollTop = transcript.scrollHeight;
        return message;
    }

    function setPending(active) {
        pending = active;
        send.disabled = active;
        quickReplies.forEach(button => { button.disabled = active; });
    }

    async function ask(question) {
        const text = question.trim().slice(0, input.maxLength);
        if (!text || pending) return;
        setPending(true);
        addMessage(text, true);
        const status = addMessage("One moment…");
        try {
            const response = await fetch(chat.dataset.chatUrl, {
                method: "POST",
                headers: { ...csrfHeaders, "Content-Type": "application/json" },
                body: JSON.stringify({ question: text, recipe_id: Number(chat.dataset.recipeId) || null }),
            });
            const result = await response.json();
            if (!response.ok || !result.success) {
                addMessage(result.error || "I could not look that up. Please try again.");
                return;
            }
            addMessage(result.answer);
        } catch {
            addMessage("I could not connect to Recipe Box. Please try again.");
        } finally {
            status.remove();
            transcript.scrollTop = transcript.scrollHeight;
            setPending(false);
        }
    }

    function fitViewport() {
        if (!panel.hidden && viewport?.scale === 1) {
            const offset = Math.max(0, document.documentElement.clientHeight - viewport.height - viewport.offsetTop);
            chat.style.setProperty("--chef-keyboard-offset", `${offset}px`);
            chat.style.setProperty("--chef-viewport-height", `${viewport.height}px`);
            chat.classList.toggle("is-compact", viewport.height < 380);
        } else {
            chat.style.removeProperty("--chef-keyboard-offset");
            chat.style.removeProperty("--chef-viewport-height");
            chat.classList.remove("is-compact");
        }
    }

    function setOpen(open) {
        panel.hidden = !open;
        launcher.setAttribute("aria-expanded", String(open));
        launcher.setAttribute("aria-label", open ? "Close Recipe Box help" : "Open Recipe Box help");
        launcher.classList.toggle("is-opening", open);
        launcher.classList.toggle("is-closing", !open);
        fitViewport();
        if (open) close.focus({ preventScroll: true });
        else launcher.focus({ preventScroll: true });
    }

    launcher.addEventListener("click", () => setOpen(panel.hidden));
    close.addEventListener("click", () => setOpen(false));
    chat.addEventListener("keydown", event => {
        if (event.key === "Escape" && !panel.hidden) {
            event.preventDefault();
            setOpen(false);
        }
    });
    form.addEventListener("submit", event => {
        event.preventDefault();
        if (pending || !input.value.trim()) return;
        const question = input.value;
        input.value = "";
        ask(question);
    });
    quickReplies.forEach(button => {
        button.addEventListener("click", () => ask(button.dataset.question));
    });
    viewport?.addEventListener("resize", fitViewport);
    viewport?.addEventListener("scroll", fitViewport);
    chat.hidden = false;
})();
