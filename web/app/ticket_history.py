"""The ticket history site: a member logs in and sees their closed tickets."""

import re
from datetime import datetime

from config.settings import (
    API_BASE,
    MYSTICRAFT_CLIENT_ID,
    MYSTICRAFT_CLIENT_SECRET,
    MYSTICRAFT_REDIRECT_URI,
    MYSTICRAFT_TOKEN,
)
from flask import Blueprint, abort, redirect, render_template, request, session

from utils.request import requests_session

ticket_history = Blueprint("ticket_history", __name__)

HOST = "ticket.mysticraft.xyz"
BOT = {"Authorization": f"Bot {MYSTICRAFT_TOKEN}"}
LOGIN_URL = (
    f"{API_BASE}/oauth2/authorize?client_id={MYSTICRAFT_CLIENT_ID}"
    f"&redirect_uri={MYSTICRAFT_REDIRECT_URI}"
    f"&response_type=code&scope=identify"
    f"&prompt=none"
)
ACTION_ROW = 1
BUTTON = 2


def page():
    """Gives the history page, or the login page to a visitor who is not logged in."""
    user = session.get("user_data")
    if not user:
        return render_template("ticket_history_login.html")
    return render_template("ticket_history.html", user=user)


def login_failed(reason):
    """Gives the login page with the reason the login did not work."""
    return render_template("ticket_history_login.html", error=reason)


def dm_channel(user_id):
    """Gives the bot's DM channel with a member, or None."""
    answer = requests_session.post(
        f"{API_BASE}/users/@me/channels", headers=BOT, json={"recipient_id": user_id}
    )
    if answer.status_code not in (200, 201):
        print(f"Failed to get DM channel with user {user_id}: {answer.status_code}")
        return None
    return answer.json()


def dm_messages(channel_id):
    """Gives every message of a DM channel, newest first."""
    messages, before = [], None
    while True:
        answer = requests_session.get(
            f"{API_BASE}/channels/{channel_id}/messages",
            headers=BOT,
            params={"limit": 100, **({"before": before} if before else {})},
        )
        if answer.status_code != 200:
            print(f"Error fetching messages: {answer.status_code}")
            return messages
        batch = answer.json()
        if not batch:
            return messages
        messages.extend(batch)
        before = batch[-1]["id"]


def server_name(description):
    """Gives the server named in bold in a closed-ticket embed, or None."""
    match = re.search(r"\*\*(.+?)\*\*", description or "")
    return match.group(1).replace("🎫", "").strip() if match else None


def closed_at(timestamp):
    """Gives an embed timestamp as a datetime, or None when it cannot be read."""
    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return None


def transcript_link(message):
    """Gives the address of the first link button under a message, or None."""
    for row in message.get("components", []):
        if row.get("type") != ACTION_ROW:
            continue
        for button in row.get("components", []):
            if button.get("type") == BUTTON and button.get("url"):
                return button["url"]
    return None


def closed_ticket(embed, link):
    """Gives what the history page shows for one closed-ticket embed."""
    fields = embed.get("fields", [])
    closed = closed_at(embed.get("timestamp", ""))
    return {
        "category": fields[0].get("value", "Others") if fields else "Tickets",
        "guild_name": server_name(embed.get("description", "")),
        "timestamp": closed,
        "date_str": closed.isoformat() if closed else "Unknown",
        "transcript_link": link,
        "closing_reason": fields[1].get("value") if len(fields) > 1 else None,
    }


def closed_tickets(messages):
    """Gives the closed tickets found in a member's DMs, newest first, one per transcript."""
    tickets, seen = [], set()
    for message in messages:
        link = transcript_link(message)
        for embed in message.get("embeds", []):
            if not embed.get("title", "").startswith("Ticket closed"):
                continue
            if link and link not in seen:
                seen.add(link)
                tickets.append(closed_ticket(embed, link))
    undated = datetime.min
    tickets.sort(
        key=lambda t: (
            t["timestamp"].replace(tzinfo=None) if t["timestamp"] else undated
        ),
        reverse=True,
    )
    return tickets


@ticket_history.before_request
def only_this_site():
    if request.host != HOST:
        abort(404)


@ticket_history.route("/api/tickets")
def tickets():
    user = session.get("user_data")
    if not user:
        return {"error": "Not authenticated"}, 401
    try:
        channel = dm_channel(user.get("id"))
        found = closed_tickets(dm_messages(channel["id"])) if channel else []
        return {"tickets": found, "error": None}
    except Exception as error:
        return {"tickets": [], "error": f"Error loading ticket history: {str(error)}"}


@ticket_history.route("/callback")
def callback():
    if request.args.get("error"):
        return login_failed("Authentication cancelled.")
    code = request.args.get("code")
    if not code:
        return login_failed("No authorization code received.")
    answer = requests_session.post(
        f"{API_BASE}/oauth2/token",
        data={
            "client_id": MYSTICRAFT_CLIENT_ID,
            "client_secret": MYSTICRAFT_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": MYSTICRAFT_REDIRECT_URI,
        },
    )
    if answer.status_code != 200:
        print("Token exchange failed:", answer.status_code)
        return login_failed("Failed to authenticate with Discord.")
    access_token = answer.json().get("access_token")
    if not access_token:
        return login_failed("Failed to retrieve access token.")
    user = requests_session.get(
        f"{API_BASE}/users/@me", headers={"Authorization": f"Bearer {access_token}"}
    )
    if user.status_code != 200:
        print("Failed to fetch user information:", user.status_code)
        return login_failed("Failed to fetch user information.")
    user = user.json()
    session["user_data"] = {
        "id": user.get("id"),
        "username": user.get("username"),
        "discriminator": user.get("discriminator"),
        "access_token": access_token,
    }
    return redirect("/")
