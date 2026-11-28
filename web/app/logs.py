"""Shows a closed ticket's transcript from its log link."""

import hashlib

from app.ticket_history import HOST as MYSTICRAFT_HOST
from config.settings import API_BASE, BOT_TOKEN, BRAWL_TOKEN, MYSTICRAFT_TOKEN
from flask import Blueprint, Response, request

from utils.request import requests_session

logs = Blueprint("logs", __name__)

TAMPERED = "Invalid or tampered log link. Please ensure the link is correct."


def tokens():
    """Gives the bot tokens that may hold the log message, in the order to try."""
    return (
        [MYSTICRAFT_TOKEN]
        if request.host == MYSTICRAFT_HOST
        else [BOT_TOKEN, BRAWL_TOKEN]
    )


def log_message(channel_id, message_id):
    """Gives the log message as the first bot that can read it sees it, or None."""
    for token in tokens():
        answer = requests_session.get(
            f"{API_BASE}/channels/{channel_id}/messages/{message_id}",
            headers={"Authorization": f"Bot {token}"},
        )
        if answer.status_code == 200:
            return answer.json()
    return None


@logs.route("/logs/<token>")
def view_log(token):
    parts = token.split("-")
    if len(parts) != 3:
        return TAMPERED, 400
    channel_id, message_id, checksum = parts
    if not (channel_id.isdigit() and message_id.isdigit()):
        return "Log not found. Please check your link and permissions.", 404
    try:
        message = log_message(channel_id, message_id)
        if message is None:
            return "Log not found. Please check your link and permissions.", 404
        if not message.get("attachments"):
            return "No transcript found for the ticket.", 404
        transcript = requests_session.get(message["attachments"][0]["url"]).content
        expected = hashlib.sha256(transcript + channel_id.encode()).hexdigest()[:20]
        if checksum != expected:
            return TAMPERED, 403
        return Response(transcript, mimetype="text/html; charset=utf-8")
    except Exception as error:
        print(f"Error loading log: {error}")
        return "Error loading log. Please try again later.", 500
