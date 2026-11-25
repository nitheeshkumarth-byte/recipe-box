export const ingredients = {
    dough: { name: "Dough", color: 0xe8bd7b, price: 2 },
    sauce: { name: "Sauce", color: 0xc34b39, price: 1 },
    cheese: { name: "Cheese", color: 0xf8dc8b, price: 1 },
    tomato: { name: "Tomato", color: 0xd86551, price: 1, chop: true },
    onion: { name: "Onion", color: 0xa66a9b, price: 1, chop: true },
    capsicum: { name: "Capsicum", color: 0x628959, price: 1, chop: true },
    mushroom: { name: "Mushroom", color: 0xb18b6d, price: 1, chop: true },
    paneer: { name: "Paneer", color: 0xeadab7, price: 2 },
    olive: { name: "Olives", color: 0x575446, price: 1 },
    corn: { name: "Corn", color: 0xeab653, price: 1 },
};

export const recipes = [
    { id: "cheese", name: "Cheese Pizza", unlock: 0, toppings: [] },
    { id: "tomato", name: "Tomato Pizza", unlock: 0, toppings: ["tomato"] },
    { id: "mushroom", name: "Mushroom Pizza", unlock: 0, toppings: ["mushroom"] },
    { id: "vegetable", name: "Vegetable Pizza", unlock: 45, toppings: ["onion", "capsicum", "tomato"] },
    { id: "paneer", name: "Paneer Pizza", unlock: 105, toppings: ["paneer", "onion"] },
];

export const customers = [
    { name: "Maya", skin: 0xc68662, hair: 0x573630, coat: 0x7b9a78, greeting: "Something cozy today, please." },
    { name: "Theo", skin: 0xf0ba8c, hair: 0x87594b, coat: 0xb46d5b, greeting: "I’ve been looking forward to lunch!" },
    { name: "Nila", skin: 0xad6f57, hair: 0x352a2b, coat: 0x7585a0, greeting: "Could you make my usual?" },
    { name: "Jo", skin: 0xe8a384, hair: 0x4e3736, coat: 0xd3a45d, greeting: "It smells wonderful in here." },
    { name: "Sam", skin: 0x915541, hair: 0x302c29, coat: 0x997292, greeting: "I’m ready for something from the oven." },
];

export const shop = [
    { id: "fern", name: "Fern wallpaper", price: 24, swatch: "#91a57d", kind: "wall" },
    { id: "rose", name: "Rose wallpaper", price: 24, swatch: "#c78b83", kind: "wall" },
    { id: "walnut", name: "Walnut counter", price: 32, swatch: "#80543f", kind: "counter" },
    { id: "plants", name: "Window herbs", price: 19, swatch: "#617e55", kind: "plants" },
    { id: "oven", name: "Calibrated oven", price: 42, swatch: "#986b5b", kind: "equipment" },
];

export const dayLength = 3;
export const baseIngredients = ["dough", "sauce", "cheese"];
export const temperatures = [190, 220, 250];
