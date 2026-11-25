import { dayLength, ingredients, recipes, shop, temperatures } from "./data.js";
import { doneness, loadProfile, newPizza, newProfile, nextDay, orderFor, place, requirements, saveProfile, settle } from "./rules.js";
import { createRestaurant } from "./scene.js";

const panel = document.getElementById("game-panel");
const hud = document.getElementById("game-hud");
const home = document.getElementById("game-home");
const live = document.getElementById("game-notice");
const frame = document.querySelector(".game-frame");
const saved = loadProfile();
const state = {
    profile: saved || newProfile(), screen: "menu", order: null, pizza: null,
    result: null, selected: null, drag: null, chopAt: -Infinity, guestX: 448, started: Boolean(saved),
};
let engine;
let audio;
let ambience;

function sound(note = 380, length = .14) {
    if (!audio || !state.profile.effects || audio.state !== "running") return;
    const oscillator = audio.createOscillator();
    const gain = audio.createGain();
    oscillator.frequency.setValueAtTime(note, audio.currentTime);
    oscillator.frequency.exponentialRampToValueAtTime(note * .69, audio.currentTime + length);
    gain.gain.setValueAtTime(state.profile.effects * .1, audio.currentTime);
    gain.gain.exponentialRampToValueAtTime(.001, audio.currentTime + length);
    oscillator.connect(gain).connect(audio.destination);
    oscillator.start();
    oscillator.stop(audio.currentTime + length);
}

function updateAmbience() {
    window.clearInterval(ambience);
    if (!audio || !state.profile.music || document.hidden) return;
    let beat = 0;
    ambience = window.setInterval(() => {
        if (audio.state !== "running") return;
        const oscillator = audio.createOscillator();
        const gain = audio.createGain();
        oscillator.type = "sine";
        oscillator.frequency.value = [196, 247, 294, 330, 294, 247][beat++ % 6];
        gain.gain.setValueAtTime(state.profile.music * .065, audio.currentTime);
        gain.gain.exponentialRampToValueAtTime(.001, audio.currentTime + .66);
        oscillator.connect(gain).connect(audio.destination);
        oscillator.start();
        oscillator.stop(audio.currentTime + .66);
    }, 530);
}

function notice(text = "") { live.textContent = text; }
function persist() {
    if (!saveProfile(state.profile)) notice("Browser storage is unavailable. This run is playable until you leave the page.");
}

function coinLabel() {
    const { day, coins, reputation, xp } = state.profile;
    hud.textContent = `Day ${day}   ·   ${coins} coins   ·   Reputation ${reputation}   ·   Level ${1 + Math.floor(xp / 45)}`;
}

function screen(name, html, shouldFocus = true) {
    state.screen = name;
    frame.dataset.screen = name;
    panel.innerHTML = html;
    home.hidden = name === "menu";
    hud.hidden = name === "menu";
    coinLabel();
    if (shouldFocus) panel.querySelector("h1,h2")?.focus({ preventScroll: true });
}

const heading = text => `<h2 tabindex="-1">${text}</h2>`;
const button = (id, label, primary = false) => `<button type="button" data-action="${id}"${primary ? ' class="game-primary"' : ""}>${label}</button>`;
const actionsBar = content => `<div class="game-actions">${content}</div>`;
const recipeName = () => state.order.left ? "Half-and-half pizza" : state.order.recipe.name;
const orderItems = () => state.order.left ? "Mushrooms on the left, tomatoes on the right. Sauce and cheese across the whole pizza."
    : requirements(state.order).map(id => ingredients[id].name).join(" · ");

function menu() {
    state.order = null;
    state.result = null;
    notice();
    screen("menu", `<h1 tabindex="-1">Little Kitchen</h1><p class="game-subtitle">The neighborhood pizza shop</p>${actionsBar(
        button("play", state.started ? "Continue game" : "Play", true) + button("shop", "Restaurant") +
        button("book", "Recipe book") + button("settings", "Settings") + '<a href="/">Exit to website</a>',
    )}`);
}

function customer() {
    if (state.profile.summary) return daySummary();
    state.order = orderFor(state.profile);
    state.result = null;
    state.pizza = newPizza();
    state.selected = null;
    state.drag = null;
    state.clarified = false;
    state.arrival = 0;
    state.guestX = -66;
    sound(750, .3);
    showCustomer();
}

function showCustomer(focus = true) {
    const { order } = state;
    screen("customer", `${heading(order.customer.name)}
        <p class="game-dialogue">${state.clarified ? orderItems() :
            `${order.customer.greeting} I’d like a ${recipeName().toLowerCase()}.`}</p>
        <div class="game-meters"><label>Patience <meter id="counter-patience" min="0" max="${order.seconds}" value="${Math.max(0, order.seconds - state.pizza.elapsed)}"></meter></label></div>
        ${actionsBar(button("accept", "Accept order", true) + button("clarify", "Clarify order"))}`, focus);
}

function showCooking() {
    screen("cook", `${heading(recipeName())}
        <p class="game-ticket">${orderItems()}</p>
        <div class="game-meters">
            <label>Patience <meter id="game-patience" min="0" max="${state.order.seconds}" high="${state.order.seconds * .6}" low="${state.order.seconds * .2}" optimum="${state.order.seconds}"></meter></label>
            <label>Oven <meter id="game-heat" min="0" max="15" low="6" high="9" optimum="7"></meter><span id="game-doneness"></span></label>
        </div>
        <p id="game-hint" class="game-hint">Drag dough onto the board, then spread sauce, cheese, and toppings.</p>
        ${actionsBar(button("oven", "Start oven", true) + button("plate", "Plate pizza") + button("serve", "Serve") + button("discard", "Discard"))}
        <details class="game-access">
            <summary>Tap or keyboard controls</summary>
            <div class="game-actions">
                <label>Ingredient <select id="game-ingredient" aria-label="Ingredient">${Object.entries(ingredients).map(([id, item]) => `<option value="${id}">${item.name}</option>`).join("")}</select></label>
                <label>Position <select id="game-sector" aria-label="Position">${["Upper-right", "Right upper", "Right lower", "Lower-right", "Lower-left", "Left lower", "Left upper", "Upper-left"].map((label, index) => `<option value="${index}">${label}</option>`).join("")}</select></label>
                ${button("place", "Add ingredient")}${button("chop", "Chop selected")}
                <label>Oven temperature <select id="game-temp" aria-label="Oven temperature">${temperatures.map(value => `<option${value === 220 ? " selected" : ""}>${value}</option>`).join("")}</select> °C</label>
            </div>
        </details>`);
    updateCooking();
}

function updateCooking() {
    if (state.screen !== "cook") return;
    const pizza = state.pizza;
    panel.querySelector("#game-patience").value = Math.max(0, state.order.seconds - pizza.elapsed);
    panel.querySelector("#game-heat").value = pizza.heat;
    panel.querySelector("#game-doneness").textContent = pizza.oven === "idle" ? "Ready" : doneness(pizza, state.profile.owned.includes("oven"));
    const oven = panel.querySelector('[data-action="oven"]');
    oven.disabled = !pizza.pieces.dough || pizza.oven === "off";
    oven.textContent = pizza.oven === "on" ? "Remove pizza" : "Start oven";
    panel.querySelector('[data-action="plate"]').disabled = pizza.oven !== "off" || pizza.plated;
    panel.querySelector('[data-action="serve"]').disabled = !pizza.plated;
    panel.querySelector("#game-temp").disabled = pizza.oven !== "idle";
}

function select(id) {
    if (state.pizza.oven !== "idle") return;
    state.selected = id;
    panel.querySelector("#game-ingredient").value = id;
    const stock = state.profile.inventory[id];
    const loaded = state.pizza.pieces[id];
    const prep = ingredients[id].chop ? ` · Chop ${state.pizza.chopped[id] || 0}/3` : "";
    panel.querySelector("#game-hint").textContent = `${ingredients[id].name} · ${stock} portions in stock${prep}${loaded ? ` · ${loaded.size} placed` : ""}`;
}

function addIngredient(sector, quiet = false) {
    const { pizza, profile, selected } = state;
    if (selected && place(pizza, profile, selected, sector)) {
        sound(310 + sector * 30, .085);
        select(selected);
        coinLabel();
        updateCooking();
    } else if (!quiet) {
        notice(!pizza.pieces.dough && selected !== "dough" ? "Add dough first." :
            "That spot is filled, the oven is in use, or the ingredient is unavailable.");
    }
}

function chop() {
    if (!ingredients[state.selected]?.chop || state.pizza.oven !== "idle") {
        notice("Select a fresh vegetable to use the chopping board.");
        return;
    }
    const pizza = state.pizza;
    pizza.chopped[state.selected] = Math.min(3, (pizza.chopped[state.selected] || 0) + 1);
    state.chopAt = engine.loop.now;
    sound(220, .055);
    select(state.selected);
}

function oven() {
    const pizza = state.pizza;
    if (pizza.oven === "idle" && pizza.pieces.dough) {
        pizza.oven = "on";
        sound(450, .14);
        notice("Watch the oven meter. Remove the pizza when it’s perfectly baked.");
    } else if (pizza.oven === "on") {
        pizza.oven = "off";
        sound(670, .25);
        notice("Pizza removed. Move it to the plate, then serve the customer.");
    } else {
        notice("Prepare a pizza before using the oven.");
    }
    updateCooking();
}

function plate() {
    if (state.pizza.oven !== "off" || state.pizza.plated) return;
    state.pizza.plated = true;
    sound(510);
    updateCooking();
    notice("Pizza plated and ready to serve.");
}

function serve() {
    if (!state.pizza.plated) return;
    state.result = settle(state.profile, state.order, state.pizza);
    persist();
    sound(state.result.score >= 75 ? 780 : 250, .38);
    const result = state.result;
    screen("result", `${heading(result.reaction)}
        <p class="game-score">${result.score}<small>/ 100</small></p>
        <p>+${result.reward} coins · +${result.tip} tip · +${result.xp} XP</p>
        <p class="game-metrics">Ingredients ${Math.round(result.ingredientsScore)}/40 · Placement ${Math.round(result.coverageScore)}/20 · Bake ${result.heatScore}/25 · Speed ${Math.round(result.speed)}/15</p>
        <ul>${(result.feedback.length ? result.feedback : ["Everything on the order was just right."]).map(item => `<li>${item}</li>`).join("")}</ul>
        ${actionsBar(button("next", state.profile.summary ? "Day summary" : "Next customer", true))}`);
    notice();
}

function daySummary() {
    const { totals, day } = state.profile;
    screen("summary", `${heading(`Day ${day} complete`)}
        <dl class="game-totals">
            <dt>Customers served</dt><dd>${totals.served} / ${dayLength}</dd>
            <dt>Successful orders</dt><dd>${totals.successful}</dd>
            <dt>Failed orders</dt><dd>${totals.served - totals.successful}</dd>
            <dt>Revenue</dt><dd>${totals.revenue} coins</dd>
            <dt>Ingredient expenses</dt><dd>${totals.costs} coins</dd>
            <dt>Tips included</dt><dd>${totals.tips} coins</dd>
            <dt>Order profit</dt><dd>${totals.revenue - totals.costs} coins</dd>
            <dt>Experience</dt><dd>+${totals.xp} XP</dd>
            <dt>Reputation change</dt><dd>${totals.reputation}</dd>
        </dl>
        ${actionsBar(button("new-day", "Open next day", true) + button("shop", "Visit restaurant shop"))}`);
}

function recipeBook() {
    screen("book", `${heading("Recipe book")}<ul class="game-list">${recipes.map(recipe =>
        `<li><strong>${recipe.name}</strong><span>${requirements({ recipe }).map(id => ingredients[id].name).join(" · ")}</span>
            <span>${recipe.unlock > state.profile.xp ? `Unlocks at ${recipe.unlock} XP` :
                `Mastery · ${state.profile.mastery[recipe.id] || 0} successful orders`}</span></li>`).join("")}</ul>`);
}

function restaurant() {
    screen("shop", `${heading("Your restaurant")}<ul class="game-list">${shop.map(item => {
        const owned = state.profile.owned.includes(item.id);
        const equipped = state.profile.equipped[item.kind] === item.id;
        return `<li><span class="game-swatch" style="--swatch:${item.swatch}"></span><strong>${item.name}</strong>
            <button type="button" data-shop="${item.id}"${equipped ? " disabled" : ""}>
            ${equipped ? "Equipped" : owned ? "Equip" : `Buy · ${item.price} coins`}</button></li>`;
    }).join("")}</ul>`);
}

function settings() {
    screen("settings", `${heading("Settings")}
        <label>Music <input type="range" min="0" max="1" step=".05" value="${state.profile.music}" data-setting="music"></label>
        <label>Sound effects <input type="range" min="0" max="1" step=".05" value="${state.profile.effects}" data-setting="effects"></label>`);
}

const handlers = {
    play() { state.started = true; persist(); customer(); },
    accept() { showCooking(); },
    clarify() { state.clarified = true; showCustomer(false); panel.querySelector('[data-action="accept"]').focus(); },
    next() { customer(); },
    "new-day"() { nextDay(state.profile); persist(); customer(); },
    oven, plate, serve, chop,
    place() { addIngredient(Number(panel.querySelector("#game-sector").value)); },
    discard() {
        if (!Object.keys(state.pizza.pieces).length) return;
        const { cost, elapsed } = state.pizza;
        state.pizza = { ...newPizza(), cost, elapsed };
        state.selected = null;
        showCooking();
        notice("Pizza discarded. Ingredient costs still count.");
    },
    shop: restaurant, book: recipeBook, settings,
};

function tick(delta) {
    if (document.hidden) return;
    if (state.screen === "customer") {
        state.arrival = Math.min(1, state.arrival + delta / .85);
        state.guestX = -66 + 514 * (1 - (1 - state.arrival) ** 3);
        if (state.arrival === 1) {
            state.pizza.elapsed += delta;
            panel.querySelector("#counter-patience").value = Math.max(0, state.order.seconds - state.pizza.elapsed);
        }
    } else if (state.screen === "result") {
        state.guestX = Math.min(970, state.guestX + delta * 48);
    } else if (state.screen === "cook") {
        state.pizza.elapsed += delta;
        if (state.pizza.oven === "on") state.pizza.heat += delta * (state.pizza.temperature / 220) ** 2;
        tick.accumulator = (tick.accumulator || 0) + delta;
        if (tick.accumulator >= .12) { tick.accumulator = 0; updateCooking(); }
    }
}

if (!window.Phaser) {
    panel.innerHTML = `<h1>Little Kitchen</h1><p role="alert">The game engine couldn’t load. Check your connection and reload.</p><a href="/">Back to Recipe Box</a>`;
} else {
    engine = createRestaurant(window.Phaser, state, { ready: menu, tick, select, place: addIngredient, chop, oven, plate, notice });
}

panel.addEventListener("click", event => {
    const target = event.target.closest("button");
    if (!target) return;
    if (!audio && window.AudioContext) {
        audio = new AudioContext();
        updateAmbience();
    }
    if (audio?.state === "suspended") void audio.resume().catch(() => {});
    const item = shop.find(entry => entry.id === target.dataset.shop);
    if (!item) {
        handlers[target.dataset.action]?.();
        return;
    }
    const profile = state.profile;
    if (!profile.owned.includes(item.id)) {
        if (profile.coins < item.price) { notice("You need more coins for this item."); return; }
        profile.coins -= item.price;
        profile.owned.push(item.id);
    }
    profile.equipped[item.kind] = item.id;
    persist();
    restaurant();
    notice(`${item.name} equipped.`);
});
panel.addEventListener("change", event => {
    if (event.target.id === "game-ingredient") select(event.target.value);
    else if (event.target.id === "game-temp") state.pizza.temperature = Number(event.target.value);
    else if (["music", "effects"].includes(event.target.dataset.setting)) {
        state.profile[event.target.dataset.setting] = Number(event.target.value);
        updateAmbience();
        sound();
        persist();
    }
});
home.addEventListener("click", () => {
    if (state.screen === "cook" && state.pizza.cost &&
        !window.confirm("Return to the game menu? This order will restart.")) return;
    if (state.screen === "cook") state.profile = loadProfile() || newProfile();
    menu();
});
document.addEventListener("visibilitychange", updateAmbience);
window.addEventListener("pagehide", event => {
    if (event.persisted) return;
    window.clearInterval(ambience);
    if (audio) void audio.close().catch(() => {});
    engine?.destroy(true);
});
