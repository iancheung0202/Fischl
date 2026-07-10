from firebase_admin import db
from concurrent.futures import ThreadPoolExecutor
from flask import Blueprint, request, session, redirect, jsonify
import time
import html
import psycopg2

from config.settings import API_BASE, BOT_TOKEN, MORA_EMOTE, POSTGRES_HOST, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
from utils.request import requests_session, verify_guild_access
from utils.theme import wrap_page
from utils.loading import create_loading_skeleton, create_async_script, create_loading_container, create_empty_content
from utils.minigames import get_db_connection

def process_pending_shop_edits(guild_id):
    """Process any pending scheduled shop edits"""
    try:
        current_time = time.time()
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, description, cost, multiple, stock, pending_stock_change, pending_scheduled_time
            FROM minigame_rewards
            WHERE gid = %s AND item_type = 'shop_item'
              AND pending_scheduled_time IS NOT NULL AND pending_scheduled_time <= %s
        """, (int(guild_id), current_time))
        
        rows = cursor.fetchall()
        processed_count = 0
        
        for row in rows:
            item_id, name, desc, cost, multiple, current_stock, stock_change, scheduled_time = row
            
            print(f"Processing edit for item {name} in guild {guild_id}")
            
            if stock_change.startswith(('+', '-')):
                if current_stock == -1:
                    current_stock = 0
                try:
                    change = int(stock_change)
                    new_stock = current_stock + change
                except ValueError:
                    sign = stock_change[0]
                    num_str = stock_change[1:].strip()
                    num = int(num_str) if num_str else 0
                    new_stock = current_stock + num if sign == '+' else current_stock - num
            else:
                try:
                    new_stock = int(stock_change)
                except ValueError:
                    print(f"Invalid stock value: {stock_change}")
                    continue
            
            if new_stock < -1:
                new_stock = 0
            
            cursor.execute(
                "UPDATE minigame_rewards SET stock = %s, pending_stock_change = NULL, pending_scheduled_time = NULL WHERE id = %s",
                (new_stock, item_id)
            )
            processed_count += 1
            print(f"Updated stock for {name} from {current_stock} to {new_stock}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
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
    "Group Blackjack",
    "Teyvat Emoji Riddles",
    "Galaxy Emoji Riddles",
    "Double or Keep",
    "Know Your Members",
    "Hangman",
    "Mora Auction House",
    "Mora Heist",
    "Simple Math Game",
    "Tik Tac Tok"
]

letter_emojis = [ "🇦", "🇧", "🇨", "🇩", "🇪", "🇫", "🇬", "🇭", "🇮", "🇯", "🇰", "🇱", "🇲", "🇳", "🇴", "🇵", "🇶", "🇷", "🇸", "🇹", "🇺", "🇻", "🇼", "🇽", "🇾", "🇿" ] 
letterList = [ "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z" ]

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

        <!-- Minigames Configuration Info -->
        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow dark:shadow-gray-700 p-6 mb-6">
          <h3 class="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Minigames Configuration</h3>
          <div class="bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-700 rounded-xl p-6 text-center">
            <p class="text-gray-700 dark:text-gray-300 text-lg mb-2">
              <b>This area is under construction.</b> Use <code class="bg-gray-200 dark:bg-gray-700 px-2 py-0.5 rounded font-mono text-sm">/events settings</code>, <code class="bg-gray-200 dark:bg-gray-700 px-2 py-0.5 rounded font-mono text-sm">/shop</code>, or <code class="bg-gray-200 dark:bg-gray-700 px-2 py-0.5 rounded font-mono text-sm">/milestones</code> <b>slash command on Discord to configure everything with ease for now.</b>
            </p>
          </div>
        </div>

        <!-- Shop Management Section -->
        <div class="mt-12" style="display: none !important; visibility: hidden !important;">
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
        <div class="mt-12" style="display: none !important; visibility: hidden !important;">
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
                    
                    const linkHtml = purchase.link ? `
                      <a href="${{purchase.link}}" target="_blank" class="absolute top-3 right-3 text-gray-400 hover:text-blue-500 dark:hover:text-blue-400 transition-colors z-10" title="View original purchase message">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path>
                        </svg>
                      </a>
                    ` : '';
                    
                    const purchaseHtml = `
                      <div class="border border-gray-200 dark:border-gray-600 rounded-lg p-4 mb-3 bg-gray-50 dark:bg-gray-700 relative">
                        ${{linkHtml}}
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
        with ThreadPoolExecutor(max_workers=2) as executor:
            channels_future = executor.submit(fetch_guild_channels)
            roles_future = executor.submit(fetch_guild_roles)

            try:
                channels = channels_future.result()
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

        return jsonify({
            "header": header_html,
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
            "frequency": frequency,
            "events": letterList.copy(),  # Enable all games by default
        }

        ref = db.reference(f"/Chat Minigames System/{channel_id}")
        ref.set(data)

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
        ref = db.reference(f"/Chat Minigames System/{channel_id}")
        if ref.get():
            ref.delete()
            return jsonify({"success": True, "message": "Configuration deleted successfully"})
        else:
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
        pending_by_item = {}
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, name, description, cost, multiple, stock, pending_stock_change, pending_scheduled_time "
                "FROM minigame_rewards WHERE gid = %s AND item_type = 'shop_item' AND pending_stock_change IS NOT NULL "
                "ORDER BY pending_scheduled_time",
                (int(guild_id),)
            )
            for row in cursor.fetchall():
                item_id, name, desc, cost, multiple, stock, stock_change, sched = row
                item_key = str(name)
                if item_key not in pending_by_item:
                    pending_by_item[item_key] = []
                pending_by_item[item_key].append({
                    "item_identifier": name,
                    "stock_change": stock_change,
                    "scheduled_time": sched,
                    "edit_key": str(item_id)
                })
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Error fetching pending edits: {e}")

        # Get shop items from database
        shop_items = []
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name, description, cost, multiple, stock FROM minigame_rewards WHERE gid = %s AND item_type = 'shop_item' ORDER BY id",
                (int(guild_id),)
            )
            for row in cursor.fetchall():
                item_data = {
                    "name": row[0],
                    "description": row[1],
                    "cost": row[2],
                    "multiple": row[3],
                    "stock": row[4]
                }
                
                # Add role info if it's a role ID
                if str(row[0]).isdigit() and str(row[0]) in guild_roles:
                    item_data["role"] = guild_roles[str(row[0])]
                
                # Add pending edits info if any exist for this item
                item_data["pending_edits"] = pending_by_item.get(str(row[0]), [])
                
                shop_items.append(item_data)
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Error fetching shop items: {e}")

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

        # Check for duplicates
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM minigame_rewards WHERE gid = %s AND item_type = 'shop_item' AND name = %s",
                (int(guild_id), str(name))
            )
            if cursor.fetchone():
                cursor.close()
                conn.close()
                return jsonify({"success": False, "message": "Item with this name/role already exists"}), 400
            cursor.close()
            conn.close()
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500

        # Insert new item
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO minigame_rewards (gid, item_type, name, description, cost, multiple, stock) VALUES (%s, 'shop_item', %s, %s, %s, %s, %s)",
                (int(guild_id), str(name), str(description), str(cost), bool(multiple), int(stock_val))
            )
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500

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

        # Find and remove the item, capture its cost before deleting
        item_cost = 0
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT cost FROM minigame_rewards WHERE gid = %s AND item_type = 'shop_item' AND name = %s",
                (int(guild_id), str(item_name))
            )
            row = cursor.fetchone()
            if not row:
                cursor.close()
                conn.close()
                return jsonify({"success": False, "message": "Item not found"}), 404
            item_cost = int(row[0])
            cursor.execute(
                "DELETE FROM minigame_rewards WHERE gid = %s AND item_type = 'shop_item' AND name = %s",
                (int(guild_id), str(item_name))
            )
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500

        # Handle compensation if requested
        if compensate:
            try:
                compensated_users = 0
                
                conn = get_db_connection()
                cursor = conn.cursor()

                # Query to get affected users and their item count
                cursor.execute("""
                    SELECT uid, COUNT(*) as items_removed
                    FROM minigame_inventory
                    WHERE title = %s AND gid = %s
                    GROUP BY uid
                """, (str(item_name), int(guild_id)))
                
                affected_users = cursor.fetchall()
                
                # Delete all items matching this reward
                cursor.execute(
                    "DELETE FROM minigame_inventory WHERE title = %s AND gid = %s",
                    (str(item_name), int(guild_id))
                )
                
                # Add compensation mora for each affected user
                for user_id, items_removed in affected_users:
                    compensation = item_cost * items_removed
                    ts = int(time.time())
                    cursor.execute(
                        "INSERT INTO minigame_mora (uid, gid, cid, timestamp, count) VALUES (%s, %s, %s, %s, %s)",
                        (user_id, guild_id, 0, ts, compensation)
                    )
                    compensated_users += 1
                
                conn.commit()
                cursor.close()
                conn.close()
                
                message = f"Item deleted successfully. Compensated {compensated_users} users with {item_cost:,} Mora each."
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
            
            # Get current item from database
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name, description, cost, multiple, stock FROM minigame_rewards WHERE gid = %s AND item_type = 'shop_item' AND name = %s",
                    (int(guild_id), str(old_name))
                )
                current_row = cursor.fetchone()
                if not current_row:
                    cursor.close()
                    conn.close()
                    return jsonify({"success": False, "message": "Item not found"}), 404
                cursor.close()
                conn.close()
            except Exception as e:
                return jsonify({"success": False, "message": str(e)}), 500
            
            # Check if only stock is changing
            only_stock = (
                current_row[0] == new_name and
                str(current_row[1]) == str(description) and
                str(current_row[2]) == str(cost) and
                bool(current_row[3]) == bool(multiple)
            )
            
            if only_stock:
                # Handle stock-only change
                if stock and str(stock).strip():
                    stock_str = str(stock).strip()
                    
                    if stock_str.startswith(('+', '-')):
                        try:
                            int(stock_str[1:]) if stock_str[1:] else 0
                            stock_change = stock_str
                        except ValueError:
                            return jsonify({"success": False, "message": "Invalid relative stock change format"}), 400
                    else:
                        try:
                            stock_val = int(stock_str)
                            stock_change = "-1" if stock_val < 0 else str(stock_val)
                        except ValueError:
                            return jsonify({"success": False, "message": "Invalid stock value"}), 400
                else:
                    stock_change = "-1"
                
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE minigame_rewards SET pending_stock_change = %s, pending_scheduled_time = %s WHERE gid = %s AND item_type = 'shop_item' AND name = %s",
                        (stock_change, float(scheduled_time), int(guild_id), str(old_name))
                    )
                    conn.commit()
                    cursor.close()
                    conn.close()
                except Exception as e:
                    return jsonify({"success": False, "message": str(e)}), 500
                
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

        # Update item in database
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Check if new name conflicts with existing items (unless it's the same item)
            if old_name != new_name:
                cursor.execute(
                    "SELECT id FROM minigame_rewards WHERE gid = %s AND item_type = 'shop_item' AND name = %s",
                    (int(guild_id), str(new_name))
                )
                if cursor.fetchone():
                    cursor.close()
                    conn.close()
                    return jsonify({"success": False, "message": "Item with this name/role already exists"}), 400
            
            cursor.execute(
                "UPDATE minigame_rewards SET name = %s, description = %s, cost = %s, multiple = %s, stock = %s WHERE gid = %s AND item_type = 'shop_item' AND name = %s",
                (str(new_name), str(description), str(cost), bool(multiple), int(stock_val), int(guild_id), str(old_name))
            )
            if cursor.rowcount == 0:
                cursor.close()
                conn.close()
                return jsonify({"success": False, "message": "Item not found"}), 404
            
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500

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

        # Clear the pending edit on the reward row (edit_key is the item id)
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE minigame_rewards SET pending_stock_change = NULL, pending_scheduled_time = NULL WHERE id = %s AND gid = %s",
                (int(edit_key), int(guild_id))
            )
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500

        return jsonify({"success": True, "message": "Pending edit deleted successfully"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@minigames.route("/api/configure/<guild_id>/shop/purchase-history", methods=["GET"])
def api_shop_purchase_history(guild_id):
    """API endpoint for shop purchase history with pagination from PostgreSQL"""
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

        # Query PostgreSQL for purchase history (cost != 0 excludes milestones)
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT uid, title, description, cost, timestamp, link
            FROM minigame_inventory
            WHERE gid = %s AND cost != 0
            ORDER BY timestamp DESC
            LIMIT %s OFFSET %s
        """, (int(guild_id), limit, offset))

        purchases_rows = cursor.fetchall()

        cursor.execute("""
            SELECT COUNT(*)
            FROM minigame_inventory
            WHERE gid = %s AND cost != 0
        """, (int(guild_id),))
        total_purchases = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        # Get unique user IDs for this page
        user_ids = list(set(str(row[0]) for row in purchases_rows))

        # Fetch user information from Discord API
        user_data = {}
        if user_ids:
            try:
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
        for row in purchases_rows:
            uid, title, description, cost, timestamp, link = row
            uid_str = str(uid)
            user_info = user_data.get(uid_str, {'username': 'Unknown User'})

            enhanced_purchases.append({
                'user_id': uid_str,
                'username': user_info.get('username', 'Unknown User'),
                'discriminator': user_info.get('discriminator'),
                'avatar': user_info.get('avatar'),
                'global_name': user_info.get('global_name'),
                'item_name': title,
                'item_description': description or '',
                'cost': cost,
                'timestamp': int(timestamp.timestamp()) if hasattr(timestamp, 'timestamp') else int(timestamp),
                'link': link or ''
            })

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
        milestones_data = []
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, description, name, threshold FROM minigame_rewards WHERE gid = %s AND item_type = 'milestone' ORDER BY id",
                (int(guild_id),)
            )
            milestones_data = cursor.fetchall()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Error fetching milestones: {e}")
        
        # Parse milestones
        milestones = []
        for row in milestones_data:
            db_id, description, reward, threshold = row
            milestone_info = {
                "id": str(db_id),
                "description": description,
                "reward": reward,
                "threshold": threshold
            }
            
            # Add role info if it's a role ID
            if str(reward).isdigit() and str(reward) in guild_roles:
                milestone_info["role"] = guild_roles[str(reward)]
            
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
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO minigame_rewards (gid, item_type, name, description, threshold) VALUES (%s, 'milestone', %s, %s, %s)",
                (int(guild_id), str(reward), str(description), int(threshold))
            )
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500

        # Award to existing users who meet the threshold (similar to bot logic)
        try:
            import time
            
            count = 0
            # Get qualified users from PostgreSQL
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT uid, SUM(count) as total
                    FROM minigame_mora
                    WHERE gid = %s
                    GROUP BY uid
                    HAVING SUM(count) >= %s
                """, (guild_id, threshold))
                qualified_users = [(row[0], row[1]) for row in cursor.fetchall()]
                cursor.close()
                conn.close()
            except Exception as db_error:
                print(f"Error querying PostgreSQL: {db_error}")
                qualified_users = []

            for user_id, mora_total in qualified_users:
                # Check if the user already has this reward in this guild
                conn = get_db_connection()
                cursor = conn.cursor()
                
                cursor.execute(
                    "SELECT COUNT(*) FROM minigame_inventory WHERE uid = %s AND gid = %s AND title = %s",
                    (user_id, guild_id, reward)
                )
                has_reward = cursor.fetchone()[0] > 0
                
                if not has_reward:
                    count += 1
                    # Prepare item data and insert into PostgreSQL
                    ts = int(time.time())
                    cursor.execute(
                        "INSERT INTO minigame_inventory (uid, gid, title, description, cost, timestamp, pinned) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                        (user_id, guild_id, reward, description, 0, ts, False)
                    )
                    conn.commit()
                
                cursor.close()
                conn.close()

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
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM minigame_rewards WHERE id = %s AND gid = %s AND item_type = 'milestone'",
                (int(milestone_id), int(guild_id))
            )
            if cursor.rowcount == 0:
                cursor.close()
                conn.close()
                return jsonify({"success": False, "message": "Milestone not found"}), 404
            conn.commit()
            cursor.close()
            conn.close()
            
            return jsonify({"success": True, "message": "Milestone deleted successfully"})
        except (ValueError, Exception) as e:
            return jsonify({"success": False, "message": str(e)}), 400

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
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE minigame_rewards SET name = %s, description = %s, threshold = %s WHERE id = %s AND gid = %s AND item_type = 'milestone'",
                (str(reward), str(description), int(threshold), int(milestone_id), int(guild_id))
            )
            if cursor.rowcount == 0:
                cursor.close()
                conn.close()
                return jsonify({"success": False, "message": "Milestone not found"}), 404
            conn.commit()
            cursor.close()
            conn.close()
            
            return jsonify({"success": True, "message": "Milestone updated successfully"})
        except (ValueError, Exception) as e:
            return jsonify({"success": False, "message": str(e)}), 400

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
            ref = db.reference(f"/Chat Minigames System/{channel_id}")
            val = ref.get()
            if val and isinstance(val, dict):
                return {
                    "frequency": val.get("frequency", 100),
                    "events": val.get("events", letterList.copy()),
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

        # Ensure at least one game is enabled
        if not enabled_games:
            return redirect(f"/configure/{guild_id}/minigames/edit/{channel_id}?message=At+least+one+game+must+be+enabled")

        # Update the configuration
        ref = db.reference(f"/Chat Minigames System/{channel_id}")
        updated_data = {
            "frequency": frequency,
            "events": enabled_games,
        }
        ref.set(updated_data)

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
        ref = db.reference("/Chat Minigames System")
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
            for channel_id, val in events_data.items():
                if str(channel_id) in guild_channel_ids and isinstance(val, dict):
                    total_channels += 1
                    total_enabled_games += len(val.get("events", []))
                    freq = val.get("frequency", 100)
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