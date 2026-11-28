"""The website: fischl.app, the profile pages, ticket transcripts and the ticket history site."""

import os

from app import ticket_history
from app.logs import logs
from app.profile import profile
from config.settings import API_BASE, CLIENT_ID, PROFILE_REDIRECT_URI, REDIRECT_URI
from flask import Flask, abort, redirect, render_template, request, session

SITE = "fischl.app"
HOSTS = (SITE, ticket_history.HOST)

app = Flask(__name__, static_url_path="")
app.secret_key = os.urandom(24)
app.url_map.strict_slashes = False

for blueprint in (logs, profile, ticket_history.ticket_history):
    app.register_blueprint(blueprint)


def discord_login(redirect_uri):
    """Sends the visitor to Discord to log in to fischl.app."""
    return redirect(
        f"{API_BASE}/oauth2/authorize?client_id={CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code&scope=identify guilds"
        f"&prompt=none"
    )


def site_page(name):
    """Gives a static page of fischl.app; other sites get a 404."""
    if request.host != SITE:
        abort(404)
    return app.send_static_file(name)


@app.before_request
def restrict_domain():
    if not request.path.startswith("/logs") and request.host not in HOSTS:
        abort(404)


@app.errorhandler(404)
def page_not_found(error):
    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_server_error(error):
    return render_template("500.html"), 500


@app.route("/")
def home():
    if request.host == SITE:
        return app.send_static_file("index.html")
    return ticket_history.page()


@app.route("/login")
def login():
    if request.host == SITE:
        return discord_login(REDIRECT_URI)
    return redirect(ticket_history.LOGIN_URL)


@app.route("/auth")
def auth():
    return discord_login(PROFILE_REDIRECT_URI)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/variables")
def variables():
    return site_page("variables.html")


@app.route("/legal")
def legal():
    return site_page("legal/index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
