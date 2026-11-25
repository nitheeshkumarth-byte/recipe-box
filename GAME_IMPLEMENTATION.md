# Little Kitchen

Open **Play & Cook** from Recipe Box or go to `/game`. Accept an order, drag dough and toppings onto the pizza, and use the oven and serving pass. **Tap or keyboard controls** exposes ingredients, positions, and chopping through standard controls.

## Integration

- Flask serves the game through the app’s existing access rules. Vercel and the Vite development proxy forward `/game` to Flask. Saved recipes, the recipe-specific **Let’s Cook** mode, and Chef chat stay on their existing routes.
- `static/little-kitchen/data.js` defines ingredients, recipes, customers, shop items, and day length. `rules.js` holds the JSDoc data contracts, scoring, inventory, progression, and save logic. `scene.js` draws the restaurant and handles Phaser pointer input. `game.js` handles screen transitions, keyboard controls, and audio.
- Phaser 3.90 is loaded from a pinned jsDelivr URL with a SHA-384 integrity check. First load needs CDN access. The game uses the existing JavaScript module setup so Flask can serve it without a separate build or Node runtime. Audio uses generated Web Audio tones. This release introduces no environment variables or database migrations.

## Playable release

- Five pizza recipes and five animated customers, three orders per day, and half-and-half orders from day three.
- Drag and tap ingredient placement, swipe-to-spread sauce, repeated chopping, an oven with three temperatures, plating, and serving.
- Deterministic scoring for ingredients, placement, doneness, and speed. Orders award coins and XP and change reputation. A day summary shows recipe expenses, tips, and order profit.
- Recipes unlock through XP. The shop sells two wallpapers, a counter, window herbs, and an oven upgrade.
- Browser saves update after completed orders, day transitions, settings changes, and purchases. An unfinished order restarts on reload. Data stays on the current browser and origin.

## Follow-on work

- Account-linked storage in the existing database, server-validated rewards and purchases, and cross-device recovery belong in the persistence phase. Browser values are a local game save.
- The original procedural art is the first asset pass. A production art pass can add coordinated sprite sheets, richer expressions, layered furnishings, and recorded audio. The current engine supports pizza assembly. Dough kneading, broader cooking mechanics, and other restaurant categories can extend it.
- Additional daily challenges, achievements, and shop categories remain future progression work.

## Verification

Run `node tests/little_kitchen_rules.mjs` for scoring, inventory, earnings, and temperature. Run `python -m tests.little_kitchen_smoke` for the order loop in Chromium. Set `RECIPE_CHROME_CHANNEL=chrome` to use locally installed Chrome. The browser test uses a disposable SQLite database and needs CDN access.
