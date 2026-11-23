from flask import Blueprint, jsonify, render_template, send_from_directory, current_app, url_for

pwa_bp = Blueprint("pwa", __name__)


@pwa_bp.get("/favicon.ico")
def favicon():
    return send_from_directory(current_app.static_folder, "icons/recipe-box-favicon.ico",
                               mimetype="image/vnd.microsoft.icon")


@pwa_bp.get("/manifest.webmanifest")
def manifest():
    icon = lambda name: url_for("static", filename=f"icons/{name}")
    response = jsonify({
        "id": url_for("home"), "start_url": url_for("home"),
        "scope": url_for("home"), "name": "Recipe Box", "short_name": "Recipe Box",
        "display": "standalone", "background_color": "#f6f4eb", "theme_color": "#304d3b",
        "icons": [
            {"src": icon("recipe-box-192.png"), "sizes": "192x192", "type": "image/png"},
            {"src": icon("recipe-box-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
        ],
    })
    response.mimetype = "application/manifest+json"
    return response


@pwa_bp.get("/service-worker.js")
def service_worker():
    response = send_from_directory(current_app.static_folder, "service-worker.js", mimetype="text/javascript")
    response.cache_control.no_cache = True
    return response


@pwa_bp.get("/offline")
def offline():
    return render_template("offline.html")
