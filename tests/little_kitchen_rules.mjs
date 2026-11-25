import assert from "node:assert/strict";
import { doneness, newPizza, newProfile, nextDay, orderFor, place, scoreOrder, settle } from "../static/little-kitchen/rules.js";
import { recipes } from "../static/little-kitchen/data.js";

const profile = newProfile();
const order = orderFor(profile);
const pizza = newPizza();
assert.equal(place(pizza, profile, "sauce", 0), false);
assert.equal(place(pizza, profile, "dough", 0), true);
assert.equal(place(pizza, profile, "dough", 1), false);
for (const id of ["sauce", "cheese"]) {
    for (const sector of [0, 1, 2, 3]) assert.equal(place(pizza, profile, id, sector), true);
    assert.equal(profile.inventory[id], 6);
}
pizza.heat = 7;
assert.equal(scoreOrder(order, pizza, profile).score, 100);
assert.equal(settle(profile, order, pizza).xp, 20);
assert.equal(profile.coins, 57);
assert.equal(profile.totals.costs, 4);
assert.ok(scoreOrder(order, newPizza(), profile).score < 50);
for (const [heat, result] of [[0, "Undercooked"], [8, "Perfectly baked"], [11, "Overcooked"], [15, "Burnt"]]) {
    pizza.heat = heat;
    assert.equal(doneness(pizza, false), result);
}
profile.day = 3;
profile.totals.served = 2;
const half = orderFor(profile);
const halves = newPizza();
for (const [id, sector] of [["dough", 0], ["mushroom", 4], ["mushroom", 5], ["mushroom", 6],
    ["tomato", 1], ["tomato", 2], ["tomato", 3]]) {
    place(halves, profile, id, sector);
}
halves.chopped = { mushroom: 3, tomato: 3 };
const correct = scoreOrder(half, halves, profile).coverageScore;
halves.pieces.mushroom = new Set([0, 1, 2]);
assert.ok(scoreOrder(half, halves, profile).coverageScore < correct);
settle(profile, half, halves);
assert.equal(profile.summary, true);
nextDay(profile);
assert.equal(profile.day, 4);
assert.equal(profile.totals.served, 0);
assert.equal(recipes.length, 5);
console.log("Little Kitchen deterministic scoring, inventory, earnings, temperature, and progression passed.");
