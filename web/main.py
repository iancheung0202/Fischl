import os
import requests

from datetime import datetime
from flask import Flask, redirect, request, session, abort, render_template
from config.settings import API_BASE, CLIENT_ID, REDIRECT_URI, PROFILE_REDIRECT_URI, MYSTICRAFT_REDIRECT_URI, MYSTICRAFT_CLIENT_ID, MYSTICRAFT_CLIENT_SECRET, MYSTICRAFT_TOKEN

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
    if not request.path.startswith("/logs") and request.host not in ["fischl.app", "ticket.mysticraft.xyz"]:
      abort(404)

@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template("500.html"), 500

def get_dm_channel_with_user(user_id, bot_token):
    headers = {"Authorization": f"Bot {bot_token}"}
    
    response = requests.post(
        f"{API_BASE}/users/@me/channels",
        headers=headers,
        json={"recipient_id": user_id},
    )
    
    if response.status_code not in [200, 201]:
        return None
    
    channel = response.json()
    return channel


def fetch_dm_messages(channel_id, bot_token):
    headers = {"Authorization": f"Bot {bot_token}"}
    messages = []
    after = None
    
    while True:
        params = {"limit": 100}
        if after:
            params["after"] = after
        response = requests.get(f"{API_BASE}/channels/{channel_id}/messages", headers=headers, params=params,)
        if response.status_code != 200:
            break
        batch = response.json()
        if not batch:
            break
        messages.extend(batch)
        after = batch[-1]["id"]
    
    return messages


def extract_guild_name(description):
    if not description:
        return None
    import re
    match = re.search(r'\*\*(.+?)\*\*', description)
    if match:
        return match.group(1).replace("🎫", "").strip()
    return None


def extract_closed_tickets(messages):
    tickets = []
    seen_links = set()
    
    for message in messages:
        embeds = message.get("embeds", [])
        for embed in embeds:
            title = embed.get("title", "")
            if "closed" in title.lower() and "ticket" in title.lower():
                category = "Tickets"
                fields = embed.get("fields", [])
                if fields and len(fields) > 0:
                    category = fields[0].get("value", "Others")
                description = embed.get("description", "")
                guild_name = extract_guild_name(description)
                timestamp = embed.get("timestamp", "")
                timestamp_obj = None
                if timestamp:
                    try:
                        timestamp_obj = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    except:
                        pass
                transcript_link = None
                components = message.get("components", [])
                for component in components:
                    if component.get("type") == 1:
                        buttons = component.get("components", [])
                        for button in buttons:
                            if button.get("type") == 2:
                                if button.get("url"):
                                    transcript_link = button["url"]
                                    break
                    if transcript_link:
                        break
                if transcript_link and transcript_link not in seen_links:
                    seen_links.add(transcript_link)
                    tickets.append({
                        "category": category,
                        "guild_name": guild_name,
                        "timestamp": timestamp_obj,
                        "date_str": timestamp_obj.isoformat() if timestamp_obj else "Unknown",
                        "transcript_link": transcript_link,
                    })
    
    tickets.sort(key=lambda x: x["timestamp"] or datetime.min, reverse=True)
    return tickets

@app.route("/")
def home():
    if request.host == "fischl.app":
        return app.send_static_file("index.html")
    elif request.host == "ticket.mysticraft.xyz":
        user_data = session.get("user_data")
        if not user_data:
            return render_template("ticket_history_login.html")
        
        return render_template("ticket_history.html", user=user_data)
    else:
        abort(404)

@app.route("/api/tickets")
def get_tickets():
    if request.host != "ticket.mysticraft.xyz":
        abort(404)
    
    user_data = session.get("user_data")
    if not user_data:
        return {"error": "Not authenticated"}, 401
    
    try:
        user_id = user_data.get("id")
        dm_channel = get_dm_channel_with_user(user_id, MYSTICRAFT_TOKEN)
        if not dm_channel:
            return {"tickets": [], "error": None}
        messages = fetch_dm_messages(dm_channel["id"], MYSTICRAFT_TOKEN)
        tickets = extract_closed_tickets(messages)
        return {"tickets": tickets, "error": None}
    
    except Exception as e:
        return {"tickets": [], "error": f"Error loading ticket history: {str(e)}"}

@app.route("/login")
def login():
    if request.host == "fischl.app":
        scope = "identify guilds"
        return redirect(
            f"{API_BASE}/oauth2/authorize?client_id={CLIENT_ID}"
            f"&redirect_uri={REDIRECT_URI}"
            f"&response_type=code&scope={scope}"
            f"&prompt=none"
        )
    elif request.host == "ticket.mysticraft.xyz":
        scope = "identify"
        return redirect(
            f"{API_BASE}/oauth2/authorize?client_id={MYSTICRAFT_CLIENT_ID}"
            f"&redirect_uri={MYSTICRAFT_REDIRECT_URI}"
            f"&response_type=code&scope={scope}"
            f"&prompt=none"
        )
    else:
        abort(404)

@app.route("/auth")
def auth():
    """Profile authentication route"""
    scope = "identify guilds"
    return redirect(
        f"{API_BASE}/oauth2/authorize?client_id={MYSTICRAFT_CLIENT_ID}"
        f"&redirect_uri={MYSTICRAFT_REDIRECT_URI}"
        f"&response_type=code&scope={scope}"
        f"&prompt=none"
    )

@app.route("/callback")
def callback():
    """Callback route for ticket history authentication"""
    if request.host != "ticket.mysticraft.xyz":
        abort(404)
    
    code = request.args.get("code")
    error = request.args.get("error")
    
    if error:
        return render_template("ticket_history_login.html", error="Authentication cancelled.")
    
    if not code:
        return render_template("ticket_history_login.html", error="No authorization code received.")
    
    data = {
        "client_id": MYSTICRAFT_CLIENT_ID,
        "client_secret": MYSTICRAFT_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": MYSTICRAFT_REDIRECT_URI,
    }
    
    response = requests.post(f"{API_BASE}/oauth2/token", data=data)
    
    if response.status_code != 200:
        print("Token exchange failed:", response.text)
        return render_template("ticket_history_login.html", error="Failed to authenticate with Discord.")
    
    token_data = response.json()
    access_token = token_data.get("access_token")
    
    if not access_token:
        return render_template("ticket_history_login.html", error="Failed to retrieve access token.")
    
    headers = {"Authorization": f"Bearer {access_token}"}
    user_response = requests.get(f"{API_BASE}/users/@me", headers=headers)
    
    if user_response.status_code != 200:
        print("Failed to fetch user information:", user_response.text)
        return render_template("ticket_history_login.html", error="Failed to fetch user information.")
    
    user_info = user_response.json()
    
    session["user_data"] = {
        "id": user_info.get("id"),
        "username": user_info.get("username"),
        "discriminator": user_info.get("discriminator"),
        "access_token": access_token,
    }
    
    return redirect("/")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
