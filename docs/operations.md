# Operating Recipe Box

## Individual accounts

1. Start with a separate Supabase project and private photo bucket for staging. Provision two Auth users so you can test both sides of the account boundary.
2. Configure `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, and a stable random `SECRET_KEY`. Leave both Supabase identity settings empty for legacy single-user mode.
3. Run the migration through `bash scripts/migrate.sh` with a role that can create and grant `recipe_box_runtime`. For a dedicated web and worker database login, grant that login membership in `recipe_box_runtime` and use it in `DATABASE_URL`. Put the schema owner connection in `MIGRATION_DATABASE_URL`. Use a direct or session-mode connection for migration and role management.
4. Existing recipes remain unowned until assigned. From a privileged connection, run `flask --app app claim-legacy-recipes USER_UUID` to preview the count. Re-run with `--apply` only after confirming the owner's Supabase Auth UUID. Legacy mode only shows unowned records.
5. For mandatory authenticator codes, set `SUPABASE_REQUIRE_TOTP=1` and enable enrollment and verification in Supabase. Provision accounts in Supabase Auth.
6. For SAML, configure the identity provider in Supabase, set `SUPABASE_SSO_DOMAINS` to the allowed comma-separated domains, and register `PUBLIC_APP_URL/auth/callback` with its state query in the redirect allowlist. Verify each organization before relying on SSO.
7. Keep account photos in a private bucket. Set `RECIPE_SIGNED_PHOTOS=1` after testing the S3 endpoint from staging. Signed links expire after two minutes. Leave `IMAGE_BASE_URL` unset for private deployments.

## Render and monitoring

An existing service can keep its name and adopt `bash scripts/migrate.sh` as its pre-deploy command, `bash scripts/start_web.sh` as its start command, and `/readyz` as its health path. Alternatively, import `render.yaml` after creating its `recipe-box-production` environment group. The Blueprint provisions paid web, worker, cache, and job instances. Use `render.staging.yaml` separately with its own Supabase database, bucket, and `recipe-box-staging` environment group.

Use separate Redis URLs for cache and queue. When no queue is configured, the original photo stays available. Without Redis, chat context uses the SQL cache. Set an OTLP collector endpoint and credentials if you want telemetry. Monitor account errors, database readiness, thumbnail queue latency, image errors and AI response times. The start script logs paths without query strings and excludes auth endpoints from automatic Flask tracing.

For optional hybrid retrieval, set `CHEF_HYBRID_SEARCH=1`, `CHEF_RAG_PROVIDER=gemini`, and `GEMINI_API_KEY`. Run `flask --app app rebuild-chef-index` as the schema owner with pgvector installed in the `extensions` schema. Rebuild after source or embedding-model changes. This opt-in mode sends vetted passages and filtered questions to Gemini. Local-only mode sends neither.

## Vercel frontend

Import the repository into Vercel with the repository root and the **Other** preset. The root `vercel.mjs` builds `web/` and routes API, auth, private media and PWA requests to the HTTPS origin in `RECIPE_BOX_BACKEND`. Set this public origin per Vercel environment. Preview and production should use separate backends and databases once staging is provisioned. All database and storage credentials stay on Render.

To develop locally, run `python app.py` and then `npm ci --prefix web` and `npm run --prefix web dev` in another shell. Set `RECIPE_BOX_BACKEND` before starting Vite if Flask is on an alternate port. Run `python -m tests.split_browser_smoke` with Playwright Chromium installed to check the frontend and proxy together.

Keep the production apex on Render until the Vercel preview passes sign-in, recipe, upload and offline checks. Verify `api.jobscope.eu` on Render, then proxy that record in Cloudflare. Set `RECIPE_BOX_BACKEND=https://api.jobscope.eu` and redeploy Vercel before moving the apex to Vercel. Using the apex itself as Vercel's backend after cutover would create a routing loop. Bypass shared caching for authenticated pages, API responses, and private photos. Keep the previous DNS target for rollback.

## Backup and restore drill

Configure Supabase database backups and point-in-time recovery to match your recovery target. Copy Storage objects to a separate protected backup location on a matching schedule. Database backups contain photo references, while Storage copies contain the files.

Restore both backups into an isolated staging database and bucket. Verify account isolation using two accounts, recipe edits, and photo downloads before documenting the elapsed recovery time and the matching backup timestamps. GitHub Actions tests a PostgreSQL dump and restore using disposable data.

## Web and native mobile apps

Open the HTTPS web app on a phone and install it from the browser. On iPhone, choose Add to Home Screen in Safari’s Share menu. The app shows an offline notice without caching private recipe pages.

The Expo app in `mobile/` reuses the hosted website and adds a native toolbar, hardware back navigation, and recipe-link sharing. Run `npm ci`, set `EXPO_PUBLIC_RECIPE_BOX_URL` to the staging HTTPS origin, and run `npm start`. To use SSO in the native shell, configure `EXPO_PUBLIC_RECIPE_BOX_SSO_ORIGINS` with the exact HTTPS origins and test the organization's embedded sign-in policy.

For a device build, link the project to your EAS account, set the corresponding preview and production URL variables, and run `eas build --profile preview --platform android` or `eas build --profile preview --platform ios`. Replace the example package identifiers with ones you control before linking store credentials.
