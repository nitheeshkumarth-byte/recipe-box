# Recipe Box help

## Project overview and architecture

Recipe Box is a personal recipe manager. Flask routes render Jinja pages, while JavaScript handles interactive features such as the deck, themes, and chat. SQLAlchemy stores recipes, ingredients, and tags in SQLite locally or PostgreSQL when configured. Supabase Storage can hold photos in production. Gemini is optional for recipe suggestions, origins, and nutrition estimates.

## Add or create a recipe

Open Add Recipe, enter a title and cooking instructions, and optionally add servings, tags, ingredients, and a photo. Choose Save Recipe to add it to your collection.

## Edit or rename a recipe

Open a recipe and choose Edit. Change the title, ingredients, servings, or instructions and choose Save Changes. Changing the title clears the saved dish origin. Changing ingredients or servings clears the saved nutrition estimate.

## Delete a recipe

Open a recipe, choose Delete, and confirm. You can also delete a recipe from List view. Deletion has no undo in Recipe Box.

## Ingredients and quantities

On the Add or Edit page, choose Add ingredient and enter the name, amount, and unit. Leave the amount blank if it has no fixed quantity. Use the remove button next to an ingredient to drop that row.

## Upload, replace, and photo size limit

In the Add or Edit form, choose Upload a photo or Change photo, select a PNG, JPEG, GIF, or WebP up to 5 MB, then save. The new photo replaces the old one when the edit succeeds. If the database commit fails, the old photo is kept and the replacement is cleaned up. There is no separate Remove photo option.

## Servings, portions, and scaling

Change Servings on a recipe page to scale the ingredients for that visit. To change the saved number of servings, use Edit. Nutrition stays per serving as you adjust portions.

## Search, filters, and tags

Search from the home page by title, instructions, ingredient name, or tag. Click a tag to filter the collection. The search and tag filter can be used together. The home page shows nine recipes per page.

## Favorites and bookmarks

Open a recipe and choose Add to Favorites. Choose Favorites in the navigation to browse your saved favorites. Select Favorited again on the recipe to remove the bookmark.

## Ratings and stars

Open a recipe, choose one to five stars from the rating dropdown, and select Rate.

## Swipe the deck or switch to List

Choose Deck on the home page. Swipe left or right on mobile, drag on desktop, or use the arrow buttons or keyboard arrows. Tap the front card to open the recipe. Use List to view recipes at a glance. The deck cycles through the current page and respects reduced-motion settings.

## Theme and color palette

Choose Theme in the navigation and pick Sage, Ocean Blue, Lavender, Terracotta, or Midnight Dark. The recipe pages update immediately and the browser remembers the palette locally.

## AI recipe suggestions and Auto-fill

On Add Recipe, enter a dish title and choose Auto-fill to generate a draft with ingredients and instructions. Review the suggestions before saving. Auto-fill needs a configured Gemini API key and flags existing exact title matches.

## Nutrition, calories, and macros

On a recipe with ingredient quantities, choose Estimate nutrition. It uses Gemini to estimate calories, protein, carbs, and fat per serving. The app caches successful estimates and clears them when you edit the original ingredients or servings.

## Where a dish comes from

Choose Where does this dish come from? on the detail page. Gemini provides the likely origin and a short history when configured. The page calls the API endpoint POST /api/origin/<recipe_id>. Successful results are saved until the recipe is renamed.

## Sign in, access, and passwords

If you see the Sign in page, use your account email and password. If your browser shows a password prompt instead, use recipebox and the password from the site owner. For a password reset, contact the account administrator.

## Install and use the app offline

On a phone, use Add to Home Screen in your browser to install the web app. Opening recipes requires an internet connection, so you'll see an offline notice if you disconnect.

## Deployment, database, and photo storage

Recipe Box runs on Flask with SQLite for local development and can use Supabase PostgreSQL on Render. SQLAlchemy manages recipes and Alembic manages schema migrations. Live photos can use Supabase Storage via its S3-compatible API, while local photos are saved in the instance directory. Render can use /readyz to check database connectivity.

## API and Swagger documentation

Choose API Docs in the navigation to open the Swagger console. Mutation requests use a session-bound CSRF token. The console automatically includes the token on same-origin POST requests. The project's README explains how to configure a custom API client.

## Chef chat and session memory

The chef can read recipes you have access to and answer from their saved ingredients, instructions, ratings, origin, and nutrition. Try asking it to scale a recipe to eight servings or total the calories for a batch. It explains the arithmetic and can reuse the last recipe and serving count in follow-ups. It remembers context for up to 30 minutes and does not store raw questions or recipe text.
