"""Exercise Little Kitchen with real Phaser pointer events and a disposable session."""

import os
import threading
from unittest.mock import patch

from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///:memory:"}, clear=True), patch("dotenv.load_dotenv"):
    from app import app

from model import db

with app.app_context():
    db.create_all()

server = make_server("127.0.0.1", 0, app)
threading.Thread(target=server.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{server.server_port}"


def canvas_point(page, x, y):
    box = page.locator("#game-canvas canvas").bounding_box()
    return box["x"] + x * box["width"] / 890, box["y"] + y * box["height"] / 510


def add_at(page, ingredient, positions):
    page.get_by_label("Ingredient", exact=True).select_option(ingredient)
    for position in positions:
        page.get_by_label("Position", exact=True).select_option(str(position))
        page.get_by_role("button", name="Add ingredient", exact=True).click()


def serve(page):
    page.get_by_role("button", name="Remove pizza").click()
    page.get_by_role("button", name="Plate pizza").click()
    page.get_by_role("button", name="Serve", exact=True).click()


try:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel=os.getenv("RECIPE_CHROME_CHANNEL") or None)
        page = browser.new_page(viewport={"width": 1100, "height": 850})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(url)
        page.get_by_role("link", name="Play & Cook").click()
        page.get_by_role("button", name="Play", exact=True).click(timeout=20000)
        page.get_by_role("heading", name="Maya").wait_for()
        page.get_by_role("button", name="Clarify order").click()
        page.get_by_text("Dough · Sauce · Cheese", exact=True).wait_for()
        page.get_by_role("button", name="Accept order").click()

        origin = canvas_point(page, 65, 99)
        destination = canvas_point(page, 443, 299)
        page.mouse.move(*origin)
        page.mouse.down()
        page.mouse.move(*destination, steps=12)
        page.mouse.up()
        assert page.get_by_role("button", name="Start oven").is_enabled()
        page.get_by_text("Tap or keyboard controls", exact=True).click()
        add_at(page, "sauce", range(4))
        add_at(page, "cheese", range(4))
        page.get_by_role("button", name="Start oven").click()
        page.get_by_text("Perfectly baked", exact=True).wait_for(timeout=12000)
        serve(page)
        page.get_by_role("heading", name="Excellent").wait_for()

        for _ in range(2):
            page.get_by_role("button", name="Next customer").click()
            page.get_by_role("button", name="Accept order").click()
            page.get_by_text("Tap or keyboard controls", exact=True).click()
            add_at(page, "dough", [0])
            page.get_by_role("button", name="Start oven").click()
            serve(page)
            page.get_by_role("heading", name="Disappointed").wait_for()
            page.get_by_text("Missing sauce.", exact=True).wait_for()

        page.get_by_role("button", name="Day summary").click()
        page.get_by_role("heading", name="Day 1 complete").wait_for()
        page.get_by_text("3 / 3", exact=True).wait_for()
        page.reload()
        page.get_by_role("button", name="Continue game").click()
        page.get_by_role("heading", name="Day 1 complete").wait_for()
        page.get_by_role("button", name="Open next day").click()
        page.get_by_text("Day 2", exact=False).wait_for()
        page.get_by_role("button", name="Game menu").click()
        page.get_by_role("button", name="Restaurant", exact=True).click()
        fern = page.get_by_role("listitem").filter(has_text="Fern wallpaper")
        fern.get_by_role("button", name="Buy").click()
        assert fern.get_by_role("button", name="Equipped").is_disabled()
        page.reload()
        page.get_by_role("button", name="Restaurant", exact=True).click()
        assert fern.get_by_role("button", name="Equipped").is_disabled()
        assert not errors, errors

        mobile = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        touch = mobile.new_page()
        touch.goto(url + "/game")
        touch.get_by_role("button", name="Play", exact=True).tap(timeout=20000)
        touch.get_by_role("button", name="Accept order").tap()
        touch.touchscreen.tap(*canvas_point(touch, 65, 99))
        touch.touchscreen.tap(*canvas_point(touch, 443, 299))
        assert touch.get_by_role("button", name="Start oven").is_enabled()
        assert touch.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        browser.close()
finally:
    server.shutdown()

print("Little Kitchen mouse and touch, order scoring, day summary, and resume passed.")
