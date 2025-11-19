import re
import html

from firebase_admin import db
from concurrent.futures import ThreadPoolExecutor
from flask import Blueprint, request, session, redirect, jsonify

from config.settings import API_BASE, BOT_TOKEN
from utils.request import requests_session, verify_guild_access
from utils.theme import wrap_page
from utils.loading import create_loading_container, create_async_script

tickets = Blueprint('tickets', __name__)

@tickets.route("/configure/<guild_id>/ticket")
def configure_ticket(guild_id):
    if "discord_token" not in session:
        return redirect("/")

    message = request.args.get('message', '')
    
    content = f"""
      <main class="p-6 max-w-3xl mx-auto">
        <div id="guild-header">
          <div class="flex items-center gap-4 mb-6">
            <div class="animate-pulse bg-gray-200 dark:bg-gray-600 w-20 h-20 rounded-full"></div>
            <div>
              <div class="animate-pulse bg-gray-200 dark:bg-gray-600 h-6 w-48 rounded mb-2"></div>
              <div class="animate-pulse bg-gray-200 dark:bg-gray-600 h-4 w-32 rounded"></div>
            </div>
          </div>
        </div>

        {f'<div class="bg-green-100 dark:bg-green-900 border border-green-400 dark:border-green-600 text-green-700 dark:text-green-300 px-4 py-3 rounded mb-4">{message.replace("+", " ")}</div>' if message else ''}

        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow dark:shadow-gray-700 p-6">
          <h3 class="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Ticket System Configuration</h3>
          
          <div id="ticket-form-container">
            {create_loading_container("Loading configuration options...", "flex flex-col items-center justify-center py-12")}
          </div>
        </div>
      </main>

      <script>
        fetch('/api/configure/{guild_id}/ticket/info')
          .then(response => response.json())
          .then(data => {{
            if (data.error) {{
              document.querySelector('main').innerHTML = 
                '<div class="p-6 max-w-3xl mx-auto text-center"><h1 class="text-2xl font-bold text-red-600 dark:text-red-400 mb-4">Access Denied</h1><p class="text-gray-600 dark:text-gray-300">' + data.error + '</p></div>';
              return;
            }}
            
            document.getElementById('guild-header').innerHTML = data.header;
            
            document.getElementById('ticket-form-container').innerHTML = data.form;
            
            if (typeof initializeTicketForm === 'function') {{
              initializeTicketForm();
            }}
          }})
          .catch(error => {{
            console.error('Error loading ticket info:', error);
            document.querySelector('main').innerHTML = 
              '<div class="p-6 max-w-3xl mx-auto text-center"><h1 class="text-2xl font-bold text-red-600 dark:text-red-400 mb-4">Error</h1><p class="text-gray-600 dark:text-gray-300">Failed to load page. Please refresh.</p></div>';
          }});
        
        function initializeTicketForm() {{
          const enabledCheckbox = document.querySelector('input[name="enabled"]');
          if (enabledCheckbox) {{
            enabledCheckbox.addEventListener('change', function() {{
              const ticketSettings = document.getElementById('ticketSettings');
              if (ticketSettings) {{
                ticketSettings.classList.toggle('hidden', !this.checked);
                
                const requiredFields = document.querySelectorAll('#ticketSettings [required]');
                requiredFields.forEach(field => {{
                  field.required = this.checked;
                }});
              }}
            }});
          }}
        }}
      </script>
    """

    return wrap_page("Configure Tickets", content, [(f"/configure/{guild_id}", "Back to Guild Configuration", "text-blue-500 dark:text-blue-400 font-medium hover:underline")])

@tickets.route("/api/configure/<guild_id>/ticket/info")
def api_ticket_info(guild_id):
    if "discord_token" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    try:
        discord_token = session['discord_token']
        
        success, guild, status_code = verify_guild_access(guild_id, discord_token)
        if not success:
            return jsonify(guild), status_code

        def fetch_guild_channels():
            return requests_session.get(f"{API_BASE}/guilds/{guild_id}/channels", headers={"Authorization": f"Bot {BOT_TOKEN}"}).json()
        
        def fetch_guild_roles():
            return requests_session.get(f"{API_BASE}/guilds/{guild_id}/roles", headers={"Authorization": f"Bot {BOT_TOKEN}"}).json()
        
        def fetch_ticket_settings():
            ref = db.reference("/Tickets")
            tickets = ref.get()
            current_settings = None
            
            if tickets:
                for key, value in tickets.items():
                    if value.get("Server ID") == int(guild_id):
                        current_settings = value
                        break
            return current_settings

        with ThreadPoolExecutor(max_workers=3) as executor:
            future_channels = executor.submit(fetch_guild_channels)
            future_roles = executor.submit(fetch_guild_roles)
            future_settings = executor.submit(fetch_ticket_settings)
            
            channels = future_channels.result()
            roles = future_roles.result()
            current_settings = future_settings.result()

        icon = f"https://cdn.discordapp.com/icons/{guild['id']}/{guild['icon']}.png?size=128" if guild.get("icon") else ""

        header_html = f"""
        <div class="flex items-center gap-4 mb-6">
          {"<img src='"+icon+"' class='rounded-full w-20 h-20 shadow-md'>" if icon else "<div class='w-20 h-20 rounded-full bg-gray-200 dark:bg-gray-600 flex items-center justify-center text-gray-500 dark:text-gray-300'>"+html.escape(guild['name'][0])+"</div>"}
          <div>
            <h2 class="text-2xl font-bold text-gray-900 dark:text-white">{html.escape(guild['name'])}</h2>
            <p class="text-gray-500 dark:text-gray-400">ID: {guild['id']}</p>
          </div>
        </div>
        """

        categories = [c for c in channels if c['type'] == 4]
        text_channels = [c for c in channels if c['type'] == 0]

        category_options = "".join([
            f'<option value="{c["id"]}" {"selected" if current_settings and str(current_settings.get("Category ID")) == str(c["id"]) else ""}>{c["name"]}</option>'
            for c in categories
        ])
        
        channel_options = "".join([
            f'<option value="{c["id"]}" {"selected" if current_settings and str(current_settings.get("Log Channel ID")) == str(c["id"]) else ""}>{c["name"]}</option>'
            for c in text_channels
        ])
        
        role_options = "".join([
            f'<option value="{r["id"]}" {"selected" if current_settings and str(current_settings.get("Ping Role ID")) == str(r["id"]) else ""}>{r["name"]}</option>'
            for r in roles if not r.get('managed', False) and r['name'] != '@everyone'
        ])

        cooldown_seconds = current_settings.get("Cooldown", 0) if current_settings else 0
        cooldown_str = ""
        if cooldown_seconds > 0:
            days = cooldown_seconds // 86400
            hours = (cooldown_seconds % 86400) // 3600
            minutes = (cooldown_seconds % 3600) // 60
            if days > 0:
                cooldown_str += f"{days}d"
            if hours > 0:
                cooldown_str += f"{hours}h"
            if minutes > 0:
                cooldown_str += f"{minutes}m"

        form_html = f"""
          <form id="ticketForm" action="/configure/{guild_id}/ticket/save" method="post">
            <div class="mb-4">
              <label class="flex items-center">
                <input type="checkbox" name="enabled" class="mr-2" {'checked' if current_settings else ''}>
                <span class="font-medium text-gray-900 dark:text-white">Enable Ticket System</span>
              </label>
            </div>
            
            <div id="ticketSettings" class={'block' if current_settings else 'hidden'}>
              <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Ticket Category *</label>
                <select name="category" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md" required>
                  <option value="">Select a category</option>
                  {category_options}
                </select>
                <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">Tickets will be created in this category</p>
              </div>
              
              <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Log Channel *</label>
                <select name="log_channel" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md" required>
                  <option value="">Select a channel</option>
                  {channel_options}
                </select>
                <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">Ticket logs will be sent to this channel</p>
              </div>
              
              <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Ping Role (Optional)</label>
                <select name="ping_role" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md">
                  <option value="">No ping role</option>
                  {role_options}
                </select>
                <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">This role will be pinged when a new ticket is created</p>
              </div>
              
              <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Cooldown (Optional)</label>
                <input type="text" name="cooldown" value="{cooldown_str}" placeholder="e.g. 3d12h45m" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md">
                <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">Format: #d#h#m (days, hours, minutes)</p>
              </div>
            </div>
            
            <button type="submit" class="w-full py-2 bg-blue-500 dark:bg-blue-600 text-white rounded-md font-medium hover:bg-blue-600 dark:hover:bg-blue-700 transition">
              Save Settings
            </button>
          </form>
        """

        return jsonify({
            "header": header_html,
            "form": form_html
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@tickets.route("/api/configure/<guild_id>/header")
def api_guild_header(guild_id):
    if "discord_token" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    try:
        discord_token = session['discord_token']
        
        success, guild, status_code = verify_guild_access(guild_id, discord_token)
        if not success:
            return jsonify(guild), status_code

        icon = f"https://cdn.discordapp.com/icons/{guild['id']}/{guild['icon']}.png?size=128" if guild.get("icon") else ""

        html_content = f"""
        <div class="flex items-center gap-4 mb-6">
          {"<img src='"+icon+"' class='rounded-full w-20 h-20 shadow-md'>" if icon else "<div class='w-20 h-20 rounded-full bg-gray-200 dark:bg-gray-600 flex items-center justify-center text-gray-500 dark:text-gray-300'>"+html.escape(guild['name'][0])+"</div>"}
          <div>
            <h2 class="text-2xl font-bold text-gray-900 dark:text-white">{html.escape(guild['name'])}</h2>
            <p class="text-gray-500 dark:text-gray-400">ID: {guild['id']}</p>
          </div>
        </div>
        """

        return jsonify({"html": html_content})
    
    except Exception as e:
        return jsonify({"error": f"Failed to load guild information: {str(e)}"}), 500

@tickets.route("/api/configure/<guild_id>/ticket/form")
def api_ticket_form(guild_id):
    if "discord_token" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    try:
        discord_token = session['discord_token']
        
        success, guild, status_code = verify_guild_access(guild_id, discord_token)
        if not success:
            return jsonify(guild), status_code

        def fetch_guild_channels():
            return requests_session.get(f"{API_BASE}/guilds/{guild_id}/channels", headers={"Authorization": f"Bot {BOT_TOKEN}"}).json()
        
        def fetch_guild_roles():
            return requests_session.get(f"{API_BASE}/guilds/{guild_id}/roles", headers={"Authorization": f"Bot {BOT_TOKEN}"}).json()
        
        def fetch_ticket_settings():
            ref = db.reference("/Tickets")
            tickets = ref.get()
            current_settings = None
            
            if tickets:
                for key, value in tickets.items():
                    if value.get("Server ID") == int(guild_id):
                        current_settings = value
                        break
            return current_settings

        with ThreadPoolExecutor(max_workers=3) as executor:
            future_channels = executor.submit(fetch_guild_channels)
            future_roles = executor.submit(fetch_guild_roles)
            future_settings = executor.submit(fetch_ticket_settings)
            
            channels = future_channels.result()
            roles = future_roles.result()
            current_settings = future_settings.result()

        categories = [c for c in channels if c['type'] == 4]
        text_channels = [c for c in channels if c['type'] == 0]

        category_options = "".join([
            f'<option value="{c["id"]}" {"selected" if current_settings and str(current_settings.get("Category ID")) == str(c["id"]) else ""}>{c["name"]}</option>'
            for c in categories
        ])
        
        channel_options = "".join([
            f'<option value="{c["id"]}" {"selected" if current_settings and str(current_settings.get("Log Channel ID")) == str(c["id"]) else ""}>{c["name"]}</option>'
            for c in text_channels
        ])
        
        role_options = "".join([
            f'<option value="{r["id"]}" {"selected" if current_settings and str(current_settings.get("Ping Role ID")) == str(r["id"]) else ""}>{r["name"]}</option>'
            for r in roles if not r.get('managed', False) and r['name'] != '@everyone'
        ])

        cooldown_seconds = current_settings.get("Cooldown", 0) if current_settings else 0
        cooldown_str = ""
        if cooldown_seconds > 0:
            days = cooldown_seconds // 86400
            hours = (cooldown_seconds % 86400) // 3600
            minutes = (cooldown_seconds % 3600) // 60
            if days > 0:
                cooldown_str += f"{days}d"
            if hours > 0:
                cooldown_str += f"{hours}h"
            if minutes > 0:
                cooldown_str += f"{minutes}m"

        html_content = f"""
          <form id="ticketForm" action="/configure/{guild_id}/ticket/save" method="post">
            <div class="mb-4">
              <label class="flex items-center">
                <input type="checkbox" name="enabled" class="mr-2" {'checked' if current_settings else ''}>
                <span class="font-medium text-gray-900 dark:text-white">Enable Ticket System</span>
              </label>
            </div>
            
            <div id="ticketSettings" class={'block' if current_settings else 'hidden'}>
              <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Ticket Category *</label>
                <select name="category" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md" required>
                  <option value="">Select a category</option>
                  {category_options}
                </select>
                <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">Tickets will be created in this category</p>
              </div>
              
              <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Log Channel *</label>
                <select name="log_channel" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md" required>
                  <option value="">Select a channel</option>
                  {channel_options}
                </select>
                <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">Ticket logs will be sent to this channel</p>
              </div>
              
              <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Ping Role (Optional)</label>
                <select name="ping_role" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md">
                  <option value="">No ping role</option>
                  {role_options}
                </select>
                <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">This role will be pinged when a new ticket is created</p>
              </div>
              
              <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Cooldown (Optional)</label>
                <input type="text" name="cooldown" value="{cooldown_str}" placeholder="e.g. 3d12h45m" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md">
                <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">Format: #d#h#m (days, hours, minutes)</p>
              </div>
            </div>
            
            <button type="submit" class="w-full py-2 bg-blue-500 dark:bg-blue-600 text-white rounded-md font-medium hover:bg-blue-600 dark:hover:bg-blue-700 transition">
              Save Settings
            </button>
          </form>
        """

        return jsonify({"html": html_content})
    
    except Exception as e:
        return jsonify({"error": f"Failed to load configuration form: {str(e)}"}), 500

@tickets.route("/configure/<guild_id>/ticket/save", methods=["POST"])
def save_ticket_config(guild_id):
    if "discord_token" not in session:
        return redirect("/")

    success, guild, status_code = verify_guild_access(guild_id, session['discord_token'])
    if not success:
        return f"<h1>{guild['error']}</h1>", status_code

    enabled = request.form.get("enabled") == "on"
    
    if not enabled:
        ref = db.reference("/Tickets")
        tickets = ref.get()
        if tickets:
            for key, value in tickets.items():
                if value.get("Server ID") == int(guild_id):
                    ref.child(key).delete()
                    break
        return redirect(f"/configure/{guild_id}/ticket?message=Ticket+system+disabled")

    cooldown_str = request.form.get("cooldown", "")
    cooldown_seconds = 0
    
    if cooldown_str:
        days = re.search(r"(\d+)d", cooldown_str)
        hours = re.search(r"(\d+)h", cooldown_str)
        minutes = re.search(r"(\d+)m", cooldown_str)
        
        if days:
            cooldown_seconds += int(days.group(1)) * 86400
        if hours:
            cooldown_seconds += int(hours.group(1)) * 3600
        if minutes:
            cooldown_seconds += int(minutes.group(1)) * 60

    data = {
        "Server Name": guild["name"],
        "Server ID": int(guild_id),
        "Category ID": int(request.form.get("category")),
        "Log Channel ID": int(request.form.get("log_channel")),
        "Ping Role ID": int(request.form.get("ping_role")) if request.form.get("ping_role") else None,
        "Cooldown": cooldown_seconds
    }

    ref = db.reference("/Tickets")
    tickets = ref.get()
    
    existing_key = None
    if tickets:
        for key, value in tickets.items():
            if value.get("Server ID") == int(guild_id):
                existing_key = key
                break
    
    if existing_key:
        ref.child(existing_key).update(data)
    else:
        ref.push(data)

    return redirect(f"/configure/{guild_id}/ticket?message=Ticket+settings+saved")