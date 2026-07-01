import discord

CURRENCY_NAME = "Mora"

MORA_EMOTE = "<:MORA:1364030973611610205>"
YES_EMOTE = "<:yes:1036811164891480194>"    
NO_EMOTE = "<:no:1036810470860013639>"
RESOLVED_EMOTE = "<:resolved:1364813186028797984>"
UNRESOLVED_EMOTE = "<:yae_hi:1364813223307645000>"
HMM_EMOTE = "<:DW_elhmm:971735422147379200>"
THINK_EMOTE = "<:Paimon_Think:1414561896299888700>"
NO_STOCK_EMOTE = "<a:out_of_stock:1384990609584033812>"
LOADING_EMOTE = "<a:loading:1026905298088243240>"
SHRUG_EMOTE = "<:WrioShrug:1304094173795713114>"
HAPPY_EMOTE = "<a:NekoHappy:1335019855920758855>"
MONEYDANCE_EMOTE = "<a:moneydance:1227425759077859359>"
DOT_EMOTE = "<:dot:1357188726047899760>"

FRAMES_DIRECTORY = "./assets/Profile Frame"
INVENTORY_BG_PATH = "./assets/Mora Inventory Background"
ANIMATED_INVENTORY_BG_PATH = "./assets/Animated Mora Inventory Background"
DEFAULT_BG_PATH = "./assets/mora_bg.png"
FONT_PATH = "./assets/ja-jp.ttf"
PROFILE_CARD_PATH = "./assets/mora.png"
TYPERACER_BG_PATH = "./assets/F7E8BE.png"
TYPERACER_PATH = "./assets/typeracer.png"
CURRENCY_ICON_PATH = "./assets/mora_icon.png"

COSMETICS_DB = "/Chat Minigames Cosmetics"
REWARDS_DB = "/Chat Minigames Rewards"
CHEST_DB = "/Chat Minigames Chests"
SYSTEM_DB = "/Chat Minigames System"
QUEST_DB = "/Chat Minigames Quests"
HISTORY_DB = "/Mora Purchase History"
PACK_DB = "/Mora Drop Packs"
TRACK_PENDING_DB = "/Elite Track Pending"
SHOP_EDITS_PENDING_DB = "/Pending Shop Edits"

PRICE_UP_EMOTE = "<:price_ascending:1346329079145562112>"
PRICE_DOWN_EMOTE = "<:price_descending:1346329080462577725>"
NAME_UP_EMOTE = "<:name_ascending:1346329053455585324>"
NAME_DOWN_EMOTE = "<:name_descending:1346329054634053703>"
SHOP_SORT_OPTIONS = [("sort by cost (low to high)", PRICE_UP_EMOTE), ("sort by cost (high to low)", PRICE_DOWN_EMOTE), ("sort by name (a-z)", NAME_UP_EMOTE), ("sort by name (z-a)", NAME_DOWN_EMOTE),]
MILESTONE_SORT_OPTIONS = [("sort by threshold (low to high)", PRICE_UP_EMOTE), ("sort by threshold (high to low)", PRICE_DOWN_EMOTE), ("sort by name (a-z)", NAME_UP_EMOTE), ("sort by name (z-a)", NAME_DOWN_EMOTE),]


MORA_CHEST_NAME = "Daily Mora Chest"
MORA_CHEST_TIERS = ["Common", "Exquisite", "Precious", "Luxurious"]
MORA_CHEST_REWARDS = [2500, 7500, 15000, 30000]
MORA_CHEST_UPGRADE_CHANCES = [0.3, 0.15, 0.2]
MORA_CHEST_UPGRADE_TIMES = 4
MORA_CHEST_STREAK_BONUS = 100
MORA_CHEST_MAX_STREAK_BONUS = 10000
MORA_CHEST_SPAWN_REQ = (4, 6)
MORA_CHEST_TIMEOUT = 300 
MORA_TIER_MAP = dict(zip(MORA_CHEST_TIERS, MORA_CHEST_REWARDS))
EMOTE_STREAK = "<a:streak:1371651844652273694>"
EMOTE_MAX_STREAK = "<a:max_streak:1371655286049214672>"
EMOTE_BLANK = "<:blank:1036792889121980426>" 
EMOTE_CHESTS = {MORA_CHEST_TIERS[0]: "<a:common:1371641883121680465>", MORA_CHEST_TIERS[1]: "<a:exquisite:1371641856344985620>", MORA_CHEST_TIERS[2]: "<a:precious:1371641871452995689>", MORA_CHEST_TIERS[3]: "<a:luxurious:1371641841338023976>"}
MORA_CHEST_ICONS = {MORA_CHEST_TIERS[0]: "https://i.imgur.com/2kOfLSC.png", MORA_CHEST_TIERS[1]: "https://i.imgur.com/DBPQSAu.png", MORA_CHEST_TIERS[2]: "https://i.imgur.com/zxOlrCo.png", MORA_CHEST_TIERS[3]: "https://i.imgur.com/5nWwRdc.png"}
MORA_CHEST_DESCRIPTION = f"""## How the {MORA_CHEST_NAME} Works 🎁
{DOT_EMOTE} Earn a chest per day after sending **{MORA_CHEST_SPAWN_REQ[0]} to {MORA_CHEST_SPAWN_REQ[1]} effortful messages** in minigame channels.
{DOT_EMOTE} Messages must be spaced out and not repetitive/spammy.
{DOT_EMOTE} A chest starts as **{MORA_CHEST_TIERS[0]}**, containing {MORA_EMOTE} `{MORA_CHEST_REWARDS[0]:,}`.
{DOT_EMOTE} You get a minimum of **{MORA_CHEST_UPGRADE_TIMES} chances** to upgrade your chest.
{DOT_EMOTE} You must claim your chest within **{MORA_CHEST_TIMEOUT // 60} minutes** or it will be wasted.
{DOT_EMOTE} After claiming, wait until the next **UTC +0 midnight** to earn a new chest.
### Rewards (Base Mora) 🏆
{DOT_EMOTE} **{MORA_CHEST_TIERS[0]}**:   **`{MORA_CHEST_REWARDS[0]:,}`** Mora
{DOT_EMOTE} **{MORA_CHEST_TIERS[1]}**:   **`{MORA_CHEST_REWARDS[1]:,}`** Mora
{DOT_EMOTE} **{MORA_CHEST_TIERS[2]}**:   **`{MORA_CHEST_REWARDS[2]:,}`** Mora
{DOT_EMOTE} **{MORA_CHEST_TIERS[3]}**:   **`{MORA_CHEST_REWARDS[3]:,}`** Mora
### Upgrade Chances :arrow_up:  
{DOT_EMOTE} `{MORA_CHEST_TIERS[0]} → {MORA_CHEST_TIERS[1]}:   {MORA_CHEST_UPGRADE_CHANCES[0]*100:.0f}% chance`
{DOT_EMOTE} `{MORA_CHEST_TIERS[1]} → {MORA_CHEST_TIERS[2]}:   {MORA_CHEST_UPGRADE_CHANCES[1]*100:.0f}% chance`
{DOT_EMOTE} `{MORA_CHEST_TIERS[2]} → {MORA_CHEST_TIERS[3]}:   {MORA_CHEST_UPGRADE_CHANCES[2]*100:.0f}% chance`
### Streak Bonus {EMOTE_STREAK}
{DOT_EMOTE} You gain a **daily streak** if you claim a chest every day.
{DOT_EMOTE} Each day in your streak adds `+{MORA_CHEST_STREAK_BONUS}` {MORA_EMOTE} (max {MORA_CHEST_MAX_STREAK_BONUS}) to the reward.
{DOT_EMOTE} Miss a day? Your streak resets to 1."""

DOMAIN_NAME = "Immernachtreich Domain"
DOMAIN_DESCRIPTION = "Construct your eternal kingdom within the darkness."

BUILDINGS = {
    "schloss": {"name": "Schloss", "emoji": "🏰", "desc": "The royal castle.", "color": discord.ButtonStyle.blurple},
    "theater": {"name": "Theater", "emoji": "🎭", "desc": "Where tales are told.", "color": discord.ButtonStyle.grey},
    "bibliothek": {"name": "Bibliothek", "emoji": "📚", "desc": "Ancient wisdom.", "color": discord.ButtonStyle.success},
    "garten": {"name": "Garten", "emoji": "🌹", "desc": "Chance for double loot.", "color": discord.ButtonStyle.danger}
}

def get_rank_title(level):
    rank = "Subject"
    if level >= 10: rank = "Baron"
    if level >= 25: rank = "Viscount"
    if level >= 50: rank = "Earl"
    if level >= 75: rank = "Marquess"
    if level >= 100: rank = "Duke"
    if level >= 150: rank = "Archduke"
    if level >= 200: rank = "Prince"
    if level >= 300: rank = "Emperor"
    return rank

def calculate_cost(level):
    return int(5000 * (1.1 ** level))

def perk_info(key, lvl):
    if key == "schloss": 
        func_desc = "Command Center"
        perk_val = f"*(Max level for others)*"
    elif key == "theater": 
        func_desc = "Refund Summon"
        chance = min(50, lvl)
        perk_val = f"`{chance}%` chance"
    elif key == "bibliothek": 
        func_desc = "Quest XP Boost"
        boost = min(50, lvl)
        perk_val = f"`+{boost}%` XP"
    elif key == "garten": 
        func_desc = "Bonus Summon in Chest"
        chance = min(50, lvl)
        perk_val = f"`{chance}%` chance"
    return func_desc, perk_val

async def setup(bot):
    pass