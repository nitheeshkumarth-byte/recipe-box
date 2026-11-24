(() => {
    const chat = document.getElementById("chef-chat");
    if (!chat) return;

    const launcher = chat.querySelector(".chef-launcher");
    const launcherArea = chat.querySelector(".chef-launcher-area");
    const actions = chat.querySelector(".chef-actions");
    const talkAction = actions.querySelector('[data-chef-mode="talk"]');
    const chatAction = actions.querySelector('[data-chef-mode="chat"]');
    const panel = chat.querySelector(".chef-panel");
    const close = chat.querySelector(".chef-close");
    const transcript = chat.querySelector(".chef-transcript");
    const form = chat.querySelector(".chef-form");
    const input = chat.querySelector("#chef-question");
    const viewport = window.visualViewport;

    const quickReplies = chat.querySelectorAll("[data-question]");
    const send = form.querySelector('button[type="submit"]');
    const mic = form.querySelector(".chef-mic");
    const talk = chat.querySelector(".chef-talk");
    const voiceStatus = form.querySelector(".chef-voice-status");
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const synthesis = window.speechSynthesis;
    const canReadAloud = Boolean(synthesis && window.SpeechSynthesisUtterance);
    const canTalk = Boolean(SpeechRecognition && window.isSecureContext && canReadAloud);
    const language = document.documentElement.lang || "en";
    let pending = false;
    let talking = false;
    let recognition;
    let speech;

    function stopReading() {
        if (!speech) return;
        launcher.classList.remove("is-speaking");
        if (speech.button) speech.button.textContent = "Read aloud";
        speech = null;
        synthesis.cancel();
    }

    function readReply(text, button = null) {
        stopReading();
        cancelListening();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = language;
        const playback = { button };
        speech = playback;
        if (button) button.textContent = "Stop reading";
        if (talking) voiceStatus.textContent = "Chef is speaking…";
        utterance.onstart = () => {
            if (speech === playback) launcher.classList.add("is-speaking");
        };
        utterance.onend = () => {
            if (speech !== playback) return;
            launcher.classList.remove("is-speaking");
            speech = null;
            if (button) button.textContent = "Read aloud";
            if (talking) startListening();
        };
        const failed = () => {
            if (speech === playback) endConversation("Couldn’t read this reply aloud.");
        };
        utterance.onerror = failed;
        try {
            synthesis.speak(utterance);
        } catch {
            failed();
        }
    }

    function addReadAloud(message, text) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "chef-read-aloud";
        button.textContent = "Read aloud";
        button.addEventListener("click", () => {
            const wasReading = speech?.button === button;
            endConversation();
            if (!wasReading) readReply(text, button);
        });
        message.append(button);
    }

    function resetMic() {
        recognition = null;
        launcher.classList.remove("is-listening");
        mic.setAttribute("aria-pressed", "false");
        mic.setAttribute("aria-label", "Speak a question");
    }

    function cancelListening() {
        if (!recognition) return;
        const session = recognition;
        resetMic();
        session.abort();
    }

    function endConversation(message = "") {
        talking = false;
        cancelListening();
        stopReading();
        setPending(pending);
        voiceStatus.textContent = message;
    }

    function startListening() {
        if (panel.hidden || pending || recognition) return;
        stopReading();
        try {
            const session = new SpeechRecognition();
            session.lang = language;
            session.interimResults = false;
            let question = "";
            session.onresult = event => {
                if (recognition !== session) return;
                const spoken = event.results[event.resultIndex][0].transcript.trim();
                if (!spoken) return;
                if (talking) {
                    question = spoken;
                    return;
                }
                const draft = [input.value.trim(), spoken].filter(Boolean).join(" ");
                input.value = draft.slice(0, input.maxLength);
                voiceStatus.textContent = draft.length > input.maxLength
                    ? "Transcript shortened to fit. Review it before sending."
                    : "Review your transcript, then press Send.";
            };
            session.onerror = event => {
                if (recognition !== session) return;
                endConversation({
                    "not-allowed": "Microphone access was denied. You can still type your question.",
                    "audio-capture": "No microphone was found. You can still type your question.",
                    "no-speech": "No speech heard. Try the mic again or type your question.",
                }[event.error] || "Voice input is unavailable. You can still type your question.");
            };
            session.onend = () => {
                if (recognition !== session) return;
                resetMic();
                if (talking && question) {
                    const command = question.toLowerCase().replace(/[.!?]+$/, "").trim();
                    if (command === "stop listening" || command === "end voice") {
                        endConversation("Voice session ended.");
                    } else {
                        ask(question);
                    }
                    return;
                }
                if (["Listening…", "Finishing transcription…"].includes(voiceStatus.textContent)) {
                    endConversation("No speech heard. Start voice again or type your question.");
                }
            };
            recognition = session;
            launcher.classList.add("is-listening");
            if (!talking) {
                mic.setAttribute("aria-pressed", "true");
                mic.setAttribute("aria-label", "Stop listening");
            }
            voiceStatus.textContent = "Listening…";
            session.start();
        } catch {
            resetMic();
            endConversation("Couldn’t start the microphone. You can still type your question.");
        }
    }

    if (SpeechRecognition && window.isSecureContext) {
        mic.hidden = false;
        mic.addEventListener("click", () => {
            if (!recognition) return startListening();
            voiceStatus.textContent = "Finishing transcription…";
            recognition.stop();
        });
    }
    talk.hidden = !canTalk;
    talkAction.disabled = !canTalk;
    if (!canTalk) talkAction.title = "Voice is unavailable in this browser";
    talk.addEventListener("click", () => {
        if (talking) endConversation("Voice session ended.");
        else startConversation();
    });

    function startConversation() {
        if (!canTalk || pending || talking) return;
        cancelListening();
        talking = true;
        setPending(pending);
        startListening();
    }

    function addMessage(text, user = false, readAloud = false) {
        const message = document.createElement("div");
        message.className = `chef-message ${user ? "chef-user" : "chef-reply"}`;
        const speaker = document.createElement("span");
        speaker.className = "visually-hidden";
        speaker.textContent = user ? "You: " : "Chef: ";
        const body = document.createElement("p");
        body.className = "chef-message-text";
        body.append(speaker, text);
        message.append(body);
        if (readAloud && canReadAloud) addReadAloud(message, text);

        transcript.append(message);
        transcript.scrollTop = transcript.scrollHeight;
        return message;
    }

    function setPending(active) {
        pending = active;
        send.disabled = active;
        mic.disabled = active || talking;
        talk.disabled = active && !talking;
        talkAction.disabled = !canTalk || (active && !talking);
        talk.textContent = talking ? "End voice" : "Talk to Chef";
        quickReplies.forEach(button => { button.disabled = active; });
    }

    async function ask(question) {
        const text = question.trim().slice(0, input.maxLength);
        if (!text || pending) return;
        stopReading();
        cancelListening();
        voiceStatus.textContent = talking ? "Chef is thinking…" : "";
        setPending(true);
        addMessage(text, true);
        const status = addMessage("One moment…");
        let answer;
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
            answer = result.answer;
            addMessage(answer, false, true);
        } catch {
            addMessage("I could not connect to Recipe Box. Please try again.");
        } finally {
            status.remove();
            transcript.scrollTop = transcript.scrollHeight;
            setPending(false);
            if (talking) {
                if (answer) readReply(answer);
                else endConversation("Voice session ended. You can start it again.");
            }
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
        showActions(false);
        launcher.setAttribute("aria-label", open ? "Close Recipe Box help" : "Open Recipe Box help");
        launcher.classList.toggle("is-opening", open);
        launcher.classList.toggle("is-closing", !open);
        fitViewport();
        if (open) close.focus({ preventScroll: true });
        else {
            endConversation();
            launcher.focus({ preventScroll: true });
        }
    }

    function showActions(open) {
        actions.hidden = !open;
        launcher.setAttribute("aria-expanded", String(open || !panel.hidden));
    }

    launcherArea.addEventListener("pointerenter", event => {
        if (event.pointerType === "mouse") showActions(true);
    });
    launcherArea.addEventListener("pointerleave", event => {
        if (event.pointerType === "mouse" && !actions.contains(document.activeElement)) showActions(false);
    });
    launcherArea.addEventListener("focusout", event => {
        if (!launcherArea.contains(event.relatedTarget) && !launcherArea.matches(":hover")) showActions(false);
    });
    document.addEventListener("pointerdown", event => {
        if (!launcherArea.contains(event.target)) showActions(false);
    });
    launcher.addEventListener("click", () => {
        if (panel.hidden) showActions(true);
        else setOpen(false);
    });
    talkAction.addEventListener("click", () => {
        setOpen(true);
        startConversation();
    });
    chatAction.addEventListener("click", () => {
        endConversation();
        setOpen(true);
        input.focus({ preventScroll: true });
    });
    close.addEventListener("click", () => setOpen(false));
    chat.addEventListener("keydown", event => {
        if (event.key === "Escape" && !actions.hidden) {
            event.preventDefault();
            showActions(false);
            launcher.focus({ preventScroll: true });
        } else if (event.key === "Escape" && !panel.hidden) {
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
    window.addEventListener("pagehide", () => endConversation());
    document.addEventListener("visibilitychange", () => {
        if (document.hidden) endConversation();
    });
    chat.hidden = false;
})();
