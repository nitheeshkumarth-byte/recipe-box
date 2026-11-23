"""Exercise normal recipe flows on a phone-sized browser viewport."""

import os
import threading
from unittest.mock import patch

from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///:memory:"}, clear=True):
    with patch("dotenv.load_dotenv"):
        from app import app

from model import db

with app.app_context():
    db.create_all()
server = make_server("127.0.0.1", 0, app)
threading.Thread(target=server.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{server.server_port}"

try:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        page = context.new_page()
        page.goto(url)
        assert "recipe-box-hero-mobile.webp" in page.locator(".collection-photo img").evaluate(
            "image => image.decode().then(() => image.currentSrc)"
        )
        page.get_by_role("link", name="Add Recipe").click()
        page.get_by_label("Title").fill("Weeknight rice")
        page.get_by_label("Step by step").fill("Cook the rice.")
        page.locator('input[name="ing_name"]').first.fill("Rice")
        page.locator('input[name="ing_amount"]').first.fill("2")
        page.locator('input[name="ing_unit"]').first.fill("cups")
        page.get_by_role("button", name="Save Recipe").click()
        front_card = page.locator('#recipe-deck .flashcard[data-depth="0"]')
        front_card.wait_for()
        assert "Weeknight rice" in front_card.inner_text()
        assert front_card.locator(".flashcard-media").bounding_box()["height"] > 205
        front_card.click()
        page.get_by_role("button", name="Add to Favorites").click()
        page.get_by_role("button", name="Theme").click()
        page.get_by_role("button", name="Midnight Dark").click()
        assert page.locator("html").get_attribute("data-palette") == "midnight"
        page.get_by_role("button", name="Open Recipe Box help").click()
        page.get_by_role("button", name="Scale to 8 servings").click()
        page.get_by_text("4 cups Rice", exact=False).wait_for()
        page.get_by_role("button", name="Upload a photo").click()
        page.get_by_text("up to 5 MB", exact=False).wait_for()
        assert page.locator(".chef-transcript details").count() == 0
        assert page.request.get(url + "/manifest.webmanifest").json()["display"] == "standalone"
        page.evaluate("navigator.serviceWorker.ready")
        page.reload()
        context.set_offline(True)
        page.goto(url)
        page.get_by_role("heading", name="Recipe Box is offline").wait_for()
        browser.close()
finally:
    server.shutdown()

print("Mobile viewport recipe CRUD entry, favorites, themes, grounded chat, and PWA offline checks passed.")
