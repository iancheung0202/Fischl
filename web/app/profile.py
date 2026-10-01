import requests
import traceback
import html

from concurrent.futures import ThreadPoolExecutor
from flask import Blueprint, request, session, redirect, abort, jsonify

from config.settings import CLIENT_ID, CLIENT_SECRET, API_BASE, BOT_TOKEN, PROFILE_REDIRECT_URI, PAYPAL_CLIENT_ID, ELITE_TRACK_PRICE
from utils.firebase import save_user_to_firebase
from utils.request import requests_session
from utils.minigames import check_events_enabled, get_current_season, get_current_track, activate_elite_subscription, is_elite_active, get_db_connection
from utils.theme import wrap_page
from utils.loading import create_loading_skeleton

profile = Blueprint('profile', __name__)


@profile.route("/profile")
def view_profile():
    """Profile page - lists the user's servers so they can open the Elite Track page for one"""
    # Handle OAuth callback
    code = request.args.get("code")
    if code:
        data = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": PROFILE_REDIRECT_URI,
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

        return redirect("/profile")

    # Check authentication for normal visits
    if "discord_token" not in session:
        return redirect("/auth")

    discord_token = session['discord_token']
    user = requests_session.get(f"{API_BASE}/users/@me", headers={"Authorization": f"Bearer {discord_token}"}).json()

    content = f"""
      <main class="p-6 max-w-5xl mx-auto">
        <div class="flex items-center gap-4 mb-8">
          <img src="https://cdn.discordapp.com/avatars/{user['id']}/{user.get('avatar','')}.png?size=128" 
               alt="Avatar" class="rounded-full w-20 h-20 shadow-md">
          <div>
            <h2 class="text-2xl font-bold text-gray-900 dark:text-white">{html.escape(user['username'])}</h2>
            <p class="text-gray-500 dark:text-gray-400">ID: {user['id']}</p>
          </div>
        </div>

        <h3 class="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Your Servers</h3>
        <div id="guilds-container" class="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {create_loading_skeleton(3, "bg-white dark:bg-gray-800 rounded-2xl shadow p-6 transition-colors", "guild")}
        </div>
      </main>

      <script>
        fetch('/api/profile/data')
          .then(response => response.json())
          .then(data => {{
            if (data.error) {{
              document.getElementById('guilds-container').innerHTML = 
                '<div class="col-span-full text-center py-12"><p class="text-red-500 dark:text-red-400">' + data.error + '</p></div>';
              return;
            }}
            document.getElementById('guilds-container').innerHTML = data.html;
          }})
          .catch(error => {{
            console.error('Error loading profile data:', error);
            document.getElementById('guilds-container').innerHTML = 
              '<div class="col-span-full text-center py-12"><p class="text-red-500 dark:text-red-400">Failed to load content. Please refresh the page.</p></div>';
          }});
      </script>
    """

    return wrap_page("Profile - Fischl", content, [])


@profile.route("/api/profile/data")
def api_profile_data():
    """API endpoint for the guild list"""
    if "discord_token" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    discord_token = session['discord_token']

    def fetch_user_guilds(token):
        return requests_session.get(f"{API_BASE}/users/@me/guilds", headers={"Authorization": f"Bearer {token}"}).json()

    def fetch_bot_guilds():
        all_guilds = []
        last_id = None
        while True:
            params = {"limit": 200}
            if last_id:
                params["after"] = last_id

            try:
                resp = requests_session.get(f"{API_BASE}/users/@me/guilds", headers={"Authorization": f"Bot {BOT_TOKEN}"}, params=params)
                if resp.status_code != 200:
                    break
                data = resp.json()
                if not data:
                    break
                all_guilds.extend(data)
                if len(data) < 200:
                    break
                last_id = data[-1]["id"]
            except Exception as e:
                print(f"Error fetching bot guilds: {e}")
                break
        return all_guilds

    with ThreadPoolExecutor(max_workers=2) as executor:
        guilds_future = executor.submit(fetch_user_guilds, discord_token)
        bot_guilds_future = executor.submit(fetch_bot_guilds)

        guilds = guilds_future.result()
        bot_guilds = bot_guilds_future.result()

    bot_guild_ids = {g["id"] for g in bot_guilds}

    candidates = [g for g in guilds if g["id"] in bot_guild_ids]
    with ThreadPoolExecutor(max_workers=8) as executor:
        enabled_flags = list(executor.map(lambda g: check_events_enabled(g["id"]), candidates))
    guilds_with_events = [g for g, ok in zip(candidates, enabled_flags) if ok]
    guilds_sorted = sorted(guilds_with_events, key=lambda g: g["name"].lower())

    guild_cards = ""
    for g in guilds_sorted:
        icon = f"https://cdn.discordapp.com/icons/{g['id']}/{g['icon']}.png?size=128" if g.get("icon") else ""

        guild_cards += f"""
        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow p-6 transition-colors">
          <div class="flex items-center gap-4 mb-4">
            {"<img src='"+icon+"' class='rounded-full w-16 h-16 shadow-md'>" if icon else "<div class='w-16 h-16 rounded-full bg-gray-200 dark:bg-gray-600 flex items-center justify-center text-gray-500 dark:text-gray-300 text-xl font-bold'>"+(html.escape(g.get('name', 'Unknown')[0]) if g.get('name') else 'U')+"</div>"}
            <div class="flex-1">
              <h3 class="text-lg font-semibold text-gray-900 dark:text-white">{html.escape(g.get('name', 'Unknown Server'))}</h3>
              <p class="text-gray-500 dark:text-gray-400 text-sm">Events Enabled</p>
            </div>
          </div>
          <a href="/profile/{g['id']}" class="block w-full py-2 bg-blue-500 dark:bg-blue-600 text-white rounded-md text-center font-medium hover:bg-blue-600 dark:hover:bg-blue-700 transition">
            View Track
          </a>
        </div>"""

    guild_content = guild_cards if guild_cards else "<p class='col-span-full text-center text-gray-500 dark:text-gray-400 py-8'>No servers found with minigames enabled.</p>"

    return jsonify({"html": guild_content})


@profile.route("/profile/<guild_id>")
def profile_guild(guild_id):
    """Guild page - Elite Track upsell + the track and the user's progress"""
    if "discord_token" not in session:
        return redirect("/auth")

    discord_token = session['discord_token']
    user_id = session['user_id']

    # Verify user has access to this guild
    guilds = requests_session.get(f"{API_BASE}/users/@me/guilds", headers={"Authorization": f"Bearer {discord_token}"}).json()
    guild = next((g for g in guilds if g['id'] == guild_id), None)
    if not guild:
        abort(404)

    # Verify events are enabled in this guild
    if not check_events_enabled(guild_id):
        content = """
        <main class="p-6 max-w-3xl mx-auto">
          <div class="bg-yellow-100 dark:bg-yellow-900 border border-yellow-400 dark:border-yellow-600 text-yellow-700 dark:text-yellow-200 px-4 py-3 rounded">
            <h3 class="font-bold">Minigames Not Enabled</h3>
            <p>This server doesn't have minigames enabled, so there is no track to display.</p>
          </div>
        </main>
        """

        return wrap_page(f"Profile - {html.escape(guild['name'])}", content, [("/profile", "Back to Profile", "text-blue-500 dark:text-blue-400 font-medium hover:underline")])

    icon = f"https://cdn.discordapp.com/icons/{guild['id']}/{guild['icon']}.png?size=128" if guild.get("icon") else ""

    content = f"""
      <style>
        /* PayPal form styling fixes */
        #paypal-button-container iframe {{
          min-height: 300px !important;
        }}
      </style>

      <main class="p-6 max-w-5xl mx-auto">
        <div class="flex items-center gap-4 mb-8">
          {"<img src='"+icon+"' class='rounded-full w-16 h-16 shadow-md'>" if icon else "<div class='w-16 h-16 rounded-full bg-gray-200 dark:bg-gray-600 flex items-center justify-center text-gray-500 dark:text-gray-300'>"+html.escape(guild['name'][0])+"</div>"}
          <div>
            <h2 class="text-2xl font-bold text-gray-900 dark:text-white">{html.escape(guild['name'])}</h2>
            <p class="text-gray-500 dark:text-gray-400">Guild ID: {guild['id']}</p>
          </div>
        </div>

        <div id="elite-track-container">
          <div class="animate-pulse border-2 border-gray-300 dark:border-gray-600 bg-gray-100 dark:bg-gray-700 rounded-2xl p-6 mb-8">
            <div class="bg-gray-200 dark:bg-gray-600 h-8 w-96 rounded mb-4 mx-auto"></div>
            <div class="bg-gray-200 dark:bg-gray-600 h-4 w-full rounded mb-2"></div>
            <div class="bg-gray-200 dark:bg-gray-600 h-4 w-3/4 rounded mb-4 mx-auto"></div>
            <div class="bg-gray-200 dark:bg-gray-600 h-12 w-64 rounded mx-auto"></div>
          </div>
        </div>

        <div id="track-loading" class="text-center py-8">
          <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <p class="mt-2 text-gray-600 dark:text-gray-400">Loading track...</p>
        </div>
        <div id="track-content" style="display: none;"></div>
      </main>

      <script>
        // Load track
        fetch('/profile/{guild_id}/track')
          .then(response => response.json())
          .then(data => {{
            document.getElementById('track-loading').style.display = 'none';
            document.getElementById('track-content').style.display = 'block';
            document.getElementById('track-content').innerHTML = data.content;
          }})
          .catch(error => {{
            console.error('Error loading track:', error);
            document.getElementById('track-loading').innerHTML = '<p class="text-red-500 dark:text-red-400">Error loading content</p>';
          }});

        // Load elite track upsell asynchronously
        fetch('/api/profile/{guild_id}/info')
          .then(response => response.json())
          .then(data => {{
            if (data.error) {{
              document.getElementById('elite-track-container').innerHTML = 
                '<span class="text-red-500 dark:text-red-400">' + data.error + '</span>';
              return;
            }}
            document.getElementById('elite-track-container').innerHTML = data.elite_track_html;
          }})
          .catch(error => {{
            console.error('Error loading guild info:', error);
            document.getElementById('elite-track-container').innerHTML = 
              '<span class="text-red-500 dark:text-red-400">Error loading info</span>';
          }});
      </script>

      <!-- PayPal Modal -->
      <style>
        .gradient-text {{
          background: linear-gradient(270deg, #FC774E, #E3346E, #FC774E);
          background-size: 200% 100%;
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
          animation: gradientMove 1.5s linear infinite;
        }}
        .gradient-bg {{
          background: linear-gradient(270deg, #fd9271, #f06292, #fd9271);
          background-size: 200% 100%;
          animation: gradientMove 1.5s linear infinite;
        }}
        @keyframes gradientMove {{
          0% {{
            background-position: 0% center;
          }}
          100% {{
            background-position: 200% center;
          }}
        }}
      </style>
      <div id="paypal-modal" class="hidden fixed inset-0 bg-black bg-opacity-85 z-50 flex justify-center items-center p-4">
        <div class="relative w-full max-w-md max-h-full bg-white rounded-xl shadow-2xl text-center overflow-hidden text-gray-900 flex flex-col">
          <div class="p-6 pb-4">
            <button id="modalCloseBtn" class="absolute top-3 right-4 bg-transparent border-none text-2xl font-bold cursor-pointer text-gray-600 hover:text-gray-900" aria-label="Close modal">&times;</button>
            <h3 class="text-2xl font-bold mb-4 text-gray-900">Complete Your Purchase</h3>
            <p class="text-xl mb-4 gradient-text font-bold">Activate Elite Track in <b>{html.escape(guild['name'])}</b> for just <b>${ELITE_TRACK_PRICE}</b>!</p>
          </div>
          <div class="flex-1 overflow-y-auto px-6">
            <div id="paypal-button-container" class="min-h-0"></div>
          </div>
          <div class="p-6 pt-4">
            <div class="text-xs text-gray-600">
              <p class="mt-2 text-yellow-600">One season lasts for 3 months. Thanks for supporting the bot!</p>
            </div>
          </div>
        </div>
      </div>

      <script src="https://www.paypal.com/sdk/js?client-id={PAYPAL_CLIENT_ID}&intent=capture&enable-funding=venmo&currency=USD"></script>

      <script>
        // Modal and PayPal button logic
        const modal = document.getElementById('paypal-modal');
        const paypalContainer = document.getElementById('paypal-button-container');
        const closeBtn = document.getElementById('modalCloseBtn');

        function disableBodyScroll() {{
          document.body.style.overflow = 'hidden';
        }}

        function enableBodyScroll() {{
          document.body.style.overflow = '';
        }}

        function clearPaypalButtons() {{
          paypalContainer.innerHTML = '';
        }}

        function renderPaypalButton() {{
          // Clear before render
          clearPaypalButtons();
          
          // Check if PayPal SDK is loaded
          if (typeof paypal === 'undefined') {{
            paypalContainer.innerHTML = '<div class="text-red-400 text-center p-4">PayPal SDK failed to load. Please refresh the page.</div>';
            return;
          }}
          
          console.log('PayPal SDK loaded, rendering button...');
          
          paypal.Buttons({{
            createOrder: function(data, actions) {{
              console.log('Creating PayPal order...');
              console.log('User ID: "{user_id}", Guild ID: "{guild_id}"');
              return actions.order.create({{
                purchase_units: [{{
                  amount: {{
                    value: '{ELITE_TRACK_PRICE}',
                    currency_code: 'USD'
                  }},
                  description: 'Fischl Discord Bot Elite Track (1 season)',
                  custom_id: '{user_id}-{guild_id}'
                }}],
                application_context: {{
                  shipping_preference: 'NO_SHIPPING'  // Disable shipping address collection
                }}
              }}).then(function(orderID) {{
                console.log('Order created successfully:', orderID);
                return orderID;
              }}).catch(function(error) {{
                console.error('Error creating order:', error);
                alert('Failed to create payment order. Please try again. Error: ' + (error.message || error));
                throw error;
              }});
            }},
            onApprove: function(data, actions) {{
              console.log('Payment approved:', data);
              return actions.order.capture().then(function(details) {{
                console.log('Payment captured:', details);
                
                // Show loading state
                paypalContainer.innerHTML = '<div class="text-white text-center p-4">Processing payment...</div>';
                
                // Activate subscription immediately
                return fetch('/payment/activate', {{
                  method: 'POST',
                  headers: {{
                    'Content-Type': 'application/json',
                  }},
                  body: JSON.stringify({{
                    user_id: "{user_id}",  // Ensure string to avoid precision loss
                    guild_id: "{guild_id}",
                    order_id: data.orderID,
                    payment_details: details
                  }})
                }}).then(response => {{
                  console.log('Activation response status:', response.status);
                  if (response.ok) {{
                    window.location.href = '/payment/success?guild_id={guild_id}';
                  }} else {{
                    return response.json().then(errorData => {{
                      console.error('Activation error:', errorData);
                      alert('Payment processed but there was an error activating your subscription. Please contact support with order ID: ' + data.orderID);
                    }});
                  }}
                }}).catch(error => {{
                  console.error('Network error:', error);
                  alert('Payment processed but there was a network error. Please contact support with order ID: ' + data.orderID);
                }});
              }}).catch(function(error) {{
                console.error('Error capturing payment:', error);
                alert('Payment capture failed. Please try again.');
              }});
            }},
            onCancel: function(data) {{
              console.log('Payment cancelled:', data);
              closePaypalModal();
            }},
            onError: function(err) {{
              console.error('PayPal button error:', err);
              alert('Payment system error. Please refresh the page and try again.');
            }},
            style: {{
              layout: 'vertical',
              color: 'blue',
              shape: 'rect',
              label: 'paypal',
              height: 40
            }}
          }}).render('#paypal-button-container').catch(function(error) {{
            console.error('Failed to render PayPal button:', error);
            paypalContainer.innerHTML = '<div class="text-red-400 text-center p-4">Failed to load payment options. Please refresh the page.</div>';
          }});
        }}

        function openModal() {{
          console.log('Opening PayPal modal...');
          modal.classList.remove('hidden');
          disableBodyScroll();
          
          paypalContainer.innerHTML = '<div class="text-white text-center p-4">Loading payment options...</div>';
          
          // Small delay to ensure modal is visible before rendering button
          setTimeout(function() {{
            renderPaypalButton();
          }}, 100);
        }}

        function closePaypalModal() {{
          console.log('Closing PayPal modal...');
          modal.classList.add('hidden');
          enableBodyScroll();
          clearPaypalButtons();
        }}

        closeBtn.addEventListener('click', closePaypalModal);

        // Open modal on clicking unlock buttons (set up after elite track loads)
        document.addEventListener('click', function(e) {{
          if (e.target.classList.contains('btn-unlock')) {{
            console.log('Unlock button clicked');
            openModal();
          }}
        }});

        // Close modal if clicking outside modal-content
        modal.addEventListener('click', (e) => {{
          if (e.target === modal) {{
            closePaypalModal();
          }}
        }});
      </script>
    """

    return wrap_page(f"Profile - {html.escape(guild['name'])}", content, [("/profile", "Back to Profile", "text-blue-500 dark:text-blue-400 font-medium hover:underline")])


@profile.route("/api/profile/<guild_id>/info")
def api_profile_guild_info(guild_id):
    """API endpoint returning the Elite Track upsell banner (empty if already elite)"""
    if "discord_token" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    user_id = session['user_id']

    try:
        is_elite = is_elite_active(user_id, guild_id)

        if not is_elite:
            elite_track_html = f'''<div class="border-2 border-indigo-500 bg-indigo-200 dark:bg-indigo-900 rounded-2xl p-6 mb-8 text-black dark:text-white shadow-lg">
              <h2 class="text-2xl font-bold mb-2 text-center">Less than USD $1/month. More than worth it</h2>
              <p class="text-center text-indigo-900 dark:text-indigo-100 italic mb-4">"Cheaper than a single Genshin wish, plus you always get value."</p>
              <p class="text-lg font-semibold mb-3">Get <strong>Elite Track</strong> to unlock premium rewards to each track tier while supporting development work!</p>
              <ul class="space-y-2 mb-4 list-disc list-inside text-indigo-900 dark:text-indigo-100">
                <li>Animated backgrounds, frames, and badge titles</li>
                <li>Boosted Mora gains, gifting perks, and chest upgrades</li>
                <li>+1 extra Prestige at the final tier</li>
              </ul>
              <p class="text-indigo-900 dark:text-indigo-100 italic mb-4">One purchase only unlocks elite track rewards in one specific server.</p>
              <div class="flex justify-center mb-4">
                <button class="btn-unlock text-white font-bold py-3 px-8 rounded-lg hover:bg-indigo-50 transition gradient-bg">
                  Unlock Elite Track – USD ${ELITE_TRACK_PRICE} (3 months)
                </button>
              </div>
              <p class="text-sm text-indigo-900 dark:text-indigo-100 text-center italic">Note: One season lasts for 3 months. Thanks for supporting the bot!</p>
            </div>'''
        else:
            elite_track_html = ""

        return jsonify({"elite_track_html": elite_track_html})

    except Exception as e:
        print(f"Error loading guild info: {e}")
        return jsonify({"error": "Failed to load guild information"}), 500


@profile.route("/profile/<guild_id>/track")
def profile_track(guild_id):
    """Get track content: season header, user's progress, and the tier table"""
    if "discord_token" not in session:
        return {"error": "Not authenticated"}, 401

    user_id = session['user_id']

    # Get user XP using PostgreSQL
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT xp FROM minigame_progression WHERE gid = %s AND uid = %s",
            (guild_id, user_id)
        )
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        user_xp = result[0] if result else 0
    except Exception as e:
        print(f"Error fetching progression: {e}")
        user_xp = 0

    TRACK_DATA = get_current_track()

    # Calculate current tier
    current_tier = 0
    for tier in TRACK_DATA:
        if user_xp >= tier["cumulative_xp"]:
            current_tier = tier["tier"]
        else:
            break

    # Calculate XP in current tier
    prev_xp = TRACK_DATA[current_tier - 1]["cumulative_xp"] if current_tier > 0 else 0
    xp_in_current_tier = user_xp - prev_xp

    # Determine XP required for the next tier
    if current_tier < len(TRACK_DATA):
        next_tier_xp = TRACK_DATA[current_tier]["xp_req"]
        progress_percentage = (xp_in_current_tier / next_tier_xp) * 100 if next_tier_xp > 0 else 100
    else:
        next_tier_xp = 0
        progress_percentage = 100

    # Build track table
    track_html = ""
    max_tier_to_show = max(len(TRACK_DATA), current_tier + 2)  # Change to min if you want to show fewer tiers
    visible_tiers = TRACK_DATA[:max_tier_to_show + 1]  # inclusive

    for tier in visible_tiers:
        if tier["tier"] <= current_tier:
            status = "✅"
            row_class = "bg-green-100 dark:bg-green-900/20"
        elif tier["tier"] == current_tier + 1:
            status = "🔄"
            row_class = "bg-blue-100 dark:bg-blue-900/20"
        else:
            status = "🔐"
            row_class = "bg-gray-50 dark:bg-gray-700/20"

        # Display reward text with truncation (22 chars)
        free_reward = tier["free"].split("|")[0].strip()[:22]
        elite_reward = tier["elite"].split("|")[0].strip()[:22]

        track_html += f"""
        <tr class="{row_class}">
          <td class="px-4 py-2 font-semibold text-gray-900 dark:text-white">{tier['tier']}</td>
          <td class="px-4 py-2 text-center">{status}</td>
          <td class="px-4 py-2 text-gray-800 dark:text-gray-200">{free_reward}</td>
          <td class="px-4 py-2 text-gray-800 dark:text-gray-200">{elite_reward}</td>
        </tr>
        """

    # Show how many more tiers exist after the shown ones
    if max_tier_to_show < len(TRACK_DATA) - 1:
        hidden_remaining = len(TRACK_DATA) - (max_tier_to_show + 1)
        track_html += f"""
        <tr>
          <td colspan="4" class="px-4 py-2 text-center text-gray-500 dark:text-gray-400 italic">
            ... ({hidden_remaining} more tiers)
          </td>
        </tr>
        """

    season = get_current_season()
    is_elite = is_elite_active(user_id, guild_id)

    content = f"""
    <div class="space-y-6">
      <div class="bg-gradient-to-r from-purple-500 to-pink-500 rounded-lg p-6 text-white">
        <h3 class="text-2xl font-bold mb-2">Season {season['id']}: {season['name']}</h3>
        <div class="grid grid-cols-2 gap-4 mt-4">
          <div>
            <p class="text-sm opacity-90">Current Tier</p>
            <p class="text-2xl font-bold">{current_tier}</p>
          </div>
          <div>
            <p class="text-sm opacity-90">Total XP</p>
            <p class="text-2xl font-bold">{user_xp}</p>
          </div>
        </div>
        {"<div class='mt-4'><div class='bg-white bg-opacity-20 rounded-full h-3'><div class='bg-white h-3 rounded-full' style='width: " + str(progress_percentage) + "%'></div></div><p class='text-sm mt-1'>" + str(xp_in_current_tier) + " / " + str(next_tier_xp) + " XP to next tier</p></div>" if current_tier < len(TRACK_DATA) else ""}
      </div>
      
      <div class="bg-white dark:bg-gray-800 rounded-lg p-6 border border-gray-200 dark:border-gray-700 transition-colors">
        <h3 class="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Track Progress</h3>
        <div class="overflow-x-auto">
          <table class="w-full border-collapse">
            <thead>
              <tr class="bg-gray-100 dark:bg-gray-700">
                <th class="px-4 py-2 text-left text-gray-900 dark:text-white">Tier</th>
                <th class="px-4 py-2 text-center text-gray-900 dark:text-white">Status</th>
                <th class="px-4 py-2 text-left text-gray-900 dark:text-white">Free Track</th>
                <th class="px-4 py-2 text-left text-gray-900 dark:text-white">Elite Track {'✅' if is_elite else '❌'}</th>
              </tr>
            </thead>
            <tbody>
              {track_html}
            </tbody>
          </table>
        </div>
      </div>
    </div>
    """

    return {"content": content}


# PayPal Payment Routes

@profile.route("/payment/success")
def payment_success():
    """Payment success page"""
    if "discord_token" not in session or "user_id" not in session:
        return redirect("/login")

    # Get guild_id from query params
    guild_id = request.args.get('guild_id')
    if not guild_id:
        return "Invalid request - missing guild_id", 400

    return f'''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Payment Successful - Fischl Dashboard</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script>
            tailwind.config = {{
                theme: {{
                    extend: {{
                        colors: {{
                            primary: '#6366f1',
                            secondary: '#ec4899'
                        }}
                    }}
                }}
            }}
        </script>
    </head>
    <body class="bg-gradient-to-br from-indigo-900 via-purple-900 to-pink-900 min-h-screen flex items-center justify-center">
        <div class="bg-white/10 backdrop-blur-lg rounded-xl shadow-2xl p-8 max-w-md w-full mx-4 text-center">
            <div class="text-6xl mb-4">🎉</div>
            <h1 class="text-3xl font-bold text-white mb-4">Elite Track Activated!</h1>
            <p class="text-indigo-100 mb-6">Thank you for your purchase! Your Elite Track has been activated and you should receive a Discord notification shortly.</p>
            <p class="text-sm text-indigo-200 mb-6">Elite rewards from previous tiers will be automatically granted in the next 30 seconds.</p>
            <div class="space-y-3">
                <a href="/profile/{guild_id}" class="block w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 px-6 rounded-lg transition">
                    Back to Track
                </a>
                <p style="color: #a1a1aa;">You will be redirected automatically in <span id="redirect-timer">30</span> seconds...</p>
            </div>
        </div>
        <script>
            // Auto redirect after 30 seconds
            setTimeout(function() {{
                window.location.href = '/profile/{guild_id}';
            }}, 30000);
            // Countdown timer
            let countdown = 30;
            const timerElement = document.getElementById('redirect-timer');
            setInterval(function() {{
                if (countdown > 0) {{
                    countdown--;
                    timerElement.textContent = countdown;
                }}
            }}, 1000);
        </script>
    </body>
    </html>
    '''


@profile.route("/payment/activate", methods=["POST"])
def activate_payment():
    """Activate elite subscription after successful PayPal payment"""
    if "discord_token" not in session or "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    try:
        data = request.get_json()
        user_id = str(data.get('user_id'))  # Ensure string type to avoid precision issues
        guild_id = str(data.get('guild_id'))
        order_id = data.get('order_id')
        session_user_id = str(session["user_id"])  # Ensure string type

        print(f"Payment activation request: user_id={user_id}, guild_id={guild_id}, order_id={order_id}")
        print(f"Session user_id: {session_user_id}")
        print(f"User ID comparison: request='{user_id}' vs session='{session_user_id}'")

        # Verify the user_id matches the session
        if user_id != session_user_id:
            print(f"User ID mismatch: request_id={user_id} != session_id={session_user_id}")
            print(f"Request ID length: {len(user_id)}, Session ID length: {len(session_user_id)}")
            return jsonify({"error": "User ID mismatch", "details": f"Request: {user_id}, Session: {session_user_id}"}), 403

        # Convert to integers for the activation function
        user_id_int = int(user_id)
        guild_id_int = int(guild_id)

        # Activate elite subscription
        print(f"Activating elite subscription for user {user_id_int} in guild {guild_id_int}")
        success, message = activate_elite_subscription(user_id_int, guild_id_int, order_id)

        if success:
            print(f"Elite subscription activated successfully for user {user_id_int} in guild {guild_id_int}, order: {order_id}")
            return jsonify({"success": True, "message": message})
        else:
            print(f"Failed to activate elite subscription: {message}")
            return jsonify({"error": message}), 500

    except Exception as e:
        print(f"Error in payment activation: {e}")
        traceback.print_exc()
        return jsonify({"error": "Internal server error"}), 500


@profile.route("/payment/manual-activate", methods=["POST"])
def manual_activate_payment():
    """Manual activation for support purposes - requires special token"""
    try:
        data = request.get_json()
        support_token = data.get('support_token')
        user_id = str(data.get('user_id'))
        guild_id = str(data.get('guild_id'))
        order_id = data.get('order_id')

        # Simple security check - in production, use a proper secret
        if support_token != "support_manual_activation_2024":
            return jsonify({"error": "Invalid support token"}), 403

        print(f"Manual activation request: user_id={user_id}, guild_id={guild_id}, order_id={order_id}")

        # Convert to integers for the activation function
        user_id_int = int(user_id)
        guild_id_int = int(guild_id)

        # Activate elite subscription
        success, message = activate_elite_subscription(user_id_int, guild_id_int, order_id)

        if success:
            print(f"Manual elite subscription activated for user {user_id_int} in guild {guild_id_int}, order: {order_id}")
            return jsonify({"success": True, "message": f"Manually activated subscription for order {order_id}"})
        else:
            print(f"Manual activation failed: {message}")
            return jsonify({"error": message}), 500

    except Exception as e:
        print(f"Error in manual payment activation: {e}")
        traceback.print_exc()
        return jsonify({"error": "Internal server error"}), 500


@profile.route("/payment/webhook", methods=["POST"])
def paypal_webhook():
    """Handle PayPal IPN (Instant Payment Notification) webhook"""
    try:
        # Parse form data
        form_data = request.form.to_dict()

        # Verify payment status
        payment_status = form_data.get('payment_status', '').lower()

        # Only process completed payments
        if payment_status != 'completed':
            print(f"Payment not completed: {payment_status}")
            return "OK", 200

        custom_data = form_data.get('custom', '')  # This should contain user_id-guild_id
        txn_id = form_data.get('txn_id', '')  # PayPal transaction ID

        print(f"PayPal webhook received: {form_data}")

        # Parse custom data (should be in format: user_id-guild_id)
        if not custom_data:
            print("No custom data found in PayPal webhook")
            return "OK", 200

        try:
            user_id, guild_id = custom_data.split('-', 1)
            user_id = int(user_id)
            guild_id = int(guild_id)
        except (ValueError, IndexError):
            print(f"Invalid custom data format: {custom_data}")
            return "OK", 200

        # Activate elite subscription with transaction ID
        success, message = activate_elite_subscription(user_id, guild_id, txn_id)

        if success:
            print(f"Elite subscription activated for user {user_id} in guild {guild_id}")
        else:
            print(f"Failed to activate elite subscription: {message}")

        return "OK", 200

    except Exception as e:
        print(f"Error processing PayPal webhook: {e}")
        return "Error", 500