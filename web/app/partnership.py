import requests
import re
import concurrent
import datetime
import time
import html

from firebase_admin import db
from concurrent.futures import ThreadPoolExecutor
from flask import Blueprint, request, session, redirect, jsonify

from utils.partnership import send_panel_via_api
from config.settings import API_BASE, BOT_TOKEN
from utils.request import requests_session, verify_guild_access
from utils.theme import wrap_page
from utils.loading import create_loading_skeleton, create_async_script, create_loading_container

partnership = Blueprint('partnership', __name__)

@partnership.route("/configure/<guild_id>/partnership")
def configure_partnership(guild_id):
    if "discord_token" not in session:
        return redirect("/")

    message = request.args.get('message', '')
    
    content = f"""
      <main class="p-6 max-w-5xl mx-auto">
        <div id="guild-header">
          <div class="flex items-center gap-4 mb-6">
            <div class="animate-pulse bg-gray-200 dark:bg-gray-600 w-16 h-16 rounded-full"></div>
            <div>
              <div class="animate-pulse bg-gray-200 dark:bg-gray-600 h-6 w-48 rounded mb-2"></div>
              <div class="animate-pulse bg-gray-200 dark:bg-gray-600 h-4 w-32 rounded"></div>
            </div>
          </div>
        </div>

        {f'<div class="bg-green-100 dark:bg-green-900 border border-green-400 dark:border-green-600 text-green-700 dark:text-green-300 px-4 py-3 rounded mb-4">{message.replace("+", " ")}</div>' if message else ''}

        <div id="stats-container" class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
          {create_loading_skeleton(3, "bg-white dark:bg-gray-800 rounded-2xl shadow dark:shadow-gray-700 p-6", "stats")}
        </div>

        <div id="main-content-container" class="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {create_loading_container("Loading partnership configuration...", "col-span-full flex flex-col items-center justify-center py-12")}
        </div>
      </main>

      <script>
        fetch('/api/configure/{guild_id}/partnership/info')
          .then(response => response.json())
          .then(data => {{
            if (data.error) {{
              document.querySelector('main').innerHTML = 
                '<div class="p-6 max-w-5xl mx-auto text-center"><h1 class="text-2xl font-bold text-red-600 dark:text-red-400 mb-4">Access Denied</h1><p class="text-gray-600 dark:text-gray-300">' + data.error + '</p></div>';
              return;
            }}
            
            document.getElementById('guild-header').innerHTML = data.header;
            
            document.getElementById('stats-container').innerHTML = data.stats;
            
            document.getElementById('main-content-container').innerHTML = data.content;
            
            if (typeof initializePartnershipForm === 'function') {{
              initializePartnershipForm();
            }}
          }})
          .catch(error => {{
            console.error('Error loading partnership info:', error);
            document.querySelector('main').innerHTML = 
              '<div class="p-6 max-w-5xl mx-auto text-center"><h1 class="text-2xl font-bold text-red-600 dark:text-red-400 mb-4">Error</h1><p class="text-gray-600 dark:text-gray-300">Failed to load page. Please refresh.</p></div>';
          }});
        
        function initializePartnershipForm() {{
          let initialCheckboxState = false;
          const enabledCheckbox = document.querySelector('input[name="enabled"]');
          
          if (enabledCheckbox) {{
            initialCheckboxState = enabledCheckbox.checked;
            
            enabledCheckbox.addEventListener('change', function() {{
              const partnershipSettings = document.getElementById('partnershipSettings');
              if (partnershipSettings) {{
                partnershipSettings.classList.toggle('hidden', !this.checked);
                
                const requiredFields = document.querySelectorAll('#partnershipSettings [required]');
                requiredFields.forEach(field => {{
                  field.required = this.checked;
                }});
              }}
            }});
          }}
          
          const partnershipForm = document.getElementById('partnershipForm');
          if (partnershipForm) {{
            partnershipForm.addEventListener('submit', function(e) {{
              const isEnabled = document.getElementById('enabledCheckbox').checked;
              
              if (initialCheckboxState && !isEnabled) {{
                e.preventDefault();
                
                if (confirm('Warning: Disabling the partnership system will permanently delete all partners and groups. Are you sure you want to continue?')) {{
                  this.submit();
                }}
              }}
            }});
          }}
        }}
        
        function sendPanel() {{
          if (confirm('Send partnership panel to the configured channel?')) {{
            fetch('/configure/{guild_id}/partnership/send-panel', {{method: 'POST'}})
              .then(response => response.json())
              .then(data => {{
                alert(data.message);
                if (data.success) location.reload();
              }});
          }}
        }}
      </script>
    """
    
    return wrap_page(f"Configure Partnerships", content, [("/configure/" + guild_id, "Back to Guild Configuration", "text-blue-500 dark:text-blue-400 font-medium hover:underline")])

@partnership.route("/api/configure/<guild_id>/partnership/info")
def api_partnership_info(guild_id):
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
        
        def fetch_partnership_config():
            config_ref = db.reference(f"/Partner/config/{guild_id}")
            return config_ref.get()
        
        def fetch_partners():
            partners_ref = db.reference(f"/Partner/partners/{guild_id}")
            return partners_ref.get() or {}
        
        def fetch_categories():
            categories_ref = db.reference(f"/Partner/categories/{guild_id}")
            return categories_ref.get() or {}
        
        def fetch_blacklist():
            blacklist_ref = db.reference(f"/Partner/Blacklist/{guild_id}")
            return blacklist_ref.get() or {}

        with ThreadPoolExecutor(max_workers=6) as executor:
            future_channels = executor.submit(fetch_guild_channels)
            future_roles = executor.submit(fetch_guild_roles)
            future_config = executor.submit(fetch_partnership_config)
            future_partners = executor.submit(fetch_partners)
            future_categories = executor.submit(fetch_categories)
            future_blacklist = executor.submit(fetch_blacklist)
            
            channels = future_channels.result()
            roles = future_roles.result()
            current_config = future_config.result()
            partners = future_partners.result()
            categories = future_categories.result()
            blacklist = future_blacklist.result()

        if isinstance(channels, dict) and 'message' in channels:
            raise Exception("Bot is not in this guild. Please invite it first.")

        text_channels = [c for c in channels if c['type'] == 0]
        partner_roles = [r for r in roles if not r.get('managed', False) and r['name'] != '@everyone']

        icon = f"https://cdn.discordapp.com/icons/{guild['id']}/{guild['icon']}.png?size=128" if guild.get("icon") else ""

        header_html = f"""
        <div class="flex items-center gap-4 mb-6">
          {"<img src='"+icon+"' class='rounded-full w-16 h-16 shadow-md'>" if icon else "<div class='w-16 h-16 rounded-full bg-gray-200 dark:bg-gray-600 flex items-center justify-center text-gray-500 dark:text-gray-300'>"+html.escape(guild['name'][0])+"</div>"}
          <div>
            <h2 class="text-2xl font-bold text-gray-900 dark:text-white">{html.escape(guild['name'])}</h2>
            <p class="text-gray-500 dark:text-gray-400">Partnership System Configuration</p>
          </div>
        </div>
        """

        stats_html = f"""
          <div class="bg-white dark:bg-gray-800 rounded-2xl shadow dark:shadow-gray-700 p-6">
            <h3 class="text-lg font-semibold mb-2 text-gray-900 dark:text-white">Partners</h3>
            <p class="text-3xl font-bold text-purple-600 dark:text-purple-400">{len(partners)}</p>
            <p class="text-sm text-gray-500 dark:text-gray-400">Active partnerships</p>
          </div>
          <div class="bg-white dark:bg-gray-800 rounded-2xl shadow dark:shadow-gray-700 p-6">
            <h3 class="text-lg font-semibold mb-2 text-gray-900 dark:text-white">Groups</h3>
            <p class="text-3xl font-bold text-blue-600 dark:text-blue-400">{len(categories)}</p>
            <p class="text-sm text-gray-500 dark:text-gray-400">Partner categories</p>
          </div>
          <div class="bg-white dark:bg-gray-800 rounded-2xl shadow dark:shadow-gray-700 p-6">
            <h3 class="text-lg font-semibold mb-2 text-gray-900 dark:text-white">Blacklisted</h3>
            <p class="text-3xl font-bold text-red-600 dark:text-red-400">{len(blacklist)}</p>
            <p class="text-sm text-gray-500 dark:text-gray-400">Blocked servers</p>
          </div>
        """

        channel_options = "".join([
            f'<option value="{c["id"]}" {"selected" if current_config and str(current_config.get("log_channel")) == str(c["id"]) else ""}>{c["name"]}</option>'
            for c in text_channels
        ])
        
        request_channel_options = "".join([
            f'<option value="{c["id"]}" {"selected" if current_config and str(current_config.get("request_channel")) == str(c["id"]) else ""}>{c["name"]}</option>'
            for c in text_channels
        ])
        
        panel_channel_options = "".join([
            f'<option value="{c["id"]}" {"selected" if current_config and str(current_config.get("panel_channel")) == str(c["id"]) else ""}>{c["name"]}</option>'
            for c in text_channels
        ])
        
        role_options = "".join([
            f'<option value="{r["id"]}" {"selected" if current_config and str(current_config.get("partner_role")) == str(r["id"]) else ""}>{r["name"]}</option>'
            for r in partner_roles
        ])
        
        manager_role_options = "".join([
            f'<option value="{r["id"]}" {"selected" if current_config and str(current_config.get("partner_manager_role_id")) == str(r["id"]) else ""}>{r["name"]}</option>'
            for r in partner_roles
        ])

        cooldown_str = ""
        if current_config and current_config.get("user_cooldown", 0) > 0:
            cooldown_seconds = current_config["user_cooldown"]
            days = cooldown_seconds // 86400
            hours = (cooldown_seconds % 86400) // 3600
            minutes = (cooldown_seconds % 3600) // 60
            if days > 0:
                cooldown_str += f"{days}d"
            if hours > 0:
                cooldown_str += f"{hours}h"
            if minutes > 0:
                cooldown_str += f"{minutes}m"

        content_html = f"""
          <div class="bg-white dark:bg-gray-800 rounded-2xl shadow dark:shadow-gray-700 p-6">
            <h3 class="text-xl font-semibold mb-4 text-gray-900 dark:text-white">System Configuration</h3>
            
            <form action="/configure/{guild_id}/partnership/setup" method="post" id="partnershipForm">
              <div class="mb-4">
                <label class="flex items-center">
                  <input type="checkbox" name="enabled" class="mr-2" id="enabledCheckbox" {'checked' if current_config else ''}>
                  <span class="font-medium text-gray-900 dark:text-white">Enable Partnership System</span>
                </label>
              </div>
              
              <div id="partnershipSettings" class={'block' if current_config else 'hidden'}>
                <div class="mb-4">
                  <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Log Channel *</label>
                  <select name="log_channel" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md" required>
                    <option value="">Select a channel</option>
                    {channel_options}
                  </select>
                </div>
                
                <div class="mb-4">
                  <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Partner Role *</label>
                  <select name="partner_role" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md" required>
                    <option value="">Select a role</option>
                    {role_options}
                  </select>
                </div>
                
                <div class="mb-4">
                  <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Request Channel *</label>
                  <select name="request_channel" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md" required>
                    <option value="">Select a channel</option>
                    {request_channel_options}
                  </select>
                </div>
                
                <div class="mb-4">
                  <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Panel Channel *</label>
                  <select name="panel_channel" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md" required>
                    <option value="">Select a channel</option>
                    {panel_channel_options}
                  </select>
                </div>
                
                <div class="mb-4">
                  <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Partner Manager Role (Optional)</label>
                  <select name="partner_manager_role" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md">
                    <option value="">No manager role</option>
                    {manager_role_options}
                  </select>
                </div>
                
                <div class="mb-4">
                  <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">User Cooldown (Optional)</label>
                  <input type="text" name="user_cooldown" value="{cooldown_str}" placeholder="e.g. 3d12h45m" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md">
                  <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">Format: #d#h#m (days, hours, minutes)</p>
                </div>
              </div>
              
              <button type="submit" class="w-full py-2 bg-purple-500 dark:bg-purple-600 text-white rounded-md font-medium hover:bg-purple-600 dark:hover:bg-purple-700 transition">
                Save Configuration
              </button>
            </form>
          </div>

          <div class="bg-white dark:bg-gray-800 rounded-2xl shadow dark:shadow-gray-700 p-6">
            <h3 class="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Quick Actions</h3>
            {f'''
            <div class="space-y-3">
              <a href="/configure/{guild_id}/partnership/groups" class="block w-full py-2 bg-blue-500 dark:bg-blue-600 text-white rounded-md text-center font-medium hover:bg-blue-600 dark:hover:bg-blue-700 transition">
                Manage Groups
              </a>
              <a href="/configure/{guild_id}/partnership/partners" class="block w-full py-2 bg-green-500 dark:bg-green-600 text-white rounded-md text-center font-medium hover:bg-green-600 dark:hover:bg-green-700 transition">
                Manage Partners
              </a>
              <a href="/configure/{guild_id}/partnership/blacklist" class="block w-full py-2 bg-red-500 dark:bg-red-600 text-white rounded-md text-center font-medium hover:bg-red-600 dark:hover:bg-red-700 transition">
                Manage Blacklist
              </a>
              <a href="/configure/{guild_id}/partnership/panel" class="block w-full py-2 bg-purple-500 dark:bg-purple-600 text-white rounded-md text-center font-medium hover:bg-purple-600 dark:hover:bg-purple-700 transition">
                Edit Panel
              </a>
              
              <button onclick="sendPanel()" class="block w-full py-2 bg-amber-500 dark:bg-amber-600 text-white rounded-md text-center font-medium hover:bg-amber-600 dark:hover:bg-amber-700 transition">Send Panel</button>
              ''' if current_config else '<p class="text-gray-500 dark:text-gray-400">Enable the system first to access to more actions.</p>'}
            </div>
          </div>
        """

        return jsonify({
            "header": header_html,
            "stats": stats_html,
            "content": content_html
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@partnership.route("/api/configure/<guild_id>/partnership/data")
def api_partnership_data(guild_id):
    if "discord_token" not in session:
        return {"error": "Not authenticated"}, 401

    discord_token = session['discord_token']
    
    success, guild, status_code = verify_guild_access(guild_id, discord_token, require_bot_in_guild=False)
    if not success:
        return guild, status_code

    def fetch_guild_channels():
        return requests_session.get(f"{API_BASE}/guilds/{guild_id}/channels", headers={"Authorization": f"Bot {BOT_TOKEN}"}).json()
    
    def fetch_guild_roles():
        return requests_session.get(f"{API_BASE}/guilds/{guild_id}/roles", headers={"Authorization": f"Bot {BOT_TOKEN}"}).json()
    
    def fetch_partnership_config():
        config_ref = db.reference(f"/Partner/config/{guild_id}")
        return config_ref.get()
    
    def fetch_partners():
        partners_ref = db.reference(f"/Partner/partners/{guild_id}")
        return partners_ref.get() or {}
    
    def fetch_categories():
        categories_ref = db.reference(f"/Partner/categories/{guild_id}")
        return categories_ref.get() or {}
    
    def fetch_blacklist():
        blacklist_ref = db.reference(f"/Partner/Blacklist/{guild_id}")
        return blacklist_ref.get() or {}

    with ThreadPoolExecutor(max_workers=6) as executor:
        future_channels = executor.submit(fetch_guild_channels)
        future_roles = executor.submit(fetch_guild_roles)
        future_config = executor.submit(fetch_partnership_config)
        future_partners = executor.submit(fetch_partners)
        future_categories = executor.submit(fetch_categories)
        future_blacklist = executor.submit(fetch_blacklist)
        
        channels = future_channels.result()
        roles = future_roles.result()
        current_config = future_config.result()
        partners = future_partners.result()
        categories = future_categories.result()
        blacklist = future_blacklist.result()

    if isinstance(channels, dict) and 'message' in channels:
        return {"error": "Bot is not in this guild. Please invite it first."}, 400

    text_channels = [c for c in channels if c['type'] == 0]
    partner_roles = [r for r in roles if not r.get('managed', False) and r['name'] != '@everyone']

    channel_options = "".join([
        f'<option value="{c["id"]}" {"selected" if current_config and str(current_config.get("log_channel")) == str(c["id"]) else ""}>{c["name"]}</option>'
        for c in text_channels
    ])
    
    request_channel_options = "".join([
        f'<option value="{c["id"]}" {"selected" if current_config and str(current_config.get("request_channel")) == str(c["id"]) else ""}>{c["name"]}</option>'
        for c in text_channels
    ])
    
    panel_channel_options = "".join([
        f'<option value="{c["id"]}" {"selected" if current_config and str(current_config.get("panel_channel")) == str(c["id"]) else ""}>{c["name"]}</option>'
        for c in text_channels
    ])
    
    role_options = "".join([
        f'<option value="{r["id"]}" {"selected" if current_config and str(current_config.get("partner_role")) == str(r["id"]) else ""}>{r["name"]}</option>'
        for r in partner_roles
    ])

    cooldown_str = ""
    if current_config and current_config.get("user_cooldown", 0) > 0:
        cooldown_seconds = current_config["user_cooldown"]
        days = cooldown_seconds // 86400
        hours = (cooldown_seconds % 86400) // 3600
        minutes = (cooldown_seconds % 3600) // 60
        if days > 0:
            cooldown_str += f"{days}d"
        if hours > 0:
            cooldown_str += f"{hours}h"
        if minutes > 0:
            cooldown_str += f"{minutes}m"

    stats_html = f"""
          <div class="bg-white dark:bg-gray-800 rounded-2xl shadow dark:shadow-gray-700 p-6">
            <h3 class="text-lg font-semibold mb-2 text-gray-900 dark:text-white">Partners</h3>
            <p class="text-3xl font-bold text-purple-600 dark:text-purple-400">{len(partners)}</p>
            <p class="text-sm text-gray-500 dark:text-gray-400">Active partnerships</p>
          </div>
          <div class="bg-white dark:bg-gray-800 rounded-2xl shadow dark:shadow-gray-700 p-6">
            <h3 class="text-lg font-semibold mb-2 text-gray-900 dark:text-white">Groups</h3>
            <p class="text-3xl font-bold text-blue-600 dark:text-blue-400">{len(categories)}</p>
            <p class="text-sm text-gray-500 dark:text-gray-400">Partner categories</p>
          </div>
          <div class="bg-white dark:bg-gray-800 rounded-2xl shadow dark:shadow-gray-700 p-6">
            <h3 class="text-lg font-semibold mb-2 text-gray-900 dark:text-white">Blacklisted</h3>
            <p class="text-3xl font-bold text-red-600 dark:text-red-400">{len(blacklist)}</p>
            <p class="text-sm text-gray-500 dark:text-gray-400">Blocked servers</p>
          </div>
    """

    config_html = f"""
          <div class="bg-white dark:bg-gray-800 rounded-2xl shadow dark:shadow-gray-700 p-6">
            <h3 class="text-xl font-semibold mb-4 text-gray-900 dark:text-white">System Configuration</h3>
            
            <form action="/configure/{guild_id}/partnership/setup" method="post" id="partnershipForm">
              <div class="mb-4">
                <label class="flex items-center">
                  <input type="checkbox" name="enabled" class="mr-2" id="enabledCheckbox" {'checked' if current_config else ''}>
                  <span class="font-medium text-gray-900 dark:text-white">Enable Partnership System</span>
                </label>
              </div>
              
              <div id="partnershipSettings" class={'block' if current_config else 'hidden'}>
                <div class="mb-4">
                  <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Log Channel *</label>
                  <select name="log_channel" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md" required>
                    <option value="">Select a channel</option>
                    {channel_options}
                  </select>
                </div>
                
                <div class="mb-4">
                  <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Partner Role *</label>
                  <select name="partner_role" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md" required>
                    <option value="">Select a role</option>
                    {role_options}
                  </select>
                </div>
                
                <div class="mb-4">
                  <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Request Channel (Optional)</label>
                  <select name="request_channel" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md">
                    <option value="">Select a channel</option>
                    {request_channel_options}
                  </select>
                </div>
                
                <div class="mb-4">
                  <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Panel Channel (Optional)</label>
                  <select name="panel_channel" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md">
                    <option value="">Select a channel</option>
                    {panel_channel_options}
                  </select>
                </div>
                
                <div class="mb-4">
                  <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">User Cooldown (Optional)</label>
                  <input type="text" name="user_cooldown" value="{cooldown_str}" placeholder="e.g., 7d, 12h, 30m" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md">
                  <small class="text-gray-500 dark:text-gray-400">How long users must wait between partnership applications</small>
                </div>
                
                <button type="submit" class="bg-green-500 dark:bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-600 dark:hover:bg-green-700 transition">Save Configuration</button>
              </div>
            </form>
          </div>

          <div class="bg-white dark:bg-gray-800 rounded-2xl shadow dark:shadow-gray-700 p-6">
            <h3 class="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Quick Actions</h3>
            {f'''
            <div class="space-y-3">
              <a href="/configure/{guild_id}/partnership/groups" class="block w-full py-2 bg-blue-500 dark:bg-blue-600 text-white rounded-md text-center font-medium hover:bg-blue-600 dark:hover:bg-blue-700 transition">
                Manage Groups
              </a>
              <a href="/configure/{guild_id}/partnership/partners" class="block w-full py-2 bg-green-500 dark:bg-green-600 text-white rounded-md text-center font-medium hover:bg-green-600 dark:hover:bg-green-700 transition">
                Manage Partners
              </a>
              <a href="/configure/{guild_id}/partnership/blacklist" class="block w-full py-2 bg-red-500 dark:bg-red-600 text-white rounded-md text-center font-medium hover:bg-red-600 dark:hover:bg-red-700 transition">
                Manage Blacklist
              </a>
              <a href="/configure/{guild_id}/partnership/panel" class="block w-full py-2 bg-purple-500 dark:bg-purple-600 text-white rounded-md text-center font-medium hover:bg-purple-600 dark:hover:bg-purple-700 transition">
                Edit Panel
              </a>
              
              <button onclick="sendPanel()" class="block w-full py-2 bg-amber-500 dark:bg-amber-600 text-white rounded-md text-center font-medium hover:bg-amber-600 dark:hover:bg-amber-700 transition">Send Panel</button>
              ''' if current_config else '<p class="text-gray-500 dark:text-gray-400">Enable the system first to access to more actions.</p>'}
            </div>
          </div>
    """

    return {
        "stats_html": stats_html,
        "config_html": config_html,
        "initial_config_state": bool(current_config)
    }

@partnership.route("/configure/<guild_id>/partnership/setup", methods=["POST"])
def save_partnership_config(guild_id):
    if "discord_token" not in session:
        return redirect("/")

    success, guild, status_code = verify_guild_access(guild_id, session['discord_token'], require_bot_in_guild=False)
    if not success:
        return f"<h1>{guild['error']}</h1>", status_code

    enabled = request.form.get("enabled") == "on"
    
    if not enabled:
        db.reference(f"/Partner/config/{guild_id}").delete()
        db.reference(f"/Partner/partners/{guild_id}").delete() 
        db.reference(f"/Partner/categories/{guild_id}").delete()
        db.reference(f"/Partner/panels/{guild_id}").delete()
        return redirect(f"/configure/{guild_id}?message=Partnership+system+disabled")

    cooldown_str = request.form.get("user_cooldown", "")
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

    config_data = {
        "log_channel": int(request.form.get("log_channel")),
        "partner_role": int(request.form.get("partner_role")),
        "request_channel": int(request.form.get("request_channel")),
        "panel_channel": int(request.form.get("panel_channel")),
        "partner_manager_role_id": int(request.form.get("partner_manager_role")) if request.form.get("partner_manager_role") else None,
        "user_cooldown": cooldown_seconds
    }

    db.reference(f"/Partner/config/{guild_id}").update(config_data)
    return redirect(f"/configure/{guild_id}/partnership?message=Configuration+saved+successfully")

@partnership.route("/configure/<guild_id>/partnership/send-panel", methods=["POST"])
def send_partnership_panel(guild_id):
    if "discord_token" not in session:
        return {"success": False, "message": "Not authenticated"}, 401

    try:
        result = send_panel_via_api(guild_id)
        if result["success"]:
            return {"success": True, "message": result["message"]}
        else:
            return {"success": False, "message": result["message"]}, 500
    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}, 500

@partnership.route("/configure/<guild_id>/partnership/disable", methods=["POST"])
def disable_partnership_system(guild_id):
    if "discord_token" not in session:
        return {"success": False, "message": "Not authenticated"}, 401

    try:
        def delete_config():
            return db.reference(f"/Partner/config/{guild_id}").delete()
        
        def delete_partners():
            return db.reference(f"/Partner/partners/{guild_id}").delete()
        
        def delete_categories():
            return db.reference(f"/Partner/categories/{guild_id}").delete()
        
        def delete_panels():
            return db.reference(f"/Partner/panels/{guild_id}").delete()
        
        def delete_blacklist():
            return db.reference(f"/Partner/Blacklist/{guild_id}").delete()

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(delete_config),
                executor.submit(delete_partners),
                executor.submit(delete_categories),
                executor.submit(delete_panels),
                executor.submit(delete_blacklist)
            ]
            
            for future in concurrent.futures.as_completed(futures):
                future.result()
        
        return {"success": True, "message": "Partnership system disabled successfully"}
    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}, 500


@partnership.route("/configure/<guild_id>/partnership/groups")
def manage_groups(guild_id):
    if "discord_token" not in session:
        return redirect("/")

    discord_token = session['discord_token']

    success, guild, status_code = verify_guild_access(guild_id, discord_token, require_bot_in_guild=False)
    if not success:
        return f"<h1>{guild['error']}</h1>", status_code

    def fetch_categories():
        categories_ref = db.reference(f"/Partner/categories/{guild_id}")
        return categories_ref.get() or {}
    
    def fetch_partners():
        partners_ref = db.reference(f"/Partner/partners/{guild_id}")
        return partners_ref.get() or {}

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_categories = executor.submit(fetch_categories)
        future_partners = executor.submit(fetch_partners)
        
        categories = future_categories.result()
        partners = future_partners.result()
    
    category_counts = {}
    for partner in partners.values():
        cat = partner.get('category', 'Unknown')
        category_counts[cat] = category_counts.get(cat, 0) + 1

    icon = f"https://cdn.discordapp.com/icons/{guild['id']}/{guild['icon']}.png?size=128" if guild.get("icon") else ""
    message = request.args.get('message', '')

    category_cards = ""
    for cat_name, cat_data in categories.items():
        partner_count = category_counts.get(cat_name, 0)
        category_cards += f"""
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow dark:shadow-gray-700 p-4">
          <div class="flex justify-between items-start mb-2">
            <h4 class="font-semibold text-lg text-gray-900 dark:text-white">{cat_data.get('title', cat_name)}</h4>
            <span class="text-sm px-2 py-1 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded" style="color: {cat_data.get('color', '#5865F2')}">{partner_count} partners</span>
          </div>
          <p class="text-sm text-gray-600 dark:text-gray-300 mb-3">
            <strong>Name:</strong> {cat_name}<br>
            <strong>Prefix:</strong> {cat_data.get('prefix', '-')}<br>
            <strong>Suffix:</strong> {cat_data.get('suffix', 'None') or 'None'}
          </p>
          <div class="flex gap-2">
            <a href="/configure/{guild_id}/partnership/groups/edit/{cat_name}" class="flex-1 py-1 bg-blue-500 dark:bg-blue-600 text-white rounded text-center text-sm hover:bg-blue-600 dark:hover:bg-blue-700 transition">
              Edit
            </a>
            <button onclick="deleteGroup('{cat_name}')" class="flex-1 py-1 bg-red-500 dark:bg-red-600 text-white rounded text-sm hover:bg-red-600 dark:hover:bg-red-700 transition">
              Delete
            </button>
          </div>
        </div>
        """

    content = f"""
      <main class="p-6 max-w-6xl mx-auto">
        <div class="flex items-center gap-4 mb-6">
          {"<img src='"+icon+"' class='rounded-full w-12 h-12 shadow-md'>" if icon else "<div class='w-12 h-12 rounded-full bg-gray-200 dark:bg-gray-600 flex items-center justify-center text-gray-500 dark:text-gray-300'>"+html.escape(guild['name'][0])+"</div>"}
          <div>
            <h2 class="text-2xl font-bold text-gray-900 dark:text-white">{html.escape(guild['name'])}</h2>
            <p class="text-gray-500 dark:text-gray-400">Partnership Groups</p>
          </div>
        </div>

        {f'<div class="bg-green-100 dark:bg-green-900 border border-green-400 dark:border-green-600 text-green-700 dark:text-green-300 px-4 py-3 rounded mb-4">{message.replace("+", " ")}</div>' if message else ''}

        <div class="flex justify-between items-center mb-6">
          <h3 class="text-xl font-semibold text-gray-900 dark:text-white">Groups ({len(categories)})</h3>
          <a href="/configure/{guild_id}/partnership/groups/add" class="py-2 px-4 bg-green-500 dark:bg-green-600 text-white rounded-md font-medium hover:bg-green-600 dark:hover:bg-green-700 transition">
            Add Group
          </a>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {category_cards if category_cards else '<div class="col-span-full text-center py-8 text-gray-500 dark:text-gray-400">No groups created yet. Create your first group to get started!</div>'}
        </div>
      </main>

      <script>
        function deleteGroup(groupName) {{
          if (confirm(`Delete group "${{groupName}}" and all its partners? This cannot be undone!`)) {{
            fetch(`/configure/{guild_id}/partnership/groups/delete/${{encodeURIComponent(groupName)}}`, {{
              method: 'POST'
            }}).then(response => response.json())
              .then(data => {{
                alert(data.message);
                if (data.success) location.reload();
              }});
          }}
        }}
      </script>
    """

    return wrap_page(f"Manage Groups - {html.escape(guild['name'])}", content, [("/configure/" + guild_id + "/partnership", "Back to Partnerships", "text-blue-500 dark:text-blue-400 font-medium hover:underline")])

@partnership.route("/configure/<guild_id>/partnership/groups/add")
def add_group_form(guild_id):
    if "discord_token" not in session:
        return redirect("/")
    
    discord_token = session['discord_token']
    success, guild, status_code = verify_guild_access(guild_id, discord_token, user_guilds_only=True)
    if not success:
        return f"<h1>{guild['error']}</h1>", status_code

    icon = f"https://cdn.discordapp.com/icons/{guild['id']}/{guild['icon']}.png?size=128" if guild.get("icon") else ""

    content = f"""
      <main class="p-6 max-w-2xl mx-auto">
        <div class="flex items-center gap-4 mb-6">
          {"<img src='"+icon+"' class='rounded-full w-12 h-12 shadow-md'>" if icon else "<div class='w-12 h-12 rounded-full bg-gray-200 dark:bg-gray-600 flex items-center justify-center text-gray-500 dark:text-gray-300'>"+guild['name'][0]+"</div>"}
          <div>
            <h2 class="text-2xl font-bold text-gray-900 dark:text-white">Add New Group</h2>
            <p class="text-gray-500 dark:text-gray-400">Create a new partnership group</p>
          </div>
        </div>

        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow dark:shadow-gray-700 p-6">
          <form action="/configure/{guild_id}/partnership/groups/add" method="post">
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Group Name *</label>
              <input type="text" name="name" required class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md" placeholder="e.g. premium-servers">
              <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">No spaces allowed. Use hyphens or underscores.</p>
            </div>
            
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Display Title</label>
              <input type="text" name="title" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md" placeholder="e.g. Premium Servers">
              <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">Leave blank to use group name</p>
            </div>
            
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Embed Color</label>
              <input type="text" name="color" value="#5865F2" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md" placeholder="#5865F2">
            </div>
            
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Line Prefix</label>
              <input type="text" name="prefix" value="-" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md" placeholder="-">
              <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">Character(s) shown before each partner</p>
            </div>
            
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Line Suffix</label>
              <input type="text" name="suffix" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md" placeholder="Optional">
              <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">Character(s) shown after each partner</p>
            </div>
            
            <div class="mb-6">
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Thumbnail URL</label>
              <input type="url" name="thumbnail" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md" placeholder="https://example.com/image.png">
              <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">Optional thumbnail for the group embed</p>
            </div>
            
            <button type="submit" class="w-full py-2 bg-green-500 dark:bg-green-600 text-white rounded-md font-medium hover:bg-green-600 dark:hover:bg-green-700 transition">
              Create Group
            </button>
          </form>
        </div>
      </main>
    """
    
    return wrap_page(f"Add Group - {html.escape(guild['name'])}", content, [("/configure/" + guild_id + "/partnership/groups", "Back to Groups", "text-blue-500 dark:text-blue-400 font-medium hover:underline")])

@partnership.route("/configure/<guild_id>/partnership/groups/add", methods=["POST"])
def add_group_submit(guild_id):
    if "discord_token" not in session:
        return redirect("/")

    try:
        name = request.form.get("name").strip()
        if not re.match(r"^[\w-]+$", name):
            return redirect(f"/configure/{guild_id}/partnership/groups?message=Invalid+group+name.+Use+only+letters,+numbers,+hyphens,+and+underscores.")

        categories_ref = db.reference(f"/Partner/categories/{guild_id}")
        categories = categories_ref.get() or {}
        if name.lower() in [k.lower() for k in categories.keys()]:
            return redirect(f"/configure/{guild_id}/partnership/groups?message=Group+already+exists.")

        group_data = {
            "title": request.form.get("title").strip() or name,
            "color": request.form.get("color") or "#5865F2",
            "prefix": request.form.get("prefix") or "-",
            "suffix": request.form.get("suffix", ""),
            "thumbnail": request.form.get("thumbnail") or None,
            "created_at": int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        }

        categories_ref.child(name).set(group_data)
        return redirect(f"/configure/{guild_id}/partnership/groups?message=Group+created+successfully")

    except Exception as e:
        return redirect(f"/configure/{guild_id}/partnership/groups?message=Error+creating+group:+{str(e)}")

@partnership.route("/configure/<guild_id>/partnership/groups/edit/<group_name>")
def edit_group_form(guild_id, group_name):
    if "discord_token" not in session:
        return redirect("/")

    discord_token = session['discord_token']
    success, guild, status_code = verify_guild_access(guild_id, discord_token, user_guilds_only=True)
    if not success:
        return f"<h1>{guild['error']}</h1>", status_code

    categories_ref = db.reference(f"/Partner/categories/{guild_id}")
    categories = categories_ref.get() or {}
    if group_name not in categories:
        return redirect(f"/configure/{guild_id}/partnership/groups?message=Group+not+found")

    group_data = categories[group_name]
    icon = f"https://cdn.discordapp.com/icons/{guild['id']}/{guild['icon']}.png?size=128" if guild.get("icon") else ""

    content = f"""
      <main class="p-6 max-w-2xl mx-auto">
        <div class="flex items-center gap-4 mb-6">
          {"<img src='"+icon+"' class='rounded-full w-12 h-12 shadow-md'>" if icon else "<div class='w-12 h-12 rounded-full bg-gray-200 dark:bg-gray-600 flex items-center justify-center text-gray-500 dark:text-gray-300'>"+html.escape(guild['name'][0])+"</div>"}
          <div>
            <h2 class="text-2xl font-bold text-gray-900 dark:text-white">Edit Group: {group_name}</h2>
            <p class="text-gray-500 dark:text-gray-400">Modify group settings</p>
          </div>
        </div>

        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow dark:shadow-gray-700 p-6">
          <form action="/configure/{guild_id}/partnership/groups/edit/{group_name}" method="post">
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Group Name</label>
              <input type="text" name="group_name" value="{group_name}" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md" required>
              <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">Used for alphabetical ordering. All partners and data will be preserved when changing the name.</p>
            </div>
            
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Display Title</label>
              <input type="text" name="title" value="{group_data.get('title', group_name)}" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md">
            </div>
            
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Embed Color</label>
              <input type="text" name="color" value="{group_data.get('color', '#5865F2')}" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md">
            </div>
            
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Line Prefix</label>
              <input type="text" name="prefix" value="{group_data.get('prefix', '-')}" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md">
            </div>
            
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Line Suffix</label>
              <input type="text" name="suffix" value="{group_data.get('suffix', '')}" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md">
            </div>
            
            <div class="mb-6">
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Thumbnail URL</label>
              <input type="url" name="thumbnail" value="{group_data.get('thumbnail') or ''}" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md">
            </div>
            
            <button type="submit" class="w-full py-2 bg-blue-500 dark:bg-blue-600 text-white rounded-md font-medium hover:bg-blue-600 dark:hover:bg-blue-700 transition">
              Save Changes
            </button>
          </form>
        </div>
      </main>
    """
    
    return wrap_page(f"Edit Group - {html.escape(guild['name'])}", content, [("/configure/" + guild_id + "/partnership/groups", "Back to Groups", "text-blue-500 dark:text-blue-400 font-medium hover:underline")])

@partnership.route("/configure/<guild_id>/partnership/groups/edit/<group_name>", methods=["POST"])
def edit_group_submit(guild_id, group_name):
    if "discord_token" not in session:
        return redirect("/")

    try:
        new_group_name = request.form.get("group_name").strip()
        if not new_group_name:
            return redirect(f"/configure/{guild_id}/partnership/groups?message=Group+name+cannot+be+empty")

        group_data = {
            "title": request.form.get("title").strip() or new_group_name,
            "color": request.form.get("color") or "#5865F2", 
            "prefix": request.form.get("prefix") or "-",
            "suffix": request.form.get("suffix", ""),
            "thumbnail": request.form.get("thumbnail") or None
        }

        categories_ref = db.reference(f"/Partner/categories/{guild_id}")
        
        if new_group_name != group_name:
            existing_categories = categories_ref.get() or {}
            if new_group_name in existing_categories:
                return redirect(f"/configure/{guild_id}/partnership/groups?message=Group+name+already+exists")
            
            old_group_data = categories_ref.child(group_name).get()
            if old_group_data:
                partners_ref = db.reference(f"/Partner/partners/{guild_id}")
                partners = partners_ref.get() or {}
                for partner_id, partner_data in partners.items():
                    if partner_data.get('category') == group_name:
                        partners_ref.child(partner_id).update({'category': new_group_name})
                
                categories_ref.child(group_name).delete()
                
            categories_ref.child(new_group_name).set(group_data)
            message = "Group+name+and+data+updated+successfully"
        else:
            categories_ref.child(group_name).update(group_data)
            message = "Group+updated+successfully"
            
        return redirect(f"/configure/{guild_id}/partnership/groups?message={message}")

    except Exception as e:
        return redirect(f"/configure/{guild_id}/partnership/groups?message=Error+updating+group:+{str(e)}")

@partnership.route("/configure/<guild_id>/partnership/groups/delete/<group_name>", methods=["POST"])
def delete_group(guild_id, group_name):
    if "discord_token" not in session:
        return {"success": False, "message": "Not authenticated"}, 401

    try:
        partners_ref = db.reference(f"/Partner/partners/{guild_id}")
        partners = partners_ref.get() or {}
        deleted_count = 0

        for partner_id, partner_data in partners.items():
            if partner_data.get('category') == group_name:
                partners_ref.child(partner_id).delete()
                deleted_count += 1

        db.reference(f"/Partner/categories/{guild_id}").child(group_name).delete()

        return {"success": True, "message": f"Group deleted along with {deleted_count} partner(s)"}

    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}, 500


@partnership.route("/configure/<guild_id>/partnership/partners")
def manage_partners(guild_id):
    if "discord_token" not in session:
        return redirect("/")

    discord_token = session['discord_token']
    
    success, guild, status_code = verify_guild_access(guild_id, discord_token, require_bot_in_guild=False)
    if not success:
        return f"<h1>{guild['error']}</h1>", status_code

    def fetch_partners():
        partners_ref = db.reference(f"/Partner/partners/{guild_id}")
        return partners_ref.get() or {}
    
    def fetch_categories():
        categories_ref = db.reference(f"/Partner/categories/{guild_id}")
        return categories_ref.get() or {}

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_partners = executor.submit(fetch_partners)
        future_categories = executor.submit(fetch_categories)
        
        partners = future_partners.result()
        categories = future_categories.result()

    icon = f"https://cdn.discordapp.com/icons/{guild['id']}/{guild['icon']}.png?size=128" if guild.get("icon") else ""
    message = request.args.get('message', '')

    partner_cards = ""
    for partner_id, partner_data in partners.items():
        category_name = partner_data.get('category', 'Unknown')
        
        created_at = partner_data.get('timestamp')
        if created_at and isinstance(created_at, (int, float)):
            created_date = datetime.datetime.fromtimestamp(created_at, tz=datetime.timezone.utc)
            formatted_date = created_date.strftime('%Y-%m-%d %H:%M UTC')
        else:
            formatted_date = 'Unknown'
            
        partner_cards += f"""
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow dark:shadow-gray-700 p-4">
          <div class="flex justify-between items-start mb-2">
            <h4 class="font-semibold text-lg text-gray-900 dark:text-white">{partner_data.get('name', 'Unknown')}</h4>
            <span class="text-xs px-2 py-1 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded">{category_name}</span>
          </div>
          <p class="text-sm text-gray-600 dark:text-gray-300 mb-3">
            <strong>Invite:</strong> <a href="https://discord.gg/{partner_data.get('invite', '#')}" target="_blank" class="text-blue-500 dark:text-blue-400 hover:underline">{partner_data.get('invite', 'N/A')}</a><br>
            <strong>Added:</strong> {formatted_date}
          </p>
          <div class="flex gap-2">
            <button onclick="removePartner('{partner_id}', '{partner_data.get('name', 'Unknown')}')" class="flex-1 py-1 bg-red-500 dark:bg-red-600 text-white rounded text-sm hover:bg-red-600 dark:hover:bg-red-700 transition">
              Remove
            </button>
          </div>
        </div>
        """

    content = f"""
      <main class="p-6 max-w-6xl mx-auto">
        <div class="flex items-center gap-4 mb-6">
          {"<img src='"+icon+"' class='rounded-full w-12 h-12 shadow-md'>" if icon else "<div class='w-12 h-12 rounded-full bg-gray-200 dark:bg-gray-600 flex items-center justify-center text-gray-500 dark:text-gray-300'>"+html.escape(guild['name'][0])+"</div>"}
          <div>
            <h2 class="text-2xl font-bold text-gray-900 dark:text-white">{html.escape(guild['name'])}</h2>
            <p class="text-gray-500 dark:text-gray-400">Partnership Partners</p>
          </div>
        </div>

        {f'<div class="bg-green-100 dark:bg-green-900 border border-green-400 dark:border-green-600 text-green-700 dark:text-green-300 px-4 py-3 rounded mb-4">{message.replace("+", " ")}</div>' if message else ''}

        <div class="flex justify-between items-center mb-6">
          <h3 class="text-xl font-semibold text-gray-900 dark:text-white">Partners ({len(partners)})</h3>
          <a href="/configure/{guild_id}/partnership/partners/add" class="py-2 px-4 bg-green-500 dark:bg-green-600 text-white rounded-md font-medium hover:bg-green-600 dark:hover:bg-green-700 transition">
            Add Partner
          </a>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {partner_cards if partner_cards else '<div class="col-span-full text-center py-8 text-gray-500 dark:text-gray-400">No partners added yet. Add your first partner to get started!</div>'}
        </div>
      </main>

      <script>
        function removePartner(partnerId, partnerName) {{
          if (confirm(`Remove partner "${{partnerName}}"? This cannot be undone!`)) {{
            fetch(`/configure/{guild_id}/partnership/partners/delete/${{partnerId}}`, {{
              method: 'POST'
            }}).then(response => response.json())
              .then(data => {{
                alert(data.message);
                if (data.success) location.reload();
              }});
          }}
        }}
      </script>
    """
    
    return wrap_page(f"Manage Partners - {html.escape(guild['name'])}", content, [("/configure/" + guild_id + "/partnership", "Back to Partnerships", "text-blue-500 dark:text-blue-400 font-medium hover:underline")])

@partnership.route("/configure/<guild_id>/partnership/partners/add")
def add_partner_form(guild_id):
    if "discord_token" not in session:
        return redirect("/")
    
    discord_token = session['discord_token']
    success, guild, status_code = verify_guild_access(guild_id, discord_token, user_guilds_only=True)
    if not success:
        return f"<h1>{guild['error']}</h1>", status_code

    categories_ref = db.reference(f"/Partner/categories/{guild_id}")
    categories = categories_ref.get() or {}

    if not categories:
        return redirect(f"/configure/{guild_id}/partnership/partners?message=Please+create+at+least+one+group+first")

    icon = f"https://cdn.discordapp.com/icons/{guild['id']}/{guild['icon']}.png?size=128" if guild.get("icon") else ""

    category_options = "".join([
        f'<option value="{cat_name}">{cat_data.get("title", cat_name)}</option>'
        for cat_name, cat_data in categories.items()
    ])

    content = f"""
      <main class="p-6 max-w-2xl mx-auto">
        <div class="flex items-center gap-4 mb-6">
          {"<img src='"+icon+"' class='rounded-full w-12 h-12 shadow-md'>" if icon else "<div class='w-12 h-12 rounded-full bg-gray-200 dark:bg-gray-600 flex items-center justify-center text-gray-500 dark:text-gray-300'>"+html.escape(guild['name'][0])+"</div>"}
          <div>
            <h2 class="text-2xl font-bold text-gray-900 dark:text-white">Add New Partner</h2>
            <p class="text-gray-500 dark:text-gray-400">Add a server to your partnership panel</p>
          </div>
        </div>

        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow dark:shadow-gray-700 p-6">
          <form action="/configure/{guild_id}/partnership/partners/add" method="post">
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Server Name *</label>
              <input type="text" name="name" required class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md" placeholder="e.g. Awesome Gaming Server">
            </div>
            
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Invite Link *</label>
              <input type="url" name="invite" required class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md" placeholder="https://discord.gg/example">
              <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">Please include https:// and ensure it's a permanent invite</p>
            </div>
            
            <div class="mb-6">
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Group *</label>
              <select name="group" required class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md">
                <option value="">Select a group</option>
                {category_options}
              </select>
              <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">The category this server belongs to</p>
            </div>
            
            <button type="submit" class="w-full py-2 bg-green-500 dark:bg-green-600 text-white rounded-md font-medium hover:bg-green-600 dark:hover:bg-green-700 transition">
              Add Partner
            </button>
          </form>
        </div>
      </main>
    """
    
    return wrap_page(f"Add Partner - {html.escape(guild['name'])}", content, [("/configure/" + guild_id + "/partnership/partners", "Back to Partners", "text-blue-500 dark:text-blue-400 font-medium hover:underline")])

@partnership.route("/configure/<guild_id>/partnership/partners/add", methods=["POST"])
def add_partner_submit(guild_id):
    if "discord_token" not in session:
        return redirect("/")

    try:
        name = request.form.get("name").strip()
        invite = request.form.get("invite").strip()
        group = request.form.get("group").strip()

        if not name or not invite or not group:
            return redirect(f"/configure/{guild_id}/partnership/partners?message=All+fields+are+required")

        if not (invite.startswith("https://discord.gg/") or invite.startswith("https://discord.com/invite/")):
            return redirect(f"/configure/{guild_id}/partnership/partners?message=Invalid+invite+format.+Must+start+with+https://discord.gg/+or+https://discord.com/invite/")

        if "/invite/" in invite:
            code = invite.split("/invite/")[1].split("?")[0]
        else:
            code = invite.split("discord.gg/")[1].split("?")[0]

        partners_ref = db.reference(f"/Partner/partners/{guild_id}")
        existing_partners = partners_ref.get() or {}
        
        for partner_data in existing_partners.values():
            existing_invite = partner_data.get('invite', '')
            if code in existing_invite:
                return redirect(f"/configure/{guild_id}/partnership/partners?message=Partner+already+exists+with+this+invite")

        partner_data = {
            "name": name,
            "invite": invite,
            "category": group,
            "timestamp": int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        }

        partners_ref.push(partner_data)
        return redirect(f"/configure/{guild_id}/partnership/partners?message=Partner+added+successfully")

    except Exception as e:
        return redirect(f"/configure/{guild_id}/partnership/partners?message=Error+adding+partner:+{str(e)}")

@partnership.route("/configure/<guild_id>/partnership/partners/delete/<partner_id>", methods=["POST"])
def delete_partner(guild_id, partner_id):
    if "discord_token" not in session:
        return {"success": False, "message": "Not authenticated"}, 401

    try:
        db.reference(f"/Partner/partners/{guild_id}").child(partner_id).delete()
        return {"success": True, "message": "Partner removed successfully"}

    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}, 500

@partnership.route("/configure/<guild_id>/partnership/blacklist")
def manage_blacklist(guild_id):
    if "discord_token" not in session:
        return redirect("/")

    discord_token = session['discord_token']
    success, guild, status_code = verify_guild_access(guild_id, discord_token, user_guilds_only=True)
    if not success:
        return f"<h1>{guild['error']}</h1>", status_code

    blacklist_ref = db.reference(f"/Partner/Blacklist/{guild_id}")
    blacklist = blacklist_ref.get() or {}

    icon = f"https://cdn.discordapp.com/icons/{guild['id']}/{guild['icon']}.png?size=128" if guild.get("icon") else ""
    message = request.args.get('message', '')

    blacklist_cards = ""
    for server_id in blacklist.keys():
        blacklist_cards += f"""
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow dark:shadow-gray-700 p-4">
          <div class="flex justify-between items-start mb-2">
            <h4 class="font-semibold text-lg text-gray-900 dark:text-white">Server ID: {server_id}</h4>
            <span class="text-xs px-2 py-1 bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-300 rounded">Blacklisted</span>
          </div>
          <div class="flex gap-2 mt-3">
            <button onclick="unblacklistServer('{server_id}')" class="flex-1 py-1 bg-green-500 dark:bg-green-600 text-white rounded text-sm hover:bg-green-600 dark:hover:bg-green-700 transition">
              Unblacklist
            </button>
          </div>
        </div>
        """

    content = f"""
      <main class="p-6 max-w-6xl mx-auto">
        <div class="flex items-center gap-4 mb-6">
          {"<img src='"+icon+"' class='rounded-full w-12 h-12 shadow-md'>" if icon else "<div class='w-12 h-12 rounded-full bg-gray-200 dark:bg-gray-600 flex items-center justify-center text-gray-500 dark:text-gray-300'>"+html.escape(guild['name'][0])+"</div>"}
          <div>
            <h2 class="text-2xl font-bold text-gray-900 dark:text-white">{html.escape(guild['name'])}</h2>
            <p class="text-gray-500 dark:text-gray-400">Partnership Blacklist</p>
          </div>
        </div>

        {f'<div class="bg-green-100 dark:bg-green-900 border border-green-400 dark:border-green-600 text-green-700 dark:text-green-300 px-4 py-3 rounded mb-4">{message.replace("+", " ")}</div>' if message else ''}

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div class="bg-white dark:bg-gray-800 rounded-2xl shadow dark:shadow-gray-700 p-6">
            <h3 class="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Add to Blacklist</h3>
            
            <form action="/configure/{guild_id}/partnership/blacklist/add" method="post">
              <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Method</label>
                <select name="method" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md" onchange="toggleInput(this.value)">
                  <option value="server_id">Server ID</option>
                  <option value="invite_link">Invite Link</option>
                </select>
              </div>
              
              <div class="mb-4" id="server-id-input">
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Server ID</label>
                <input type="text" name="server_id" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md" placeholder="123456789012345678">
              </div>
              
              <div class="mb-4 hidden" id="invite-input">
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Invite Link</label>
                <input type="url" name="invite_link" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md" placeholder="https://discord.gg/example">
              </div>
              
              <button type="submit" class="w-full py-2 bg-red-500 dark:bg-red-600 text-white rounded-md font-medium hover:bg-red-600 dark:hover:bg-red-700 transition">
                Add to Blacklist
              </button>
            </form>
          </div>

          <div class="bg-white dark:bg-gray-800 rounded-2xl shadow dark:shadow-gray-700 p-6">
            <h3 class="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Blacklisted Servers ({len(blacklist)})</h3>
            
            <div class="space-y-3 max-h-96 overflow-y-auto">
              {blacklist_cards if blacklist_cards else '<p class="text-gray-500 dark:text-gray-400 text-center py-8">No servers blacklisted</p>'}
            </div>
          </div>
        </div>
      </main>

      <script>
        function toggleInput(method) {{
          const serverIdInput = document.getElementById('server-id-input');
          const inviteInput = document.getElementById('invite-input');
          
          if (method === 'server_id') {{
            serverIdInput.classList.remove('hidden');
            inviteInput.classList.add('hidden');
            serverIdInput.querySelector('input').required = true;
            inviteInput.querySelector('input').required = false;
          }} else {{
            serverIdInput.classList.add('hidden');
            inviteInput.classList.remove('hidden');
            serverIdInput.querySelector('input').required = false;
            inviteInput.querySelector('input').required = true;
          }}
        }}
        
        function unblacklistServer(serverId) {{
          if (confirm(`Remove server ${{serverId}} from blacklist?`)) {{
            fetch(`/configure/{guild_id}/partnership/blacklist/remove/${{serverId}}`, {{
              method: 'POST'
            }}).then(response => response.json())
              .then(data => {{
                alert(data.message);
                if (data.success) location.reload();
              }});
          }}
        }}
      </script>
    """
    
    return wrap_page(f"Manage Blacklist - {html.escape(guild['name'])}", content, [("/configure/" + guild_id + "/partnership", "Back to Partnerships", "text-blue-500 dark:text-blue-400 font-medium hover:underline")])

@partnership.route("/configure/<guild_id>/partnership/blacklist/add", methods=["POST"])
def add_to_blacklist(guild_id):
    if "discord_token" not in session:
        return redirect("/")

    try:
        method = request.form.get("method")
        
        if method == "server_id":
            server_id = request.form.get("server_id").strip()
            if not server_id.isdigit():
                return redirect(f"/configure/{guild_id}/partnership/blacklist?message=Invalid+server+ID+format")
                
        elif method == "invite_link":
            invite_link = request.form.get("invite_link").strip()
            
            try:
                if "/invite/" in invite_link:
                    code = invite_link.split("/invite/")[1].split("?")[0]
                else:
                    code = invite_link.split("discord.gg/")[1].split("?")[0]
                
                invite_response = requests.get(f"{API_BASE}/invites/{code}", headers={"Authorization": f"Bot {BOT_TOKEN}"})
                if invite_response.status_code != 200:
                    return redirect(f"/configure/{guild_id}/partnership/blacklist?message=Could+not+fetch+server+info+from+invite")
                
                invite_data = invite_response.json()
                server_id = invite_data["guild"]["id"]
                
            except Exception:
                return redirect(f"/configure/{guild_id}/partnership/blacklist?message=Invalid+invite+link+format")
        else:
            return redirect(f"/configure/{guild_id}/partnership/blacklist?message=Invalid+method")

        db.reference(f"/Partner/Blacklist/{guild_id}").child(server_id).set(True)
        return redirect(f"/configure/{guild_id}/partnership/blacklist?message=Server+blacklisted+successfully")

    except Exception as e:
        return redirect(f"/configure/{guild_id}/partnership/blacklist?message=Error+blacklisting+server:+{str(e)}")

@partnership.route("/configure/<guild_id>/partnership/blacklist/remove/<server_id>", methods=["POST"])
def remove_from_blacklist(guild_id, server_id):
    if "discord_token" not in session:
        return {"success": False, "message": "Not authenticated"}, 401

    try:
        db.reference(f"/Partner/Blacklist/{guild_id}").child(server_id).delete()
        return {"success": True, "message": "Server removed from blacklist successfully"}

    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}, 500


@partnership.route("/configure/<guild_id>/partnership/panel")
def manage_panel(guild_id):
    if "discord_token" not in session:
        return redirect("/")

    discord_token = session['discord_token']
    success, guild, status_code = verify_guild_access(guild_id, discord_token, user_guilds_only=True)
    if not success:
        return f"<h1>{guild['error']}</h1>", status_code

    config_ref = db.reference(f"/Partner/config/{guild_id}")
    config = config_ref.get() or {}
    embed_config = config.get('embed', {})
    header = embed_config.get('header', {})
    footer = embed_config.get('footer', {})

    icon = f"https://cdn.discordapp.com/icons/{guild['id']}/{guild['icon']}.png?size=128" if guild.get("icon") else ""
    message = request.args.get('message', '')

    content = f"""
      <main class="p-6 max-w-6xl mx-auto">
        <div class="flex items-center gap-4 mb-6">
          {"<img src='"+icon+"' class='rounded-full w-12 h-12 shadow-md'>" if icon else "<div class='w-12 h-12 rounded-full bg-gray-200 dark:bg-gray-600 flex items-center justify-center text-gray-500 dark:text-gray-300'>"+html.escape(guild['name'][0])+"</div>"}
          <div>
            <h2 class="text-2xl font-bold text-gray-900 dark:text-white">{html.escape(guild['name'])}</h2>
            <p class="text-gray-500 dark:text-gray-400">Partnership Panel Configuration</p>
          </div>
        </div>

        {f'<div class="bg-green-100 dark:bg-green-900 border border-green-400 dark:border-green-600 text-green-700 dark:text-green-300 px-4 py-3 rounded mb-4">{message.replace("+", " ")}</div>' if message else ''}

        <form action="/configure/{guild_id}/partnership/panel/edit" method="post">
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            <div class="bg-white dark:bg-gray-800 rounded-2xl shadow dark:shadow-gray-700 p-6">
              <h3 class="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Header Embed</h3>
              <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Title</label>
                <input type="text" name="header_title" value="{header.get('title', '')}" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md" placeholder="Server Partner List">
              </div>
              
              <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Description</label>
                <textarea name="header_description" rows="3" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md" placeholder="Welcome to our partner list!">{header.get('description', '')}</textarea>
              </div>
              
              <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Color (Hex)</label>
                <input type="text" name="header_color" value="{header.get('color', '#5865F2')}" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md" placeholder="#5865F2">
              </div>
              
              <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Thumbnail URL</label>
                <input type="url" name="header_thumbnail" value="{header.get('thumbnail', '')}" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md" placeholder="https://example.com/image.png">
              </div>
              
              <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Image URL</label>
                <input type="url" name="header_image" value="{header.get('image', '')}" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md" placeholder="https://example.com/banner.png">
              </div>
            </div>

            <div class="bg-white dark:bg-gray-800 rounded-2xl shadow dark:shadow-gray-700 p-6">
              <h3 class="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Footer Embed</h3>
              <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Title</label>
                <input type="text" name="footer_title" value="{footer.get('title', '')}" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md" placeholder="Instructions">
              </div>
              
              <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Description</label>
                <textarea name="footer_description" rows="3" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md" placeholder="Click the button below to request a partnership!">{footer.get('description', '')}</textarea>
              </div>
              
              <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Color (Hex)</label>
                <input type="text" name="footer_color" value="{footer.get('color', '#5865F2')}" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md" placeholder="#5865F2">
              </div>
              
              <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Thumbnail URL</label>
                <input type="url" name="footer_thumbnail" value="{footer.get('thumbnail', '')}" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md" placeholder="https://example.com/image.png">
              </div>
              
              <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Image URL</label>
                <input type="url" name="footer_image" value="{footer.get('image', '')}" class="w-full p-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md" placeholder="https://example.com/banner.png">
              </div>
            </div>
          </div>

          <div class="flex justify-center mb-6">
            <button type="submit" class="py-3 px-8 bg-purple-500 dark:bg-purple-600 text-white rounded-md font-medium hover:bg-purple-600 dark:hover:bg-purple-700 transition text-lg">
              Save Panel Configuration
            </button>
          </div>
        </form>

      </main>
    """
    
    return wrap_page(f"Manage Panel - {html.escape(guild['name'])}", content, [("/configure/" + guild_id + "/partnership", "Back to Partnerships", "text-blue-500 dark:text-blue-400 font-medium hover:underline")])

@partnership.route("/configure/<guild_id>/partnership/panel/edit", methods=["POST"])
def edit_panel(guild_id):
    if "discord_token" not in session:
        return redirect("/")

    try:
        header_data = {
            "title": request.form.get("header_title") or None,
            "description": request.form.get("header_description") or None,
            "color": request.form.get("header_color") or "#5865F2",
            "thumbnail": request.form.get("header_thumbnail") or None,
            "image": request.form.get("header_image") or None
        }
        
        footer_data = {
            "title": request.form.get("footer_title") or None,
            "description": request.form.get("footer_description") or None,
            "color": request.form.get("footer_color") or "#5865F2",
            "thumbnail": request.form.get("footer_thumbnail") or None,
            "image": request.form.get("footer_image") or None
        }
        
        header_data = {k: v for k, v in header_data.items() if v is not None and v != ""}
        footer_data = {k: v for k, v in footer_data.items() if v is not None and v != ""}
        
        if not header_data.get("color"):
            header_data["color"] = "#5865F2"
        if not footer_data.get("color"):
            footer_data["color"] = "#5865F2"

        embed_ref = db.reference(f"/Partner/config/{guild_id}").child("embed")
        embed_ref.update({
            "header": header_data,
            "footer": footer_data
        })
        
        return redirect(f"/configure/{guild_id}/partnership/panel?message=Panel+configuration+updated+successfully")

    except Exception as e:
        return redirect(f"/configure/{guild_id}/partnership/panel?message=Error+updating+panel:+{str(e)}")

@partnership.route("/configure/<guild_id>/partnership/panel/edit/<section>", methods=["POST"])
def edit_panel_section(guild_id, section):
    if "discord_token" not in session:
        return redirect("/")

    try:
        data = {
            "title": request.form.get("title") or None,
            "description": request.form.get("description") or None,
            "color": request.form.get("color") or "#5865F2",
            "thumbnail": request.form.get("thumbnail") or None,
            "image": request.form.get("image") or None
        }
        
        data = {k: v for k, v in data.items() if v is not None and v != ""}
        if not data.get("color"):
            data["color"] = "#5865F2"

        db.reference(f"/Partner/config/{guild_id}").child(f"embed/{section}").update(data)
        return redirect(f"/configure/{guild_id}/partnership/panel?message={section.capitalize()}+embed+updated+successfully")

    except Exception as e:
        return redirect(f"/configure/{guild_id}/partnership/panel?message=Error+updating+{section}:+{str(e)}")

@partnership.route("/configure/<guild_id>/partnership/panel/send", methods=["POST"])
def send_panel_route(guild_id):
    if "discord_token" not in session:
        return {"success": False, "message": "Not authenticated"}, 401

    try:
        result = send_panel_via_api(guild_id)
        return {"success": result["success"], "message": result["message"]}

    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}, 500

@partnership.route("/configure/<guild_id>/partnership/panel/update", methods=["POST"])
def update_panel_route(guild_id):
    if "discord_token" not in session:
        return {"success": False, "message": "Not authenticated"}, 401

    try:
        db.reference(f"/Partner/panels/{guild_id}").update({
            "last_updated": int(time.time())
        })
        return {"success": True, "message": "Panel will be updated via Discord bot!"}

    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}, 500