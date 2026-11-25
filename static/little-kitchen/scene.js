import { ingredients } from "./data.js";

const W = 890;
const H = 510;
const center = { x: 443, y: 299 };
const ink = 0x67443d;
const crust = 0xe6ab67;
const cream = 0xffe8be;
const herb = 0x62805c;
const pantry = Object.keys(ingredients).map((id, index) => ({
    id, x: 25 + (index % 2) * 103, y: 74 + Math.floor(index / 2) * 77,
}));
const zones = { board: [696, 74, 169, 118], oven: [696, 211, 169, 160], pass: [696, 392, 169, 79] };

function block(g, x, y, w, h, radius, fill, line = ink) {
    g.fillStyle(fill).fillRoundedRect(x, y, w, h, radius);
    g.lineStyle(2, line, .8).strokeRoundedRect(x, y, w, h, radius);
}

function ellipse(g, x, y, w, h, fill, alpha = 1) {
    g.fillStyle(fill, alpha).fillEllipse(x, y, w, h);
}

function line(g, x, y, x2, y2, color, weight = 2) {
    g.lineStyle(weight, color, 1).lineBetween(x, y, x2, y2);
}

function piece(g, id, x, y, size = 18, chopped = false) {
    const color = ingredients[id].color;
    if (id === "mushroom" && !chopped) {
        block(g, x - size * .17, y, size * .34, size * .42, 3, 0xf5d7ad);
        ellipse(g, x, y - size * .08, size, size * .62, color);
        ellipse(g, x - size * .16, y - size * .23, size * .24, size * .1, cream, .8);
    } else if (["cheese", "paneer", "capsicum"].includes(id) || chopped) {
        for (let i = 0; i < 3; i++) {
            const dx = (i - 1) * size * .29;
            g.fillStyle(color).fillRoundedRect(x + dx - size * .16, y + (i % 2) * 5 - size * .23, size * .4, size * .41, 2);
            line(g, x + dx - 1, y + (i % 2) * 5 - size * .16, x + dx + size * .13, y + (i % 2) * 5 - size * .16, cream, 1);
        }
    } else {
        ellipse(g, x, y, size, size * .85, color);
        ellipse(g, x - size * .16, y - size * .15, size * .28, size * .14, cream, .75);
        if (id === "tomato") ellipse(g, x, y - size * .41, size * .34, 5, herb);
        if (id === "onion") {
            g.lineStyle(1, 0xffdbd8, .8).strokeCircle(x, y, size * .27);
            g.strokeCircle(x, y, size * .15);
        }
    }
}

function plant(g, x, y) {
    block(g, x - 23, y + 5, 46, 39, 9, 0xc77b60);
    line(g, x, y + 8, x, y - 35, herb, 4);
    for (const [dx, dy] of [[-12,-15],[12,-23],[-12,-31],[9,-42]]) ellipse(g, x + dx, y + dy, 25, 13, herb);
}

function diner(g, guest, x, y, mood, now) {
    const bob = Math.sin(now / 430) * 2.5;
    y += bob;
    ellipse(g, x, y + 110, 125, 19, 0x58463c, .22);
    block(g, x - 49, y + 34, 98, 79, 28, guest.coat);
    ellipse(g, x, y - 6, 82, 90, guest.hair);
    ellipse(g, x, y + 1, 69, 75, guest.skin);
    ellipse(g, x - 17, y - 22, 44, 32, guest.hair);
    ellipse(g, x + 14, y - 27, 43, 27, guest.hair);
    ellipse(g, x - 26, y + 10, 11, 7, 0xe28573, .65);
    ellipse(g, x + 26, y + 10, 11, 7, 0xe28573, .65);
    const blink = (now % 4200) < 135;
    for (const offset of [-13, 13]) ellipse(g, x + offset, y + 3, 5, blink ? 2 : 7, ink);
    if (mood === "Disappointed") {
        line(g, x - 7, y + 22, x, y + 17, ink, 2);
        line(g, x, y + 17, x + 7, y + 22, ink, 2);
    } else if (mood || (now % 1200) < 400) {
        ellipse(g, x, y + 20, 13, 7, ink);
    } else {
        line(g, x - 5, y + 19, x + 5, y + 19, ink, 2);
    }
}

function storefront(g, state, now) {
    const wall = state.profile.equipped.wall === "fern" ? 0xa7b794 : state.profile.equipped.wall === "rose" ? 0xd9a49b : 0xefd1ae;
    g.fillStyle(wall).fillRect(0, 0, W, H);
    for (let x = 18; x < W; x += 40) {
        g.fillStyle(0xfff3cd, .3).fillRect(x, 0, 9, 372);
    }
    block(g, 76, 65, 190, 240, 17, 0xaf7257);
    block(g, 88, 78, 166, 215, 11, 0xb4c4ae);
    for (const x of [126, 194]) ellipse(g, x, 236, 100, 108, 0x99b18d);
    ellipse(g, 200, 116, 41, 41, 0xf7e0a6);
    line(g, 171, 79, 171, 290, 0x8d5d46, 7);
    line(g, 90, 165, 250, 165, 0x8d5d46, 7);
    block(g, 614, 86, 186, 157, 12, 0x6f6c4e);
    for (let y = 110; y < 226; y += 21) line(g, 640, y, 770 - y % 13, y, 0xe4c59a, 3);
    plant(g, 799, 293);
    if (state.profile.equipped.plants) plant(g, 91, 299);
    const x = state.guestX;
    if (state.order) diner(g, state.order.customer, x, 235, state.result?.reaction, now);
    const color = state.profile.equipped.counter === "walnut" ? 0x875744 : 0xb87956;
    block(g, -25, 335, 940, 209, 12, color);
    block(g, -14, 326, W + 28, 32, 9, 0xe5a874);
    for (let i = 0; i < 6; i++) block(g, 30 + i * 148, 378, 108, 85, 10, color);
    ellipse(g, 155, 332, 66, 14, 0xf2d5a9);
    ellipse(g, 733, 321, 53, 13, 0xdfba79);
    ellipse(g, 733, 304, 37, 37, 0xce9f5e);
    ellipse(g, 733, 286, 9, 9, ink);
}

function area(g, x, y, w, h, color) {
    block(g, x, y + 5, w, h, 15, 0x724c3d);
    block(g, x, y, w, h, 15, color);
}

function pizzaArt(g, pizza, x, y, size) {
    ellipse(g, x + 4, y + 8, size + 14, size - 1, 0x583e30, .43);
    ellipse(g, x, y, size + 13, size + 13, 0xe6c697);
    if (!pizza.pieces.dough) {
        g.lineStyle(2, ink, .28).strokeCircle(x, y, size * .43);
        return;
    }
    const heat = pizza.heat;
    ellipse(g, x, y, size, size, heat > 13 ? 0x4d3933 : heat > 9 ? 0xa46440 : crust);
    ellipse(g, x, y, size * .85, size * .85, heat > 13 ? 0x755043 : 0xf6d793);
    const slice = Math.PI / 4;
    for (const sector of pizza.pieces.sauce || []) {
        const angle = (sector + .5) * slice - Math.PI / 2;
        const radius = size * .258;
        g.fillStyle(heat > 13 ? 0x6d382e : ingredients.sauce.color);
        g.slice(x, y, size * .422, angle - slice * .5, angle + slice * .5, false).fillPath();
        ellipse(g, x + Math.cos(angle) * radius, y + Math.sin(angle) * radius, size * .14, size * .105, 0xe07958, .48);
    }
    if (Object.keys(pizza.pieces).length > 1) {
        for (const [id, positions] of Object.entries(pizza.pieces)) {
            if (["dough", "sauce"].includes(id)) continue;
            for (const sector of positions) {
                const angle = (sector + .5) * slice - Math.PI / 2;
                const radius = size * (id === "cheese" ? .19 : .32);
                const offset = Object.keys(ingredients).indexOf(id) * 3;
                piece(g, id, x + Math.cos(angle) * radius + offset % 9, y + Math.sin(angle) * radius + offset % 4,
                    size * (id === "cheese" ? .12 : .105), pizza.chopped[id] >= 3);
            }
        }
    }
}

function workspace(g, state, now) {
    const pizza = state.pizza;
    g.fillStyle(0xe8ba87).fillRect(0, 0, W, H);
    for (let y = 0; y < H; y += 26) line(g, 0, y, W, y, 0xdba774, 1);
    block(g, -10, 27, W + 20, 28, 5, 0xa87358);
    area(g, 244, 75, 420, 394, 0xe9ad74);
    for (const bin of pantry) {
        area(g, bin.x, bin.y, 91, 64, state.selected === bin.id ? 0xf4d189 : 0xf5dab5);
        piece(g, bin.id, bin.x + 45, bin.y + 23, 32);
        if (!state.profile.inventory[bin.id] && !pizza.pieces[bin.id]) {
            g.fillStyle(ink, .24).fillRoundedRect(bin.x, bin.y, 91, 64, 15);
        }
    }
    area(g, ...zones.board, 0xf0bd83);
    const cut = state.selected && pizza.chopped[state.selected];
    if (ingredients[state.selected]?.chop) piece(g, state.selected, 745, 133, 43, cut >= 3);
    const chopDrop = Math.max(0, 13 - (now - state.chopAt) / 12);
    block(g, 782, 125 + chopDrop, 57, 15, 6, 0xc7d5c4);
    block(g, 825, 128 + chopDrop, 24, 10, 4, ink);
    area(g, ...zones.oven, 0xc18e76);
    block(g, 708, 229, 146, 101, 11, 0x6d5249);
    block(g, 719, 242, 124, 70, 9, pizza.oven === "on" ? 0xc47448 : 0x473b34);
    for (const x of [730, 754, 778, 802, 826]) ellipse(g, x, 347, 10, 10, 0xf4d0a4);
    if (pizza.oven === "on") {
        pizzaArt(g, pizza, 781, 277, 61);
        for (let i = 0; i < 4; i++) {
            const rise = (now / 450 + i * .25) % 1;
            ellipse(g, 744 + i * 23, 254 - rise * 45, 15 + 18 * rise, 11 + 10 * rise,
                pizza.heat > 13 ? 0x624b48 : 0xffe2b2, (1 - rise) * .5);
        }
    } else {
        pizzaArt(g, pizza, center.x, center.y, 243);
    }
    area(g, ...zones.pass, 0xecbd94);
    ellipse(g, 778, 428, 68, 40, 0xffecd2);
    ellipse(g, 778, 428, 47, 26, 0xd4a689);
    if (pizza.plated) pizzaArt(g, pizza, 778, 429, 32);
    if (state.drag) {
        const { id, x, y } = state.drag;
        ellipse(g, x + 4, y + 6, 40, 20, ink, .3);
        piece(g, id, x, y, 38);
    }
}

export function createRestaurant(Phaser, state, actions) {
    let art;
    let stationLabels = [];
    const game = new Phaser.Game({
        type: Phaser.AUTO,
        parent: "game-canvas",
        width: W,
        height: H,
        backgroundColor: "#eed6ad",
        banner: false,
        scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
        scene: {
            create() {
                art = this.add.graphics();
                const makeLabel = (x, y, text) => this.add.text(x, y, text, {
                    font: "bold 14px system-ui", color: "#51332d",
                }).setOrigin(.5, 0);
                stationLabels = [
                    ...pantry.map(bin => makeLabel(bin.x + 45, bin.y + 40, ingredients[bin.id].name)),
                    makeLabel(781, 84, "Chopping board"),
                    makeLabel(781, 215, "Oven"),
                    makeLabel(781, 452, "Plate & pass"),
                ];
                let gesture;
                const contains = (x, y, [left, top, w, h]) => x >= left && y >= top && x <= left + w && y <= top + h;
                const sector = (x, y) => Math.min(7, Math.floor(((Math.atan2(y - center.y, x - center.x) + Math.PI / 2 + Math.PI * 2)
                    % (Math.PI * 2)) / (Math.PI / 4)));
                const onPizza = (x, y) => Math.hypot(x - center.x, y - center.y) <= 134;
                this.input.on("pointerdown", pointer => {
                    if (state.screen !== "cook") return;
                    const { x, y } = pointer;
                    const bin = pantry.find(item => contains(x, y, [item.x, item.y, 91, 64]));
                    if (bin && state.pizza.oven === "idle") {
                        actions.select(bin.id);
                        gesture = { id: bin.id, x, y };
                    } else if (onPizza(x, y) && state.selected) {
                        actions.place(sector(x, y), true);
                        gesture = { spreading: state.selected === "sauce" };
                    } else if (contains(x, y, zones.board)) actions.chop();
                    else if (contains(x, y, zones.oven)) actions.oven();
                    else if (contains(x, y, zones.pass)) actions.plate();
                });
                this.input.on("pointermove", pointer => {
                    if (!gesture || state.screen !== "cook") return;
                    const { x, y } = pointer;
                    if (gesture.id && Math.hypot(x - gesture.x, y - gesture.y) > 7) state.drag = { id: gesture.id, x, y };
                    if (gesture.spreading && onPizza(x, y)) actions.place(sector(x, y), true);
                });
                this.input.on("pointerup", pointer => {
                    if (gesture?.id && state.drag && state.screen === "cook") {
                        const { x, y } = pointer;
                        if (onPizza(x, y)) actions.place(sector(x, y));
                        else if (contains(x, y, zones.board)) actions.chop();
                        else actions.notice("Drop ingredients on the pizza or chopping board.");
                    }
                    gesture = undefined;
                    state.drag = null;
                });
                this.input.on("pointerupoutside", () => { gesture = undefined; state.drag = null; });
                actions.ready();
            },
            update(now, delta) {
                actions.tick(Math.min(delta, 70) / 1000);
                const cooking = state.screen === "cook";
                for (const label of stationLabels) label.setVisible(cooking);
                if (cooking) {
                    pantry.forEach(({ id }, index) => {
                        const text = `${ingredients[id].name} · ${state.profile.inventory[id]}`;
                        if (stationLabels[index].text !== text) stationLabels[index].setText(text);
                    });
                }
                art.clear();
                if (cooking) workspace(art, state, now);
                else storefront(art, state, now);
            },
        },
    });
    return game;
}
