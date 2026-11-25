import { baseIngredients, customers, dayLength, ingredients, recipes, shop } from "./data.js";

/** @typedef {{served:number, successful:number, revenue:number, tips:number, costs:number, xp:number, reputation:number}} DayTotals */
/** @typedef {{day:number, coins:number, xp:number, reputation:number, summary:boolean, totals:DayTotals, inventory:Record<string,number>, mastery:Record<string,number>, owned:string[], equipped:Record<string,string>, music:number, effects:number}} Profile */
/** @typedef {{id:string, seconds:number, left:string|null, right:string|null, recipe:typeof recipes[number], customer:typeof customers[number]}} Order */
/** @typedef {{pieces:Record<string, Set<number>>, chopped:Record<string,number>, elapsed:number, heat:number, temperature:number, oven:"idle"|"on"|"off", plated:boolean, cost:number}} Pizza */

function totals() {
    return { served: 0, successful: 0, revenue: 0, tips: 0, costs: 0, xp: 0, reputation: 0 };
}

/** @returns {Profile} */
export function newProfile() {
    return {
        day: 1, coins: 30, xp: 0, reputation: 50, summary: false, totals: totals(),
        inventory: Object.fromEntries(Object.keys(ingredients).map(id => [id, 7])),
        mastery: {}, owned: [], equipped: {}, music: .22, effects: .55,
    };
}

const saveKey = "little-kitchen.v1";

export function loadProfile() {
    try {
        const saved = JSON.parse(localStorage.getItem(saveKey));
        const profile = newProfile();
        if (!saved || typeof saved !== "object") return null;
        for (const key of ["day", "coins", "xp", "reputation"]) {
            if (Number.isSafeInteger(saved[key]) && saved[key] >= (key === "day" ? 1 : 0)) profile[key] = saved[key];
        }
        profile.reputation = Math.min(100, profile.reputation);
        for (const key of Object.keys(profile.totals)) {
            if (Number.isSafeInteger(saved.totals?.[key])) profile.totals[key] = saved.totals[key];
        }
        profile.totals.served = Math.min(dayLength, Math.max(0, profile.totals.served));
        profile.summary = profile.totals.served === dayLength;
        for (const id of Object.keys(ingredients)) {
            if (Number.isSafeInteger(saved.inventory?.[id])) profile.inventory[id] = Math.min(99, Math.max(0, saved.inventory[id]));
        }
        for (const recipe of recipes) {
            if (Number.isSafeInteger(saved.mastery?.[recipe.id])) profile.mastery[recipe.id] = Math.max(0, saved.mastery[recipe.id]);
        }
        profile.owned = shop.filter(item => Array.isArray(saved.owned) && saved.owned.includes(item.id)).map(item => item.id);
        for (const item of shop) {
            if (profile.owned.includes(item.id) && saved.equipped?.[item.kind] === item.id) profile.equipped[item.kind] = item.id;
        }
        for (const key of ["music", "effects"]) {
            if (Number.isFinite(saved[key])) profile[key] = Math.min(1, Math.max(0, saved[key]));
        }
        return profile;
    } catch {
        return null;
    }
}

/** @param {Profile} profile */
export function saveProfile(profile) {
    try {
        localStorage.setItem(saveKey, JSON.stringify(profile));
        return true;
    } catch {
        return false;
    }
}

/** @param {Profile} profile */
export function nextDay(profile) {
    profile.day++;
    profile.totals = totals();
    profile.summary = false;
    for (const name of Object.keys(ingredients)) profile.inventory[name] = Math.max(profile.inventory[name], 5);
}

/** @param {Profile} profile @returns {Order} */
export function orderFor(profile) {
    const unlocked = recipes.filter(recipe => recipe.unlock <= profile.xp);
    const sequence = (profile.day - 1) * dayLength + profile.totals.served;
    const recipe = unlocked[sequence % unlocked.length];
    const half = profile.day >= 3 && profile.totals.served === 2;
    return { id: `${profile.day}-${profile.totals.served}`, customer: customers[sequence % customers.length],
        recipe, left: half ? "mushroom" : null, right: half ? "tomato" : null,
        seconds: half ? 110 : 75 + recipe.toppings.length * 12 };
}

/** @param {Order} order */
export function requirements(order) {
    return [...baseIngredients, ...(order.left ? [order.left, order.right] : order.recipe.toppings)];
}

/** @returns {Pizza} */
export function newPizza() {
    return { pieces: {}, chopped: {}, elapsed: 0, heat: 0, temperature: 220, oven: "idle", plated: false, cost: 0 };
}

/** @param {Pizza} pizza @param {Profile} profile @param {string} id @param {number} sector */
export function place(pizza, profile, id, sector) {
    if (!ingredients[id] || !Number.isInteger(sector) || sector < 0 || sector > 7 || pizza.oven !== "idle") return false;
    if (id !== "dough" && !pizza.pieces.dough) return false;
    if (id === "dough" && pizza.pieces.dough) return false;
    const positions = pizza.pieces[id];
    if (positions?.has(sector)) return false;
    if (!positions) {
        if (!profile.inventory[id] || profile.coins < ingredients[id].price) return false;
        profile.inventory[id]--;
        profile.coins -= ingredients[id].price;
        pizza.cost += ingredients[id].price;
        pizza.pieces[id] = new Set();
    }
    pizza.pieces[id].add(sector);
    return true;
}

/** @param {Pizza} pizza @param {boolean} calibrated */
export function doneness(pizza, calibrated) {
    if (pizza.heat < 6) return "Undercooked";
    if (pizza.heat <= (calibrated ? 11 : 9)) return "Perfectly baked";
    if (pizza.heat <= 13) return "Overcooked";
    return "Burnt";
}

/** @param {Order} order @param {Pizza} pizza @param {Profile} profile */
export function scoreOrder(order, pizza, profile) {
    const required = requirements(order);
    const actual = Object.keys(pizza.pieces);
    const missing = required.filter(id => !actual.includes(id));
    const extra = actual.filter(id => !required.includes(id));
    const ingredientsScore = 40 * Math.max(0, 1 - (missing.length + extra.length) / required.length);
    let coverage = 0;
    if (pizza.pieces.dough) coverage++;
    for (const id of required.slice(1)) {
        const positions = [...(pizza.pieces[id] || [])];
        const target = id === "sauce" || id === "cheese" ? 4 : 3;
        const correct = id === order.left ? positions.filter(sector => sector >= 4)
            : id === order.right ? positions.filter(sector => sector < 4) : positions;
        const distribution = Math.max(0, Math.min(1, (correct.length - (positions.length - correct.length)) / target));
        const preparation = ingredients[id].chop && (pizza.chopped[id] || 0) < 3 ? .7 : 1;
        coverage += distribution * preparation;
    }
    const baked = doneness(pizza, profile.owned.includes("oven"));
    const heatScore = { Undercooked: 3, "Perfectly baked": 25, Overcooked: 12, Burnt: 0 }[baked];
    const speed = 15 * Math.min(1, Math.max(0, (order.seconds - pizza.elapsed) / (order.seconds * .45)));
    const score = Math.round(ingredientsScore + 20 * coverage / required.length + heatScore + speed);
    const feedback = [
        ...missing.map(id => `Missing ${ingredients[id].name.toLowerCase()}.`),
        ...extra.map(id => `Unexpected ${ingredients[id].name.toLowerCase()}.`),
    ];
    if (coverage < required.length - missing.length) feedback.push("Spread toppings evenly and chop vegetables before adding them.");
    if (baked !== "Perfectly baked") feedback.push(`${baked}. Aim for the green zone before removing the pizza.`);
    if (speed < 10) feedback.push("The customer waited longer than expected.");
    return {
        score, ingredientsScore, coverageScore: 20 * coverage / required.length, heatScore, speed,
        reaction: score >= 90 ? "Excellent" : score >= 75 ? "Satisfied" : score >= 50 ? "Average" : "Disappointed",
        reward: score >= 50 ? Math.round(score / 4) : Math.round(score / 10),
        tip: score >= 90 ? 6 : score >= 75 ? 3 : 0, xp: Math.max(1, Math.floor(score / 5)),
        reputation: score >= 75 ? 2 : score < 50 ? -3 : 0, feedback,
    };
}

/** @param {Profile} profile @param {Order} order @param {Pizza} pizza */
export function settle(profile, order, pizza) {
    const result = scoreOrder(order, pizza, profile);
    const totals = profile.totals;
    profile.coins += result.reward + result.tip;
    profile.xp += result.xp;
    profile.reputation = Math.min(100, Math.max(0, profile.reputation + result.reputation));
    if (result.score >= 75) {
        totals.successful++;
        const id = order.left ? "mushroom" : order.recipe.id;
        profile.mastery[id] = (profile.mastery[id] || 0) + 1;
    }
    totals.served++;
    totals.revenue += result.reward + result.tip;
    totals.tips += result.tip;
    totals.costs += pizza.cost;
    totals.xp += result.xp;
    totals.reputation += result.reputation;
    profile.summary = totals.served >= dayLength;
    return result;
}
