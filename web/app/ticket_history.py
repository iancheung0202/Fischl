import requests
import json
import os
from flask import Blueprint, request, session, render_template, redirect, url_for, abort
from datetime import datetime
from config.settings import (
    API_BASE,
    MYSTICRAFT_CLIENT_ID,
    MYSTICRAFT_REDIRECT_URI,
    MYSTICRAFT_CLIENT_SECRET,
    MYSTICRAFT_TOKEN,
)

ticket_history = Blueprint("ticket_history", __name__, url_prefix="/")

def get_dm_channel_with_user(user_id, bot_token):
    """Fetch DM channel between bot and user using bot token"""
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
    """Fetch all messages from a DM channel using bot token"""
    headers = {"Authorization": f"Bot {bot_token}"}
    messages = []
    after = None
    
    while True:
        params = {"limit": 100}
        if after:
            params["after"] = after
        
        response = requests.get(
            f"{API_BASE}/channels/{channel_id}/messages",
            headers=headers,
            params=params,
        )
        
        if response.status_code != 200:
            break
        
        batch = response.json()
        if not batch:
            break
        
        messages.extend(batch)
        after = batch[-1]["id"]
    
    return messages


def extract_closed_tickets(messages):
    """Extract closed ticket info from messages with 'Ticket closed' embeds"""
    tickets = []
    
    for message in messages:
        embeds = message.get("embeds", [])
        for embed in embeds:
            title = embed.get("title", "")
            if "closed" in title.lower() and "ticket" in title.lower():
                category = "Tickets"
                fields = embed.get("fields", [])
                if fields and len(fields) > 0:
                    category = fields[0].get("value", "Tickets")
                
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
                
                if transcript_link:
                    tickets.append({
                        "category": category,
                        "timestamp": timestamp_obj,
                        "date_str": timestamp_obj.strftime("%B %d, %Y") if timestamp_obj else "Unknown",
                        "transcript_link": transcript_link,
                    })
    
    tickets.sort(key=lambda x: x["timestamp"] or datetime.min, reverse=True)
    return tickets


@ticket_history.route("/")
def index():
    if request.host.split(':')[0] != "ticket.mysticraft.xyz":
        abort(404)
    
    user_data = session.get("user_data")
    
    if not user_data:
        return render_template("ticket_history_login.html")
    
    try:
        user_id = user_data.get("id")
        
        # Fetch DM channel with user using bot token
        dm_channel = get_dm_channel_with_user(user_id, MYSTICRAFT_TOKEN)
        
        if not dm_channel:
            return render_template("ticket_history.html", tickets=[], user=user_data)
        
        # Fetch messages from DM channel using bot token
        messages = fetch_dm_messages(dm_channel["id"], MYSTICRAFT_TOKEN)
        
        # Extract closed tickets
        tickets = extract_closed_tickets(messages)
        
        return render_template("ticket_history.html", tickets=tickets, user=user_data)
    
    except Exception as e:
        return render_template("ticket_history.html", tickets=[], user=user_data, error=f"Error loading ticket history: {str(e)}")


@ticket_history.route("/login")
def login():
    if request.host.split(':')[0] != "ticket.mysticraft.xyz":
        abort(404)
    
    scope = "identify"
    return redirect(
        f"{API_BASE}/oauth2/authorize?client_id={MYSTICRAFT_CLIENT_ID}"
        f"&redirect_uri={MYSTICRAFT_REDIRECT_URI}"
        f"&response_type=code&scope={scope}"
    )


@ticket_history.route("/callback")
def callback():
    if request.host.split(':')[0] != "ticket.mysticraft.xyz":
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
    
    response = requests.post(f"{API_BASE}/oauth2/token", json=data)
    
    if response.status_code != 200:
        return render_template("ticket_history_login.html", error="Failed to authenticate with Discord.")
    
    token_data = response.json()
    access_token = token_data.get("access_token")
    
    if not access_token:
        return render_template("ticket_history_login.html", error="Failed to retrieve access token.")
    
    # Fetch user info
    headers = {"Authorization": f"Bearer {access_token}"}
    user_response = requests.get(f"{API_BASE}/users/@me", headers=headers)
    
    if user_response.status_code != 200:
        return render_template("ticket_history_login.html", error="Failed to fetch user information.")
    
    user_info = user_response.json()
    
    # Store in session
    session["user_data"] = {
        "id": user_info.get("id"),
        "username": user_info.get("username"),
        "discriminator": user_info.get("discriminator"),
        "access_token": access_token,
    }
    
    return redirect(url_for("ticket_history.index"))


@ticket_history.route("/logout")
def logout():
    if request.host.split(':')[0] != "ticket.mysticraft.xyz":
        abort(404)
    
    session.clear()
    return redirect(url_for("ticket_history.index"))
