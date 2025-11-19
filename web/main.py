import os

from flask import Flask, redirect, request, session, abort, render_template
from config.settings import API_BASE, CLIENT_ID, REDIRECT_URI, PROFILE_REDIRECT_URI

from app.logs import logs
from app.dashboard import dashboard
from app.tickets import tickets
from app.partnership import partnership
from app.profile import profile
from app.minigames import minigames

app = Flask(__name__, static_url_path="")
app.secret_key = os.urandom(24)
app.url_map.strict_slashes = False

blueprints = [logs, dashboard, tickets, partnership, profile, minigames]
for blueprint in blueprints:
    app.register_blueprint(blueprint)

@app.before_request
def restrict_domain():
    if not request.path.startswith("/logs") and request.host != "fischl.app":
      abort(404)

@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template("500.html"), 500

@app.route("/")
def home():
    return app.send_static_file("index.html")

@app.route("/login")
def login():
    scope = "identify guilds"
    return redirect(
        f"{API_BASE}/oauth2/authorize?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code&scope={scope}"
        f"&prompt=none"
    )

@app.route("/auth")
def auth():
    """Profile authentication route"""
    scope = "identify guilds"
    return redirect(
        f"{API_BASE}/oauth2/authorize?client_id={CLIENT_ID}"
        f"&redirect_uri={PROFILE_REDIRECT_URI}"
        f"&response_type=code&scope={scope}"
        f"&prompt=none"
    )

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
