"""Verify the Vite frontend against Flask through a same-origin proxy."""

import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError
from urllib.request import urlopen

from PIL import Image
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server
from tests.layout_parity import check_layout_parity

with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///:memory:"}, clear=True), patch("dotenv.load_dotenv"):
    import app as recipe_box

from model import Recipe, RecipeIngredient, db


def wait_for_frontend(frontend, url):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline and frontend.poll() is None:
        try:
            with urlopen(url, timeout=1):
                return
        except URLError:
            time.sleep(0.2)
    raise RuntimeError("Vite did not start. Run npm ci --prefix web first.")


with recipe_box.app.app_context():
    db.create_all()
server = make_server("127.0.0.1", 0, recipe_box.app)
threading.Thread(target=server.serve_forever, daemon=True).start()
with socket.socket() as port_probe:
    port_probe.bind(("127.0.0.1", 0))
    port = port_probe.getsockname()[1]

web = Path(__file__).resolve().parents[1] / "web"
url = f"http://127.0.0.1:{port}"
try:
    with tempfile.TemporaryDirectory() as folder, patch.object(recipe_box, "LOCAL_UPLOADS", Path(folder)):
        with subprocess.Popen(
            [shutil.which("node"), "node_modules/vite/bin/vite.js", "--host", "127.0.0.1", "--port", str(port), "--strictPort"],
            cwd=web, env={**os.environ, "RECIPE_BOX_BACKEND": f"http://127.0.0.1:{server.server_port}"},
        ) as frontend:
            try:
                wait_for_frontend(frontend, url)
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch()
                    context = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
                    page = context.new_page()
                    page.route("**/api/session", lambda route: route.fulfill(status=503, body="API unavailable"))
                    page.goto(url)
                    page.get_by_role("alert").wait_for()
                    assert "recipe-box-hero-mobile.webp" in page.locator(".collection-photo img").evaluate(
                        "image => image.decode().then(() => image.currentSrc)"
                    )
                    assert page.get_by_role("searchbox", name="Search recipes").is_visible()
                    page.unroute("**/api/session")
                    page.reload()
                    assert page.request.get(url + "/apidocs").ok
                    page.get_by_role("link", name="Add Recipe").click()
                    page.locator(".recipe-form .form-card").first.wait_for()
                    assert page.locator(".recipe-form .form-card").count() == 2
                    assert page.locator(".ingredient-row").evaluate("row => getComputedStyle(row).display") == "grid"
                    page.get_by_role("button", name="Add ingredient").click()
                    assert page.locator(".ingredient-row").count() == 2
                    page.get_by_role("button", name="Remove ingredient").last.click()
                    page.get_by_label("Title").fill("Weeknight rice")
                    page.get_by_label("Step by step").fill("Cook the rice.")
                    page.get_by_label("Ingredient name").fill("Rice")
                    page.get_by_label("Amount").fill("2")
                    page.get_by_label("Unit", exact=True).fill("cups")
                    photo = BytesIO()
                    Image.new("RGB", (20, 20), "red").save(photo, format="PNG")
                    page.get_by_label("Recipe photo").set_input_files({"name": "rice.png", "mimeType": "image/png", "buffer": photo.getvalue()})
                    page.get_by_role("button", name="Save Recipe").click()
                    page.get_by_role("heading", name="Weeknight rice").wait_for()
                    assert page.locator(".recipe-photo").evaluate("image => image.decode().then(() => image.naturalWidth)") == 20
                    assert page.locator(".actions-bar .action-btn").count() == 3
                    assert page.locator("#ingredient-list .ing-name").inner_text() == "Rice"
                    page.get_by_label("Rate:").select_option("4")
                    page.get_by_role("button", name="Rate", exact=True).click()
                    page.get_by_text("4 / 5", exact=True).wait_for()
                    page.get_by_role("button", name="Add to Favorites").click()
                    page.get_by_role("button", name="Remove from Favorites").wait_for()
                    page.get_by_role("button", name="Theme").click()
                    page.get_by_role("button", name="Midnight Dark").click()
                    assert page.locator("html").get_attribute("data-palette") == "midnight"
                    page.get_by_role("button", name="Open Recipe Box help").click()
                    page.get_by_role("button", name="Scale to 8 servings").click()
                    page.get_by_text("4 cups Rice", exact=False).wait_for()
                    page.get_by_role("button", name="Close help").click()
                    page.get_by_role("link", name="Edit", exact=True).click()
                    page.locator(".form-photo-preview").wait_for()
                    page.get_by_label("Title").fill("Updated rice")
                    page.get_by_role("button", name="Save Changes").click()
                    page.get_by_role("heading", name="Updated rice").wait_for()
                    page.get_by_role("link", name="Back to all recipes").click()
                    page.locator("#recipe-deck .flashcard[data-depth='0']").wait_for()
                    page.get_by_role("button", name="List", exact=True).click()
                    assert page.get_by_role("button", name="Delete Updated rice").is_visible()
                    assert page.locator("#recipe-list .mini-rating").count() == 1
                    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                    recipe_path = page.get_by_role("link", name="Updated rice", exact=True).get_attribute("href")
                    with recipe_box.app.app_context():
                        second = Recipe(title="Weekend rice", instructions="Steam the rice.", servings=2)
                        second.ingredient_lines = [RecipeIngredient(name="rice", unit="cup", amount=1),
                                                   RecipeIngredient(name="RICE", unit="g", amount=10)]
                        db.session.add(second)
                        db.session.commit()

                    page.get_by_role("link", name="Shopping List", exact=True).click()
                    for title in ("Updated rice", "Weekend rice"):
                        page.get_by_role("button", name=f"Add {title}", exact=True).click()
                    servings = page.get_by_role("spinbutton", name="Servings for Updated rice")
                    servings.fill("8")
                    servings.press("Tab")
                    total = page.get_by_role("checkbox", name="5 cups Rice", exact=True)
                    total.check()
                    assert page.get_by_role("checkbox", name="10 g RICE", exact=True).is_visible()
                    page.reload()
                    total.wait_for()
                    assert total.is_checked()
                    page.get_by_role("button", name="Remove Weekend rice", exact=True).click()
                    page.get_by_role("checkbox", name="4 cups Rice", exact=True).wait_for()
                    assert not page.get_by_role("checkbox", name="10 g RICE", exact=True).count()
                    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")

                    check_layout_parity(browser, f"http://127.0.0.1:{server.server_port}", url, recipe_path)
                    assert page.request.get(url + "/manifest.webmanifest").json()["display"] == "standalone"
                    page.evaluate("navigator.serviceWorker.ready")
                    page.reload()
                    context.set_offline(True)
                    page.goto(url)
                    page.get_by_role("heading", name="Recipe Box is offline").wait_for()
                    browser.close()
            finally:
                frontend.terminate()
finally:
    server.shutdown()

print("Split frontend recipe, photo, favorites, themes, chat, deck, shopping list, and offline checks passed.")
