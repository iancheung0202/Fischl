import requests

from firebase_admin import db
from config.settings import BOT_TOKEN, API_BASE

def _build_panel_embeds(guild_id):
    """Build partnership panel embeds - port of bot's _build_panel_embeds function"""
    config_ref = db.reference(f'Partner/config/{guild_id}')
    partners_ref = db.reference(f'Partner/partners/{guild_id}')
    categories_ref = db.reference(f'Partner/categories/{guild_id}')
    
    config = config_ref.get()
    partners = partners_ref.get() or {}
    categories = categories_ref.get() or {}
    embed_config = config.get('embed', {}) if config else {}
    header = embed_config.get('header', {})
    footer = embed_config.get('footer', {})

    embeds = []

    # Header embed
    header_embed = {
        "type": "rich",
        "color": int(header.get('color', '#5865F2').lstrip('#'), 16)
    }
    
    if header.get('title') or header.get('description'):
        if header.get('title'):
            header_embed['title'] = header['title']
        if header.get('description'):
            header_embed['description'] = header['description']
    else:
        header_embed['title'] = 'Server Partner List'
        header_embed['description'] = 'Use </partner edit-panel:1364761118324822128> and select `Header` to edit this embed!'
    
    if header.get('thumbnail'):
        header_embed['thumbnail'] = {'url': header['thumbnail']}
    if header.get('image'):
        header_embed['image'] = {'url': header['image']}

    embeds.append(header_embed)

    # Category embeds
    for cat_name, cat_data in categories.items():
        category_partners = [p for p in partners.values() if p.get('category') == cat_name]
        if not category_partners:
            continue

        # Sort partners lexicographically by name
        sorted_partners = sorted(category_partners, key=lambda x: x['name'].lower())
        lines = []
        for p in sorted_partners:
            if p['invite'].isdigit():
                lines.append(f"• [{p['name']}](https://discord.gg/{p['invite']})")
            else:
                lines.append(f"• [{p['name']}]({p['invite']})")

        fields = []
        current_start_char = 'A'
        start_idx = 0

        def next_char(c):
            return chr(ord(c) + 1) if c != 'Z' else 'Z'

        while current_start_char <= 'Z' and start_idx < len(sorted_partners):
            # Find the first server >= current_start_char
            while start_idx < len(sorted_partners):
                if sorted_partners[start_idx]['name'][0].upper() >= current_start_char:
                    break
                start_idx += 1
            else:
                break

            # Collect servers into current chunk
            current_chunk = []
            current_length = 0
            end_idx = start_idx

            for i in range(start_idx, len(sorted_partners)):
                line = lines[i]
                if current_length + len(line) + 1 > 1024:  # Discord field value limit
                    break
                current_chunk.append(line)
                current_length += len(line) + 1
                end_idx = i + 1

            if not current_chunk:
                current_start_char = next_char(current_start_char)
                continue

            # Determine end_char from the last server in the chunk
            end_char = sorted_partners[end_idx - 1]['name'][0].upper()
            fields.append({
                'name': f"{current_start_char} - {end_char}",
                'value': '\n'.join(current_chunk),
                'inline': True
            })

            # Move to next character after end_char
            current_start_char = next_char(end_char)
            start_idx = end_idx

        # Ensure the last field ends with Z
        if fields:
            last_field = fields[-1]
            last_start = last_field['name'].split(' - ')[0]
            fields[-1]['name'] = f"{last_start} - Z"

        # Split fields into groups of max 25 fields per embed
        for i in range(0, len(fields), 25):
            group = fields[i:i+25]
            group_embed = {
                "type": "rich",
                "title": cat_data.get('title', cat_name),
                "color": int(cat_data.get('color', '#5865F2').lstrip('#'), 16),
                "fields": group
            }
            if cat_data.get('thumbnail'):
                group_embed['thumbnail'] = {'url': cat_data['thumbnail']}
            embeds.append(group_embed)

    # Footer embed
    footer_embed = {
        "type": "rich",
        "color": int(footer.get('color', '#5865F2').lstrip('#'), 16),
        "footer": {
            "text": "⚡ Panel automatically updated • Powered by Fischl"
        }
    }
    
    if footer.get('title') or footer.get('description'):
        if footer.get('title'):
            footer_embed['title'] = footer['title']
        if footer.get('description'):
            footer_embed['description'] = footer['description']
    else:
        footer_embed['title'] = 'Instructions'
        footer_embed['description'] = 'Use </partner edit-panel:1364761118324822128> and select `Footer` to edit this embed!'
    
    if footer.get('thumbnail'):
        footer_embed['thumbnail'] = {'url': footer['thumbnail']}
    if footer.get('image'):
        footer_embed['image'] = {'url': footer['image']}

    embeds.append(footer_embed)
    return embeds


def send_panel_via_api(guild_id):
    """Send partnership panel directly via Discord API"""
    try:
        # Get config to find panel channel
        config_ref = db.reference(f'Partner/config/{guild_id}')
        config = config_ref.get()
        if not config or not config.get('panel_channel'):
            return {"success": False, "message": "Panel channel not configured"}

        channel_id = config['panel_channel']
        
        # Build embeds
        embeds = _build_panel_embeds(guild_id)
        
        # Create request payload
        payload = {
            "embeds": embeds,
            "components": [{
                "type": 1,  # Action Row
                "components": [{
                    "type": 2,  # Button
                    "style": 1,  # Primary (blurple)
                    "label": "Request Partnership",
                    "custom_id": "partner_request"
                }]
            }]
        }

        # Send via Discord API
        headers = {
            "Authorization": f"Bot {BOT_TOKEN}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            f"{API_BASE}/channels/{channel_id}/messages",
            json=payload,
            headers=headers
        )
        
        if response.status_code == 200:
            message_data = response.json()
            # Save panel info to database
            db.reference(f'Partner/panels/{guild_id}').set({
                'channel_id': int(channel_id),
                'message_id': int(message_data['id'])
            })
            return {"success": True, "message": "Panel sent successfully!"}
        else:
            return {"success": False, "message": f"Discord API error: {response.status_code} - {response.text}"}
            
    except Exception as e:
        return {"success": False, "message": f"Error sending panel: {str(e)}"}


def update_panel_via_api(guild_id):
    """Update existing partnership panel directly via Discord API"""
    try:
        # Get panel info
        panel_ref = db.reference(f'Partner/panels/{guild_id}')
        panel = panel_ref.get()
        if not panel or not panel.get('channel_id') or not panel.get('message_id'):
            return {"success": False, "message": "No existing panel found. Please send a new panel first."}

        channel_id = panel['channel_id']
        message_id = panel['message_id']
        
        # Build embeds
        embeds = _build_panel_embeds(guild_id)
        
        # Create request payload
        payload = {
            "embeds": embeds,
            "components": [{
                "type": 1,  # Action Row
                "components": [{
                    "type": 2,  # Button
                    "style": 1,  # Primary (blurple)
                    "label": "Request Partnership", 
                    "custom_id": "partner_request"
                }]
            }]
        }

        # Update via Discord API
        headers = {
            "Authorization": f"Bot {BOT_TOKEN}",
            "Content-Type": "application/json"
        }
        
        response = requests.patch(
            f"{API_BASE}/channels/{channel_id}/messages/{message_id}",
            json=payload,
            headers=headers
        )
        
        if response.status_code == 200:
            return {"success": True, "message": "Panel updated successfully!"}
        else:
            return {"success": False, "message": f"Discord API error: {response.status_code} - {response.text}"}
            
    except Exception as e:
        return {"success": False, "message": f"Error updating panel: {str(e)}"}