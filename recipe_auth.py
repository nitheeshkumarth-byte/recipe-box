import base64
import hashlib
import json
import os
import re
import secrets
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
PENDING_TTL = 300


class AuthError(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


auth_http = build_opener(NoRedirect())


def configure_auth(app):
    local = app.config.get("LOCAL_DEVELOPMENT")
    auth_url = "" if local else os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    key = "" if local else os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()
    if bool(auth_url) != bool(key):
        raise RuntimeError("Set both SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY to enable accounts.")
    if auth_url and not safe_https(auth_url):
        raise RuntimeError("SUPABASE_URL must be an HTTPS URL.")
    if auth_url and not os.getenv("SECRET_KEY"):
        raise RuntimeError("Set a stable SECRET_KEY before enabling accounts.")
    public_url = "" if local else os.getenv("PUBLIC_APP_URL", "").strip().rstrip("/")
    configured_domains = "" if local else os.getenv("SUPABASE_SSO_DOMAINS", "")
    domains = frozenset(domain.strip().lower() for domain in configured_domains.split(",") if domain.strip())
    if domains and not safe_https(public_url):
        raise RuntimeError("Set an HTTPS PUBLIC_APP_URL before enabling SSO.")
    if safe_https(public_url):
        app.config["SESSION_COOKIE_SECURE"] = True
    app.config.update(
        ACCOUNT_AUTH=bool(auth_url), SUPABASE_URL=auth_url, SUPABASE_KEY=key,
        SUPABASE_REQUIRE_TOTP=os.getenv("SUPABASE_REQUIRE_TOTP") == "1",
        SUPABASE_SSO_DOMAINS=domains, PUBLIC_APP_URL=public_url,
    )
    app.register_blueprint(auth_bp)


def safe_https(url):
    if not isinstance(url, str):
        return False
    parsed = urlsplit(url)
    return parsed.scheme == "https" and bool(parsed.hostname) and parsed.username is None


def provider_call(path, payload, access_token=None):
    app = current_app
    headers = {"apikey": app.config["SUPABASE_KEY"], "Content-Type": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    call = Request(app.config["SUPABASE_URL"] + "/auth/v1" + path,
                   data=json.dumps(payload).encode(), headers=headers, method="POST")
    try:
        with auth_http.open(call, timeout=8) as upstream:
            received = json.loads(upstream.read(128_000))
    except HTTPError as error:
        status = error.code
        error.close()
        if status == 429:
            raise AuthError("Too many sign-in attempts. Please wait and try again.") from None
        if 400 <= status < 500:
            raise AuthError("Supabase could not complete that sign-in request.") from None
        raise AuthError("The sign-in service is temporarily unavailable.") from None
    except (URLError, TimeoutError, ValueError):
        raise AuthError("The sign-in service is temporarily unavailable.") from None
    if not isinstance(received, dict):
        raise AuthError("The sign-in service returned an unexpected reply.")
    return received


def claims_from_provider(result):
    # Only decode tokens from the configured Supabase HTTPS response, never client input.
    try:
        token = result["access_token"]
        payload = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        user_id = str(UUID(claims["sub"]))
        expiry = min(int(claims["exp"]), int(time.time()) + 3600)
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        raise AuthError("The sign-in service returned an invalid session.") from None
    if expiry <= time.time():
        raise AuthError("This sign-in expired. Please try again.")
    return token, user_id, expiry, claims.get("aal")


def signed_in_user():
    if session.get("recipe_account_exp", 0) > time.time():
        return session.get("recipe_account_id")
    session.pop("recipe_account_id", None)
    session.pop("recipe_account_exp", None)
    return None


def seal():
    digest = hashlib.sha256(b"recipe-box-pending-auth:" + current_app.secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def complete_account(user_id, expiry):
    session.clear()
    session["recipe_account_id"] = user_id
    session["recipe_account_exp"] = expiry
    return redirect(url_for("home"))


def begin_account(result):
    access_token, user_id, expiry, level = claims_from_provider(result)
    user = result.get("user") or {}
    factors = [item for item in user.get("factors", []) if item.get("status") == "verified"]
    totp = next((item for item in factors if item.get("factor_type") == "totp"), None)
    if level == "aal2" or not (factors or current_app.config["SUPABASE_REQUIRE_TOTP"]):
        return complete_account(user_id, expiry)
    if factors and not totp:
        raise AuthError("This app uses authenticator codes. Contact your account administrator.")
    encrypted = seal().encrypt(access_token.encode()).decode()
    if len(encrypted) > 2300:
        raise AuthError("This account's verification session is too large. Contact your administrator.")
    session.clear()
    session["recipe_pending"] = encrypted
    if totp:
        session["recipe_factor_id"] = str(UUID(totp["id"]))
    return redirect(url_for("auth.mfa"))


def pending_token():
    try:
        return seal().decrypt(session["recipe_pending"].encode(), ttl=PENDING_TTL).decode()
    except (InvalidToken, KeyError):
        return None


@auth_bp.before_request
def check_config():
    if not current_app.config["ACCOUNT_AUTH"]:
        abort(404)


@auth_bp.route("/sign-in", methods=["GET", "POST"])
def sign_in():
    if signed_in_user():
        return redirect(url_for("home"))
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        if 0 < len(email) <= 254 and 0 < len(password) <= 1024:
            try:
                return begin_account(provider_call("/token?grant_type=password", {"email": email, "password": password}))
            except AuthError as error:
                flash(str(error), "error")
        else:
            flash("Enter your account email and password.", "error")
    return render_template("sign_in.html")


@auth_bp.post("/sso")
def sso():
    domain = request.form.get("domain", "").strip().lower()
    if domain not in current_app.config["SUPABASE_SSO_DOMAINS"]:
        flash("Single sign-on is unavailable for that organization.", "error")
        return redirect(url_for("auth.sign_in"))
    verifier = secrets.token_urlsafe(48)
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    state = secrets.token_urlsafe(24)
    callback = current_app.config["PUBLIC_APP_URL"] + url_for("auth.sso_callback", state=state)
    try:
        result = provider_call("/sso", {
            "domain": domain, "redirect_to": callback, "skip_http_redirect": True,
            "code_challenge": code_challenge, "code_challenge_method": "s256",
        })
        if not safe_https(result.get("url")):
            raise AuthError("The identity provider returned an invalid sign-in link.")
    except AuthError as error:
        flash(str(error), "error")
        return redirect(url_for("auth.sign_in"))
    session["recipe_sso"] = [state, verifier, int(time.time()) + PENDING_TTL]
    return redirect(result["url"])


@auth_bp.get("/callback")
def sso_callback():
    setup = session.pop("recipe_sso", None)
    code = request.args.get("code", "")
    if setup and setup[0] == request.args.get("state") and setup[2] > time.time() and 0 < len(code) <= 512:
        try:
            return begin_account(provider_call("/token?grant_type=pkce", {"auth_code": code, "code_verifier": setup[1]}))
        except AuthError as error:
            flash(str(error), "error")
    else:
        flash("Your single sign-on request expired. Please start again.", "error")
    return redirect(url_for("auth.sign_in"))


@auth_bp.route("/mfa", methods=["GET", "POST"])
def mfa():
    token = pending_token()
    if not token:
        return redirect(url_for("auth.sign_in"))
    factor = session.get("recipe_factor_id")
    if request.method == "POST":
        try:
            if not factor:
                enrolled = provider_call("/factors", {"factor_type": "totp", "issuer": "Recipe Box"}, token)
                session["recipe_factor_id"] = str(UUID(enrolled["id"]))
                session["recipe_totp_setup"] = seal().encrypt(enrolled["totp"]["secret"].encode()).decode()
                return redirect(url_for("auth.mfa"))
            code = request.form.get("code", "").strip()
            if not re.fullmatch(r"[0-9]{6}", code):
                raise AuthError("Enter the six-digit code from your authenticator.")
            challenge = provider_call(f"/factors/{factor}/challenge", {}, token)
            verified = provider_call(f"/factors/{factor}/verify", {"challenge_id": challenge["id"], "code": code}, token)
            _, user_id, expiry, level = claims_from_provider(verified)
            if level != "aal2":
                raise AuthError("Verification did not complete. Please try again.")
            return complete_account(user_id, expiry)
        except (AuthError, KeyError, TypeError, ValueError) as error:
            flash(str(error) if isinstance(error, AuthError) else "Could not verify the authenticator.", "error")
    setup = session.get("recipe_totp_setup")
    try:
        secret = seal().decrypt(setup.encode(), ttl=PENDING_TTL).decode() if setup else None
    except InvalidToken:
        session.clear()
        return redirect(url_for("auth.sign_in"))
    return render_template("mfa.html", enrolled=bool(factor), setup_secret=secret)


@auth_bp.post("/sign-out")
def sign_out():
    session.clear()
    return redirect(url_for("auth.sign_in"))


@auth_bp.after_request
def prevent_caching(response):
    response.cache_control.no_store = True
    response.headers["Referrer-Policy"] = "no-referrer"
    return response
