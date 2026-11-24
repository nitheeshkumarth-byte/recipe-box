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
        context.add_init_script("""
            window.SpeechRecognition = class {
                start() {
                    window.chefRecognition = this;
                    window.chefListeningCount = (window.chefListeningCount || 0) + 1;
                }
                stop() {
                    this.onresult({ resultIndex: 0, results: [[{ transcript: 'Scale this recipe for 8 servings' }]] });
                    this.onend();
                }
                abort() { window.chefMicAborted = true; this.onend(); }
            };
            window.speechSynthesis.speak = utterance => {
                window.chefUtterance = utterance;
                utterance.onstart();
            };
            window.speechSynthesis.cancel = () => { window.chefSpeechCancelled = true; };
        """)
        page = context.new_page()
        # A browser with the old unversioned CSS must request the current stylesheet instead.
        page.route("**/static/style.css", lambda route: route.fulfill(
            content_type="text/css", body=".collection-hero { display: flex; }"
        ))
        page.goto(url)
        entrance = page.get_by_role("button", name="Enter kitchen")
        entrance.wait_for()
        assert abs(entrance.bounding_box()["height"] - 844) < 1
        backdrop = page.locator(".kitchen-backdrop")
        assert backdrop.locator("canvas").evaluate("canvas => getComputedStyle(canvas).filter") == "grayscale(1)"
        assert backdrop.evaluate("""element => {
            const cutoff = parseFloat(getComputedStyle(element).getPropertyValue('--kitchen-nav-bottom'));
            return Math.abs(cutoff - document.querySelector('body > header').getBoundingClientRect().bottom) < 1;
        }""")
        background = page.evaluate("getComputedStyle(document.documentElement).backgroundImage")
        assert "linear-gradient" in background and "15%" in background and "86%" in background
        entrance.click()
        kitchen = page.get_by_role("dialog", name="The Executive Kitchen")
        kitchen.get_by_role("img", name="Overhead view", exact=False).wait_for()
        assert kitchen.locator("canvas").evaluate("canvas => getComputedStyle(canvas).animationName") == "kitchen-lights-on"
        kitchen.get_by_role("button", name="Pause motion").click()
        kitchen.get_by_role("button", name="Resume motion").wait_for()
        page.keyboard.press("Escape")
        assert not kitchen.is_visible()
        backdrop.locator("canvas").wait_for()
        assert entrance.evaluate("door => door === document.activeElement")
        stylesheet = page.locator('link[href*="/static/release/"]').get_attribute("href")
        css_response = page.request.get(url + stylesheet)
        assert css_response.ok and "immutable" in css_response.headers["cache-control"]
        assert "recipe-box-hero-mobile.webp" in page.locator(".collection-photo img").evaluate(
            "image => image.decode().then(() => image.currentSrc)"
        )
        hero = page.locator(".collection-hero").bounding_box()
        photo = page.locator(".collection-photo").bounding_box()
        search = page.get_by_role("searchbox", name="Search recipes").bounding_box()
        assert abs(photo["width"] - hero["width"]) < 1
        assert abs(photo["height"] - hero["height"]) < 1
        assert hero["x"] < search["x"] < search["x"] + search["width"] < hero["x"] + hero["width"]
        page.get_by_role("link", name="Add Recipe").click()
        page.get_by_role("button", name="Generate Photo").wait_for()
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
        page.get_by_role("button", name="Chat", exact=True).click()
        page.get_by_role("button", name="Speak a question").click()
        page.get_by_role("button", name="Stop listening").click()
        question = page.get_by_role("textbox", name="Ask about your recipes or Recipe Box")
        assert question.input_value() == "Scale this recipe for 8 servings"
        assert page.get_by_role("status").get_by_text("Review your transcript, then press Send.").is_visible()
        assert page.locator(".chef-user").count() == 0
        page.get_by_role("button", name="Send", exact=True).click()
        page.get_by_text("4 cups Rice", exact=False).wait_for()
        page.get_by_role("button", name="Read aloud").click()
        assert "4 cups Rice" in page.evaluate("window.chefUtterance.text")
        page.get_by_role("button", name="Stop reading").click()
        assert page.evaluate("window.chefSpeechCancelled")
        page.get_by_role("button", name="Speak a question").click()
        page.get_by_role("button", name="Close help").click()
        assert page.evaluate("window.chefMicAborted")
        page.get_by_role("button", name="Open Recipe Box help").click()
        page.get_by_role("button", name="Chat", exact=True).click()
        page.get_by_role("button", name="Speak a question").click()
        page.evaluate("""() => {
            window.chefRecognition.onerror({ error: 'not-allowed' });
            window.chefRecognition.onend();
        }""")
        assert page.get_by_text("Microphone access was denied.", exact=False).is_visible()
        listened = page.evaluate("window.chefListeningCount")
        page.get_by_role("button", name="Close help").click()
        page.get_by_role("button", name="Open Recipe Box help").click()
        page.get_by_role("button", name="Talk", exact=True).click()
        page.evaluate("window.chefRecognition.stop()")
        page.get_by_text("Chef is speaking…", exact=True).wait_for()
        assert "4 cups Rice" in page.evaluate("window.chefUtterance.text")
        assert page.locator(".chef-launcher.is-speaking").count() == 1
        assert page.evaluate("window.chefListeningCount") == listened + 1
        page.evaluate("window.chefUtterance.onend()")
        page.get_by_text("Listening…", exact=True).wait_for()
        assert page.locator(".chef-launcher.is-speaking").count() == 0
        assert page.evaluate("window.chefListeningCount") == listened + 2
        page.evaluate("""() => {
            const listener = window.chefRecognition;
            listener.onresult({ resultIndex: 0, results: [[{ transcript: 'Stop listening.' }]] });
            listener.onend();
        }""")
        page.get_by_text("Voice session ended.", exact=True).wait_for()
        page.get_by_role("button", name="Talk to Chef").wait_for()
        assert page.locator(".chef-user").count() == 2
        page.get_by_role("button", name="Upload a photo").click()
        page.get_by_text("up to 5 MB", exact=False).wait_for()
        assert page.locator(".chef-transcript details").count() == 0
        desktop = browser.new_page()
        desktop.goto(url)
        desktop.get_by_role("button", name="Open Recipe Box help").hover()
        desktop.get_by_role("button", name="Talk", exact=True).wait_for()
        desktop.get_by_role("button", name="Chat", exact=True).click()
        assert desktop.get_by_role("dialog", name="Recipe Box help").is_visible()
        desktop.close()
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
