const stations = [
    { key: "chop", name: "Chopping board", pattern: /\b(chop|dice|mince|slice|julienne|shred|cube|grate)\b/i,
        label: "Chop", repetitions: 5 },
    { key: "knead", name: "Dough bench", pattern: /\b(knead|fold the dough|work the dough)\b/i,
        label: "Knead", repetitions: 6 },
    { key: "scoop", name: "Ice cream station", pattern: /\b(scoop|ice cream|gelato|sorbet)\b/i,
        label: "Scoop", repetitions: 3 },
    { key: "pot", name: "Stovetop", pattern: /\b(cook|simmer|boil|fry|sear|steam|heat|sauté|saute|poach|braise|reduce)\b/i,
        label: "Stir pot", repetitions: 3 },
    { key: "oven", name: "Oven", pattern: /\b(bake|roast|broil|preheat)\b/i,
        label: "Set tray", repetitions: 1 },
    { key: "mix", name: "Mixing station", pattern: /\b(mix|stir|whisk|combine|beat|fold|toss|blend|grind|purée|puree|mash|crush)\b/i,
        label: "Mix", repetitions: 5 },
];
const plating = { key: "plate", name: "Finishing station", label: "Finish step", repetitions: 1 };
const ingredientModifiers = new Set(["and", "fresh", "frozen", "dried", "ground", "whole", "chopped", "sliced"]);
const icons = [
    [/onion|shallot/i, "🧅"], [/carrot/i, "🥕"], [/tomato/i, "🍅"], [/garlic/i, "🧄"], [/pepper|capsicum/i, "🫑"],
    [/potato/i, "🥔"], [/spinach|lettuce|basil|cilantro|herb/i, "🥬"], [/mushroom/i, "🍄"], [/egg/i, "🥚"],
    [/strawberr/i, "🍓"], [/lemon/i, "🍋"], [/chicken|turkey/i, "🍗"], [/rice/i, "🍚"], [/flour|dough/i, "🌾"],
];

function duration(text) {
    const units = { h: 3600, m: 60, s: 1 };
    let total = 0;
    let lastEnd;
    const pattern = /\b(\d+(?:\.\d+)?)(?:\s*(?:[-–—]|to)\s*\d+(?:\.\d+)?)?\s*-?\s*(hours?|hrs?|h|minutes?|mins?|m|seconds?|secs?|s)\b/gi;
    for (const match of text.matchAll(pattern)) {
        // Join compound durations, such as 1 hour and 30 minutes, but keep separate actions independent.
        if (lastEnd !== undefined && !/^\s*,?\s*(?:and\s+)?$/i.test(text.slice(lastEnd, match.index))) break;
        total += Number(match[1]) * units[match[2][0].toLowerCase()];
        lastEnd = match.index + match[0].length;
    }
    const seconds = Math.round(total);
    return seconds > 0 && seconds <= 7 * 86400 ? seconds : 0;
}

export function cookingSteps(instructions) {
    const sentenceSegmenter = typeof Intl.Segmenter === "function" ? new Intl.Segmenter("en", { granularity: "sentence" }) : null;
    let text = instructions.trim();
    if (/^(?:step\s+)?\d+[.)]\s+/i.test(text)) {
        text = text.replace(/(^|\s)(?:step\s+)?\d+[.)][ \t]+(?=[a-z])/gi, "$1\n");
    }
    return text.split(/\r?\n/).flatMap(line => {
        const clean = line.replace(/^\s*(?:[-•*]|(?:step\s+)?\d+[.):])\s+/i, "").trim();
        if (!clean) return [];
        return sentenceSegmenter ? Array.from(sentenceSegmenter.segment(clean), item => item.segment.trim())
            : clean.split(/(?<=[.!?])\s+(?=[A-Z])/);
    }).flatMap(line => line.split(
        /\s*(?:,?\s+(?:and\s+then|then|and))\s+(?=(?:chop|dice|mince|slice|knead|scoop|mix|whisk|stir|cook|bake|simmer|boil|roast|fry|steam|serve)\b)/i,
    )).filter(Boolean).map(text => {
        const matches = stations.map(station => ({ station, index: text.search(station.pattern) }))
            .filter(match => match.index >= 0).sort((a, b) => a.index - b.index);
        const station = matches[0]?.station || plating;
        const cut = station.key === "chop" ? text.match(station.pattern)[0].toLowerCase() : "";
        const mix = station.key === "mix" ? text.match(/\b(whisk|blend|grind|mash)\b/i)?.[0].toLowerCase() : "";
        return { text, station, cut, mix, seconds: duration(text) };
    });
}

function formatTime(seconds) {
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const padded = n => String(n).padStart(2, "0");
    return hours ? `${hours}:${padded(minutes % 60)}:${padded(seconds % 60)}` : `${padded(minutes)}:${padded(seconds % 60)}`;
}

export function mountCookingGame(recipe) {
    const launch = recipe.querySelector("[data-cook-launch]");
    const steps = cookingSteps(recipe.querySelector(".recipe-instructions").textContent);
    if (!steps.length || typeof window.HTMLDialogElement?.prototype.showModal !== "function") return;
    let dialog;

    launch.hidden = false;
    launch.addEventListener("click", () => {
        dialog ??= buildGame(recipe, launch, steps);
        dialog.showModal();
    });
}

function buildGame(recipe, launch, steps) {
    const dialog = document.createElement("dialog");
    dialog.className = "cook-game";
    dialog.setAttribute("aria-labelledby", "cook-title");
    dialog.innerHTML = `
        <div class="cook-shell">
            <header class="cook-top">
                <div><p class="cook-kicker">Recipe Box Kitchen</p><h2 id="cook-title"></h2></div>
                <button type="button" class="cook-close" aria-label="Close cooking game">×</button>
            </header>
            <div class="cook-layout">
                <section class="cook-station" aria-label="Cooking station">
                    <div class="cook-stage-head"><span data-station></span><span data-step></span></div>
                    <div class="cook-stage" aria-hidden="true">
                        <div class="cook-bench"></div>
                        <div class="cook-board"><span class="cook-produce"></span><span class="cook-cuts"></span></div>
                        <div class="cook-knife"></div>
                        <div class="cook-bowl"><span></span></div><div class="cook-whisk"></div>
                        <div class="cook-dough"></div><div class="cook-hands"><span></span><span></span></div>
                        <div class="cook-cup"><i></i><i></i><i></i></div><div class="cook-scooper"></div>
                        <div class="cook-oven"><span></span></div>
                        <div class="cook-burner"></div><div class="cook-pot"><span></span></div>
                        <div class="cook-steam"><i></i><i></i><i></i></div>
                        <div class="cook-plate"><span></span></div>
                    </div>
                    <div class="cook-play"><button type="button" class="cook-primary" data-action></button><span data-action-count></span></div>
                </section>
                <section class="cook-details" aria-label="Recipe instructions">
                    <p class="cook-kicker" data-instruction-label>Instructions</p>
                    <p class="cook-instruction" data-instruction></p>
                    <ul class="cook-ingredients" aria-label="Ingredients mentioned in this step" hidden></ul>
                    <div class="cook-timer" hidden>
                        <span>Recipe timer</span><output aria-live="off">00:00</output>
                        <button type="button" data-timer-button>Start timer</button>
                        <button type="button" data-reset-timer>Reset</button>
                    </div>
                    <p class="cook-running" data-running hidden></p>
                    <p class="cook-status" role="status"></p>
                </section>
            </div>
            <footer class="cook-footer">
                <button type="button" data-prev>Previous</button>
                <progress aria-label="Recipe progress"></progress>
                <button type="button" class="cook-primary" data-next>Next step</button>
            </footer>
        </div>`;
    document.body.append(dialog);
    const find = selector => dialog.querySelector(selector);
    const title = recipe.querySelector("h1").textContent.trim().replace(/^★\s*/, "");
    find("h2").textContent = title;
    const stage = find(".cook-stage");
    const action = find("[data-action]");
    const actionCount = find("[data-action-count]");
    const output = find("output");
    const timerButton = find("[data-timer-button]");
    const running = find("[data-running]");
    const previous = find("[data-prev]");
    const next = find("[data-next]");
    const progress = find("progress");
    const status = find(".cook-status");
    const progressByStep = steps.map(() => 0);
    const timers = steps.map(step => ({ remaining: step.seconds * 1000, deadline: 0, done: false }));
    let current = 0;
    let clock;
    progress.max = steps.length;

    function renderTimer() {
        const timer = timers[current];
        find(".cook-timer").hidden = !timer || !steps[current].seconds;
        if (timer) {
            const left = timer.deadline ? Math.max(0, timer.deadline - Date.now()) : timer.remaining;
            output.value = formatTime(Math.ceil(left / 1000));
            output.classList.toggle("is-done", timer.done);
            timerButton.textContent = timer.deadline ? "Pause timer" : timer.done ? "Restart timer" :
                left < steps[current].seconds * 1000 ? "Resume timer" : "Start timer";
        }
        stage.classList.toggle("is-heating", Boolean(timer?.deadline));
        const active = timers.flatMap((item, index) => item.deadline && index !== current
            ? [`Step ${index + 1} · ${formatTime(Math.ceil(Math.max(0, item.deadline - Date.now()) / 1000))}`] : []);
        running.textContent = active.join("  /  ");
        running.hidden = !active.length;
    }

    function updateTimers() {
        for (const [index, timer] of timers.entries()) {
            if (timer.deadline && Date.now() >= timer.deadline) {
                timer.deadline = 0;
                timer.remaining = 0;
                timer.done = true;
                status.textContent = `Recipe timer complete for step ${index + 1}.`;
            }
        }
        if (!timers.some(timer => timer.deadline)) {
            window.clearInterval(clock);
            clock = undefined;
        }
        renderTimer();
    }

    function render() {
        const step = steps[current];
        const complete = !step;
        const station = step?.station || plating;
        const count = progressByStep[current] || 0;
        const ingredients = find(".cook-ingredients");
        const stepWords = new Set((step?.text.toLowerCase().match(/[a-z]+/g) || []).map(word => word.replace(/s$/, "")));
        const matched = [...recipe.querySelectorAll("#ingredient-list li")].filter(item => {
            const name = item.querySelector(".ing-name")?.textContent.toLowerCase().split(",")[0] || "";
            return name.split(/[^a-z]+/).some(word => word.length > 2 && !ingredientModifiers.has(word)
                && stepWords.has(word.replace(/s$/, "")));
        });
        ingredients.replaceChildren(...matched.map(item => {
            const row = document.createElement("li");
            row.textContent = [...item.querySelectorAll("span")].map(span => span.textContent.trim()).filter(Boolean).join(" ");
            return row;
        }));
        ingredients.hidden = !matched.length;
        find("[data-station]").textContent = complete ? "Service pass" : station.name;
        find("[data-step]").textContent = complete ? "Finished" : `Step ${current + 1} of ${steps.length}`;
        find("[data-instruction-label]").textContent = complete ? "Recipe complete" : "Instructions";
        find("[data-instruction]").textContent = step?.text || `${title} is ready to serve in your virtual kitchen.`;
        stage.dataset.station = station.key;
        stage.dataset.cut = step?.cut || "";
        stage.dataset.progress = count;
        stage.classList.remove("is-action");
        find(".cook-produce").textContent = icons.find(([pattern]) => pattern.test(step?.text || ""))?.[1] || "🥬";
        action.hidden = complete;
        const operation = step?.cut || step?.mix;
        action.textContent = operation ? operation[0].toUpperCase() + operation.slice(1) : station.label;
        actionCount.textContent = complete ? "" : `${count} / ${station.repetitions}`;
        action.disabled = count >= station.repetitions;
        previous.disabled = current === 0;
        next.textContent = complete ? "Back to recipe" : current === steps.length - 1 ? "Finish recipe" : "Next step";
        progress.value = Math.min(current + 1, steps.length);
        renderTimer();
    }

    action.addEventListener("click", () => {
        const station = steps[current].station;
        const count = ++progressByStep[current];
        stage.dataset.progress = count;
        stage.classList.remove("is-action");
        void stage.offsetWidth;
        stage.classList.add("is-action");
        actionCount.textContent = `${count} / ${station.repetitions}`;
        if (count >= station.repetitions) {
            action.disabled = true;
            status.textContent = "Station complete.";
            if (action === document.activeElement) next.focus();
        }
    });
    timerButton.addEventListener("click", () => {
        const timer = timers[current];
        if (timer.deadline) {
            timer.remaining = Math.max(0, timer.deadline - Date.now());
            timer.deadline = 0;
        } else {
            timer.remaining ||= steps[current].seconds * 1000;
            timer.deadline = Date.now() + timer.remaining;
            timer.done = false;
            clock ??= window.setInterval(updateTimers, 250);
        }
        status.textContent = "";
        updateTimers();
    });
    find("[data-reset-timer]").addEventListener("click", () => {
        Object.assign(timers[current], { remaining: steps[current].seconds * 1000, deadline: 0, done: false });
        status.textContent = "";
        updateTimers();
    });
    previous.addEventListener("click", () => {
        current--;
        status.textContent = "";
        render();
    });
    next.addEventListener("click", () => {
        if (current === steps.length) return dialog.close();
        current++;
        status.textContent = "";
        render();
    });
    find(".cook-close").addEventListener("click", () => dialog.close());
    dialog.addEventListener("close", () => launch.focus({ preventScroll: true }));
    launch.addEventListener("click", render);
    render();
    return dialog;
}
