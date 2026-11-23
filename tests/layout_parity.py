"""Compare shared component styles and widths across the two frontends."""

from pathlib import Path


def snapshot(page, origin, route, selectors, screenshot):
    page.goto(origin + route, wait_until="domcontentloaded")
    for selector in selectors:
        page.locator(selector).first.wait_for()
    page.evaluate("document.fonts.ready")
    page.screenshot(path=screenshot, full_page=True, animations="disabled")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), f"Horizontal overflow on {route}"
    return page.evaluate("""selectors => Object.fromEntries(selectors.map(selector => {
        const element = document.querySelector(selector);
        const css = getComputedStyle(element);
        return [selector, {
            display: css.display, radius: css.borderTopLeftRadius, background: css.backgroundColor,
            color: css.color, font: css.fontSize, width: element.getBoundingClientRect().width,
        }];
    }))""", selectors)


def check_layout_parity(browser, render_origin, vercel_origin, recipe_path):
    pages = {
        "home": ("/", {".collection-hero": 3, ".collection-photo": 3, ".search-bar form": 4, ".flashcard-media": 4}),
        "recipe": (recipe_path, {".recipe-card": 4, ".rate-btn": 8, "#servings-input": 8, "#ingredient-list li": 8}),
        "editor": ("/add", {".form-card": 4, ".file-drop": None, ".ingredient-row": 4, ".save-btn": 8}),
        "shopping": ("/shopping-list", {".shopping-grid": 4, ".shopping-card": 4, ".shopping-search button": 8}),
    }
    output = Path("test-results/visual")
    output.mkdir(parents=True, exist_ok=True)
    for width, height in ((390, 844), (1440, 900)):
        context = browser.new_context(viewport={"width": width, "height": height}, reduced_motion="reduce",
                                      service_workers="block")
        try:
            page = context.new_page()
            for name, (route, selectors) in pages.items():
                results = [snapshot(page, origin, route, list(selectors), output / f"{name}-{width}-{host}.png")
                           for origin, host in ((render_origin, "render"), (vercel_origin, "vercel"))]
                for selector, tolerance in selectors.items():
                    render, vercel = (result[selector] for result in results)
                    render_width, vercel_width = render.pop("width"), vercel.pop("width")
                    assert render == vercel, f"{name} at {width}px: {selector} style differs: {render} vs {vercel}"
                    if tolerance is not None:
                        assert abs(render_width - vercel_width) <= tolerance, (
                            f"{name} at {width}px: {selector} widths differ: {render_width} vs {vercel_width}"
                        )
        finally:
            context.close()
    print("Desktop and mobile layouts match across the Flask and Vite frontends.")
