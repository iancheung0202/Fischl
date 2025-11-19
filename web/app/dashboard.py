import requests
import html

from firebase_admin import db
from concurrent.futures import ThreadPoolExecutor
from flask import Blueprint, request, session, redirect, jsonify

from config.settings import API_BASE, BOT_TOKEN, CLIENT_ID, CLIENT_SECRET, REDIRECT_URI
from utils.firebase import save_user_to_firebase
from utils.request import requests_session, verify_guild_access
from utils.theme import wrap_page
from utils.loading import create_async_script, create_empty_content, create_loading_skeleton

dashboard = Blueprint('dashboard', __name__)

@dashboard.route("/dashboard")
def view_dashboard():
    # Handle OAuth callback
    code = request.args.get("code")
    if code:
        data = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "scope": "identify guilds",
        }

        r = requests.post(f"{API_BASE}/oauth2/token", data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
        if r.status_code != 200:
            return f"Token exchange failed: {r.text}", 400

        tokens = r.json()
        session["discord_token"] = tokens["access_token"]

        user = requests.get(f"{API_BASE}/users/@me", headers={"Authorization": f"Bearer {tokens['access_token']}"}).json()
        save_user_to_firebase(user, tokens["access_token"])
        session["user_id"] = str(user["id"])  # Ensure string type to avoid precision issues

        return redirect("/dashboard")

    # Check if this is a bot/crawler accessing the page
    user_agent = request.headers.get('User-Agent', '').lower()
    bot_keywords = ['bot', 'crawler', 'spider', 'scraper', 'discordbot', 'twitterbot', 'facebookexternalhit']
    is_bot = any(keyword in user_agent for keyword in bot_keywords)
    
    if is_bot:
        # Serve a static page with OG meta tags for bots/crawlers
        bot_content = """
          <main class="p-6 max-w-5xl mx-auto text-center">
            <div class="mb-8">
              <img src="https://cdn.discordapp.com/avatars/732422232273584198/624035e5e9a841bfd3020e35a0a5c0a0.png?size=128" 
                   alt="Fischl Bot" class="rounded-full w-32 h-32 shadow-md mx-auto mb-4">
              <h1 class="text-4xl font-bold text-gray-900 dark:text-white mb-4">Fischl Dashboard</h1>
              <p class="text-xl text-gray-600 dark:text-gray-300 mb-8">
                A multi-purpose Genshin-based verified Discord bot that includes customizable ticket system, 
                co-op matchmaking, chat minigames, partnership system, and more 👀
              </p>
              <a href="/login" class="inline-block px-8 py-3 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-medium transition">
                Login with Discord
              </a>
            </div>
          </main>
        """
        return wrap_page("Fischl Dashboard - A Simple & Powerful Utility Discord Bot", bot_content, [])

    # Check authentication for normal visits
    if "discord_token" not in session:
        return redirect("/login")

    # Extract session data before threading (Flask session is not thread-safe)
    discord_token = session['discord_token']

    # First, get user info quickly to show the page
    user = requests_session.get(f"{API_BASE}/users/@me", headers={"Authorization": f"Bearer {discord_token}"}).json()
    
    # Create initial page content with user info
    initial_content = f"""
      <main class="p-6 max-w-5xl mx-auto">
        <div class="flex items-center gap-4 mb-8">
          <img src="https://cdn.discordapp.com/avatars/{user['id']}/{user.get('avatar','')}.png?size=128" 
               alt="Avatar" class="rounded-full w-20 h-20 shadow-md">
          <div>
            <h2 class="text-2xl font-bold text-gray-900 dark:text-white">{user['username']}</h2>
            <p class="text-gray-500 dark:text-gray-400">ID: {user['id']}</p>
          </div>
        </div>

        <h3 class="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Your Guilds (Admin/Owner)</h3>
        <div id="guilds-container" class="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {create_loading_skeleton(3, "bg-white dark:bg-gray-800 rounded-2xl shadow hover:shadow-lg dark:shadow-gray-700 p-5 transition-all flex flex-col items-center")}
        </div>
      </main>
      
      {create_async_script('/api/dashboard/guilds', 'guilds-container')}
    """
    
    return wrap_page("Dashboard - Fischl", initial_content, [("/profile", "My Profile", "text-blue-500 dark:text-blue-400 font-medium hover:underline")])

@dashboard.route("/api/dashboard/guilds")
def api_dashboard_guilds():
    # Check authentication
    if "discord_token" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    try:
        # Extract session data before threading (Flask session is not thread-safe)
        discord_token = session['discord_token']

        # Make concurrent API calls
        def fetch_user_guilds(token):
            return requests_session.get(f"{API_BASE}/users/@me/guilds", headers={"Authorization": f"Bearer {token}"}).json()
        
        def fetch_bot_guilds():
            return requests_session.get(f"{API_BASE}/users/@me/guilds", headers={"Authorization": f"Bot {BOT_TOKEN}"}).json()

        # Execute all API calls concurrently
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_guilds = executor.submit(fetch_user_guilds, discord_token)
            future_bot_guilds = executor.submit(fetch_bot_guilds)
            
            # Get results
            guilds = future_guilds.result()
            bot_guilds = future_bot_guilds.result()

        bot_guild_ids = {g["id"] for g in bot_guilds}

        bot_client_id = CLIENT_ID  # Fischl bot client ID
        bot_invite_scope = "bot%20applications.commands"  # scopes your bot needs
        bot_invite_url = f"https://discord.com/oauth2/authorize?client_id={bot_client_id}&scope={bot_invite_scope}&permissions=8"

        guild_cards = ""

        guilds_sorted = sorted(
            guilds,
            key=lambda g: (g["id"] not in bot_guild_ids, g["name"].lower())
        )

        for g in guilds_sorted:
            if not (g.get("owner") or (int(g.get("permissions", 0)) & 0x8)):
                continue

            icon = f"https://cdn.discordapp.com/icons/{g['id']}/{g['icon']}.png?size=128" if g.get("icon") else ""
            bot_invited = g['id'] in bot_guild_ids

            if bot_invited:
                action_button = f'<a href="/configure/{g["id"]}" class="mt-4 block w-full py-2 bg-blue-500 text-white rounded-xl text-center font-medium hover:bg-blue-600 transition">Configure</a>'
            else:
                invite_link = f"{bot_invite_url}&guild_id={g['id']}"
                action_button = f'<a href="{invite_link}" target="_blank" class="mt-4 block w-full py-2 bg-green-500 text-white rounded-xl text-center font-medium hover:bg-green-600 transition">Invite</a>'

            guild_cards += f"""
            <div class="bg-white dark:bg-gray-800 rounded-2xl shadow hover:shadow-lg dark:shadow-gray-700 p-5 transition-all flex flex-col items-center">
              <div class="flex-grow flex flex-col items-center">
                {"<img src='"+icon+"' class='w-20 h-20 rounded-full mb-3'>" if icon else "<div class='w-20 h-20 rounded-full bg-gray-200 dark:bg-gray-600 mb-3 flex items-center justify-center text-gray-500 dark:text-gray-300'>"+(g.get('name', 'Unknown')[0] if g.get('name') else 'U')+"</div>"}
                <h4 class="font-bold text-lg text-center text-gray-900 dark:text-white">{g.get('name', 'Unknown Server')}</h4>
                <p class="text-gray-400 dark:text-gray-500 text-sm">ID: {g['id']}</p>
                {"<span class='mt-2 px-3 py-1 text-xs bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300 rounded-full'>Owner</span>" if g.get("owner") else ""}
              </div>
              {action_button}
            </div>
            """
        
        html_content = guild_cards if guild_cards else create_empty_content("No guilds where you are admin/owner.")
        
        return jsonify({"html": html_content})
    
    except Exception as e:
        return jsonify({"error": f"Failed to load guilds: {str(e)}"}), 500

@dashboard.route("/configure/<guild_id>")
def configure_guild(guild_id):
    if "discord_token" not in session:
        return redirect("/")

    # Load page immediately without any verification
    # All verification will happen in the async API calls
    
    # Page content with loading states - no guild info since we haven't verified access yet
    content = f"""
      <main class="p-6 max-w-5xl mx-auto">
        <div id="guild-header">
          <!-- Guild header will be loaded async -->
          <div class="flex items-center gap-4 mb-6">
            <div class="animate-pulse bg-gray-200 dark:bg-gray-600 w-20 h-20 rounded-full"></div>
            <div>
              <div class="animate-pulse bg-gray-200 dark:bg-gray-600 h-6 w-48 rounded mb-2"></div>
              <div class="animate-pulse bg-gray-200 dark:bg-gray-600 h-4 w-32 rounded"></div>
            </div>
          </div>
        </div>

        <div id="message-container"></div>

        <div id="features-container" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <!-- Loading states for features -->
          <div class="bg-white dark:bg-gray-800 rounded-2xl shadow dark:shadow-gray-700 p-6">
            <h3 class="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Ticket System</h3>
            <p class="text-gray-600 dark:text-gray-300 mb-4">Configure the ticket system for your server</p>
            <div class="flex items-center mb-4">
              <div class="animate-pulse bg-gray-200 dark:bg-gray-600 h-6 w-16 rounded-full"></div>
            </div>
            <a href="/configure/{guild_id}/ticket" class="block w-full py-2 bg-blue-500 hover:bg-blue-600 dark:bg-blue-600 dark:hover:bg-blue-700 text-white rounded-md text-center font-medium transition">
              Configure Tickets
            </a>
          </div>

          <div class="bg-white dark:bg-gray-800 rounded-2xl shadow dark:shadow-gray-700 p-6">
            <h3 class="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Partnership System</h3>
            <p class="text-gray-600 dark:text-gray-300 mb-4">Manage server partnerships and partner lists</p>
            <div class="flex items-center mb-4">
              <div class="animate-pulse bg-gray-200 dark:bg-gray-600 h-6 w-16 rounded-full"></div>
            </div>
            <a href="/configure/{guild_id}/partnership" class="block w-full py-2 bg-purple-500 hover:bg-purple-600 dark:bg-purple-600 dark:hover:bg-purple-700 text-white rounded-md text-center font-medium transition">
              Configure Partnerships
            </a>
          </div>

          <div class="bg-white dark:bg-gray-800 rounded-2xl shadow dark:shadow-gray-700 p-6">
            <h3 class="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Minigames System</h3>
            <p class="text-gray-600 dark:text-gray-300 mb-4">Configure random minigames and events for your channels</p>
            <div class="flex items-center mb-4">
              <div class="animate-pulse bg-gray-200 dark:bg-gray-600 h-6 w-16 rounded-full"></div>
            </div>
            <a href="/configure/{guild_id}/minigames" class="block w-full py-2 bg-yellow-500 hover:bg-yellow-600 dark:bg-yellow-600 dark:hover:bg-yellow-700 text-white rounded-md text-center font-medium transition">
              Configure Minigames
            </a>
          </div>
        </div>
      </main>
      
      <script>
        // Load guild header and status info in a single call
        fetch('/api/configure/{guild_id}/info')
          .then(response => response.json())
          .then(data => {{
            if (data.error) {{
              // If there's an error with guild access, show error page
              document.querySelector('main').innerHTML = 
                '<div class="p-6 max-w-5xl mx-auto text-center"><h1 class="text-2xl font-bold text-red-600 dark:text-red-400 mb-4">Access Denied</h1><p class="text-gray-600 dark:text-gray-300">' + data.error + '</p></div>';
              return;
            }}
            
            // Update header
            document.getElementById('guild-header').innerHTML = data.header;
            
            // Update features
            document.getElementById('features-container').innerHTML = data.features;
            
            // Show success message if present
            const urlParams = new URLSearchParams(window.location.search);
            const message = urlParams.get('message');
            if (message) {{
              document.getElementById('message-container').innerHTML = 
                '<div class="bg-green-100 dark:bg-green-900 border border-green-400 dark:border-green-600 text-green-700 dark:text-green-300 px-4 py-3 rounded mb-4">' + 
                message.replace(/\\+/g, ' ') + '</div>';
            }}
          }})
          .catch(error => {{
            console.error('Error loading guild info:', error);
            document.querySelector('main').innerHTML = 
              '<div class="p-6 max-w-3xl mx-auto text-center"><h1 class="text-2xl font-bold text-red-600 dark:text-red-400 mb-4">Error</h1><p class="text-gray-600 dark:text-gray-300">Failed to load page. Please refresh.</p></div>';
          }});
      </script>
    """
    
    return wrap_page("Configure Guild", content, [("/dashboard", "Back to Dashboard", "text-blue-500 dark:text-blue-400 font-medium hover:underline")])

@dashboard.route("/api/configure/<guild_id>/info")
def api_configure_info(guild_id):
    if "discord_token" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    try:
        # Extract session data before any threading
        discord_token = session['discord_token']
        
        # Verify guild access (no admin or bot checks needed for info display)
        success, guild, status_code = verify_guild_access(guild_id, discord_token, require_admin=False, require_bot_in_guild=False)
        if not success:
            return jsonify(guild), status_code

        def check_ticket_system():
            ref = db.reference("/Tickets")
            tickets = ref.get()
            has_ticket_system = False
            
            if tickets:
                for key, value in tickets.items():
                    if value.get("Server ID") == int(guild_id):
                        has_ticket_system = True
                        break
            return has_ticket_system

        def check_partnership_system():
            partner_ref = db.reference(f"/Partner/config/{guild_id}")
            partner_config = partner_ref.get()
            return partner_config is not None

        def check_minigames_system():
            try:
                # First, get all channels for this guild in one API call
                response = requests_session.get(f"{API_BASE}/guilds/{guild_id}/channels", 
                                              headers={"Authorization": f"Bot {BOT_TOKEN}"})
                if response.status_code != 200:
                    print(f"Failed to fetch guild channels: {response.status_code}")
                    return False
                
                guild_channels = response.json()
                if not isinstance(guild_channels, list):
                    print("Invalid response format for guild channels")
                    return False
                
                # Create a set of channel IDs for this guild for fast lookup
                guild_channel_ids = {str(channel['id']) for channel in guild_channels if channel.get('type') == 0}
                
                # Now check the minigames database
                ref = db.reference("/Global Events System")
                events_data = ref.get()
                if events_data and isinstance(events_data, dict):
                    for key, val in events_data.items():
                        if isinstance(val, dict) and "Channel ID" in val:
                            # Check if this channel belongs to the current guild
                            if str(val["Channel ID"]) in guild_channel_ids:
                                return True
                return False
            except Exception as e:
                print(f"Error checking minigames system: {e}")
                return False

        # Execute database checks concurrently
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_tickets = executor.submit(check_ticket_system)
            future_partners = executor.submit(check_partnership_system)
            future_minigames = executor.submit(check_minigames_system)
            
            has_ticket_system = future_tickets.result()
            has_partnership_system = future_partners.result()
            has_minigames_system = future_minigames.result()

        icon = f"https://cdn.discordapp.com/icons/{guild['id']}/{guild['icon']}.png?size=128" if guild.get("icon") else ""

        # Generate guild header HTML
        header_html = f"""
        <div class="flex items-center gap-4 mb-6">
          {"<img src='"+icon+"' class='rounded-full w-20 h-20 shadow-md'>" if icon else "<div class='w-20 h-20 rounded-full bg-gray-200 dark:bg-gray-600 flex items-center justify-center text-gray-500 dark:text-gray-300'>"+html.escape(guild['name'][0])+"</div>"}
          <div>
            <h2 class="text-2xl font-bold text-gray-900 dark:text-white">{html.escape(guild['name'])}</h2>
            <p class="text-gray-500 dark:text-gray-400">ID: {guild['id']}</p>
            {"<p class='text-green-600 dark:text-green-400 font-semibold'>You are the owner</p>" if guild.get("owner") else ""}
          </div>
        </div>
        """

        # Generate the feature cards with status
        features_html = f"""
          <div class="bg-white dark:bg-gray-800 rounded-2xl shadow dark:shadow-gray-700 p-6">
            <h3 class="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Ticket System</h3>
            <p class="text-gray-600 dark:text-gray-300 mb-4">Configure the ticket system for your server</p>
            <div class="flex items-center mb-4">
              {f'<span class="inline-flex items-center px-2 py-1 text-sm font-medium text-green-700 dark:text-green-300 bg-green-100 dark:bg-green-900 rounded-full">Enabled</span>' if has_ticket_system else f'<span class="inline-flex items-center px-2 py-1 text-sm font-medium text-red-700 dark:text-red-300 bg-red-100 dark:bg-red-900 rounded-full">Disabled</span>'}
            </div>
            <a href="/configure/{guild_id}/ticket" class="block w-full py-2 bg-blue-500 hover:bg-blue-600 dark:bg-blue-600 dark:hover:bg-blue-700 text-white rounded-md text-center font-medium transition">
              Configure Tickets
            </a>
          </div>

          <div class="bg-white dark:bg-gray-800 rounded-2xl shadow dark:shadow-gray-700 p-6">
            <h3 class="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Partnership System</h3>
            <p class="text-gray-600 dark:text-gray-300 mb-4">Manage server partnerships and partner lists</p>
            <div class="flex items-center mb-4">
              {f'<span class="inline-flex items-center px-2 py-1 text-sm font-medium text-green-700 dark:text-green-300 bg-green-100 dark:bg-green-900 rounded-full">Enabled</span>' if has_partnership_system else f'<span class="inline-flex items-center px-2 py-1 text-sm font-medium text-red-700 dark:text-red-300 bg-red-100 dark:bg-red-900 rounded-full">Disabled</span>'}
            </div>
            <a href="/configure/{guild_id}/partnership" class="block w-full py-2 bg-purple-500 hover:bg-purple-600 dark:bg-purple-600 dark:hover:bg-purple-700 text-white rounded-md text-center font-medium transition">
              Configure Partnerships
            </a>
          </div>

          <div class="bg-white dark:bg-gray-800 rounded-2xl shadow dark:shadow-gray-700 p-6">
            <h3 class="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Minigames System</h3>
            <p class="text-gray-600 dark:text-gray-300 mb-4">Configure random minigames and events for your channels</p>
            <div class="flex items-center mb-4">
              {f'<span class="inline-flex items-center px-2 py-1 text-sm font-medium text-green-700 dark:text-green-300 bg-green-100 dark:bg-green-900 rounded-full">Enabled</span>' if has_minigames_system else f'<span class="inline-flex items-center px-2 py-1 text-sm font-medium text-red-700 dark:text-red-300 bg-red-100 dark:bg-red-900 rounded-full">Disabled</span>'}
            </div>
            <a href="/configure/{guild_id}/minigames" class="block w-full py-2 bg-yellow-500 hover:bg-yellow-600 dark:bg-yellow-600 dark:hover:bg-yellow-700 text-white rounded-md text-center font-medium transition">
              Configure Minigames
            </a>
          </div>
        """

        return jsonify({
            "header": header_html,
            "features": features_html
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@dashboard.route("/api/configure/<guild_id>/status")
def api_configure_status(guild_id):
    if "discord_token" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    try:
        # Extract session data before any threading
        discord_token = session['discord_token']
        
        # Verify guild access (no admin or bot checks needed for status display)
        success, guild, status_code = verify_guild_access(guild_id, discord_token, require_admin=False, require_bot_in_guild=False)
        if not success:
            return jsonify(guild), status_code

        # Make concurrent Firebase database calls
        def check_ticket_system():
            ref = db.reference("/Tickets")
            tickets = ref.get()
            has_ticket_system = False
            
            if tickets:
                for key, value in tickets.items():
                    if value.get("Server ID") == int(guild_id):
                        has_ticket_system = True
                        break
            return has_ticket_system

        def check_partnership_system():
            partner_ref = db.reference(f"/Partner/config/{guild_id}")
            partner_config = partner_ref.get()
            return partner_config is not None

        # Execute database calls concurrently
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_tickets = executor.submit(check_ticket_system)
            future_partners = executor.submit(check_partnership_system)
            
            has_ticket_system = future_tickets.result()
            has_partnership_system = future_partners.result()

        # Generate the feature cards with status
        html_content = f"""
          <div class="bg-white dark:bg-gray-800 rounded-2xl shadow dark:shadow-gray-700 p-6">
            <h3 class="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Ticket System</h3>
            <p class="text-gray-600 dark:text-gray-300 mb-4">Configure the ticket system for your server</p>
            <div class="flex items-center mb-4">
              {f'<span class="inline-flex items-center px-2 py-1 text-sm font-medium text-green-700 dark:text-green-300 bg-green-100 dark:bg-green-900 rounded-full">Enabled</span>' if has_ticket_system else f'<span class="inline-flex items-center px-2 py-1 text-sm font-medium text-red-700 dark:text-red-300 bg-red-100 dark:bg-red-900 rounded-full">Disabled</span>'}
            </div>
            <a href="/configure/{guild_id}/ticket" class="block w-full py-2 bg-blue-500 hover:bg-blue-600 dark:bg-blue-600 dark:hover:bg-blue-700 text-white rounded-md text-center font-medium transition">
              Configure Tickets
            </a>
          </div>

          <div class="bg-white dark:bg-gray-800 rounded-2xl shadow dark:shadow-gray-700 p-6">
            <h3 class="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Partnership System</h3>
            <p class="text-gray-600 dark:text-gray-300 mb-4">Manage server partnerships and partner lists</p>
            <div class="flex items-center mb-4">
              {f'<span class="inline-flex items-center px-2 py-1 text-sm font-medium text-green-700 dark:text-green-300 bg-green-100 dark:bg-green-900 rounded-full">Enabled</span>' if has_partnership_system else f'<span class="inline-flex items-center px-2 py-1 text-sm font-medium text-red-700 dark:text-red-300 bg-red-100 dark:bg-red-900 rounded-full">Disabled</span>'}
            </div>
            <a href="/configure/{guild_id}/partnership" class="block w-full py-2 bg-purple-500 hover:bg-purple-600 dark:bg-purple-600 dark:hover:bg-purple-700 text-white rounded-md text-center font-medium transition">
              Configure Partnerships
            </a>
          </div>
        """

        return jsonify({"html": html_content})
    
    except Exception as e:
        return jsonify({"error": f"Failed to load feature status: {str(e)}"}), 500