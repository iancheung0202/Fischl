import requests
import hashlib
from flask import Blueprint, request, Response

from config.settings import API_BASE, BOT_TOKEN, MYSTICRAFT_TOKEN, BLOCK_CENTRAL_TOKEN, BRAWL_TOKEN

logs = Blueprint('logs', __name__)

@logs.route("/logs/<token>")
def view_log(token):
    try:
        # Parse token
        parts = token.split('-')
        if len(parts) != 3:
            return "Invalid or tampered log link. Please ensure the link is correct.", 400
            
        channel_id, message_id, checksum = parts

        token = BOT_TOKEN
        if request.host == "ticket.mysticraft.xyz":
          token = MYSTICRAFT_TOKEN
        
        headers = {"Authorization": f"Bot {token}"}
        message_url = f"{API_BASE}/channels/{channel_id}/messages/{message_id}"
        response = requests.get(message_url, headers=headers)
        
        if response.status_code != 200:
            if request.host == "ticket.mysticraft.xyz":
                token = BLOCK_CENTRAL_TOKEN
            else:
                token = BRAWL_TOKEN

            headers = {"Authorization": f"Bot {token}"}
            message_url = f"{API_BASE}/channels/{channel_id}/messages/{message_id}"
            response = requests.get(message_url, headers=headers)
            if response.status_code != 200:
                return "Log not found. Please check your link and permissions.", 404

        message = response.json()
        
        if not message.get('attachments'):
            return "No transcript found for the ticket.", 404
            
        attachment = message['attachments'][0]
        
        file_response = requests.get(attachment['url'], headers=headers)
        file_content = file_response.content
        
        expected_checksum = hashlib.sha256(file_content + channel_id.encode()).hexdigest()[:20]
        if checksum != expected_checksum:
            return "Invalid or tampered log link. Please ensure the link is correct.", 403

        return Response(file_content, mimetype="text/html; charset=utf-8")
        
    except Exception as e:
        return f"Error loading log: {str(e)}", 500