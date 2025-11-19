from firebase_admin import db
from concurrent.futures import ThreadPoolExecutor
from flask import Blueprint, request, session, redirect, jsonify
import time
import html

from config.settings import API_BASE, BOT_TOKEN, MORA_EMOTE
from utils.request import requests_session, verify_guild_access
from utils.theme import wrap_page
from utils.loading import create_loading_skeleton, create_async_script, create_loading_container, create_empty_content

def process_pending_shop_edits(guild_id):
    """Process any pending scheduled shop edits"""
    try:
        current_time = time.time()
        ref = db.reference(f"/Pending Shop Edits/{guild_id}")
        pending_edits = ref.get() or {}
        
        processed_count = 0
        for key, edit in list(pending_edits.items()):
            scheduled_time = edit.get('scheduled_time', 0)
            
            # Skip if not yet time
            if scheduled_time > current_time:
                continue
                
            print(f"Processing edit for item {edit['item_identifier']} in guild {guild_id}")
                
            # Get current rewards
            guild_ref = db.reference("/Global Events Rewards")
            guild_rewards = guild_ref.get() or {}
            rewards_list = None
            guild_key = None
            
            for gkey, gval in guild_rewards.items():
                if isinstance(gval, dict) and gval.get("Server ID") == int(guild_id):
                    rewards_list = gval.get("Rewards", [])
                    guild_key = gkey
                    break
            
            if not rewards_list:
                print(f"No rewards found for guild {guild_id}")
                ref.child(key).delete()
                continue
                
            # Convert old format to new format if needed
            for i, reward in enumerate(rewards_list):
                if len(reward) < 5:
                    rewards_list[i] = reward + [-1]
                
            # Find the item and process stock change
            item_found = False
            for i, item in enumerate(rewards_list):
                if item[0] == edit['item_identifier']:
                    current_stock = item[4]
                    stock_change = edit['stock_change']
                    
                    # Handle relative changes
                    if stock_change.startswith(('+', '-')):
                        # Convert unlimited stock to 0 for relative operations
                        if current_stock == -1:
                            current_stock = 0
                        
                        # Parse the relative change
                        try:
                            change = int(stock_change)
                            new_stock = current_stock + change
                        except ValueError:
                            # Handle cases like "+10" without space
                            sign = stock_change[0]
                            num_str = stock_change[1:].strip()
                            if not num_str:
                                num = 0
                            else:
                                num = int(num_str)
                            new_stock = current_stock + num if sign == '+' else current_stock - num
                    else:
                        # Absolute value
                        try:
                            new_stock = int(stock_change)
                            # Handle unlimited stock case
                            if new_stock == -1:
                                new_stock = -1
                        except ValueError:
                            # Invalid value, skip
                            print(f"Invalid stock value: {stock_change}")
                            continue
                    
                    # Clamp to valid range (but preserve -1 for unlimited)
                    if new_stock < -1:
                        new_stock = 0
                    
                    # Update stock
                    rewards_list[i][4] = new_stock
                    item_found = True
                    print(f"Updated stock for {item[0]} from {current_stock} to {new_stock}")
                    break
            
            if item_found:
                # Update Firebase
                guild_ref.child(guild_key).update({"Rewards": rewards_list})
                processed_count += 1
            else:
                print(f"Item {edit['item_identifier']} not found in guild {guild_id}")
            
            # Remove processed edit
            ref.child(key).delete()
        
        print(f"Processed {processed_count} pending edits for guild {guild_id}")
        return processed_count
    except Exception as e:
        print(f"Error processing pending shop edits: {e}")
        return 0

minigames = Blueprint('minigames', __name__)

# Minigame titles from the Discord bot
minigame_titles = [
    "Boss Battle Blitz",
    "Quicktype Racer", 
    "Egg Walk",
    "Match The Profile Picture",
    "Split or Steal",
    "Reverse Number Quicktype",
    "Pick Up Ice Cream",
    "Snatch The Watermelon",
    "Guess The Mystery Number",
    "Memory Game",
    "Who Said That",
    "Unscramble Words",
    "Two Truths, One Lie",
    "Currency Counting",
    "Rock Paper Scissors Duel",
    "Roll A Dice",
    "Teyvat Voiceline Quiz",
    "Teyvat Emoji Riddles",
    "Galaxy Emoji Riddles",
    "Double or Keep",
    "Know Your Members",
    "Hangman",
    "Mora Auction House",
    "Mora Heist"
]

letter_emojis = [
    "🇦", "🇧", "🇨", "🇩", "🇪", "🇫", "🇬", "🇭", "🇮", "🇯", "🇰", "🇱", 
    "🇲", "🇳", "🇴", "🇵", "🇶", "🇷", "🇸", "🇹", "🇺", "🇻", "🇼", "🇽"
]

letterList = [
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L",
    "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X"
]

frequency_choices = [
    {"name": "Very Frequent (~10%)", "value": "10"},
    {"name": "Frequent (~5%)", "value": "20"},
    {"name": "Occasional (~3%)", "value": "30"},
    {"name": "Uncommon (~2%)", "value": "50"},
    {"name": "Rare (~1%)", "value": "100"},
    {"name": "Very Rare (~0.5%)", "value": "200"},
]

@minigames.route("/configure/<guild_id>/minigames")
def configure_minigames(guild_id):
    if "discord_token" not in session:
        return redirect("/")

    # Get message parameter for success/error messages
    message = request.args.get('message', '')
    
    # Page content with loading - verification will happen in async API call
    content = f"""
      <main class="p-6 max-w-6xl mx-auto">
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

        {f'<div class="bg-green-100 dark:bg-green-900 border border-green-400 dark:border-green-600 text-green-700 dark:text-green-300 px-4 py-3 rounded mb-4">{message.replace("+", " ")}</div>' if message else ''}

        <!-- Tab Navigation -->
        <div class="mb-6">
          <nav class="flex space-x-1 bg-gray-100 dark:bg-gray-700 rounded-lg p-1">
            <button id="tab-channels" class="flex-1 py-2 px-4 text-sm font-medium rounded-md bg-white dark:bg-gray-800 text-blue-600 dark:text-blue-400 shadow-sm" onclick="switchTab('channels')">
              Configured Channels
            </button>
            <button id="tab-add" class="flex-1 py-2 px-4 text-sm font-medium rounded-md text-gray-500 dark:text-gray-300 hover:text-gray-700 dark:hover:text-gray-100" onclick="switchTab('add')">
              Add New Channel
            </button>
          </nav>
        </div>

        <!-- Configured Channels Tab -->
        <div id="channels-tab" class="tab-content">
          <div class="bg-white dark:bg-gray-800 rounded-2xl shadow dark:shadow-gray-700 p-6 mb-6">
            <h3 class="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Configured Channels</h3>
            <p class="text-gray-600 dark:text-gray-300 mb-4">Manage minigames for channels that already have the system enabled.</p>
            
            <div id="channels-container" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {create_loading_skeleton(3, "bg-gray-50 dark:bg-gray-700 rounded-xl p-4 mb-4", "guild")}
            </div>
          </div>
        </div>

        <!-- Add New Channel Tab -->
        <div id="add-tab" class="tab-content hidden">
          <div class="bg-white dark:bg-gray-800 rounded-2xl shadow dark:shadow-gray-700 p-6">
            <h3 class="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Enable Minigames in New Channel</h3>
            <p class="text-gray-600 dark:text-gray-300 mb-6">Choose a channel and frequency to enable the minigame system.</p>
            
            <div id="add-form-container">
              {create_loading_container("Loading available channels...", "flex flex-col items-center justify-center py-12")}
            </div>
          </div>
        </div>

        <!-- Shop Management Section -->
        <div class="mt-12">
          <h2 class="text-3xl font-bold text-gray-900 dark:text-white mb-6">Shop Management</h2>
          
          <!-- Shop Tab Navigation -->
          <div class="mb-6">
            <nav class="flex space-x-1 bg-gray-100 dark:bg-gray-700 rounded-lg p-1">
              <button id="tab-shop-items" class="flex-1 py-2 px-4 text-sm font-medium rounded-md bg-white dark:bg-gray-800 text-blue-600 dark:text-blue-400 shadow-sm" onclick="switchShopTab('items')">
                Shop Items
              </button>
              <button id="tab-shop-add" class="flex-1 py-2 px-4 text-sm font-medium rounded-md text-gray-500 dark:text-gray-300 hover:text-gray-700 dark:hover:text-gray-100" onclick="switchShopTab('add')">
                Add New Item
              </button>
              <button id="tab-shop-history" class="flex-1 py-2 px-4 text-sm font-medium rounded-md text-gray-500 dark:text-gray-300 hover:text-gray-700 dark:hover:text-gray-100" onclick="switchShopTab('history')">
                Purchase History
              </button>
            </nav>
          </div>

          <!-- Shop Items Tab -->
          <div id="shop-items-tab" class="tab-content">
            <div class="bg-white dark:bg-gray-800 rounded-2xl shadow dark:shadow-gray-700 p-6 mb-6">
              <h3 class="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Current Shop Items</h3>
              <p class="text-gray-600 dark:text-gray-300 mb-4">Manage existing items in your server's shop.</p>
              
              <div id="shop-items-container">
                {create_loading_skeleton(3, "bg-gray-50 dark:bg-gray-700 rounded-xl p-4 mb-4", "shop")}
              </div>
            </div>
          </div>

          <!-- Add Shop Item Tab -->
          <div id="shop-add-tab" class="tab-content hidden">
            <div class="bg-white dark:bg-gray-800 rounded-2xl shadow dark:shadow-gray-700 p-6">
              <h3 class="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Add New Shop Item</h3>
              <p class="text-gray-600 dark:text-gray-300 mb-6">Create a new item for your server's shop.</p>
              
              <div id="shop-add-form-container">
                {create_loading_container("Loading form...", "flex flex-col items-center justify-center py-12")}
              </div>
            </div>
          </div>

          <!-- Purchase History Tab -->
          <div id="shop-history-tab" class="tab-content hidden">
            <div class="bg-white dark:bg-gray-800 rounded-2xl shadow dark:shadow-gray-700 p-6">
              <h3 class="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Purchase History</h3>
              <p class="text-gray-600 dark:text-gray-300 mb-6">View all recent purchases made in your server's shop.</p>
              
              <div id="purchase-history-container" class="max-h-96 overflow-y-auto">
                {create_loading_container("Loading purchase history...", "flex flex-col items-center justify-center py-12")}
              </div>
              
              <!-- Load More Button -->
              <div id="load-more-container" class="hidden text-center mt-4">
                <button id="load-more-history" onclick="loadMoreHistory()" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
                  Load More
                </button>
              </div>
              <div class="text-center mt-2" id="purchase-history-subtext">
                <p class="text-gray-500 dark:text-gray-400 italic text-sm">Only purchases made after October 6, 2025 are logged.</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Milestones Management Section -->
        <div class="mt-12">
          <h2 class="text-3xl font-bold text-gray-900 dark:text-white mb-6">Milestones Management</h2>
          
          <!-- Milestones Tab Navigation -->
          <div class="mb-6">
            <nav class="flex space-x-1 bg-gray-100 dark:bg-gray-700 rounded-lg p-1">
              <button id="tab-milestones-items" class="flex-1 py-2 px-4 text-sm font-medium rounded-md bg-white dark:bg-gray-800 text-blue-600 dark:text-blue-400 shadow-sm" onclick="switchMilestonesTab('items')">
                Milestones
              </button>
              <button id="tab-milestones-add" class="flex-1 py-2 px-4 text-sm font-medium rounded-md text-gray-500 dark:text-gray-300 hover:text-gray-700 dark:hover:text-gray-100" onclick="switchMilestonesTab('add')">
                Add New Milestone
              </button>
            </nav>
          </div>

          <!-- Milestones Items Tab -->
          <div id="milestones-items-tab" class="tab-content">
            <div class="bg-white dark:bg-gray-800 rounded-2xl shadow dark:shadow-gray-700 p-6 mb-6">
              <h3 class="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Current Milestones</h3>
              <p class="text-gray-600 dark:text-gray-300 mb-4">Manage existing milestones for your server.</p>
              
              <div id="milestones-items-container">
                {create_loading_skeleton(3, "bg-gray-50 dark:bg-gray-700 rounded-xl p-4 mb-4", "milestones")}
              </div>
            </div>
          </div>

          <!-- Add Milestone Tab -->
          <div id="milestones-add-tab" class="tab-content hidden">
            <div class="bg-white dark:bg-gray-800 rounded-2xl shadow dark:shadow-gray-700 p-6">
              <h3 class="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Add New Milestone</h3>
              <p class="text-gray-600 dark:text-gray-300 mb-6">Create a new milestone for your server.</p>
              
              <div id="milestones-add-form-container">
                {create_loading_container("Loading form...", "flex flex-col items-center justify-center py-12")}
              </div>
            </div>
          </div>
        </div>
      </main>

      <script>
        // Load all data sequentially to avoid Discord API rate limiting issues
        loadAllDataSequentially();
        
        // Tab switching functionality
        function switchTab(tab) {{
          // Update tab buttons
          document.getElementById('tab-channels').className = tab === 'channels' ? 
            'flex-1 py-2 px-4 text-sm font-medium rounded-md bg-white dark:bg-gray-800 text-blue-600 dark:text-blue-400 shadow-sm' :
            'flex-1 py-2 px-4 text-sm font-medium rounded-md text-gray-500 dark:text-gray-300 hover:text-gray-700 dark:hover:text-gray-100';
          
          document.getElementById('tab-add').className = tab === 'add' ? 
            'flex-1 py-2 px-4 text-sm font-medium rounded-md bg-white dark:bg-gray-800 text-blue-600 dark:text-blue-400 shadow-sm' :
            'flex-1 py-2 px-4 text-sm font-medium rounded-md text-gray-500 dark:text-gray-300 hover:text-gray-700 dark:hover:text-gray-100';
          
          // Update tab content
          document.getElementById('channels-tab').className = tab === 'channels' ? 'tab-content' : 'tab-content hidden';
          document.getElementById('add-tab').className = tab === 'add' ? 'tab-content' : 'tab-content hidden';
        }}

        // Delete channel confirmation
        function deleteChannel(channelId, channelName) {{
          if (confirm(`Are you sure you want to disable minigames for #${{channelName}}? This action cannot be undone.`)) {{
            fetch(`/configure/{guild_id}/minigames/delete/${{channelId}}`, {{method: 'POST'}})
              .then(response => response.json())
              .then(data => {{
                if (data.success) {{
                  window.location.href = `/configure/{guild_id}/minigames?message=${{encodeURIComponent(data.message || 'Channel configuration deleted successfully')}}`;
                }} else {{
                  window.location.href = `/configure/{guild_id}/minigames?message=${{encodeURIComponent(data.message || 'Failed to delete channel configuration')}}&type=error`;
                }}
              }})
              .catch(error => {{
                console.error('Error:', error);
                window.location.href = `/configure/{guild_id}/minigames?message=${{encodeURIComponent('An error occurred while deleting the configuration')}}&type=error`;
              }});
          }}
        }}

        // Shop tab switching functionality
        function switchShopTab(tab) {{
          // Update tab buttons
          document.getElementById('tab-shop-items').className = tab === 'items' ? 
            'flex-1 py-2 px-4 text-sm font-medium rounded-md bg-white dark:bg-gray-800 text-blue-600 dark:text-blue-400 shadow-sm' :
            'flex-1 py-2 px-4 text-sm font-medium rounded-md text-gray-500 dark:text-gray-300 hover:text-gray-700 dark:hover:text-gray-100';
          
          document.getElementById('tab-shop-add').className = tab === 'add' ? 
            'flex-1 py-2 px-4 text-sm font-medium rounded-md bg-white dark:bg-gray-800 text-blue-600 dark:text-blue-400 shadow-sm' :
            'flex-1 py-2 px-4 text-sm font-medium rounded-md text-gray-500 dark:text-gray-300 hover:text-gray-700 dark:hover:text-gray-100';
          
          document.getElementById('tab-shop-history').className = tab === 'history' ? 
            'flex-1 py-2 px-4 text-sm font-medium rounded-md bg-white dark:bg-gray-800 text-blue-600 dark:text-blue-400 shadow-sm' :
            'flex-1 py-2 px-4 text-sm font-medium rounded-md text-gray-500 dark:text-gray-300 hover:text-gray-700 dark:hover:text-gray-100';
          
          // Update tab content
          document.getElementById('shop-items-tab').className = tab === 'items' ? 'tab-content' : 'tab-content hidden';
          document.getElementById('shop-add-tab').className = tab === 'add' ? 'tab-content' : 'tab-content hidden';
          document.getElementById('shop-history-tab').className = tab === 'history' ? 'tab-content' : 'tab-content hidden';
          
          // Load purchase history when history tab is clicked
          if (tab === 'history') {{
            loadPurchaseHistory(1, true);
          }}
        }}

        // Milestones tab switching functionality
        function switchMilestonesTab(tab) {{
          // Update tab buttons
          document.getElementById('tab-milestones-items').className = tab === 'items' ? 
            'flex-1 py-2 px-4 text-sm font-medium rounded-md bg-white dark:bg-gray-800 text-blue-600 dark:text-blue-400 shadow-sm' :
            'flex-1 py-2 px-4 text-sm font-medium rounded-md text-gray-500 dark:text-gray-300 hover:text-gray-700 dark:hover:text-gray-100';
          
          document.getElementById('tab-milestones-add').className = tab === 'add' ? 
            'flex-1 py-2 px-4 text-sm font-medium rounded-md bg-white dark:bg-gray-800 text-blue-600 dark:text-blue-400 shadow-sm' :
            'flex-1 py-2 px-4 text-sm font-medium rounded-md text-gray-500 dark:text-gray-300 hover:text-gray-700 dark:hover:text-gray-100';
          
          // Update tab content
          document.getElementById('milestones-items-tab').className = tab === 'items' ? 'tab-content' : 'tab-content hidden';
          document.getElementById('milestones-add-tab').className = tab === 'add' ? 'tab-content' : 'tab-content hidden';
        }}

        // Global variables to store data
        let shopItemsData = [];
        let milestonesData = [];

        // Load all data sequentially to avoid Discord API rate limiting
        async function loadAllDataSequentially() {{
          console.log('Starting sequential data loading...');
          
          // First, load channel config (minigames info) and get Discord data
          let discordData = null;
          try {{
            console.log('Loading channel config...');
            discordData = await loadChannelConfig();
            console.log('Channel config loaded successfully');
          }} catch (error) {{
            console.error('Failed to load channel config:', error);
            document.querySelector('main').innerHTML = 
              '<div class="p-6 max-w-6xl mx-auto text-center"><h1 class="text-2xl font-bold text-red-600 dark:text-red-400 mb-4">Error</h1><p class="text-gray-600 dark:text-gray-300">Failed to load page. Please refresh.</p></div>';
            return;
          }}
          
          // Wait 500ms before loading shop config
          console.log('Waiting 500ms before loading shop config...');
          await new Promise(resolve => setTimeout(resolve, 500));
          
          // Load shop data with retry for cold start, passing Discord data
          let shopLoaded = false;
          try {{
            console.log('Loading shop config...');
            await loadShopDataWithRetry(discordData);
            shopLoaded = true;
            console.log('Shop config loaded successfully');
          }} catch (error) {{
            console.error('Failed to load shop config:', error);
          }}
          
          // Wait 500ms before loading milestones config
          console.log('Waiting 500ms before loading milestones config...');
          await new Promise(resolve => setTimeout(resolve, 500));
          
          // Load milestones data, passing Discord data
          let milestonesLoaded = false;
          try {{
            console.log('Loading milestones config...');
            await loadMilestonesData(discordData);
            milestonesLoaded = true;
            console.log('Milestones config loaded successfully');
          }} catch (error) {{
            console.error('Failed to load milestones config:', error);
          }}
          
          // Show summary
          if (shopLoaded && milestonesLoaded) {{
            console.log('All secondary data loaded successfully');
          }} else if (shopLoaded || milestonesLoaded) {{
            console.log('Partial secondary data loaded - page is still functional');
            document.querySelector('main').innerHTML += 
              '<div class="bg-yellow-100 dark:bg-yellow-900 border border-yellow-400 dark:border-yellow-600 text-yellow-700 dark:text-yellow-300 px-4 py-3 rounded mb-4">Some data could not be loaded, but you can still use the available features. Try refreshing later.</div>';
          }} else {{
            console.log('No secondary data loaded, but page remains functional');
            document.querySelector('main').innerHTML += 
              '<div class="bg-orange-100 dark:bg-orange-900 border border-orange-400 dark:border-orange-600 text-orange-700 dark:text-orange-300 px-4 py-3 rounded mb-4">Could not load existing data, but you can still add new items and milestones.</div>';
          }}
          
          console.log('Sequential loading completed');
          
          // Convert all timestamps to local time after page loads
          convertTimestampsToLocalTime();
        }}
        
        // Function to convert timestamps to local time
        function convertTimestampsToLocalTime() {{
          const timeElements = document.querySelectorAll('.local-time[data-timestamp]');
          timeElements.forEach(element => {{
            const timestamp = parseFloat(element.getAttribute('data-timestamp'));
            if (!isNaN(timestamp)) {{
              const localDate = new Date(timestamp * 1000);
              const formattedTime = localDate.toLocaleDateString('en-US', {{
                month: 'short',
                day: 'numeric', 
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
              }});
              element.textContent = formattedTime;
            }}
          }});
        }}
        
        // Load channel config (minigames info) and return Discord data for reuse
        function loadChannelConfig() {{
          return fetch('/api/configure/{guild_id}/minigames/info')
            .then(response => {{
              if (!response.ok) {{
                throw new Error(`HTTP error! status: ${{response.status}}`);
              }}
              return response.json();
            }})
            .then(data => {{
              if (data.error) {{
                throw new Error(data.error);
              }}
              
              // Update header
              document.getElementById('guild-header').innerHTML = data.header;
              
              // Update channels container
              document.getElementById('channels-container').innerHTML = data.channels;
              
              // Update add form
              document.getElementById('add-form-container').innerHTML = data.addForm;
              
              // Return Discord data for reuse in other endpoints
              return {{
                userGuilds: data.userGuilds,
                guildRoles: data.guildRoles,
                guildChannels: data.guildChannels
              }};
            }});
        }}

        // Shop data loading with retry for cold start issues
        async function loadShopDataWithRetry(discordData) {{
          const maxRetries = 2;
          
          for (let attempt = 1; attempt <= maxRetries; attempt++) {{
            try {{
              if (attempt > 1) {{
                console.log(`Retrying shop data load (attempt ${{attempt}})...`);
                // Wait longer on retry
                await new Promise(resolve => setTimeout(resolve, 2000));
              }}
              
              await loadShopData(discordData);
              return; // Success, exit retry loop
            }} catch (error) {{
              if (attempt === maxRetries) {{
                throw error; // Last attempt failed, re-throw
              }}
              console.warn(`Shop data load attempt ${{attempt}} failed:`, error.message);
            }}
          }}
        }}

        // Load shop data
        function loadShopData(discordData) {{
          // Use POST request to send Discord data in body instead of URL params
          const requestBody = discordData ? {{ discord_data: discordData }} : {{}};
          
          return fetch('/api/configure/{guild_id}/shop/info', {{
            method: 'POST',
            headers: {{
              'Accept': 'application/json',
              'Content-Type': 'application/json'
            }},
            body: JSON.stringify(requestBody)
          }})
            .then(response => {{
              if (!response.ok) {{
                throw new Error(`HTTP error! status: ${{response.status}}`);
              }}
              return response.json();
            }})
            .then(data => {{
              if (data.error) {{
                document.getElementById('shop-items-container').innerHTML = 
                  '<div class="text-center py-8"><p class="text-red-600 dark:text-red-400">' + data.error + '</p></div>';
                document.getElementById('shop-add-form-container').innerHTML = 
                  '<div class="text-center py-8"><p class="text-red-600 dark:text-red-400">' + data.error + '</p></div>';
                return;
              }}
              
              shopItemsData = data.itemsData || [];
              document.getElementById('shop-items-container').innerHTML = data.items;
              document.getElementById('shop-add-form-container').innerHTML = data.addForm;
            }})
            .catch(error => {{
              console.error('Error loading shop data:', error);
              // Show fallback UI
              document.getElementById('shop-items-container').innerHTML = 
                '<div class="text-center py-8"><p class="text-yellow-600 dark:text-yellow-400">Failed to load shop items. You can still add new items below.</p></div>';
              
              // Show basic add form as fallback
              document.getElementById('shop-add-form-container').innerHTML = `
                <form onsubmit="addShopItem(event)" class="space-y-4 bg-white dark:bg-gray-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700">
                  <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">Add Shop Item</h3>
                  <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Item Name</label>
                      <input type="text" name="name" required class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white">
                    </div>
                    <div>
                      <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Cost (Mora)</label>
                      <input type="number" name="cost" required min="1" class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white">
                    </div>
                  </div>
                  <div>
                    <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Description</label>
                    <textarea name="description" required rows="3" class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white"></textarea>
                  </div>
                  <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Stock (-1 for unlimited)</label>
                      <input type="number" name="stock" required value="-1" class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white">
                    </div>
                    <div class="flex items-end">
                      <label class="flex items-center">
                        <input type="checkbox" name="multiple" class="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500 dark:bg-gray-700">
                        <span class="ml-2 text-sm text-gray-700 dark:text-gray-300">Allow multiple purchases</span>
                      </label>
                    </div>
                  </div>
                  <button type="submit" class="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-md transition-colors">Add Item</button>
                </form>
              `;
              
              throw error;  // Re-throw to allow sequential loading to handle it
            }});
        }}

        // Load milestones data
        function loadMilestonesData(discordData) {{
          // Use POST request to send Discord data in body instead of URL params
          const requestBody = discordData ? {{ discord_data: discordData }} : {{}};
          
          return fetch('/api/configure/{guild_id}/milestones/info', {{
            method: 'POST',
            headers: {{
              'Accept': 'application/json',
              'Content-Type': 'application/json'
            }},
            body: JSON.stringify(requestBody)
          }})
            .then(response => {{
              if (!response.ok) {{
                throw new Error(`HTTP error! status: ${{response.status}}`);
              }}
              return response.json();
            }})
            .then(data => {{
              if (data.error) {{
                document.getElementById('milestones-items-container').innerHTML = 
                  '<div class="text-center py-8"><p class="text-red-600 dark:text-red-400">' + data.error + '</p></div>';
                document.getElementById('milestones-add-form-container').innerHTML = 
                  '<div class="text-center py-8"><p class="text-red-600 dark:text-red-400">' + data.error + '</p></div>';
                return;
              }}
              
              milestonesData = data.milestonesData || [];
              document.getElementById('milestones-items-container').innerHTML = data.items;
              document.getElementById('milestones-add-form-container').innerHTML = data.addForm;
            }})
            .catch(error => {{
              console.error('Error loading milestones data:', error);
              // Show fallback UI
              document.getElementById('milestones-items-container').innerHTML = 
                '<div class="text-center py-8"><p class="text-yellow-600 dark:text-yellow-400">Failed to load milestones. You can still add new milestones below.</p></div>';
              
              // Show basic add form as fallback
              document.getElementById('milestones-add-form-container').innerHTML = `
                <form onsubmit="addMilestone(event)" class="space-y-4 bg-white dark:bg-gray-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700">
                  <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">Add Milestone</h3>
                  <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Threshold (amount needed)</label>
                      <input type="number" name="threshold" required min="1" class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white">
                    </div>
                    <div>
                      <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Reward (Role ID or item name)</label>
                      <input type="text" name="reward" required class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white">
                    </div>
                  </div>
                  <div>
                    <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Description</label>
                    <textarea name="description" required rows="3" placeholder="Description of the milestone..." class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white"></textarea>
                  </div>
                  <button type="submit" class="w-full bg-green-600 hover:bg-green-700 text-white font-medium py-2 px-4 rounded-md transition-colors">Add Milestone</button>
                </form>
              `;
              
              throw error;  // Re-throw to allow sequential loading to handle it
            }});
        }}

        // Shop management functions
        function addShopItem(event) {{
          event.preventDefault();
          const formData = new FormData(event.target);
          const data = {{
            name: formData.get('name'),
            description: formData.get('description'), 
            cost: formData.get('cost'),
            stock: formData.get('stock'),
            multiple: formData.has('multiple')
          }};

          fetch('/api/configure/{guild_id}/shop/add', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify(data)
          }})
          .then(response => response.json())
          .then(data => {{
            if (data.success) {{
              window.location.href = `/configure/{guild_id}/minigames?message=${{encodeURIComponent(data.message || 'Shop item added successfully')}}`;
            }} else {{
              window.location.href = `/configure/{guild_id}/minigames?message=${{encodeURIComponent(data.message || 'Failed to add shop item')}}&type=error`;
            }}
          }})
          .catch(error => {{
            console.error('Error:', error);
            window.location.href = `/configure/{guild_id}/minigames?message=${{encodeURIComponent('An error occurred while adding the item')}}&type=error`;
          }});
        }}

        function deleteShopItem(name, displayName, compensate) {{
          const confirmMsg = compensate ? 
            `Are you sure you want to delete "${{displayName}}"? This will compensate all users who purchased this item.` :
            `Are you sure you want to delete "${{displayName}}"? This action cannot be undone.`;
            
          if (confirm(confirmMsg)) {{
            fetch('/api/configure/{guild_id}/shop/delete', {{
              method: 'POST',
              headers: {{ 'Content-Type': 'application/json' }},
              body: JSON.stringify({{ name: name, compensate: compensate }})
            }})
            .then(response => response.json())
            .then(data => {{
              if (data.success) {{
                window.location.href = `/configure/{guild_id}/minigames?message=${{encodeURIComponent(data.message || 'Shop item deleted successfully')}}`;
              }} else {{
                window.location.href = `/configure/{guild_id}/minigames?message=${{encodeURIComponent(data.message || 'Failed to delete shop item')}}&type=error`;
              }}
            }})
            .catch(error => {{
              console.error('Error:', error);
              window.location.href = `/configure/{guild_id}/minigames?message=${{encodeURIComponent('An error occurred while deleting the item')}}&type=error`;
            }});
          }}
        }}

        function editShopItem(index) {{
          const item = shopItemsData[index];
          if (!item) {{
            window.location.href = `/configure/{guild_id}/minigames?message=${{encodeURIComponent('Item not found')}}&type=error`;
            return;
          }}

          // Create modal HTML
          const modalHtml = `
            <div id="edit-shop-modal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
              <div class="bg-white dark:bg-gray-800 rounded-lg w-full max-w-md max-h-[90vh] flex flex-col">
                <div class="flex justify-between items-center p-6 pb-4 border-b border-gray-200 dark:border-gray-600">
                  <h3 class="text-lg font-semibold text-gray-900 dark:text-white">Edit Shop Item</h3>
                  <button onclick="closeEditModal()" class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                  </button>
                </div>
                
                <div class="flex-1 overflow-y-auto p-6">
                  <form onsubmit="saveShopItemEdit(event, '${{item.name}}')">
                    <div class="space-y-4">
                      <div>
                        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Role ID or Title</label>
                      <input type="text" name="name" value="${{item.name}}" required class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white">
                    </div>
                    
                    <div>
                      <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Description</label>
                      <textarea name="description" required rows="3" class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white">${{item.description}}</textarea>
                    </div>
                    
                    <div>
                      <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Cost (Mora)</label>
                      <input type="number" name="cost" value="${{item.cost}}" required min="1" class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white">
                    </div>
                    
                    <div>
                      <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Stock (Optional)</label>
                      <input type="text" name="stock" id="stock-input" value="${{item.stock === -1 ? '' : item.stock}}" class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white" placeholder="Leave empty for unlimited">
                      <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">For immediate edits: enter an absolute number (0, 10, etc.). For scheduled edits: use +/- for relative changes (+5, -3) or absolute numbers.</p>
                    </div>
                    
                    <div class="flex items-center">
                      <input type="checkbox" name="multiple" ${{item.multiple ? 'checked' : ''}} class="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 dark:border-gray-600 rounded dark:bg-gray-700">
                      <label class="ml-2 block text-sm text-gray-900 dark:text-gray-300">Allow multiple purchases</label>
                    </div>
                    
                    <!-- Scheduling Section -->
                    <div class="border-t border-gray-200 dark:border-gray-600 pt-4">
                      <div class="flex items-center mb-3">
                        <input type="checkbox" id="schedule-edit" name="schedule_enabled" onchange="toggleScheduleSection()" class="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 dark:border-gray-600 rounded dark:bg-gray-700">
                        <label for="schedule-edit" class="ml-2 block text-sm font-medium text-gray-900 dark:text-gray-300">Schedule this edit for later</label>
                      </div>
                      
                      <div id="schedule-fields" style="display: none;" class="space-y-3">
                        <div class="bg-yellow-50 dark:bg-yellow-900/20 p-3 rounded-md mb-3">
                          <div class="flex">
                            <div class="flex-shrink-0">
                              <svg class="h-5 w-5 text-yellow-400" fill="currentColor" viewBox="0 0 20 20">
                                <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path>
                              </svg>
                            </div>
                            <div class="ml-3">
                              <h3 class="text-sm font-medium text-yellow-800 dark:text-yellow-200">Scheduled Edits</h3>
                              <p class="text-sm text-yellow-700 dark:text-yellow-300 mt-1">Scheduled edits only support stock changes. If you modify other fields, the edit will be rejected. For full item edits, please update immediately.</p>
                            </div>
                          </div>
                        </div>
                        <div class="bg-blue-50 dark:bg-blue-900/20 p-3 rounded-md">
                          <p class="text-sm text-blue-800 dark:text-blue-200 mb-2">Schedule when this edit should be applied automatically:</p>
                          <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                            <div>
                              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Date</label>
                              <input type="date" name="schedule_date" class="w-full px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white">
                            </div>
                            <div>
                              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Time</label>
                              <input type="time" name="schedule_time" class="w-full px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white">
                            </div>
                          </div>
                          <p class="text-xs text-gray-600 dark:text-gray-400 mt-2">Time is in your local timezone. Leave empty for immediate update.</p>
                        </div>
                      </div>
                    </div>
                  </div>
                  
                  <div class="flex gap-3 mt-6">
                    <button type="submit" class="flex-1 py-2 px-4 bg-blue-500 hover:bg-blue-600 text-white font-medium rounded-md transition">
                      Save Changes
                    </button>
                    <button type="button" onclick="closeEditModal()" class="flex-1 py-2 px-4 bg-gray-500 hover:bg-gray-600 text-white font-medium rounded-md transition">
                      Cancel
                    </button>
                  </div>
                  </form>
                </div>
              </div>
            </div>
          `;

          // Add modal to page
          document.body.insertAdjacentHTML('beforeend', modalHtml);
        }}

        // Purchase history management functions
        let currentHistoryPage = 1;
        let historyLoading = false;
        let hasMoreHistory = true;
        
        function loadPurchaseHistory(page = 1, reset = false) {{
          if (historyLoading) return;
          historyLoading = true;
          
          const container = document.getElementById('purchase-history-container');
          const loadMoreContainer = document.getElementById('load-more-container');
          const purchaseHistorySubtext = document.getElementById('purchase-history-subtext');
          
          if (reset) {{
            container.innerHTML = `
              <div class="flex flex-col items-center justify-center py-12">
                <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 dark:border-blue-400"></div>
                <p class="mt-2 text-gray-600 dark:text-gray-300">Loading purchase history...</p>
              </div>
            `;
            currentHistoryPage = 1;
            hasMoreHistory = true;
          }}
          
          fetch(`/api/configure/{guild_id}/shop/purchase-history?page=${{page}}&limit=10`)
            .then(response => response.json())
            .then(data => {{
              if (data.success) {{
                if (reset) {{
                  container.innerHTML = '';
                }}
                
                if (data.purchases.length === 0 && page === 1) {{
                  container.innerHTML = `
                    <div class="text-center py-12">
                      <div class="mx-auto w-16 h-16 mb-4 text-gray-400">
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z"></path>
                        </svg>
                      </div>
                      <h3 class="text-lg font-medium text-gray-900 dark:text-white mb-2">No Purchase History</h3>
                      <p class="text-gray-600 dark:text-gray-300">No purchases have been made in this server yet.</p>
                      <p class="text-gray-500 dark:text-gray-400 italic text-sm">Only purchases made after October 6, 2025 are logged.</p>
                    </div>
                  `;
                  loadMoreContainer.classList.add('hidden');
                }} else {{
                  // Add purchase entries
                  data.purchases.forEach(purchase => {{
                    const purchaseDate = new Date(purchase.timestamp * 1000);
                    const localTimeString = purchaseDate.toLocaleString();
                    
                    const avatarUrl = purchase.avatar ? 
                      `https://cdn.discordapp.com/avatars/${{purchase.user_id}}/${{purchase.avatar}}.png?size=64` : 
                      'https://cdn.discordapp.com/embed/avatars/0.png';
                    
                    const displayName = purchase.global_name || purchase.username;
                    const discriminator = purchase.discriminator && purchase.discriminator !== '0' ? 
                      `#${{purchase.discriminator}}` : '';
                    
                    const itemDescription = purchase.item_description ? 
                      `<p class="text-sm text-gray-600 dark:text-gray-400 mt-1">${{purchase.item_description}}</p>` : '';
                    
                    const purchaseHtml = `
                      <div class="border border-gray-200 dark:border-gray-600 rounded-lg p-4 mb-3 bg-gray-50 dark:bg-gray-700 relative">
                        ${{purchase.link ? `
                          <a href="${{purchase.link}}" target="_blank" class="absolute top-3 right-3 text-gray-400 hover:text-blue-500 dark:hover:text-blue-400 transition-colors z-10" title="View original purchase message">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path>
                            </svg>
                          </a>
                        ` : ''}}
                        <div class="flex items-start space-x-3">
                          <img src="${{avatarUrl}}" alt="${{displayName}}" class="w-10 h-10 rounded-full">
                          <div class="flex-1 min-w-0">
                            <div>
                              <h4 class="text-sm font-medium text-gray-900 dark:text-white truncate ${{purchase.link ? 'pr-8' : ''}}">
                                <span class="font-bold">${{displayName}}</span> bought <span class="font-bold">${{purchase.item_name}}</span>
                              </h4>
                            </div>
                            <div class="mt-1 text-xs text-gray-600 dark:text-gray-400">
                              User ID: ${{purchase.user_id}}
                              <div class="flex items-center justify-between mt-2">
                                <span class="text-sm font-medium text-red-600 dark:text-red-400">
                                  {MORA_EMOTE} -${{purchase.cost.toLocaleString()}}
                                </span>
                                <span class="text-xs text-gray-500 dark:text-gray-400 border border-gray-300 dark:border-gray-500 rounded-full px-2 py-1">
                                  ${{localTimeString}}
                                </span>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    `;
                    container.insertAdjacentHTML('beforeend', purchaseHtml);
                  }});
                  
                  hasMoreHistory = data.pagination.has_more;
                  currentHistoryPage = page;
                  
                  // Show/hide load more button
                  if (hasMoreHistory) {{
                    loadMoreContainer.classList.remove('hidden');
                    purchaseHistorySubtext.classList.add('hidden');
                  }} else {{
                    loadMoreContainer.classList.add('hidden');
                    purchaseHistorySubtext.classList.remove('hidden');
                  }}
                }}
              }} else {{
                container.innerHTML = `
                  <div class="text-center py-12">
                    <div class="mx-auto w-16 h-16 mb-4 text-red-400">
                      <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.98-.833-2.75 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z"></path>
                      </svg>
                    </div>
                    <h3 class="text-lg font-medium text-gray-900 dark:text-white mb-2">Error Loading History</h3>
                    <p class="text-gray-600 dark:text-gray-300">${{data.error || 'Failed to load purchase history'}}</p>
                  </div>
                `;
              }}
            }})
            .catch(error => {{
              console.error('Error loading purchase history:', error);
              container.innerHTML = `
                <div class="text-center py-12">
                  <div class="mx-auto w-16 h-16 mb-4 text-red-400">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.98-.833-2.75 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z"></path>
                    </svg>
                  </div>
                  <h3 class="text-lg font-medium text-gray-900 dark:text-white mb-2">Connection Error</h3>
                  <p class="text-gray-600 dark:text-gray-300">Failed to connect to the server. Please try again.</p>
                </div>
              `;
            }})
            .finally(() => {{
              historyLoading = false;
              
              // Restore load more button state if it exists
              const loadMoreButton = document.getElementById('load-more-history');
              if (loadMoreButton && loadMoreButton.disabled) {{
                loadMoreButton.style.cursor = 'pointer';
                loadMoreButton.classList.remove('opacity-50');
                loadMoreButton.classList.add('hover:bg-gray-200', 'dark:hover:bg-gray-700');
                loadMoreButton.disabled = false;
                loadMoreButton.innerHTML = 'Load More';
              }}
            }});
        }}
        
        function loadMoreHistory() {{
          // Add loading animation to button and temporarily disable it
          const loadMoreButton = document.getElementById('load-more-history');
          if (!loadMoreButton) return; // Safety check
          
          loadMoreButton.style.cursor = 'not-allowed';
          loadMoreButton.classList.add('opacity-50');
          loadMoreButton.classList.remove('hover:bg-gray-200', 'dark:hover:bg-gray-700');
          loadMoreButton.disabled = true;
          loadMoreButton.innerHTML = `
            <div class="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-2 inline-block"></div>
            Loading...
          `;
          
          // Load more history and restore button state
          if (hasMoreHistory && !historyLoading) {{
            loadPurchaseHistory(currentHistoryPage + 1, false);
          }} else {{
            // Restore button state immediately if conditions aren't met
            loadMoreButton.style.cursor = 'pointer';
            loadMoreButton.classList.remove('opacity-50');
            loadMoreButton.classList.add('hover:bg-gray-200', 'dark:hover:bg-gray-700');
            loadMoreButton.disabled = false;
            loadMoreButton.innerHTML = 'Load More';
          }}
        }}

        // Milestone management functions
        function addMilestone(event) {{
          event.preventDefault();
          const formData = new FormData(event.target);
          const data = {{
            threshold: formData.get('threshold'),
            reward: formData.get('reward'),
            description: formData.get('description') || 'Reached milestone'
          }};

          fetch('/api/configure/{guild_id}/milestones/add', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify(data)
          }})
          .then(response => response.json())
          .then(data => {{
            if (data.success) {{
              window.location.href = `/configure/{guild_id}/minigames?message=${{encodeURIComponent(data.message || 'Milestone added successfully')}}`;
            }} else {{
              window.location.href = `/configure/{guild_id}/minigames?message=${{encodeURIComponent(data.message || 'Failed to add milestone')}}&type=error`;
            }}
          }})
          .catch(error => {{
            console.error('Error:', error);
            window.location.href = `/configure/{guild_id}/minigames?message=${{encodeURIComponent('An error occurred while adding the milestone')}}&type=error`;
          }});
        }}

        function deleteMilestone(id, name, threshold) {{
          if (confirm(`Are you sure you want to delete the milestone "${{name}}" (${{threshold.toLocaleString()}} Mora)? This action cannot be undone.`)) {{
            fetch('/api/configure/{guild_id}/milestones/delete', {{
              method: 'POST',
              headers: {{ 'Content-Type': 'application/json' }},
              body: JSON.stringify({{ id: id }})
            }})
            .then(response => response.json())
            .then(data => {{
              if (data.success) {{
                window.location.href = `/configure/{guild_id}/minigames?message=${{encodeURIComponent(data.message || 'Milestone deleted successfully')}}`;
              }} else {{
                window.location.href = `/configure/{guild_id}/minigames?message=${{encodeURIComponent(data.message || 'Failed to delete milestone')}}&type=error`;
              }}
            }})
            .catch(error => {{
              console.error('Error:', error);
              window.location.href = `/configure/{guild_id}/minigames?message=${{encodeURIComponent('An error occurred while deleting the milestone')}}&type=error`;
            }});
          }}
        }}

        // Shop edit modal functions
        function toggleScheduleSection() {{
          const checkbox = document.getElementById('schedule-edit');
          const fields = document.getElementById('schedule-fields');
          if (checkbox && fields) {{
            fields.style.display = checkbox.checked ? 'block' : 'none';
          }}
        }}
        
        function closeEditModal() {{
          const modal = document.getElementById('edit-shop-modal') || document.getElementById('edit-milestone-modal');
          if (modal) {{
            modal.remove();
          }}
        }}

        function saveShopItemEdit(event, oldName) {{
          event.preventDefault();
          const formData = new FormData(event.target);
          
          const data = {{
            oldName: oldName,
            name: formData.get('name'),
            description: formData.get('description'),
            cost: formData.get('cost'),
            stock: formData.get('stock'),
            multiple: formData.has('multiple')
          }};
          
          // Handle scheduling
          if (formData.has('schedule_enabled')) {{
            const scheduleDate = formData.get('schedule_date');
            const scheduleTime = formData.get('schedule_time');
            
            if (scheduleDate && scheduleTime) {{
              // Convert local datetime to UTC timestamp
              const localDateTime = new Date(`${{scheduleDate}}T${{scheduleTime}}`);
              data.scheduled_time = Math.floor(localDateTime.getTime() / 1000);
            }}
          }}

          fetch('/api/configure/{guild_id}/shop/edit', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify(data)
          }})
          .then(response => response.json())
          .then(data => {{
            if (data.success) {{
              let message = data.message || 'Shop item updated successfully';
              if (data.scheduled_time) {{
                // Format the timestamp in user's local time
                const localTime = new Date(data.scheduled_time * 1000).toLocaleString();
                message += ` for ${{localTime}}`;
              }}
              window.location.href = `/configure/{guild_id}/minigames?message=${{encodeURIComponent(message)}}`;
            }} else {{
              window.location.href = `/configure/{guild_id}/minigames?message=${{encodeURIComponent(data.message || 'Failed to update shop item')}}&type=error`;
            }}
          }})
          .catch(error => {{
            console.error('Error:', error);
            window.location.href = `/configure/{guild_id}/minigames?message=${{encodeURIComponent('An error occurred while updating the item')}}&type=error`;
          }});
        }}

        function editMilestone(id) {{
          // Get the button that was clicked to access data attributes
          const button = event.target;
          const reward = button.getAttribute('data-reward');
          const threshold = button.getAttribute('data-threshold');
          const description = button.getAttribute('data-description');
          
          // Create modal HTML
          const modalHtml = `
            <div id="edit-milestone-modal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
              <div class="bg-white dark:bg-gray-800 rounded-lg w-full max-w-md max-h-[90vh] flex flex-col">
                <div class="flex justify-between items-center p-6 pb-4 border-b border-gray-200 dark:border-gray-600">
                  <h3 class="text-lg font-semibold text-gray-900 dark:text-white">Edit Milestone</h3>
                  <button onclick="closeEditModal()" class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                  </button>
                </div>
                
                <div class="flex-1 overflow-y-auto p-6">
                  <form onsubmit="saveMilestoneEdit(event, '${{id}}')">
                    <div class="space-y-4">
                      <div>
                        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Mora Threshold</label>
                        <input type="number" name="threshold" value="${{threshold}}" required min="1" class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white">
                      </div>
                    
                    <div>
                      <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Role ID or Title</label>
                      <input type="text" name="reward" value="${{reward}}" required class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white">
                    </div>
                    
                    <div>
                      <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Description</label>
                      <textarea name="description" rows="3" class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white">${{description}}</textarea>
                    </div>
                  
                  <div class="flex gap-3 mt-6">
                    <button type="submit" class="flex-1 py-2 px-4 bg-blue-500 hover:bg-blue-600 text-white font-medium rounded-md transition">
                      Save Changes
                    </button>
                    <button type="button" onclick="closeEditModal()" class="flex-1 py-2 px-4 bg-gray-500 hover:bg-gray-600 text-white font-medium rounded-md transition">
                      Cancel
                    </button>
                  </div>
                  </form>
                </div>
              </div>
            </div>
          `;

          // Add modal to page
          document.body.insertAdjacentHTML('beforeend', modalHtml);
        }}

        function saveMilestoneEdit(event, milestoneId) {{
          event.preventDefault();
          const formData = new FormData(event.target);
          
          const data = {{
            id: milestoneId,
            threshold: formData.get('threshold'),
            reward: formData.get('reward'),
            description: formData.get('description') || 'Reached milestone'
          }};

          fetch('/api/configure/{guild_id}/milestones/edit', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify(data)
          }})
          .then(response => response.json())
          .then(data => {{
            if (data.success) {{
              window.location.href = `/configure/{guild_id}/minigames?message=${{encodeURIComponent(data.message || 'Milestone updated successfully')}}`;
            }} else {{
              window.location.href = `/configure/{guild_id}/minigames?message=${{encodeURIComponent(data.message || 'Failed to update milestone')}}&type=error`;
            }}
          }})
          .catch(error => {{
            console.error('Error:', error);
            window.location.href = `/configure/{guild_id}/minigames?message=${{encodeURIComponent('An error occurred while updating the milestone')}}&type=error`;
          }});
        }}

        // Delete pending edit function
        function deletePendingEdit(editKey) {{
          if (confirm('Are you sure you want to delete this pending edit?')) {{
            fetch(`/api/configure/{guild_id}/shop/delete-pending-edit`, {{
              method: 'POST',
              headers: {{ 'Content-Type': 'application/json' }},
              body: JSON.stringify({{ edit_key: editKey }})
            }})
            .then(response => response.json())
            .then(data => {{
              if (data.success) {{
                window.location.href = `/configure/{guild_id}/minigames?message=${{encodeURIComponent(data.message || 'Pending edit deleted successfully')}}`;
              }} else {{
                window.location.href = `/configure/{guild_id}/minigames?message=${{encodeURIComponent(data.message || 'Failed to delete pending edit')}}&type=error`;
              }}
            }})
            .catch(error => {{
              console.error('Error:', error);
              window.location.href = `/configure/{guild_id}/minigames?message=${{encodeURIComponent('An error occurred while deleting the pending edit')}}&type=error`;
            }});
          }}
        }}
      </script>
    """
    
    return wrap_page("Configure Minigames", content, [(f"/configure/{guild_id}", "Back to Guild Configuration", "text-blue-500 dark:text-blue-400 font-medium hover:underline")])

@minigames.route("/api/configure/<guild_id>/minigames/info")
def api_minigames_info(guild_id):
    """API endpoint for minigames configuration data"""
    if "discord_token" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    try:
        # Extract session data before any threading
        discord_token = session['discord_token']
        
        # Verify guild access and permissions
        success, guild, status_code = verify_guild_access(guild_id, discord_token)
        if not success:
            return jsonify(guild), status_code

        def fetch_guild_channels():
            try:
                response = requests_session.get(f"{API_BASE}/guilds/{guild_id}/channels", headers={"Authorization": f"Bot {BOT_TOKEN}"})
                if response.status_code == 200:
                    channels = response.json()
                    if isinstance(channels, list):
                        return channels
                    else:
                        print(f"Invalid channels response format: {type(channels)}")
                        return {"error": "Invalid response format from Discord API"}
                else:
                    print(f"Discord API error for guild channels: {response.status_code}")
                    return {"error": f"Discord API error: {response.status_code}"}
            except Exception as e:
                print(f"Exception in fetch_guild_channels: {e}")
                return {"error": f"Failed to fetch channels: {str(e)}"}
        
        def fetch_minigame_settings():
            try:
                ref = db.reference("/Global Events System")
                events_data = ref.get()
                configured_channels = {}
                if events_data and isinstance(events_data, dict):
                    for key, val in events_data.items():
                        if isinstance(val, dict) and "Channel ID" in val:
                            configured_channels[str(val["Channel ID"])] = {
                                "frequency": val.get("Frequency", 100),
                                "events": val.get("Events", letterList.copy()),
                                "key": key
                            }
                return configured_channels
            except Exception as e:
                print(f"Error fetching minigame settings: {e}")
                return {}
        
        def fetch_guild_roles():
            try:
                response = requests_session.get(f"{API_BASE}/guilds/{guild_id}/roles", headers={"Authorization": f"Bot {BOT_TOKEN}"})
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"Discord API error for guild roles: {response.status_code}")
                    return []
            except Exception as e:
                print(f"Exception in fetch_guild_roles: {e}")
                return []

        # Execute data loading calls concurrently  
        with ThreadPoolExecutor(max_workers=3) as executor:
            channels_future = executor.submit(fetch_guild_channels)
            settings_future = executor.submit(fetch_minigame_settings)
            roles_future = executor.submit(fetch_guild_roles)

            try:
                channels = channels_future.result()
                configured_channels = settings_future.result()
                guild_roles = roles_future.result()
            except Exception as e:
                print(f"Error getting future results: {e}")
                return jsonify({"error": str(e)}), 500

        # Check if channels fetch returned an error
        if isinstance(channels, dict) and 'error' in channels:
            return jsonify({"error": f"Failed to load channels: {channels['error']}"}), 500

        # Ensure channels is a list
        if not isinstance(channels, list):
            return jsonify({"error": f"Invalid channel data received from Discord API. Got: {type(channels)}"}), 500

        icon = f"https://cdn.discordapp.com/icons/{guild['id']}/{guild['icon']}.png?size=128" if guild.get("icon") else ""

        # Generate guild header HTML
        header_html = f"""
        <div class="flex items-center gap-4 mb-6">
          {"<img src='"+icon+"' class='rounded-full w-20 h-20 shadow-md'>" if icon else "<div class='w-20 h-20 rounded-full bg-gray-200 dark:bg-gray-600 flex items-center justify-center text-gray-500 dark:text-gray-300 text-2xl font-bold'>"+html.escape(guild['name'][0])+"</div>"}
          <div>
            <h2 class="text-2xl font-bold text-gray-900 dark:text-white">{html.escape(guild['name'])}</h2>
            <p class="text-gray-500 dark:text-gray-400">ID: {guild['id']}</p>
            {"<p class='text-green-600 dark:text-green-400 font-semibold'>You are the owner</p>" if guild.get("owner") else ""}
          </div>
        </div>
        """

        # Generate configured channels cards
        text_channels = []
        try:
            # Safely filter text channels
            for channel in channels:
                if isinstance(channel, dict) and channel.get('type') == 0:
                    text_channels.append(channel)
        except Exception as e:
            return jsonify({"error": f"Error processing channels: {str(e)}"}), 500
        
        # Create channel map for quick lookup
        channel_map = {}
        try:
            for c in text_channels:
                if isinstance(c, dict) and 'id' in c and 'name' in c:
                    channel_map[str(c['id'])] = c
        except Exception as e:
            return jsonify({"error": f"Error creating channel map: {str(e)}"}), 500
        
        # Filter configured channels to only include those from this guild
        guild_configured_channels = {}
        try:
            for channel_id, config in configured_channels.items():
                if channel_id in channel_map:
                    guild_configured_channels[channel_id] = config
        except Exception as e:
            return jsonify({"error": f"Error filtering configured channels: {str(e)}"}), 500
        
        channels_html = ""
        try:
            if guild_configured_channels:
                for channel_id, config in guild_configured_channels.items():
                    channel = channel_map[channel_id]
                    if not isinstance(channel, dict) or 'name' not in channel:
                        continue
                        
                    frequency_name = next((f["name"] for f in frequency_choices if f["value"] == str(config["frequency"])), f"Custom ({100//config['frequency']}%)")
                    enabled_games_count = len(config.get("events", []))
                    total_games = len(minigame_titles)
                    
                    # Escape channel name to prevent XSS
                    channel_name = str(channel['name']).replace("'", "&#39;").replace('"', '&quot;')
                    
                    channels_html += f"""
                    <div class="bg-gray-50 dark:bg-gray-700 rounded-xl p-4 border border-gray-200 dark:border-gray-600">
                      <div class="flex items-center gap-3 mb-3">
                        <div class="w-10 h-10 border-2 border-gray-400 dark:border-gray-500 rounded-lg flex items-center justify-center">
                          <span class="text-gray-600 dark:text-gray-400 font-bold">#</span>
                        </div>
                        <div class="flex-1 min-w-0">
                          <h4 class="font-semibold text-gray-900 dark:text-white truncate">#{channel_name}</h4>
                          <p class="text-sm text-gray-500 dark:text-gray-400">{frequency_name}</p>
                        </div>
                      </div>
                      
                      <div class="mb-4">
                        <div class="flex justify-between items-center mb-1">
                          <span class="text-sm text-gray-600 dark:text-gray-300">Enabled Games</span>
                          <span class="text-sm font-medium text-gray-900 dark:text-white">{enabled_games_count}/{total_games}</span>
                        </div>
                        <div class="w-full bg-gray-200 dark:bg-gray-600 rounded-full h-2">
                          <div class="bg-blue-500 dark:bg-blue-600 h-2 rounded-full" style="width: {(enabled_games_count/total_games)*100}%"></div>
                        </div>
                      </div>
                      
                      <div class="flex gap-2">
                        <a href="/configure/{guild_id}/minigames/edit/{channel_id}" class="flex-1 py-2 px-3 bg-blue-500 hover:bg-blue-600 dark:bg-blue-600 dark:hover:bg-blue-700 text-white text-sm font-medium rounded-md text-center transition">
                          Edit
                        </a>
                        <button onclick="deleteChannel('{channel_id}', '{channel_name}')" class="flex-1 py-2 px-3 bg-red-500 hover:bg-red-600 dark:bg-red-600 dark:hover:bg-red-700 text-white text-sm font-medium rounded-md transition">
                          Delete
                        </button>
                      </div>
                    </div>
                    """
            
            if not channels_html:
                channels_html = create_empty_content("No channels have minigames enabled yet. Use the 'Add New Channel' tab to get started.")
        except Exception as e:
            return jsonify({"error": f"Error generating channel cards: {str(e)}"}), 500

        # Generate add new channel form
        available_channels = []
        try:
            available_channels = [c for c in text_channels if isinstance(c, dict) and str(c.get('id', '')) not in guild_configured_channels]
        except Exception as e:
            return jsonify({"error": f"Error filtering available channels: {str(e)}"}), 500
        
        add_form_html = ""
        try:
            if available_channels:
                channel_options = ""
                for c in available_channels:
                    if isinstance(c, dict) and 'id' in c and 'name' in c:
                        channel_name = str(c['name']).replace('"', '&quot;')
                        channel_options += f'<option value="{c["id"]}">{channel_name}</option>'
                
                frequency_options = "".join([
                    f'<option value="{f["value"]}">{f["name"]}</option>'
                    for f in frequency_choices
                ])
                
                add_form_html = f"""
                <form method="POST" action="/configure/{guild_id}/minigames/add" class="space-y-6">
                  <div>
                    <label for="channel" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Select Channel
                    </label>
                    <select name="channel" id="channel" required class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white">
                      <option value="">Choose a channel...</option>
                      {channel_options}
                    </select>
                  </div>
                  
                  <div>
                    <label for="frequency" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Event Frequency
                    </label>
                    <select name="frequency" id="frequency" required class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white">
                      <option value="">Choose frequency...</option>
                      {frequency_options}
                    </select>
                    <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">Higher percentages mean more frequent events</p>
                  </div>
                  
                  <button type="submit" class="w-full py-3 px-4 bg-green-500 hover:bg-green-600 dark:bg-green-600 dark:hover:bg-green-700 text-white font-medium rounded-md transition">
                    Enable Minigames
                  </button>
                </form>
                """
            else:
                add_form_html = create_empty_content("All available channels already have minigames enabled.")
        except Exception as e:
            add_form_html = f'<div class="text-center py-12"><p class="text-red-500 dark:text-red-400">Error generating form: {str(e)}</p></div>'

        return jsonify({
            "header": header_html,
            "channels": channels_html,
            "addForm": add_form_html,
            # Include Discord data for reuse in other endpoints
            "userGuilds": guild,
            "guildRoles": guild_roles,
            "guildChannels": channels
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@minigames.route("/configure/<guild_id>/minigames/add", methods=["POST"])
def add_minigames_channel(guild_id):
    """Add minigames to a new channel"""
    if "discord_token" not in session:
        return redirect("/")

    try:
        # Verify guild access and permissions (without bot check for form submission)
        success, guild, status_code = verify_guild_access(guild_id, session['discord_token'], require_bot_in_guild=False)
        if not success:
            return redirect(f"/configure/{guild_id}/minigames?message={guild['error'].replace(' ', '+')}")

        channel_id = int(request.form.get("channel"))
        frequency = int(request.form.get("frequency"))

        # Add to database (same structure as Discord bot)
        data = {
            "Channel ID": channel_id,
            "Frequency": frequency,
            "Events": letterList.copy(),  # Enable all games by default
        }

        ref = db.reference("/Global Events System")
        ref.push().set(data)

        return redirect(f"/configure/{guild_id}/minigames?message=Minigames+enabled+successfully")

    except Exception as e:
        return redirect(f"/configure/{guild_id}/minigames?message=Error:+{str(e)}")

@minigames.route("/configure/<guild_id>/minigames/delete/<channel_id>", methods=["POST"])
def delete_minigames_channel(guild_id, channel_id):
    """Delete minigames configuration for a channel"""
    if "discord_token" not in session:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    try:
        # Verify access
        discord_token = session['discord_token']
        success, guild, status_code = verify_guild_access(guild_id, discord_token)
        if not success:
            return jsonify(guild), status_code

        # Find and delete from database
        ref = db.reference("/Global Events System")
        events_data = ref.get()
        
        if events_data:
            for key, val in events_data.items():
                if isinstance(val, dict) and str(val.get("Channel ID")) == str(channel_id):
                    ref.child(key).delete()
                    return jsonify({"success": True, "message": "Configuration deleted successfully"})

        return jsonify({"success": False, "message": "Configuration not found"}), 404

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# Shop Management Endpoints
@minigames.route("/api/configure/<guild_id>/shop/info", methods=["GET", "POST"])
def api_shop_info(guild_id):
    """API endpoint for shop configuration data"""
    if "discord_token" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    try:
        # Check if Discord data is provided via request body (from frontend)
        discord_data = None
        if request.method == "POST":
            request_data = request.get_json() or {}
            discord_data = request_data.get('discord_data')
        
        if discord_data:
            # Use provided Discord data (from frontend)
            guild = discord_data['userGuilds']
            guild_roles = {str(role['id']): role for role in discord_data['guildRoles']}
        else:
            # Fallback: fetch Discord data directly
            discord_token = session['discord_token']
            
            # Verify guild access and permissions
            success, guild, status_code = verify_guild_access(guild_id, discord_token)
            if not success:
                return jsonify(guild), status_code
                
            # Get guild roles
            try:
                roles_response = requests_session.get(f"{API_BASE}/guilds/{guild_id}/roles", headers={"Authorization": f"Bot {BOT_TOKEN}"})
                if roles_response.status_code == 200:
                    roles = roles_response.json()
                    guild_roles = {str(role['id']): role for role in roles}
                else:
                    guild_roles = {}
            except Exception as e:
                print(f"Error fetching guild roles: {e}")
                guild_roles = {}

        # Process any pending scheduled edits first
        process_pending_shop_edits(guild_id)

        # Get pending shop edits for this guild
        pending_ref = db.reference(f"/Pending Shop Edits/{guild_id}")
        pending_edits = pending_ref.get() or {}
        
        # Organize pending edits by item identifier
        pending_by_item = {}
        for key, edit in pending_edits.items():
            item_id = edit.get('item_identifier')
            if item_id:
                if item_id not in pending_by_item:
                    pending_by_item[item_id] = []
                # Include the key so we can delete the edit later
                edit_with_key = edit.copy()
                edit_with_key['edit_key'] = key
                pending_by_item[item_id].append(edit_with_key)

        # Get shop items from database
        ref = db.reference("/Global Events Rewards")
        rewards_data = ref.get() or {}
        
        # Parse shop items for this guild
        shop_items = []
        guild_key = None
        for key, data in rewards_data.items():
            if isinstance(data, dict) and data.get("Server ID") == int(guild_id):
                guild_key = key
                items = data.get("Rewards", [])
                for item in items:
                    if len(item) >= 3:
                        # Convert old format to new format if needed
                        item_data = {
                            "name": item[0],
                            "description": item[1],
                            "cost": item[2],
                            "multiple": item[3] if len(item) > 3 else False,
                            "stock": item[4] if len(item) > 4 else -1
                        }
                        
                        # Add role info if it's a role ID
                        if str(item[0]).isdigit() and str(item[0]) in guild_roles:
                            item_data["role"] = guild_roles[str(item[0])]
                        
                        # Add pending edits info if any exist for this item
                        item_data["pending_edits"] = pending_by_item.get(str(item[0]), [])
                        
                        shop_items.append(item_data)
                break

        # Generate shop items HTML
        items_html = ""
        if shop_items:
            items_html += '<div class="grid grid-cols-1 lg:grid-cols-2 gap-4">'
            for i, item in enumerate(shop_items):
                role_info = ""
                if "role" in item:
                    role = item["role"]
                    color = f"#{role['color']:06x}" if role['color'] else "#99aab5"
                    role_info = f"""
                    <div class="flex items-center gap-2 mb-2">
                      <div class="w-4 h-4 rounded-full" style="background-color: {color}"></div>
                      <span class="font-medium text-gray-900 dark:text-white">@{role['name']}</span>
                    </div>
                    """
                
                stock_info = ""
                if item["stock"] != -1:
                    stock_color = "text-red-600 dark:text-red-400" if item["stock"] == 0 else "text-gray-600 dark:text-gray-300"
                    stock_text = "Out of Stock" if item["stock"] == 0 else f"{item['stock']} remaining"
                    stock_info = f'<p class="text-sm {stock_color} mb-2">📦 {stock_text}</p>'
                
                multiple_badge = ""
                if item["multiple"]:
                    multiple_badge = '<div class="absolute top-3 right-3"><span class="inline-flex items-center justify-center w-6 h-6 rounded-full text-xs bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">🔄</span></div>'

                # Generate pending edits info
                pending_edits_html = ""
                if item.get("pending_edits"):
                    pending_edits = item["pending_edits"]
                    # Sort by scheduled time
                    sorted_edits = sorted(pending_edits, key=lambda x: x.get('scheduled_time', 0))
                    
                    pending_items = []
                    for edit in sorted_edits:
                        scheduled_time = edit.get('scheduled_time', 0)
                        stock_change = edit.get('stock_change', '')
                        edit_key = edit.get('edit_key', '')
                        
                        # Format the scheduled time (will be converted to local time by JavaScript)
                        try:
                            # Send timestamp to frontend for local time conversion
                            formatted_time = f'<span class="local-time" data-timestamp="{scheduled_time}">{scheduled_time}</span>'
                        except:
                            formatted_time = "Invalid time"
                        
                        # Format the stock change
                        if stock_change == "-1":
                            change_text = "Set to unlimited"
                        elif stock_change.startswith(('+', '-')):
                            change_text = f"Change by {stock_change}"
                        else:
                            change_text = f"Set to {stock_change}"
                        
                        pending_items.append(f"""
                        <div class="flex items-center justify-between text-xs">
                          <div class="flex-1">
                            <div class="flex items-center justify-between">
                              <span class="text-orange-700 dark:text-orange-300">{formatted_time}</span>
                              <span class="font-medium text-orange-800 dark:text-orange-200">{change_text}</span>
                            </div>
                          </div>
                          <button onclick="deletePendingEdit('{edit_key}')" class="ml-2 p-1 text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 transition-colors" title="Delete pending edit">
                            <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                              <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd"></path>
                            </svg>
                          </button>
                        </div>
                        """)
                    
                    if pending_items:
                        pending_edits_html = f"""
                        <div class="mt-3 p-2 bg-orange-50 dark:bg-orange-900/20 rounded-lg border border-orange-200 dark:border-orange-800">
                          <div class="flex items-center gap-1 mb-2">
                            <span class="text-xs font-medium text-orange-800 dark:text-orange-200">⏰ Pending Stock Changes</span>
                          </div>
                          <div class="space-y-1">
                            {''.join(pending_items)}
                          </div>
                        </div>
                        """

                items_html += f"""
                <div class="relative bg-gray-50 dark:bg-gray-700 rounded-xl p-4 border border-gray-200 dark:border-gray-600">
                  {multiple_badge}
                  <div class="flex items-start justify-between mb-3">
                    <div class="flex-1">
                      <h4 class="font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                        <span class="bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200 px-2 py-1 rounded-full text-sm font-medium">
                          {MORA_EMOTE} {int(item['cost']):,}
                        </span>
                        <span>{item["name"] if role_info == '' else role_info}</span>
                      </h4>
                      <p class="text-sm text-gray-600 dark:text-gray-300 mt-2">{item["description"]}</p>
                      {stock_info}
                      {pending_edits_html}
                    </div>
                  </div>
                  
                  <div class="flex gap-2">
                    <button onclick="editShopItem({i})" class="flex-1 py-2 px-3 bg-blue-500 hover:bg-blue-600 dark:bg-blue-600 dark:hover:bg-blue-700 text-white text-sm font-medium rounded-md transition">
                      Edit
                    </button>
                    <button onclick="deleteShopItem('{item['name'].replace("'", "&#39;")}', '{item['name'].replace("'", "&#39;")}', true)" class="flex-1 py-2 px-3 bg-red-500 hover:bg-red-600 dark:bg-red-600 dark:hover:bg-red-700 text-white text-sm font-medium rounded-md transition">
                      Delete
                    </button>
                  </div>
                </div>
                """
            items_html += '</div>'  # Close grid container
        else:
            items_html = create_empty_content("No shop items found. Use the 'Add New Item' tab to create your first item.")

        # Generate add form HTML
        add_form_html = f"""
        <form onsubmit="addShopItem(event)" class="space-y-6">
          <div>
            <label for="shop-name" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Role ID or Title
            </label>
            <input type="text" name="name" id="shop-name" required 
                   class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white"
                   placeholder="Role ID (numbers only) or custom title">
            <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">Enter a role ID for role rewards, or custom text for titles</p>
          </div>
          
          <div>
            <label for="shop-description" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Description
            </label>
            <textarea name="description" id="shop-description" required rows="3"
                      class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white"
                      placeholder="Describe what this reward gives"></textarea>
          </div>
          
          <div>
            <label for="shop-cost" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Cost (Mora)
            </label>
            <input type="number" name="cost" id="shop-cost" required min="1"
                   class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white"
                   placeholder="Enter cost in Mora">
          </div>
          
          <div>
            <label for="shop-stock" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Stock (Optional)
            </label>
            <input type="number" name="stock" id="shop-stock" min="0"
                   class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white"
                   placeholder="Leave empty for unlimited stock">
            <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">Set a stock limit, or leave empty for unlimited</p>
          </div>
          
          <div class="flex items-center">
            <input type="checkbox" name="multiple" id="shop-multiple"
                   class="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 dark:border-gray-600 rounded dark:bg-gray-700">
            <label for="shop-multiple" class="ml-2 block text-sm text-gray-900 dark:text-gray-300">
              Allow multiple purchases (titles only)
            </label>
          </div>
          
          <button type="submit" class="w-full py-3 px-4 bg-green-500 hover:bg-green-600 dark:bg-green-600 dark:hover:bg-green-700 text-white font-medium rounded-md transition">
            Add Shop Item
          </button>
        </form>
        """

        return jsonify({
            "items": items_html,
            "addForm": add_form_html,
            "itemsData": shop_items
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@minigames.route("/api/configure/<guild_id>/shop/add", methods=["POST"])
def api_add_shop_item(guild_id):
    """Add a new shop item"""
    if "discord_token" not in session:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    try:
        # Verify access
        discord_token = session['discord_token']
        
        success, guild, status_code = verify_guild_access(guild_id, discord_token, user_guilds_only=True)
        if not success:
            return jsonify(guild), status_code

        # Get form data
        data = request.get_json()
        name = data.get("name", "").strip()
        description = data.get("description", "").strip()
        cost = int(data.get("cost", 0))
        stock = data.get("stock")
        multiple = data.get("multiple", False)

        if not name or not description or cost <= 0:
            return jsonify({"success": False, "message": "Invalid input data"}), 400

        # Validate role if it's a role ID
        if name.isdigit():
            try:
                roles_response = requests_session.get(f"{API_BASE}/guilds/{guild_id}/roles", headers={"Authorization": f"Bot {BOT_TOKEN}"})
                if roles_response.status_code == 200:
                    roles = roles_response.json()
                    role_exists = any(role['id'] == name for role in roles)
                    if not role_exists:
                        return jsonify({"success": False, "message": "Role ID does not exist in this server"}), 400
            except Exception:
                return jsonify({"success": False, "message": "Could not validate role"}), 500

        # Handle stock
        stock_val = -1
        if stock and str(stock).strip():
            try:
                stock_val = int(stock)
                if stock_val < 0:
                    stock_val = -1
            except ValueError:
                return jsonify({"success": False, "message": "Invalid stock value"}), 400

        # Get existing rewards
        ref = db.reference("/Global Events Rewards")
        rewards_data = ref.get() or {}
        
        # Find guild's rewards or create new
        guild_key = None
        rewards_list = []
        for key, guild_data in rewards_data.items():
            if isinstance(guild_data, dict) and guild_data.get("Server ID") == int(guild_id):
                guild_key = key
                rewards_list = guild_data.get("Rewards", [])
                break

        # Check for duplicates
        for item in rewards_list:
            if len(item) > 0 and str(item[0]) == str(name):
                return jsonify({"success": False, "message": "Item with this name/role already exists"}), 400

        # Add new item
        new_item = [name, description, cost, multiple, stock_val]
        rewards_list.append(new_item)

        # Save to database
        guild_data = {
            "Server ID": int(guild_id),
            "Rewards": rewards_list
        }

        if guild_key:
            ref.child(guild_key).set(guild_data)
        else:
            ref.push().set(guild_data)

        return jsonify({"success": True, "message": "Shop item added successfully"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@minigames.route("/api/configure/<guild_id>/shop/delete", methods=["POST"])
def api_delete_shop_item(guild_id):
    """Delete a shop item"""
    if "discord_token" not in session:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    try:
        # Verify access
        discord_token = session['discord_token']
        
        success, guild, status_code = verify_guild_access(guild_id, discord_token, user_guilds_only=True)
        if not success:
            return jsonify(guild), status_code

        data = request.get_json()
        item_name = data.get("name", "").strip()
        compensate = data.get("compensate", False)

        if not item_name:
            return jsonify({"success": False, "message": "Item name is required"}), 400

        # Get existing rewards
        ref = db.reference("/Global Events Rewards")
        rewards_data = ref.get() or {}
        
        guild_key = None
        rewards_list = []
        item_to_delete = None
        
        for key, guild_data in rewards_data.items():
            if isinstance(guild_data, dict) and guild_data.get("Server ID") == int(guild_id):
                guild_key = key
                rewards_list = guild_data.get("Rewards", [])
                
                # Find and remove the item
                for i, item in enumerate(rewards_list):
                    if len(item) > 0 and str(item[0]) == str(item_name):
                        item_to_delete = rewards_list.pop(i)
                        break
                break

        if not item_to_delete:
            return jsonify({"success": False, "message": "Item not found"}), 404

        # Save updated list
        if guild_key:
            guild_data = {
                "Server ID": int(guild_id),
                "Rewards": rewards_list
            }
            ref.child(guild_key).set(guild_data)

        # Handle compensation if requested
        if compensate and len(item_to_delete) >= 3:
            try:
                cost = int(item_to_delete[2])
                inventory_ref = db.reference("/User Events Inventory")
                inventories = inventory_ref.get() or {}
                
                compensated_users = 0
                for inv_key, inv_data in inventories.items():
                    if not isinstance(inv_data, dict):
                        continue
                        
                    items = inv_data.get("Items", [])
                    user_id = inv_data.get("User ID")
                    
                    # Find and remove items, count how many
                    items_removed = 0
                    new_items = []
                    for item in items:
                        if (len(item) >= 4 and str(item[0]) == str(item_name) 
                            and str(item[3]) == str(guild_id)):
                            items_removed += 1
                        else:
                            new_items.append(item)
                    
                    if items_removed > 0:
                        # Update inventory
                        inv_data["Items"] = new_items
                        inventory_ref.child(inv_key).set(inv_data)
                        
                        # Add compensation to user's mora
                        compensation = cost * items_removed
                        mora_ref = db.reference(f"/Mora/{user_id}")
                        user_mora = mora_ref.get() or {}
                        guild_mora = user_mora.get(str(guild_id), 0)
                        user_mora[str(guild_id)] = guild_mora + compensation
                        mora_ref.set(user_mora)
                        
                        compensated_users += 1
                
                message = f"Item deleted successfully. Compensated {compensated_users} users with {cost:,} Mora each."
            except Exception as e:
                message = f"Item deleted successfully, but compensation failed: {str(e)}"
        else:
            message = "Item deleted successfully."

        return jsonify({"success": True, "message": message})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@minigames.route("/api/configure/<guild_id>/shop/edit", methods=["POST"])
def api_edit_shop_item(guild_id):
    """Edit a shop item"""
    if "discord_token" not in session:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    try:
        # Verify access
        discord_token = session['discord_token']

        success, guild, status_code = verify_guild_access(guild_id, discord_token, user_guilds_only=True)
        if not success:
            return jsonify(guild), status_code

        data = request.get_json()
        old_name = data.get("oldName", "").strip()
        new_name = data.get("name", "").strip()
        description = data.get("description", "").strip()
        cost = int(data.get("cost", 0))
        stock = data.get("stock")
        multiple = data.get("multiple", False)
        scheduled_time = data.get("scheduled_time")

        if not old_name or not new_name or not description or cost <= 0:
            return jsonify({"success": False, "message": "Invalid input data"}), 400
            
        # If scheduled, store in pending edits
        if scheduled_time:
            current_time = time.time()
            if float(scheduled_time) <= current_time:
                return jsonify({"success": False, "message": "Scheduled time must be in the future"}), 400
            
            # Get current item to compare changes
            ref = db.reference("/Global Events Rewards")
            rewards_data = ref.get() or {}
            current_item = None
            
            for key, guild_data in rewards_data.items():
                if isinstance(guild_data, dict) and guild_data.get("Server ID") == int(guild_id):
                    for item in guild_data.get("Rewards", []):
                        if len(item) > 0 and str(item[0]) == str(old_name):
                            current_item = item
                            break
                    break
            
            if not current_item:
                return jsonify({"success": False, "message": "Item not found"}), 404
            
            # Check if only stock is changing (consistent with Discord bot approach)
            current_stock = current_item[4] if len(current_item) > 4 else -1
            is_stock_only_change = (
                str(current_item[0]) == str(new_name) and
                str(current_item[1]) == str(description) and
                int(current_item[2]) == int(cost) and
                bool(current_item[3]) == bool(multiple)
            )
            
            if is_stock_only_change:
                # Handle stock-only change (like Discord bot)
                if stock and str(stock).strip():
                    # Convert to string and handle different formats
                    stock_str = str(stock).strip()
                    
                    # Validate stock change format
                    if stock_str.startswith(('+', '-')):
                        # Relative change - validate the number part
                        try:
                            int(stock_str[1:]) if stock_str[1:] else 0
                            stock_change = stock_str
                        except ValueError:
                            return jsonify({"success": False, "message": "Invalid relative stock change format"}), 400
                    else:
                        # Absolute value
                        try:
                            stock_val = int(stock_str)
                            if stock_val < 0:
                                stock_change = "-1"  # unlimited
                            else:
                                stock_change = str(stock_val)
                        except ValueError:
                            return jsonify({"success": False, "message": "Invalid stock value"}), 400
                else:
                    stock_change = "-1"  # unlimited
                    
                edit_data = {
                    "item_identifier": old_name,
                    "scheduled_time": float(scheduled_time),
                    "stock_change": stock_change
                }
                pending_ref = db.reference(f"/Pending Shop Edits/{guild_id}")
                pending_ref.push().set(edit_data)
                
                # Convert timestamp to readable format for user (show in local time)
                # The frontend sends UTC timestamp, but we need to show it in user's local time
                # We'll send the timestamp to frontend and let JavaScript format it in user's timezone
                return jsonify({"success": True, "message": f"Stock update successfully scheduled", "scheduled_time": scheduled_time}) 
            else:
                return jsonify({"success": False, "message": "Scheduled edits are only supported for stock-only changes. Please edit other fields immediately."}), 400

        # Validate role if it's a role ID
        if new_name.isdigit():
            try:
                roles_response = requests_session.get(f"{API_BASE}/guilds/{guild_id}/roles", headers={"Authorization": f"Bot {BOT_TOKEN}"})
                if roles_response.status_code == 200:
                    roles = roles_response.json()
                    role_exists = any(role['id'] == new_name for role in roles)
                    if not role_exists:
                        return jsonify({"success": False, "message": "Role ID does not exist in this server"}), 400
            except Exception:
                return jsonify({"success": False, "message": "Could not validate role"}), 500

        # Handle stock
        stock_val = -1
        if stock and str(stock).strip():
            try:
                stock_val = int(stock)
                if stock_val < 0:
                    stock_val = -1
            except ValueError:
                return jsonify({"success": False, "message": "Invalid stock value"}), 400

        # Get existing rewards
        ref = db.reference("/Global Events Rewards")
        rewards_data = ref.get() or {}
        
        guild_key = None
        rewards_list = []
        item_found = False
        
        for key, guild_data in rewards_data.items():
            if isinstance(guild_data, dict) and guild_data.get("Server ID") == int(guild_id):
                guild_key = key
                rewards_list = guild_data.get("Rewards", [])
                
                # Find and update the item
                for i, item in enumerate(rewards_list):
                    if len(item) > 0 and str(item[0]) == str(old_name):
                        # Check if new name conflicts with existing items (unless it's the same item)
                        if old_name != new_name:
                            for other_item in rewards_list:
                                if len(other_item) > 0 and str(other_item[0]) == str(new_name):
                                    return jsonify({"success": False, "message": "Item with this name/role already exists"}), 400
                        
                        # Update the item
                        rewards_list[i] = [new_name, description, cost, multiple, stock_val]
                        item_found = True
                        break
                break

        if not item_found:
            return jsonify({"success": False, "message": "Item not found"}), 404

        # Save updated list
        if guild_key:
            guild_data = {
                "Server ID": int(guild_id),
                "Rewards": rewards_list
            }
            ref.child(guild_key).set(guild_data)

        return jsonify({"success": True, "message": "Shop item updated successfully"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@minigames.route("/api/configure/<guild_id>/shop/delete-pending-edit", methods=["POST"])
def api_delete_pending_edit(guild_id):
    """Delete a pending shop edit"""
    if "discord_token" not in session:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    try:
        # Verify access
        discord_token = session['discord_token']

        success, guild, status_code = verify_guild_access(guild_id, discord_token, user_guilds_only=True)
        if not success:
            return jsonify(guild), status_code

        data = request.get_json()
        edit_key = data.get("edit_key", "").strip()
        
        if not edit_key:
            return jsonify({"success": False, "message": "Edit key is required"}), 400

        # Delete the pending edit from the database
        pending_ref = db.reference(f"/Pending Shop Edits/{guild_id}/{edit_key}")
        pending_ref.delete()

        return jsonify({"success": True, "message": "Pending edit deleted successfully"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@minigames.route("/api/configure/<guild_id>/shop/purchase-history", methods=["GET"])
def api_shop_purchase_history(guild_id):
    """API endpoint for shop purchase history with pagination"""
    if "discord_token" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    try:
        # Verify access
        discord_token = session['discord_token']

        success, guild, status_code = verify_guild_access(guild_id, discord_token, user_guilds_only=True)
        if not success:
            return jsonify(guild), status_code

        # Get pagination parameters
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
        offset = (page - 1) * limit

        # Get purchase history from database
        history_ref = db.reference(f"/Mora Purchase History/{guild_id}")
        all_purchases_data = history_ref.get() or {}
        
        # Flatten all purchases with user_id and purchase_id info
        all_purchases = []
        for user_id, user_purchases in all_purchases_data.items():
            if isinstance(user_purchases, dict):
                for purchase_id, purchase_data in user_purchases.items():
                    if isinstance(purchase_data, dict):
                        purchase_entry = purchase_data.copy()
                        purchase_entry['user_id'] = user_id
                        purchase_entry['purchase_id'] = purchase_id
                        all_purchases.append(purchase_entry)
        
        # Sort by timestamp (newest first)
        all_purchases.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        
        # Apply pagination
        total_purchases = len(all_purchases)
        purchases_page = all_purchases[offset:offset + limit]
        
        # Get unique user IDs for this page
        user_ids = list(set(purchase['user_id'] for purchase in purchases_page))
        
        # Fetch user information from Discord API
        user_data = {}
        if user_ids:
            try:
                # Batch fetch users using bot token
                for user_id in user_ids:
                    try:
                        user_response = requests_session.get(
                            f"{API_BASE}/users/{user_id}",
                            headers={"Authorization": f"Bot {BOT_TOKEN}"}
                        )
                        if user_response.status_code == 200:
                            user_info = user_response.json()
                            user_data[user_id] = {
                                'username': user_info.get('username', 'Unknown User'),
                                'discriminator': user_info.get('discriminator'),
                                'avatar': user_info.get('avatar'),
                                'global_name': user_info.get('global_name')
                            }
                        else:
                            user_data[user_id] = {'username': 'Unknown User'}
                    except Exception as e:
                        print(f"Error fetching user {user_id}: {e}")
                        user_data[user_id] = {'username': 'Unknown User'}
            except Exception as e:
                print(f"Error fetching user data: {e}")
        
        # Enhance purchase data with user information
        enhanced_purchases = []
        for purchase in purchases_page:
            user_id = purchase['user_id']
            user_info = user_data.get(user_id, {'username': 'Unknown User'})
            
            enhanced_purchase = {
                'user_id': user_id,
                'username': user_info.get('username', 'Unknown User'),
                'discriminator': user_info.get('discriminator'),
                'avatar': user_info.get('avatar'),
                'global_name': user_info.get('global_name'),
                'item_name': purchase.get('item_name', 'Unknown Item'),
                'item_description': purchase.get('item_description', ''),
                'cost': purchase.get('cost', 0),
                'timestamp': purchase.get('timestamp', 0),
                'purchase_id': purchase.get('purchase_id'),
                'link': purchase.get('link', '')
            }
            enhanced_purchases.append(enhanced_purchase)
        
        has_more = (offset + limit) < total_purchases
        
        return jsonify({
            "success": True,
            "purchases": enhanced_purchases,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total_purchases,
                "has_more": has_more,
                "total_pages": (total_purchases + limit - 1) // limit
            }
        })

    except Exception as e:
        print(f"Error in purchase history: {e}")
        return jsonify({"error": str(e)}), 500

# Milestones Management Endpoints  
@minigames.route("/api/configure/<guild_id>/milestones/info", methods=["GET", "POST"])
def api_milestones_info(guild_id):
    """API endpoint for milestones configuration data"""
    if "discord_token" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    try:
        # Check if Discord data is provided via request body (from frontend)
        discord_data = None
        if request.method == "POST":
            request_data = request.get_json() or {}
            discord_data = request_data.get('discord_data')
        
        if discord_data:
            # Use provided Discord data (from frontend)
            guild = discord_data['userGuilds']
            guild_roles = {str(role['id']): role for role in discord_data['guildRoles']}
        else:
            # Fallback: fetch Discord data directly
            discord_token = session['discord_token']
            
            # Verify guild access and permissions
            success, guild, status_code = verify_guild_access(guild_id, discord_token)
            if not success:
                return jsonify(guild), status_code
                
            # Get guild roles
            try:
                roles_response = requests_session.get(f"{API_BASE}/guilds/{guild_id}/roles", headers={"Authorization": f"Bot {BOT_TOKEN}"})
                if roles_response.status_code == 200:
                    roles = roles_response.json()
                    guild_roles = {str(role['id']): role for role in roles}
                else:
                    guild_roles = {}
            except Exception as e:
                print(f"Error fetching guild roles: {e}")
                guild_roles = {}

        # Get milestones from database
        ref = db.reference(f"/Milestones/{guild_id}")
        milestones_data = ref.get() or {}
        
        # Parse milestones
        milestones = []
        for milestone_id, milestone_data in milestones_data.items():
            if isinstance(milestone_data, dict):
                milestone_info = {
                    "id": milestone_id,
                    "threshold": milestone_data.get("threshold", 0),
                    "reward": milestone_data.get("reward", ""),
                    "description": milestone_data.get("description", "")
                }
                
                # Add role info if it's a role ID
                reward = str(milestone_info["reward"])
                if reward.isdigit() and reward in guild_roles:
                    milestone_info["role"] = guild_roles[reward]
                
                milestones.append(milestone_info)

        # Sort by threshold
        milestones.sort(key=lambda x: x["threshold"])

        # Generate milestones HTML
        items_html = ""
        if milestones:
            items_html += '<div class="grid grid-cols-1 lg:grid-cols-2 gap-4">'
            for milestone in milestones:
                role_info = ""
                if "role" in milestone:
                    role = milestone["role"]
                    color = f"#{role['color']:06x}" if role['color'] else "#99aab5"
                    role_info = f"""
                    <div class="flex items-center gap-2 mb-2">
                      <div class="w-4 h-4 rounded-full" style="background-color: {color}"></div>
                      <span class="font-medium">@{role['name']}</span>
                    </div>
                    """

                items_html += f"""
                <div class="bg-gray-50 dark:bg-gray-700 rounded-xl p-4 border border-gray-200 dark:border-gray-600">
                  <div class="flex items-start justify-between mb-3">
                    <div class="flex-1">
                      <h4 class="font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                        <span class="bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200 px-2 py-1 rounded-full text-sm font-medium">
                          {MORA_EMOTE} {milestone['threshold']:,}
                        </span>
                        <span>{milestone['reward'] if role_info == '' else role_info}</span>
                      </h4>
                      <p class="text-sm text-gray-600 dark:text-gray-300 mt-2">{milestone['description']}</p>
                    </div>
                  </div>
                  
                  <div class="flex gap-2">
                    <button onclick="editMilestone('{milestone['id']}')" 
                            data-reward="{milestone['reward'].replace('"', '&quot;').replace("'", '&#39;')}"
                            data-threshold="{milestone['threshold']}"
                            data-description="{milestone['description'].replace('"', '&quot;').replace("'", '&#39;')}"
                            class="flex-1 py-2 px-3 bg-blue-500 hover:bg-blue-600 dark:bg-blue-600 dark:hover:bg-blue-700 text-white text-sm font-medium rounded-md transition">
                      Edit
                    </button>
                    <button onclick="deleteMilestone('{milestone['id']}', '{milestone['reward'].replace("'", "&#39;")}', {milestone['threshold']})" 
                            class="flex-1 py-2 px-3 bg-red-500 hover:bg-red-600 dark:bg-red-600 dark:hover:bg-red-700 text-white text-sm font-medium rounded-md transition">
                      Delete
                    </button>
                  </div>
                </div>
                """
            items_html += '</div>'  # Close grid container
        else:
            items_html = create_empty_content("No milestones found. Use the 'Add New Milestone' tab to create your first milestone.")

        # Generate add form HTML
        add_form_html = f"""
        <form onsubmit="addMilestone(event)" class="space-y-6">
          <div>
            <label for="milestone-threshold" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Mora Threshold
            </label>
            <input type="number" name="threshold" id="milestone-threshold" required min="1"
                   class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white"
                   placeholder="e.g., 10000">
            <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">Amount of Mora needed to unlock this milestone</p>
          </div>
          
          <div>
            <label for="milestone-reward" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Role ID or Title
            </label>
            <input type="text" name="reward" id="milestone-reward" required 
                   class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white"
                   placeholder="Role ID (numbers only) or custom title">
            <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">Enter a role ID for role rewards, or custom text for titles</p>
          </div>
          
          <div>
            <label for="milestone-description" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Description
            </label>
            <textarea name="description" id="milestone-description" rows="3"
                      class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white"
                      placeholder="What does this milestone represent?"></textarea>
            <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">Optional description (defaults to 'Reached milestone')</p>
          </div>
          
          <button type="submit" class="w-full py-3 px-4 bg-green-500 hover:bg-green-600 dark:bg-green-600 dark:hover:bg-green-700 text-white font-medium rounded-md transition">
            Add Milestone
          </button>
        </form>
        """

        return jsonify({
            "items": items_html,
            "addForm": add_form_html,
            "milestonesData": milestones
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@minigames.route("/api/configure/<guild_id>/milestones/add", methods=["POST"])
def api_add_milestone(guild_id):
    """Add a new milestone"""
    if "discord_token" not in session:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    try:
        # Verify access
        discord_token = session['discord_token']
        
        success, guild, status_code = verify_guild_access(guild_id, discord_token, user_guilds_only=True)
        if not success:
          return jsonify(guild), status_code

        # Get form data
        data = request.get_json()
        threshold = int(data.get("threshold", 0))
        reward = data.get("reward", "").strip()
        description = data.get("description", "Reached milestone").strip()

        if threshold <= 0 or not reward:
            return jsonify({"success": False, "message": "Invalid input data"}), 400

        # Validate role if it's a role ID
        if reward.isdigit():
            try:
                roles_response = requests_session.get(f"{API_BASE}/guilds/{guild_id}/roles", headers={"Authorization": f"Bot {BOT_TOKEN}"})
                if roles_response.status_code == 200:
                    roles = roles_response.json()
                    role_exists = any(role['id'] == reward for role in roles)
                    if not role_exists:
                        return jsonify({"success": False, "message": "Role ID does not exist in this server"}), 400
            except Exception:
                return jsonify({"success": False, "message": "Could not validate role"}), 500

        # Save to database
        ref = db.reference(f"/Milestones/{guild_id}")
        milestone_data = {
            "threshold": threshold,
            "reward": reward,
            "description": description
        }
        ref.push().set(milestone_data)

        # Award to existing users who meet the threshold (similar to bot logic)
        try:
            import time
            
            # Helper function to get guild-specific mora
            def get_guild_mora(user_data, guild_id):
                if isinstance(user_data, dict):
                    return user_data.get(str(guild_id), 0)
                return 0
            
            count = 0
            mora_ref = db.reference("/Mora")
            all_users = mora_ref.get() or {}

            for user_id, user_data in all_users.items():
                guild_mora = get_guild_mora(user_data, str(guild_id))
                if guild_mora >= threshold:
                    # Check if the user already has this reward in this guild
                    inventory_ref = db.reference("/User Events Inventory")
                    inventories = inventory_ref.get() or {}
                    has_reward = False
                    
                    for inv_key, inv_data in inventories.items():
                        if inv_data.get("User ID") == user_id:
                            for item in inv_data.get("Items", []):
                                if len(item) >= 4 and item[0] == reward and str(item[3]) == str(guild_id):
                                    has_reward = True
                                    break
                            if has_reward:
                                break
                    
                    if not has_reward:
                        count += 1
                        # Prepare item data
                        item_data = [
                            reward, 
                            description,
                            0,  # Cost (free for milestones)
                            int(guild_id),
                            int(time.time())
                        ]
                        
                        # Update inventory
                        found = False
                        for inv_key, inv_data in inventories.items():
                            if inv_data.get("User ID") == user_id:
                                items = inv_data.get("Items", [])
                                items.append(item_data)
                                inventory_ref.child(inv_key).update({"Items": items})
                                found = True
                                break
                                
                        if not found:
                            inventory_data = {"User ID": user_id, "Items": [item_data]}
                            inventory_ref.push().set(inventory_data)

            message = f"Milestone added successfully! Automatically awarded to {count} existing users who qualified."
        except Exception as e:
            print(f"Error awarding milestone to existing users: {e}")
            message = "Milestone added successfully!"

        return jsonify({"success": True, "message": message})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@minigames.route("/api/configure/<guild_id>/milestones/delete", methods=["POST"])
def api_delete_milestone(guild_id):
    """Delete a milestone"""
    if "discord_token" not in session:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    try:
        # Verify access
        discord_token = session['discord_token']
        
        success, guild, status_code = verify_guild_access(guild_id, discord_token, user_guilds_only=True)
        if not success:
          return jsonify(guild), status_code

        data = request.get_json()
        milestone_id = data.get("id", "").strip()

        if not milestone_id:
            return jsonify({"success": False, "message": "Milestone ID is required"}), 400

        # Delete from database
        ref = db.reference(f"/Milestones/{guild_id}")
        milestone_ref = ref.child(milestone_id)
        
        # Check if milestone exists
        if not milestone_ref.get():
            return jsonify({"success": False, "message": "Milestone not found"}), 404
            
        milestone_ref.delete()

        return jsonify({"success": True, "message": "Milestone deleted successfully"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@minigames.route("/api/configure/<guild_id>/milestones/edit", methods=["POST"])
def api_edit_milestone(guild_id):
    """Edit a milestone"""
    if "discord_token" not in session:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    try:
        # Verify access
        discord_token = session['discord_token']

        success, guild, status_code = verify_guild_access(guild_id, discord_token, user_guilds_only=True)
        if not success:
          return jsonify(guild), status_code

        data = request.get_json()
        milestone_id = data.get("id", "").strip()
        threshold = int(data.get("threshold", 0))
        reward = data.get("reward", "").strip()
        description = data.get("description", "Reached milestone").strip()

        if not milestone_id or threshold <= 0 or not reward:
            return jsonify({"success": False, "message": "Invalid input data"}), 400

        # Validate role if it's a role ID
        if reward.isdigit():
            try:
                roles_response = requests_session.get(f"{API_BASE}/guilds/{guild_id}/roles", headers={"Authorization": f"Bot {BOT_TOKEN}"})
                if roles_response.status_code == 200:
                    roles = roles_response.json()
                    role_exists = any(role['id'] == reward for role in roles)
                    if not role_exists:
                        return jsonify({"success": False, "message": "Role ID does not exist in this server"}), 400
            except Exception:
                return jsonify({"success": False, "message": "Could not validate role"}), 500

        # Update in database
        ref = db.reference(f"/Milestones/{guild_id}")
        milestone_ref = ref.child(milestone_id)
        
        # Check if milestone exists
        if not milestone_ref.get():
            return jsonify({"success": False, "message": "Milestone not found"}), 404
            
        milestone_data = {
            "threshold": threshold,
            "reward": reward,
            "description": description
        }
        milestone_ref.set(milestone_data)

        return jsonify({"success": True, "message": "Milestone updated successfully"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@minigames.route("/configure/<guild_id>/minigames/edit/<channel_id>")
def edit_minigames_channel(guild_id, channel_id):
    """Edit minigames configuration for a specific channel"""
    if "discord_token" not in session:
        return redirect("/")

    # Get message parameter for success/error messages  
    message = request.args.get('message', '')

    content = f"""
      <main class="p-6 max-w-4xl mx-auto">
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

        {f'<div class="bg-green-100 dark:bg-green-900 border border-green-400 dark:border-green-600 text-green-700 dark:text-green-300 px-4 py-3 rounded mb-4">{message.replace("+", " ")}</div>' if message else ''}

        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow dark:shadow-gray-700 p-6">
          <div id="channel-header">
            <div class="animate-pulse bg-gray-200 dark:bg-gray-600 h-6 w-64 rounded mb-4"></div>
          </div>
          
          <div id="edit-form-container">
            {create_loading_container("Loading configuration...", "flex flex-col items-center justify-center py-12")}
          </div>
        </div>
      </main>

      <script>
        // Load guild header and edit form data
        fetch('/api/configure/{guild_id}/minigames/edit/{channel_id}/info')
          .then(response => response.json())
          .then(data => {{
            if (data.error) {{
              document.querySelector('main').innerHTML = 
                '<div class="p-6 max-w-4xl mx-auto text-center"><h1 class="text-2xl font-bold text-red-600 dark:text-red-400 mb-4">Error</h1><p class="text-gray-600 dark:text-gray-300">' + data.error + '</p></div>';
              return;
            }}
            
            // Update header
            document.getElementById('guild-header').innerHTML = data.header;
            
            // Update channel header
            document.getElementById('channel-header').innerHTML = data.channelHeader;
            
            // Update form
            document.getElementById('edit-form-container').innerHTML = data.form;
          }})
          .catch(error => {{
            console.error('Error loading edit info:', error);
            document.querySelector('main').innerHTML = 
              '<div class="p-6 max-w-4xl mx-auto text-center"><h1 class="text-2xl font-bold text-red-600 dark:text-red-400 mb-4">Error</h1><p class="text-gray-600 dark:text-gray-300">Failed to load page. Please refresh.</p></div>';
          }});

        // Toggle games functionality
        function toggleGame(letter) {{
          const checkbox = document.getElementById('game-' + letter);
          const card = checkbox.closest('.game-card');
          
          if (checkbox.checked) {{
            card.classList.remove('opacity-50');
            card.classList.add('border-green-500', 'dark:border-green-400');
          }} else {{
            card.classList.add('opacity-50');
            card.classList.remove('border-green-500', 'dark:border-green-400');
          }}
        }}

        // Bulk toggle functionality
        function toggleAll(enable) {{
          const checkboxes = document.querySelectorAll('input[name="enabled_games[]"]');
          checkboxes.forEach(checkbox => {{
            checkbox.checked = enable;
            toggleGame(checkbox.value);
          }});
        }}
      </script>
    """

    return wrap_page("Edit Minigames", content, [(f"/configure/{guild_id}/minigames", "Back to Minigames", "text-blue-500 dark:text-blue-400 font-medium hover:underline")])

@minigames.route("/api/configure/<guild_id>/minigames/edit/<channel_id>/info")
def api_edit_minigames_info(guild_id, channel_id):
    """API endpoint for edit minigames configuration data"""
    if "discord_token" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    try:
        # Extract session data before any threading
        discord_token = session['discord_token']
        
        # Verify guild access and permissions
        success, guild, status_code = verify_guild_access(guild_id, discord_token)
        if not success:
            return jsonify(guild), status_code

        def fetch_channel_info():
            try:
                response = requests_session.get(f"{API_BASE}/guilds/{guild_id}/channels", headers={"Authorization": f"Bot {BOT_TOKEN}"})
                if response.status_code == 200:
                    channels = response.json()
                    if isinstance(channels, list):
                        channel = next((c for c in channels if str(c['id']) == str(channel_id)), None)
                        if not channel:
                            raise ValueError("Channel not found")
                        return channel
                    else:
                        raise ValueError("Invalid response format from Discord API")
                else:
                    raise ValueError(f"Discord API error: {response.status_code}")
            except Exception as e:
                raise ValueError(f"Failed to fetch channel info: {str(e)}")
        
        def fetch_current_config():
            ref = db.reference("/Global Events System")
            events_data = ref.get()
            if events_data:
                for key, val in events_data.items():
                    if isinstance(val, dict) and str(val.get("Channel ID")) == str(channel_id):
                        return {
                            "frequency": val.get("Frequency", 100),
                            "events": val.get("Events", letterList.copy()),
                            "key": key
                        }
            return None

        # Execute data loading calls concurrently
        with ThreadPoolExecutor(max_workers=2) as executor:
            channel_future = executor.submit(fetch_channel_info)
            config_future = executor.submit(fetch_current_config)

            channel = channel_future.result()
            current_config = config_future.result()

        if not current_config:
            return jsonify({"error": "No minigames configuration found for this channel"}), 404

        icon = f"https://cdn.discordapp.com/icons/{guild['id']}/{guild['icon']}.png?size=128" if guild.get("icon") else ""

        # Generate guild header HTML
        header_html = f"""
        <div class="flex items-center gap-4 mb-6">
          {"<img src='"+icon+"' class='rounded-full w-20 h-20 shadow-md'>" if icon else "<div class='w-20 h-20 rounded-full bg-gray-200 dark:bg-gray-600 flex items-center justify-center text-gray-500 dark:text-gray-300 text-2xl font-bold'>"+html.escape(guild['name'][0])+"</div>"}
          <div>
            <h2 class="text-2xl font-bold text-gray-900 dark:text-white">{html.escape(guild['name'])}</h2>
            <p class="text-gray-500 dark:text-gray-400">ID: {guild['id']}</p>
          </div>
        </div>
        """

        # Generate channel header
        channel_header_html = f"""
        <h3 class="text-xl font-semibold text-gray-900 dark:text-white mb-2">Configure Minigames for #{channel['name']}</h3>
        <p class="text-gray-600 dark:text-gray-300">Customize the frequency and select which games are enabled for this channel.</p>
        """

        # Generate frequency options
        frequency_options = "".join([
            f'<option value="{f["value"]}" {"selected" if str(current_config["frequency"]) == f["value"] else ""}>{f["name"]}</option>'
            for f in frequency_choices
        ])

        # Generate game selection grid
        enabled_events = set(current_config["events"])
        games_html = ""
        
        for i, (letter, emoji, title) in enumerate(zip(letterList, letter_emojis, minigame_titles)):
            is_enabled = letter in enabled_events
            card_classes = "game-card border-2 rounded-lg p-4 transition-all cursor-pointer hover:shadow-md"
            if is_enabled:
                card_classes += " border-green-500 dark:border-green-400"
            else:
                card_classes += " border-gray-200 dark:border-gray-600 opacity-50"
            
            games_html += f"""
            <div class="{card_classes}">
              <label for="game-{letter}" class="flex items-center space-x-3 cursor-pointer">
                <input type="checkbox" 
                       id="game-{letter}" 
                       name="enabled_games[]" 
                       value="{letter}" 
                       {"checked" if is_enabled else ""}
                       onchange="toggleGame('{letter}')"
                       class="w-5 h-5 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 dark:focus:ring-blue-600 dark:ring-offset-gray-800 focus:ring-2 dark:bg-gray-700 dark:border-gray-600">
                <span class="text-2xl pointer-events-none">{emoji}</span>
                <span class="text-sm font-medium text-gray-900 dark:text-white flex-1 pointer-events-none">{title}</span>
              </label>
            </div>
            """

        # Generate the complete form
        form_html = f"""
        <form method="POST" action="/configure/{guild_id}/minigames/edit/{channel_id}/save" class="space-y-6">
          <div>
            <label for="frequency" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Event Frequency
            </label>
            <select name="frequency" id="frequency" required class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white">
              {frequency_options}
            </select>
            <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Current setting: {100//current_config['frequency']}% chance per message
            </p>
          </div>

          <div>
            <div class="flex justify-between items-center mb-4">
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300">
                Enabled Games ({len(enabled_events)}/{len(minigame_titles)})
              </label>
              <div class="space-x-2">
                <button type="button" onclick="toggleAll(true)" class="px-3 py-1 text-xs bg-green-500 hover:bg-green-600 text-white rounded">
                  Enable All
                </button>
                <button type="button" onclick="toggleAll(false)" class="px-3 py-1 text-xs bg-red-500 hover:bg-red-600 text-white rounded">
                  Disable All
                </button>
              </div>
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 max-h-96 overflow-y-auto border border-gray-200 dark:border-gray-600 rounded-lg p-4">
              {games_html}
            </div>
          </div>

          <div class="flex gap-4">
            <button type="submit" class="flex-1 py-3 px-4 bg-blue-500 hover:bg-blue-600 dark:bg-blue-600 dark:hover:bg-blue-700 text-white font-medium rounded-md transition">
              Save Changes
            </button>
            <a href="/configure/{guild_id}/minigames" class="flex-1 py-3 px-4 bg-gray-500 hover:bg-gray-600 dark:bg-gray-600 dark:hover:bg-gray-700 text-white font-medium rounded-md text-center transition">
              Cancel
            </a>
          </div>
        </form>
        """

        return jsonify({
            "header": header_html,
            "channelHeader": channel_header_html,
            "form": form_html
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@minigames.route("/configure/<guild_id>/minigames/edit/<channel_id>/save", methods=["POST"])
def save_minigames_config(guild_id, channel_id):
    """Save minigames configuration for a channel"""
    if "discord_token" not in session:
        return redirect("/")

    try:
        # Verify access
        discord_token = session['discord_token']
        success, guild, status_code = verify_guild_access(guild_id, discord_token, user_guilds_only=True)
        
        if not success:
            return redirect(f"/configure/{guild_id}/minigames?message=Access+denied")

        frequency = int(request.form.get("frequency"))
        enabled_games = request.form.getlist("enabled_games[]")

        # Find existing configuration in database
        ref = db.reference("/Global Events System")
        events_data = ref.get()
        
        config_key = None
        if events_data:
            for key, val in events_data.items():
                if isinstance(val, dict) and str(val.get("Channel ID")) == str(channel_id):
                    config_key = key
                    break

        if not config_key:
            return redirect(f"/configure/{guild_id}/minigames/edit/{channel_id}?message=Configuration+not+found")

        # Ensure at least one game is enabled
        if not enabled_games:
            return redirect(f"/configure/{guild_id}/minigames/edit/{channel_id}?message=At+least+one+game+must+be+enabled")

        # Update the configuration
        updated_data = {
            "Channel ID": int(channel_id),
            "Frequency": frequency,
            "Events": enabled_games,
        }

        ref.child(config_key).set(updated_data)

        return redirect(f"/configure/{guild_id}/minigames/edit/{channel_id}?message=Configuration+saved+successfully")

    except Exception as e:
        return redirect(f"/configure/{guild_id}/minigames/edit/{channel_id}?message=Error:+{str(e)}")

# Additional utility routes for enhanced functionality

@minigames.route("/api/configure/<guild_id>/minigames/stats")
def api_minigames_stats(guild_id):
    """API endpoint for minigames statistics"""
    if "discord_token" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    try:
        # Verify access
        discord_token = session['discord_token']
        
        success, guild, status_code = verify_guild_access(guild_id, discord_token, user_guilds_only=True)
        if not success:
          return jsonify(guild), status_code

        # Get minigames data
        ref = db.reference("/Global Events System")
        events_data = ref.get()
        
        # Get guild channels to verify they belong to this guild
        try:
            response = requests_session.get(f"{API_BASE}/guilds/{guild_id}/channels", headers={"Authorization": f"Bot {BOT_TOKEN}"})
            if response.status_code == 200:
                channels = response.json()
                if isinstance(channels, list):
                    guild_channel_ids = {str(c['id']) for c in channels if c.get('type') == 0}
                else:
                    return jsonify({"error": "Invalid response format from Discord API"}), 500
            else:
                return jsonify({"error": f"Discord API error: {response.status_code}"}), 500
        except Exception as e:
            return jsonify({"error": f"Failed to fetch channels: {str(e)}"}), 500
        
        total_channels = 0
        total_enabled_games = 0
        frequency_distribution = {}
        
        if events_data:
            for key, val in events_data.items():
                if isinstance(val, dict) and str(val.get("Channel ID")) in guild_channel_ids:
                    total_channels += 1
                    total_enabled_games += len(val.get("Events", []))
                    freq = val.get("Frequency", 100)
                    freq_name = next((f["name"] for f in frequency_choices if f["value"] == str(freq)), f"Custom ({100//freq}%)")
                    frequency_distribution[freq_name] = frequency_distribution.get(freq_name, 0) + 1

        return jsonify({
            "totalChannels": total_channels,
            "totalEnabledGames": total_enabled_games,
            "averageGamesPerChannel": round(total_enabled_games / total_channels, 1) if total_channels > 0 else 0,
            "frequencyDistribution": frequency_distribution
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500