"""Check the public request path without writing to the recipe collection."""

import argparse
import json
import sys
import time
from http.cookiejar import CookieJar
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener


def check(origin):
    client = build_opener(HTTPCookieProcessor(CookieJar()))
    client.addheaders = [("User-Agent", "Recipe Box production check")]

    def read_json(path, *, body=None, headers=None):
        request = Request(origin + path, data=body, headers=headers or {})
        with client.open(request, timeout=55) as response:
            if response.headers.get_content_type() != "application/json":
                raise ValueError(f"{path} returned a non-JSON response")
            return json.load(response)

    session = read_json("/api/session")
    token = session.get("csrf_token")
    if not token:
        raise ValueError("The public session did not include a CSRF token")
    catalog = read_json("/api/recipes")
    recipes = catalog.get("recipes", [])
    if not catalog.get("total") or not recipes:
        raise ValueError("The public recipe collection is empty")
    print("Recipe collection and session passed.", flush=True)

    sample = next((recipe for recipe in recipes if (recipe.get("photo") or "").startswith("/photos/")), None)
    if not sample:
        raise ValueError("The public recipe collection has no photo on its first page")
    recipe_id = sample.get("id")
    if type(recipe_id) is not int or recipe_id <= 0:
        raise ValueError("The sample recipe has an invalid ID")
    detail = read_json(f"/api/recipes/{recipe_id}")
    if not detail.get("instructions"):
        raise ValueError("The sample recipe has no instructions")
    photo = urlsplit(sample["photo"])
    if photo.netloc or photo.scheme or not photo.path.startswith("/photos/"):
        raise ValueError("The sample photo has an invalid path")
    with client.open(origin + sample["photo"], timeout=55) as response:
        if response.headers.get_content_maintype() != "image" or not response.read(128):
            raise ValueError("The sample recipe photo did not return an image")
    print("Recipe details and photo passed.", flush=True)

    chat = read_json("/api/chef-chat", body=json.dumps({"question": "How do I upload a photo?"}).encode(),
                     headers={"Content-Type": "application/json", "X-CSRF-Token": token})
    if not chat.get("success") or "5 MB" not in (chat.get("answer") or ""):
        raise ValueError("The public chef did not return the expected upload help")
    print("Public chef chat passed.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", default="https://www.jobscope.eu")
    origin = parser.parse_args().origin.rstrip("/")
    for attempt in range(2):
        try:
            check(origin)
            return 0
        except (URLError, TimeoutError, ValueError) as error:
            print(f"Production check {attempt + 1} failed: {error}", file=sys.stderr, flush=True)
            if attempt == 0:
                time.sleep(5)
    return 1


if __name__ == "__main__":
    sys.exit(main())
