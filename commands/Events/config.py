import discord
try:
    from utils.commands import SlashCommand
except ImportError:
    class SlashCommand:
        def __init__(self, name):
            self.name = name

        def __str__(self):
            return f"`/{self.name}`"

CURRENCY_NAME = "Mora"
MORA_EMOTE = "<:MORA:1364030973611610205>"

SIGIL_CURRENCY_NAME = "Sigils"
SIGIL_EMOTE = "<a:sigils:1402736987902967850>"

YES_EMOTE = "<:yes:1036811164891480194>"    
NO_EMOTE = "<:no:1036810470860013639>"
YES_EMOTE_2 = "<:BunnyYes:1224838535979204748>"
NO_EMOTE_2 = "<:BunnyNo:1224838553218060349>"
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
CONFUSED_EMOTE = "<:PinkConfused:1204614149628498010>"
REPLY_EMOTE = "<:reply:1036792837821435976>"

GUILD_MORA_EMOTE = MORA_EMOTE
GLOBAL_MORA_EMOTE = "<:global_mora:1525244303784542301>"
GUILD_SIGIL_EMOTE = SIGIL_EMOTE
GLOBAL_SIGIL_EMOTE = "<:global_sigils:1525244339213566102>"

MORA_TO_XP_RATIO = 0.01
SIGILS_TO_XP_RATIO = 1000

DEFAULT_CHAT_RANGE = (19, 25)
DEFAULT_CHAT_MAX_CAP = 60
DEFAULT_CHAT_MSG_RANGE = (15, 20)

BALANCE_COMMAND = "mora"
PROFILE_LINK_BUTTON = discord.ui.Button(label="Earn Daily Rewards", style=discord.ButtonStyle.link, url=f"https://fischl.app/profile", emoji="<a:legacy:1345876714240213073>", row=1, disabled=False)

FRAMES_DIRECTORY = "./assets/Profile Frame"
INVENTORY_BG_PATH = "./assets/Mora Inventory Background"
ANIMATED_INVENTORY_BG_PATH = "./assets/Animated Mora Inventory Background"
GRAPHS_DIRECTORY = "./assets/graph"
DEFAULT_BG_PATH = "./assets/mora_bg.png"
FONT_PATH = "./assets/ja-jp.ttf"
FONT_PRESETS = {
    "Default": FONT_PATH,
    "Arimo": "/usr/share/fonts/truetype/croscore/Arimo-Bold.ttf",
    "Cousine": "/usr/share/fonts/truetype/croscore/Cousine-Bold.ttf",
    "Tinos": "/usr/share/fonts/truetype/croscore/Tinos-Bold.ttf",
    "DejaVu Sans": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "DejaVu Serif": "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "DejaVu Sans Mono": "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "FreeMono": "/usr/share/fonts/truetype/freefont/FreeMonoBold.ttf",
    "FreeSans": "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "FreeSerif": "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf",
}
PROFILE_CARD_PATH = "./assets/mora.png"
TYPERACER_BG_PATH = "./assets/F7E8BE.png"
TYPERACER_PATH = "./assets/typeracer.png"
CURRENCY_ICON_PATH = "./assets/mora_icon.png"

PRICE_UP_EMOTE = "<:price_ascending:1346329079145562112>"
PRICE_DOWN_EMOTE = "<:price_descending:1346329080462577725>"
NAME_UP_EMOTE = "<:name_ascending:1346329053455585324>"
NAME_DOWN_EMOTE = "<:name_descending:1346329054634053703>"
SHOP_SORT_OPTIONS = [("sort by cost (low to high)", PRICE_UP_EMOTE), ("sort by cost (high to low)", PRICE_DOWN_EMOTE), ("sort by name (a-z)", NAME_UP_EMOTE), ("sort by name (z-a)", NAME_DOWN_EMOTE),]
SHOP_CURRENCY_FILTERS = [
    ("All currencies", "<:FischlRiot:1335609183885590629>"),
    ("Guild Mora", GUILD_MORA_EMOTE),
    ("Global Mora", GLOBAL_MORA_EMOTE),
    ("Guild Sigils", GUILD_SIGIL_EMOTE),
    ("Global Sigils", GLOBAL_SIGIL_EMOTE),
]
CURRENCY_INFO = {
    "guild_mora": {"emoji": GUILD_MORA_EMOTE, "label": "Guild Mora", "filter_label": "Guild Mora"},
    "global_mora": {"emoji": GLOBAL_MORA_EMOTE, "label": "Global Mora", "filter_label": "Global Mora"},
    "guild_sigils": {"emoji": GUILD_SIGIL_EMOTE, "label": "Guild Sigils", "filter_label": "Guild Sigils"},
    "global_sigils": {"emoji": GLOBAL_SIGIL_EMOTE, "label": "Global Sigils", "filter_label": "Global Sigils"},
}
MILESTONE_SORT_OPTIONS = [("sort by threshold (low to high)", PRICE_UP_EMOTE), ("sort by threshold (high to low)", PRICE_DOWN_EMOTE), ("sort by name (a-z)", NAME_UP_EMOTE), ("sort by name (z-a)", NAME_DOWN_EMOTE),]

DROP_TIERS = ["Tiny", "Small", "Medium", "Large", "Huge", "Mega"]
DROP_WEIGHTS = [0.3, 0.25, 0.2, 0.15, 0.08, 0.02]
DROP_AMOUNTS = {
    "Tiny": (500, 999),
    "Small": (1500, 2000),
    "Medium": (3000, 3500),
    "Large": (6000, 6700),
    "Huge": (9800, 10200),
    "Mega": (13000, 15000),
}
XP_BONUS_CHANCE = 0.2
BONUS_XP = 1000

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
def build_chest_description(gc: dict = None) -> str:
    if gc is None:
        gc = {}
    tier_names = gc.get("chests_tier_names", MORA_CHEST_TIERS)
    tier_rewards = gc.get("chests_tier_rewards", MORA_CHEST_REWARDS)
    upgrade_chances = gc.get("chests_upgrade_chances", MORA_CHEST_UPGRADE_CHANCES)
    spawn_req = gc.get("chests_spawn_req", list(MORA_CHEST_SPAWN_REQ))
    streak_bonus = gc.get("chests_streak_bonus", MORA_CHEST_STREAK_BONUS)
    max_streak = gc.get("chests_max_streak_bonus", MORA_CHEST_MAX_STREAK_BONUS)
    base_upgrades = gc.get("chests_base_upgrade_chances", MORA_CHEST_UPGRADE_TIMES)
    spawn_low = spawn_req[0] if len(spawn_req) > 0 else 4
    spawn_high = spawn_req[1] if len(spawn_req) > 1 else spawn_req[0]
    lines = [
        f"## How the {MORA_CHEST_NAME} Works 🎁",
        f"{DOT_EMOTE} Earn a chest per day after sending **{spawn_low} to {spawn_high} effortful messages** in minigame channels.",
        f"{DOT_EMOTE} Messages must be spaced out and not repetitive/spammy.",
        f"{DOT_EMOTE} A chest starts as **{tier_names[0] if tier_names else '?'}**, containing {MORA_EMOTE} `{tier_rewards[0]:,}`." if tier_rewards else "",
        f"{DOT_EMOTE} You get a minimum of **{base_upgrades} chances** to upgrade your chest.",
        f"{DOT_EMOTE} You must claim your chest within **{MORA_CHEST_TIMEOUT // 60} minutes** or it will be wasted.",
        f"{DOT_EMOTE} After claiming, wait until the next **UTC +0 midnight** to earn a new chest.",
        "### Rewards (Base Mora) 🏆",
    ]
    for i in range(len(tier_names)):
        r = tier_rewards[i] if i < len(tier_rewards) else 0
        lines.append(f"{DOT_EMOTE} **{tier_names[i]}**:   **`{r:,}`** Mora")
    lines.append("### Upgrade Chances :arrow_up:")
    for i in range(len(tier_names) - 1):
        c = upgrade_chances[i] * 100 if i < len(upgrade_chances) else 0
        lines.append(f"{DOT_EMOTE} `{tier_names[i]} \u2192 {tier_names[i+1]}: {c:.0f}% chance`")
    lines.append(f"### Streak Bonus {EMOTE_STREAK}")
    lines.append(f"{DOT_EMOTE} You gain a **daily streak** if you claim a chest every day.")
    lines.append(f"{DOT_EMOTE} Each day in your streak adds `+{streak_bonus}` {MORA_EMOTE} (max {max_streak}) to the reward.")
    lines.append(f"{DOT_EMOTE} Miss a day? Your streak resets to 1.")
    return "\n".join(l for l in lines if l)

VIEW_FULL_TRACK = f"| **[View Full Track](https://fischl.app/profile)**"
TIPS = [
    "Send effortful messages to earn daily mora chests 📦",
    f"Reach {SlashCommand('milestones')} to earn titles/roles! Check it out! 💎",
    f"Use {SlashCommand('customize')} to add a custom inventory background image & pin titles 🌆",
    f"Hug your favorite person(s) using {SlashCommand('hug')} 🫂",
    f"Check your inventory with {SlashCommand('mora')} with all your stats 🎉",
    f"Use {SlashCommand('gift')} to send Mora to your friends or even strangers! 🎁",
    f"Get FREE mora & minigame summons at [by **playing daily games on the website**](https://fischl.app/profile) 📈",
    f"Admins can customize using {SlashCommand('events settings')}, {SlashCommand('shop')} and {SlashCommand('milestones')} easily ⚙️**",
]

KINGDOM_NAME = "Kingdom"
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

class ThanksEliteTrack(discord.ui.Button):
    def __init__(self, is_active=False):
        super().__init__(
            label="Elite Patron",
            style=discord.ButtonStyle.green,
            disabled=True,
            emoji="❤️", 
            row=1
        )
    async def callback(self, interaction: discord.Interaction):
        pass
    
class PurchaseEliteTrack(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Elite Track",
            style=discord.ButtonStyle.green,
            emoji=MONEYDANCE_EMOTE,
            row=1
        )

    async def callback(self, interaction: discord.Interaction):
        elite_button = discord.ui.Button(
            label="Buy on Website",
            style=discord.ButtonStyle.link,
            url="https://fischl.app/profile",
        )
        
        embed = discord.Embed(
            title=f"{MONEYDANCE_EMOTE} Less than USD $1/month. MASSIVE Upgrades Inside! {MONEYDANCE_EMOTE}",
            description=(
                f"> -# *\"Cheaper than a single Genshin wish, now packed with even more value.\"*\n\n"
                f"**Elite Track** unlocks a premium reward tier alongside every free tier while supporting development work:\n\n"
                f"-# {DOT_EMOTE}**Ultimate Customization**: Unlock **Custom GIF Backgrounds**, **Fonts**, **Accent Colors**, and **Titles** to make your profile uniquely yours! <:CharlotteHeart:1191594476263702528>\n"
                f"-# {DOT_EMOTE}**Animated Cosmetics**: Exclusive animated profile frames to allow you to stand out from the crowd! <:KokoWow:1191868161851666583>\n"
                f"-# {DOT_EMOTE}**Economic Boosts**: Shop & Domain discounts, extra Mora gains, reduced gifting tax, and immediate spawns for daily chests <:PinkCelebrate:1204614140044386314>\n"
                f"-# {DOT_EMOTE}**Flexing Perks**: Earn **+1 additional Prestige** at the final tier <:LynetteSip:1335609206988079169>\n\n"
                f"**Elite rewards are server-specific, and a season lasts for 3 months.**\n"
                f"<:reply:1036792837821435976> <:YanfeiNote:1335644122253623458> ***[View Full Track Comparison](https://fischl.app/profile)***"
            ),
            color=0xfa0af6
        )
        embed.set_footer(text="Login with Discord on the website and select a server to get started.")
        embed.set_thumbnail(url="https://media.discordapp.net/attachments/1106727534479032341/1381827880488669327/elite_track.png?ex=6848eeff&is=68479d7f&hm=079b87a3cac4fdcc8c3fd3fbe615bbf1380651da2e5119c748c5e78ffaa2e752&=&format=webp&quality=lossless&width=840&height=840")
        
        view = discord.ui.View()
        view.add_item(elite_button)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

QUEST_TYPES = ["participate_minigames", "win_minigames", "win_1v1_minigames", "earn_mora", "gift_mora", "collect_chests", "earn_big_mora", "gift_mora_unique", "summon_minigame", "customize_profile", "purchase_items", "unlock_drop_packs", "upgrade_buildings", "gift_mora_poorer", "hug_user", "win_minigames_under_5s"]
QUEST_GOAL_PRESETS = {
    "participate_minigames": {
        "daily": [4, 5],
        "weekly": [14, 16, 18],
        "monthly": [60, 70, 80]
    },
    "win_minigames": {
        "daily": [2, 3],
        "weekly": [8, 9, 10],
        "monthly": [25, 30, 35]
    },
    "win_1v1_minigames": {
        "daily": [1],
        "weekly": [4, 5, 6],
        "monthly": [10, 15, 20]
    },
    "earn_mora": {
        "daily": [15000, 17500, 20000],
        "weekly": [50000, 60000, 70000],
        "monthly": [250000, 275000, 300000]
    },
    "gift_mora": {
        "daily": [1000, 2000, 3000],
        "weekly": [10000, 15000, 20000],
        "monthly": [50000, 75000, 100000]
    },
    "collect_chests": {
        "daily": [1],
        "weekly": [5, 6, 7],
        "monthly": [20, 22, 24]
    },
    "earn_big_mora": {
        "daily": [1, 2],
        "weekly": [5, 7],
        "monthly": [20, 25]
    },
    "gift_mora_unique": {
        "daily": [2, 3],
        "weekly": [5, 7],
        "monthly": [15, 20]
    },
    "summon_minigame": {
        "daily": [1],
        "weekly": [3, 4, 5, 6],
        "monthly": [15, 20]
    },
    "customize_profile": {
        "daily": [1],
        "weekly": [2, 3],
        "monthly": [5, 6]
    },
    "purchase_items": {
        "monthly": [1, 2, 3]
    },
    "unlock_drop_packs": {
        "weekly": [1],
        "monthly": [2, 3]
    },
    "upgrade_buildings": {
        "daily": [1],
        "weekly": [3, 4],
        "monthly": [8, 10]
    },
    "gift_mora_poorer": {
        "daily": [1, 2],
        "weekly": [3, 5],
        "monthly": [10, 15]
    },
    "hug_user": {
        "daily": [2, 3],
        "weekly": [5, 7],
        "monthly": [15, 20]
    },
    "win_minigames_under_5s": {
        "daily": [1, 2],
        "weekly": [4, 5],
        "monthly": [12, 15]
    }
}
QUEST_DESCRIPTIONS = {
    "participate_minigames": "Participate in minigames",
    "win_minigames": "Win minigames",
    "win_1v1_minigames": "Win 1v1 minigames",
    "earn_mora": "Earn Mora",
    "gift_mora": "Gift Mora",
    "collect_chests": "Collect chests",
    "earn_big_mora": "Earn 10k+ Mora in one go",
    "gift_mora_unique": f"{SlashCommand('gift')} Mora to different users",
    "summon_minigame": f"{SlashCommand('summon')} a minigame",
    "customize_profile": f"{SlashCommand('customize')} your profile",
    "purchase_items": f"Purchase {SlashCommand('shop')} items with {SlashCommand('buy')}",
    "unlock_drop_packs": "Unlock Mora Drop packs",
    "upgrade_buildings": "Upgrade your Kingdom buildings 🏰",
    "gift_mora_poorer": f"{SlashCommand('gift')} Mora to users with less Mora",
    "hug_user": f"{SlashCommand('hug')} other users",
    "win_minigames_under_5s": "Win minigames in under 5 seconds"
}
QUEST_XP_REWARDS = {
    "daily": 250,
    "weekly": 500,
    "monthly": 1500
}
QUEST_BONUS_XP = {
    "daily": 500,
    "weekly": 1500,
    "monthly": 4500
}

class Season:
    def __init__(self, id, name, start_ts, end_ts, track_data):
        self.id = id
        self.name = name
        self.start_ts = start_ts
        self.end_ts = end_ts
        self.track_data = track_data

SEASONS = [
    Season(
        id=1,
        name="Liyue's Lanterns",
        start_ts=1751328000,  # July 1, 2025
        end_ts=1759276800,    # October 1, 2025
        track_data = [
            {'tier': 1,  'xp_req': 250, 'cumulative_xp': 250,    'free': 'Drop Pack',                                                      'elite': 'Custom Embed Color'},
            {'tier': 2,  'xp_req': 250, 'cumulative_xp': 500,    'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 3,  'xp_req': 250, 'cumulative_xp': 750,    'free': '+3 Minigames Summon',                                            'elite': '+3 Minigames Summon'},
            {'tier': 4,  'xp_req': 250, 'cumulative_xp': 1000,    'free': 'Drop Pack',                                                      'elite': 'Mora Gain Boost +5%'},
            {'tier': 5,  'xp_req': 250, 'cumulative_xp': 1250,    'free': 'Unlocks Mora Gifting',                                            'elite': 'Mora Gift Tax -5%'},
            {'tier': 6,  'xp_req': 500, 'cumulative_xp': 1750,    'free': 'Server Title | Liyue Harbor',                                    'elite': 'Animated Background | ' + ANIMATED_INVENTORY_BG_PATH + '/Aether\'s Watch.gif'},
            {'tier': 7,  'xp_req': 500, 'cumulative_xp': 2250,   'free': 'Mora Gain Boost +5%',                                            'elite': '+1 Chest Upgrade Limit'},
            {'tier': 8,  'xp_req': 500, 'cumulative_xp': 2750,   'free': '+1 Chest Upgrade Limit',                                         'elite': 'Mora Gift Tax -5%'},
            {'tier': 9,  'xp_req': 500, 'cumulative_xp': 3250,   'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 10, 'xp_req': 500, 'cumulative_xp': 3750,   'free': 'Drop Pack',                                                      'elite': 'Animated Frame | ' + FRAMES_DIRECTORY + '/Jade Stone.gif'},
            {'tier': 11, 'xp_req': 1000, 'cumulative_xp': 4750,   'free': 'Mora Gift Tax -5%',                                              'elite': 'Mora Gain Boost +5%'},
            {'tier': 12, 'xp_req': 1000, 'cumulative_xp': 5750,   'free': '+1 Chest Upgrade Limit',                                         'elite': '+3 Minigames Summon'},
            {'tier': 13, 'xp_req': 1000, 'cumulative_xp': 6750,   'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 14, 'xp_req': 1000, 'cumulative_xp': 7750,   'free': 'Static Frame | ' + FRAMES_DIRECTORY + '/Golden Ring.png',             'elite': 'Animated Title | <a:tada:1227425729654820885> Cool Traveler'},
            {'tier': 15, 'xp_req': 1000, 'cumulative_xp': 8750,   'free': 'Drop Pack',                                                      'elite': 'Mora Gain Boost +5%'},
            {'tier': 16, 'xp_req': 2500, 'cumulative_xp': 11250,   'free': 'Mora Gift Tax -5%',                                              'elite': '+3 Minigames Summon'},
            {'tier': 17, 'xp_req': 2500, 'cumulative_xp': 13750,   'free': 'Drop Pack',                                                      'elite': 'Mora Gain Boost +5%'},
            {'tier': 18, 'xp_req': 2500, 'cumulative_xp': 16250,   'free': 'Mora Gain Boost +5%',                                            'elite': '+3 Minigames Summon'},
            {'tier': 19, 'xp_req': 2500, 'cumulative_xp': 18750,   'free': '+1 Chest Upgrade Limit',                                         'elite': 'Mora Gain Boost +5%'},
            {'tier': 20, 'xp_req': 2500, 'cumulative_xp': 21250,   'free': 'Server Title | Genshin Adventurer',                               'elite': 'Animated Frame | ' + FRAMES_DIRECTORY + '/Sakura Blossoms.gif'},
            {'tier': 21, 'xp_req': 5000, 'cumulative_xp': 26250,   'free': 'Mora Gain Boost +5%',                                            'elite': '+1 Chest Upgrade Limit'},
            {'tier': 22, 'xp_req': 5000, 'cumulative_xp': 31250,   'free': '+3 Minigames Summon',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 23, 'xp_req': 5000, 'cumulative_xp': 36250,   'free': 'Mora Gain Boost +5%',                                            'elite': '+3 Minigames Summon'},
            {'tier': 24, 'xp_req': 5000, 'cumulative_xp': 41250,   'free': 'Mora Gift Tax -5%',                                              'elite': 'Mora Gain Boost +5%'},
            {'tier': 25, 'xp_req': 5000, 'cumulative_xp': 46250,   'free': 'Mora Gain Boost +5%',                                            'elite': '+3 Minigames Summon'},
            {'tier': 26, 'xp_req': 7250, 'cumulative_xp': 53500,   'free': 'Static Frame | ' + FRAMES_DIRECTORY + '/Meander Lanterns.png',        'elite': 'Animated Background | ' + ANIMATED_INVENTORY_BG_PATH + '/Festive Night.gif'},
            {'tier': 27, 'xp_req': 7250, 'cumulative_xp': 60750,   'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 28, 'xp_req': 7250, 'cumulative_xp': 68000,   'free': '+3 Minigames Summon',                                            'elite': 'Mora Gift Tax -5%'},
            {'tier': 29, 'xp_req': 7250, 'cumulative_xp': 75250,   'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 30, 'xp_req': 7250, 'cumulative_xp': 82500,   'free': 'Animated Background | ' + ANIMATED_INVENTORY_BG_PATH + '/Stone Gate.gif', 'elite': 'Animated Title | <a:tada:1227425729654820885> Loyal Paimon'},
            {'tier': 31, 'xp_req': 7500, 'cumulative_xp': 90000,  'free': 'Prestige +1',                                                     'elite': 'Prestige +1'},
        ]
    ),
    Season(
        id=2,
        name="Season of the Dragon",
        start_ts=1759276801,   # October 1, 2025
        end_ts=1767229200,     # January 1, 2026
        track_data = [
            {'tier': 1,  'xp_req': 1000, 'cumulative_xp': 1000,    'free': 'Drop Pack',                                                      'elite': 'Custom Embed Color'},
            {'tier': 2,  'xp_req': 1000, 'cumulative_xp': 2000,    'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 3,  'xp_req': 1000, 'cumulative_xp': 3000,    'free': '+3 Minigames Summon',                                            'elite': '+3 Minigames Summon'},
            {'tier': 4,  'xp_req': 1000, 'cumulative_xp': 4000,    'free': 'Drop Pack',                                                      'elite': 'Mora Gain Boost +5%'},
            {'tier': 5,  'xp_req': 1000, 'cumulative_xp': 5000,    'free': 'Unlocks Mora Gifting',                                            'elite': 'Mora Gift Tax -5%'},
            {'tier': 6,  'xp_req': 1000, 'cumulative_xp': 6000,    'free': 'Server Title | Stromterror Winds',                                'elite': '+3 Minigames Summon'},
            {'tier': 7,  'xp_req': 1000, 'cumulative_xp': 7000,   'free': 'Mora Gain Boost +5%',                                            'elite': '+1 Chest Upgrade Limit'},
            {'tier': 8,  'xp_req': 1000, 'cumulative_xp': 8000,   'free': '+1 Chest Upgrade Limit',                                         'elite': 'Mora Gift Tax -5%'},
            {'tier': 9,  'xp_req': 1000, 'cumulative_xp': 9000,   'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 10, 'xp_req': 1000, 'cumulative_xp': 10000,   'free': 'Drop Pack',                                                      'elite': 'Animated Frame | ' + FRAMES_DIRECTORY + '/Jade Stone.gif'},
            {'tier': 11, 'xp_req': 1000, 'cumulative_xp': 11000,   'free': 'Mora Gift Tax -5%',                                              'elite': 'Mora Gain Boost +5%'},
            {'tier': 12, 'xp_req': 1000, 'cumulative_xp': 12000,   'free': '+1 Chest Upgrade Limit',                                         'elite': '+3 Minigames Summon'},
            {'tier': 13, 'xp_req': 1000, 'cumulative_xp': 13000,   'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 14, 'xp_req': 1000, 'cumulative_xp': 14000,   'free': 'Static Frame | ' + FRAMES_DIRECTORY + '/Dragon Balls.png',             'elite': 'Animated Title | <a:dragon_gif:1422382705307291770> Don\'t mess with me!'},
            {'tier': 15, 'xp_req': 1000, 'cumulative_xp': 15000,   'free': 'Drop Pack',                                                      'elite': 'Mora Gain Boost +5%'},
            {'tier': 16, 'xp_req': 2500, 'cumulative_xp': 17500,   'free': 'Mora Gift Tax -5%',                                              'elite': '+3 Minigames Summon'},
            {'tier': 17, 'xp_req': 2500, 'cumulative_xp': 20000,   'free': 'Drop Pack',                                                      'elite': 'Mora Gain Boost +5%'},
            {'tier': 18, 'xp_req': 2500, 'cumulative_xp': 22500,   'free': 'Mora Gain Boost +5%',                                            'elite': '+3 Minigames Summon'},
            {'tier': 19, 'xp_req': 2500, 'cumulative_xp': 25000,   'free': '+1 Chest Upgrade Limit',                                         'elite': 'Mora Gain Boost +5%'},
            {'tier': 20, 'xp_req': 2500, 'cumulative_xp': 27500,   'free': 'Server Title | The Master of Loong',                            'elite': 'Animated Frame | ' + FRAMES_DIRECTORY + '/Dragon Mouth.gif'},
            {'tier': 21, 'xp_req': 2500, 'cumulative_xp': 30000,   'free': 'Mora Gain Boost +5%',                                            'elite': '+1 Chest Upgrade Limit'},
            {'tier': 22, 'xp_req': 2500, 'cumulative_xp': 32500,   'free': '+3 Minigames Summon',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 23, 'xp_req': 2500, 'cumulative_xp': 35000,   'free': 'Mora Gain Boost +5%',                                            'elite': '+3 Minigames Summon'},
            {'tier': 24, 'xp_req': 2500, 'cumulative_xp': 37500,   'free': 'Mora Gift Tax -5%',                                              'elite': 'Mora Gain Boost +5%'},
            {'tier': 25, 'xp_req': 2500, 'cumulative_xp': 40000,   'free': 'Mora Gain Boost +5%',                                            'elite': '+3 Minigames Summon'},
            {'tier': 26, 'xp_req': 2500, 'cumulative_xp': 42500,   'free': 'Static Frame | ' + FRAMES_DIRECTORY + '/Green Dragon.png',        'elite': 'Animated Frame | ' + FRAMES_DIRECTORY + '/Holodragon.gif'},
            {'tier': 27, 'xp_req': 2500, 'cumulative_xp': 45000,   'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 28, 'xp_req': 2500, 'cumulative_xp': 47500,   'free': '+3 Minigames Summon',                                            'elite': 'Mora Gift Tax -5%'},
            {'tier': 29, 'xp_req': 2500, 'cumulative_xp': 50000,   'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 30, 'xp_req': 2500, 'cumulative_xp': 52500,   'free': 'Animated Title | <a:dragon1:1422382712043339836> Dragon Hunter',        'elite': 'Animated Title | <a:DragonHa:1422382728518701159> You can\'t catch me!'},
            {'tier': 31, 'xp_req': 2500, 'cumulative_xp': 55000,  'free': 'Prestige +1',                                                     'elite': 'Prestige +1'},
        ]
    ),
    Season(
        id=3,
        name="Lantern Rite Festival",
        start_ts=1767229201,   # January 1, 2026
        end_ts=1775001600,     # April 1, 2026
        track_data = [
            {'tier': 1,  'xp_req': 1000, 'cumulative_xp': 1000,    'free': 'Drop Pack',                                                      'elite': 'Custom Embed Color'},
            {'tier': 2,  'xp_req': 1000, 'cumulative_xp': 2000,    'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 3,  'xp_req': 1000, 'cumulative_xp': 3000,    'free': '+3 Minigames Summon',                                            'elite': '+10 Minigames Summon'},
            {'tier': 4,  'xp_req': 1000, 'cumulative_xp': 4000,    'free': 'Drop Pack',                                                      'elite': 'Mora Gain Boost +5%'},
            {'tier': 5,  'xp_req': 1000, 'cumulative_xp': 5000,    'free': 'Unlocks Mora Gifting',                                            'elite': 'Mora Gift Tax -5%'},
            {'tier': 6,  'xp_req': 1000, 'cumulative_xp': 6000,    'free': 'Server Title | Vigilant Yaksha',                                'elite': '+10 Minigames Summon'},
            {'tier': 7,  'xp_req': 1000, 'cumulative_xp': 7000,   'free': 'Mora Gain Boost +5%',                                            'elite': '+1 Chest Upgrade Limit'},
            {'tier': 8,  'xp_req': 1000, 'cumulative_xp': 8000,   'free': '+1 Chest Upgrade Limit',                                         'elite': 'Mora Gift Tax -5%'},
            {'tier': 9,  'xp_req': 1000, 'cumulative_xp': 9000,   'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 10, 'xp_req': 1000, 'cumulative_xp': 10000,   'free': 'Drop Pack',                                                      'elite': 'Animated Frame | ' + FRAMES_DIRECTORY + '/Jade Stone.gif'},
            {'tier': 11, 'xp_req': 1000, 'cumulative_xp': 11000,   'free': 'Mora Gift Tax -5%',                                              'elite': 'Mora Gain Boost +5%'},
            {'tier': 12, 'xp_req': 1000, 'cumulative_xp': 12000,   'free': '+1 Chest Upgrade Limit',                                         'elite': '+10 Minigames Summon'},
            {'tier': 13, 'xp_req': 1000, 'cumulative_xp': 13000,   'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 14, 'xp_req': 1000, 'cumulative_xp': 14000,   'free': 'Static Frame | ' + FRAMES_DIRECTORY + '/Firecracker.png',             'elite': 'Animated Title | <a:dragon_gif:1422382705307291770> Dragonic Defender'},
            {'tier': 15, 'xp_req': 1000, 'cumulative_xp': 15000,   'free': 'Drop Pack',                                                      'elite': 'Mora Gain Boost +5%'},
            {'tier': 16, 'xp_req': 2500, 'cumulative_xp': 17500,   'free': 'Mora Gift Tax -5%',                                              'elite': '+10 Minigames Summon'},
            {'tier': 17, 'xp_req': 2500, 'cumulative_xp': 20000,   'free': 'Drop Pack',                                                      'elite': 'Mora Gain Boost +5%'},
            {'tier': 18, 'xp_req': 2500, 'cumulative_xp': 22500,   'free': 'Mora Gain Boost +5%',                                            'elite': '+10 Minigames Summon'},
            {'tier': 19, 'xp_req': 2500, 'cumulative_xp': 25000,   'free': '+1 Chest Upgrade Limit',                                         'elite': 'Mora Gain Boost +5%'},
            {'tier': 20, 'xp_req': 2500, 'cumulative_xp': 27500,   'free': 'Server Title | Golden Prosperity',                            'elite': 'Animated Frame | ' + FRAMES_DIRECTORY + '/Dragon Mouth.gif'},
            {'tier': 21, 'xp_req': 2500, 'cumulative_xp': 30000,   'free': 'Mora Gain Boost +5%',                                            'elite': '+1 Chest Upgrade Limit'},
            {'tier': 22, 'xp_req': 2500, 'cumulative_xp': 32500,   'free': '+3 Minigames Summon',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 23, 'xp_req': 2500, 'cumulative_xp': 35000,   'free': 'Mora Gain Boost +5%',                                            'elite': '+10 Minigames Summon'},
            {'tier': 24, 'xp_req': 2500, 'cumulative_xp': 37500,   'free': 'Mora Gift Tax -5%',                                              'elite': 'Mora Gain Boost +5%'},
            {'tier': 25, 'xp_req': 2500, 'cumulative_xp': 40000,   'free': 'Mora Gain Boost +5%',                                            'elite': '+10 Minigames Summon'},
            {'tier': 26, 'xp_req': 5000, 'cumulative_xp': 45000,   'free': 'Static Frame | ' + FRAMES_DIRECTORY + '/Lunar Roof.png',        'elite': 'Animated Frame | ' + FRAMES_DIRECTORY + '/Holodragon.gif'},
            {'tier': 27, 'xp_req': 5000, 'cumulative_xp': 50000,   'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 28, 'xp_req': 5000, 'cumulative_xp': 55000,   'free': '+3 Minigames Summon',                                            'elite': 'Mora Gift Tax -5%'},
            {'tier': 29, 'xp_req': 5000, 'cumulative_xp': 60000,   'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 30, 'xp_req': 5000, 'cumulative_xp': 65000,   'free': 'Animated Title | <:guizhong:1455084957335683366> Glow of the Guizhong',        'elite': 'Animated Title | <a:dragon1:1422382712043339836> Dragonic Master'},
            {'tier': 31, 'xp_req': 5000, 'cumulative_xp': 70000,  'free': 'Prestige +1',                                                     'elite': 'Prestige +1'},
        ]
    ),
    Season(
        id=3.14, # April Fools 2026
        name="Error 404: Season Not Found",
        start_ts=1775001601,   # April 1, 2026
        end_ts=1775088000,     # April 2, 2026
        track_data = [
            {'tier': 1,  'xp_req': 1, 'cumulative_xp': 1,    'free': '+69 Chest Upgrade Limit',                                              'elite': 'pls'},
            {'tier': 2,  'xp_req': 1, 'cumulative_xp': 2,    'free': 'Mora Gain Boost +67%',                                            'elite': 'dont'},
            {'tier': 3,  'xp_req': 1, 'cumulative_xp': 3,    'free': 'Animated Title | 67 <a:clown:1487325727497130024> <-- me',       'elite': 'buy'},
        ]
    ),
    Season(
        id=4,
        name="Cryo Crystal Blessing",
        start_ts=1775088001,   # April 2, 2026
        end_ts=1782864000,     # July 1, 2026
        track_data = [
            {'tier': 1,  'xp_req': 1000, 'cumulative_xp': 1000,    'free': 'Drop Pack',                                                      'elite': 'Custom Embed Color'},
            {'tier': 2,  'xp_req': 1000, 'cumulative_xp': 2000,    'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 3,  'xp_req': 1000, 'cumulative_xp': 3000,    'free': '+3 Minigames Summon',                                            'elite': '+10 Minigames Summon'},
            {'tier': 4,  'xp_req': 1000, 'cumulative_xp': 4000,    'free': 'Drop Pack',                                                      'elite': 'Mora Gain Boost +5%'},
            {'tier': 5,  'xp_req': 1000, 'cumulative_xp': 5000,    'free': 'Unlocks Mora Gifting',                                            'elite': 'Mora Gift Tax -5%'},
            {'tier': 6,  'xp_req': 1000, 'cumulative_xp': 6000,    'free': 'Server Title | Cry||o|| about it',                                'elite': '+10 Minigames Summon'},
            {'tier': 7,  'xp_req': 1000, 'cumulative_xp': 7000,   'free': 'Mora Gain Boost +5%',                                            'elite': '+1 Chest Upgrade Limit'},
            {'tier': 8,  'xp_req': 1000, 'cumulative_xp': 8000,   'free': '+1 Chest Upgrade Limit',                                         'elite': 'Mora Gift Tax -5%'},
            {'tier': 9,  'xp_req': 1000, 'cumulative_xp': 9000,   'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 10, 'xp_req': 1000, 'cumulative_xp': 10000,   'free': 'Drop Pack',                                                      'elite': 'Animated Frame | ' + FRAMES_DIRECTORY + '/Jade Stone.gif'},
            {'tier': 11, 'xp_req': 1000, 'cumulative_xp': 11000,   'free': 'Mora Gift Tax -5%',                                              'elite': 'Mora Gain Boost +5%'},
            {'tier': 12, 'xp_req': 1000, 'cumulative_xp': 12000,   'free': '+1 Chest Upgrade Limit',                                         'elite': '+10 Minigames Summon'},
            {'tier': 13, 'xp_req': 1000, 'cumulative_xp': 13000,   'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 14, 'xp_req': 1000, 'cumulative_xp': 14000,   'free': 'Static Frame | ' + FRAMES_DIRECTORY + '/Snowglobe.png',             'elite': 'Animated Title | <a:dragon_gif:1422382705307291770> <-- me'},
            {'tier': 15, 'xp_req': 1000, 'cumulative_xp': 15000,   'free': 'Drop Pack',                                                      'elite': 'Mora Gain Boost +5%'},
            {'tier': 16, 'xp_req': 2500, 'cumulative_xp': 17500,   'free': 'Mora Gift Tax -5%',                                              'elite': '+10 Minigames Summon'},
            {'tier': 17, 'xp_req': 2500, 'cumulative_xp': 20000,   'free': 'Drop Pack',                                                      'elite': 'Mora Gain Boost +5%'},
            {'tier': 18, 'xp_req': 2500, 'cumulative_xp': 22500,   'free': 'Mora Gain Boost +5%',                                            'elite': '+10 Minigames Summon'},
            {'tier': 19, 'xp_req': 2500, 'cumulative_xp': 25000,   'free': '+1 Chest Upgrade Limit',                                         'elite': 'Mora Gain Boost +5%'},
            {'tier': 20, 'xp_req': 2500, 'cumulative_xp': 27500,   'free': 'Server Title | The Doctor',                            'elite': 'Animated Frame | ' + FRAMES_DIRECTORY + '/Dragon Mouth.gif'},
            {'tier': 21, 'xp_req': 2500, 'cumulative_xp': 30000,   'free': 'Mora Gain Boost +5%',                                            'elite': '+1 Chest Upgrade Limit'},
            {'tier': 22, 'xp_req': 2500, 'cumulative_xp': 32500,   'free': '+3 Minigames Summon',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 23, 'xp_req': 2500, 'cumulative_xp': 35000,   'free': 'Mora Gain Boost +5%',                                            'elite': '+10 Minigames Summon'},
            {'tier': 24, 'xp_req': 2500, 'cumulative_xp': 37500,   'free': 'Mora Gift Tax -5%',                                              'elite': 'Mora Gain Boost +5%'},
            {'tier': 25, 'xp_req': 2500, 'cumulative_xp': 40000,   'free': 'Mora Gain Boost +5%',                                            'elite': '+10 Minigames Summon'},
            {'tier': 26, 'xp_req': 5000, 'cumulative_xp': 45000,   'free': 'Static Frame | ' + FRAMES_DIRECTORY + '/Mountains.png',        'elite': 'Animated Frame | ' + FRAMES_DIRECTORY + '/Holodragon.gif'},
            {'tier': 27, 'xp_req': 5000, 'cumulative_xp': 50000,   'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 28, 'xp_req': 5000, 'cumulative_xp': 55000,   'free': '+3 Minigames Summon',                                            'elite': 'Mora Gift Tax -5%'},
            {'tier': 29, 'xp_req': 5000, 'cumulative_xp': 60000,   'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 30, 'xp_req': 5000, 'cumulative_xp': 65000,   'free': 'Server Title | I\'m very cold',        'elite': 'Animated Title | <a:dragon1:1422382712043339836> Cyro Conqueror'},
            {'tier': 31, 'xp_req': 5000, 'cumulative_xp': 70000,  'free': 'Prestige +1',                                                     'elite': 'Prestige +1'},
        ]
    ),
    Season(
        id=5,
        name="Summer Chapters",
        start_ts=1782864001,   # July 1, 2026
        end_ts=1790812800,     # October 1, 2026
        track_data = [
            {'tier': 1,  'xp_req': 1000, 'cumulative_xp': 1000,    'free': 'Drop Pack',                                                      'elite': 'Custom Accent Color'},
            {'tier': 2,  'xp_req': 1000, 'cumulative_xp': 2000,    'free': 'Mora Gain Boost +5%',                                            'elite': 'Express Daily Chests'},
            {'tier': 3,  'xp_req': 1000, 'cumulative_xp': 3000,    'free': '+3 Minigames Summon',                                            'elite': 'Custom Title'},
            {'tier': 4,  'xp_req': 1000, 'cumulative_xp': 4000,    'free': 'Drop Pack',                                                      'elite': 'Mora Gain Boost +10%'},
            {'tier': 5,  'xp_req': 1000, 'cumulative_xp': 5000,    'free': 'Unlocks Mora Gifting',                                           'elite': 'Mora Gift Tax -10%'},
            {'tier': 6,  'xp_req': 1000, 'cumulative_xp': 6000,    'free': 'Server Title | The Golden Apple Vacation Returns!',              'elite': 'Shop Discount +10%'},
            {'tier': 7,  'xp_req': 1000, 'cumulative_xp': 7000,   'free': 'Drop Pack',                                                       'elite': '+1 Chest Upgrade Limit'},
            {'tier': 8,  'xp_req': 1000, 'cumulative_xp': 8000,   'free': '+1 Chest Upgrade Limit',                                          'elite': 'Domain Discount +10%'},
            {'tier': 9,  'xp_req': 1000, 'cumulative_xp': 9000,   'free': 'Mora Gain Boost +5%',                                             'elite': 'Custom Card Font'},
            {'tier': 10, 'xp_req': 1000, 'cumulative_xp': 10000,   'free': 'Drop Pack',                                                      'elite': 'Custom GIF Background'},
            {'tier': 11, 'xp_req': 1000, 'cumulative_xp': 11000,   'free': 'Mora Gift Tax -5%',                                              'elite': 'Animated Frame | ' + FRAMES_DIRECTORY + '/Jade Stone.gif'},
            {'tier': 12, 'xp_req': 1000, 'cumulative_xp': 12000,   'free': '+1 Chest Upgrade Limit',                                         'elite': 'Mora Gain Boost +10%'},
            {'tier': 13, 'xp_req': 1000, 'cumulative_xp': 13000,   'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gift Tax -10%'},
            {'tier': 14, 'xp_req': 1000, 'cumulative_xp': 14000,   'free': 'Static Frame | ' + FRAMES_DIRECTORY + '/Snowglobe.png',          'elite': 'Shop Discount +10%'},
            {'tier': 15, 'xp_req': 1000, 'cumulative_xp': 15000,   'free': 'Drop Pack',                                                      'elite': '+30 Minigames Summon'},
            {'tier': 16, 'xp_req': 2500, 'cumulative_xp': 17500,   'free': 'Mora Gift Tax -5%',                                              'elite': '+1 Chest Upgrade Limit'},
            {'tier': 17, 'xp_req': 2500, 'cumulative_xp': 20000,   'free': 'Drop Pack',                                                      'elite': 'Domain Discount +10%'},
            {'tier': 18, 'xp_req': 2500, 'cumulative_xp': 22500,   'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +10%'},
            {'tier': 19, 'xp_req': 2500, 'cumulative_xp': 25000,   'free': '+1 Chest Upgrade Limit',                                         'elite': 'Shop Discount +10%'},
            {'tier': 20, 'xp_req': 2500, 'cumulative_xp': 27500,   'free': 'Server Title | Immernachtreich Apokalypse',                      'elite': 'Domain Discount +10%'},
            {'tier': 21, 'xp_req': 2500, 'cumulative_xp': 30000,   'free': 'Mora Gain Boost +5%',                                            'elite': 'Animated Frame | ' + FRAMES_DIRECTORY + '/Dragon Mouth.gif'},
            {'tier': 22, 'xp_req': 2500, 'cumulative_xp': 32500,   'free': '+3 Minigames Summon',                                            'elite': 'Mora Gain Boost +10%'},
            {'tier': 23, 'xp_req': 2500, 'cumulative_xp': 35000,   'free': 'Mora Gain Boost +5%',                                            'elite': '+1 Chest Upgrade Limit'},
            {'tier': 24, 'xp_req': 2500, 'cumulative_xp': 37500,   'free': 'Mora Gift Tax -5%',                                              'elite': 'Shop Discount +10%'},
            {'tier': 25, 'xp_req': 2500, 'cumulative_xp': 40000,   'free': 'Drop Pack',                                                      'elite': 'Domain Discount +10%'},
            {'tier': 26, 'xp_req': 5000, 'cumulative_xp': 45000,   'free': 'Static Frame | ' + FRAMES_DIRECTORY + '/Mountains.png',          'elite': 'Animated Frame | ' + FRAMES_DIRECTORY + '/Holodragon.gif'},
            {'tier': 27, 'xp_req': 5000, 'cumulative_xp': 50000,   'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +10%'},
            {'tier': 28, 'xp_req': 5000, 'cumulative_xp': 55000,   'free': '+3 Minigames Summon',                                            'elite': 'Mora Gift Tax -10%'},
            {'tier': 29, 'xp_req': 5000, 'cumulative_xp': 60000,   'free': 'Drop Pack',                                                      'elite': 'Shop Discount +10%'},
            {'tier': 30, 'xp_req': 5000, 'cumulative_xp': 65000,   'free': 'Server Title | What a beautiful day!',                           'elite': 'Domain Discount +10%'},
            {'tier': 31, 'xp_req': 5000, 'cumulative_xp': 70000,  'free': 'Prestige +1',                                                     'elite': 'Prestige +1'},
        ]
    ),
]

REWARD_TYPES = {
    "Drop Pack": "drop_pack",
    "Animated Background": "animated_background",
    "Custom GIF Background": "custom_gif_background",
    "Static Frame": "static_frame",
    "Animated Frame": "animated_frame",
    "Prestige +1": "prestige",
    "Mora Gain Boost +5%": "mora_boost",
    "Mora Gain Boost +67%": "mora_boost_67",
    "+1 Chest Upgrade Limit": "chest_upgrade",
    "+69 Chest Upgrade Limit": "chest_upgrade_69",
    "Unlocks Mora Gifting": "unlock_gifting",
    "Mora Gift Tax -5%": "gift_tax",
    "+3 Minigames Summon": "minigame_summon",
    "Custom Embed Color": "accent_color",
    "Custom Accent Color": "accent_color",
    "Server Title": "title",
    "Custom Title": "custom_title",
    "Animated Title": "title",
    "Custom Card Font": "font_unlock",
    "Shop Discount +10%": "shop_discount",
    "Domain Discount +10%": "domain_discount",
    "Express Daily Chests": "express_daily_chests",
    "+30 Minigames Summon": "minigame_summon_30",
}

XP_QUEST_EMBED = discord.Embed(
    title="What Are XP & Quests? <:AlbedoQuestion:1191574408544923799>",
    color=discord.Color.random()
).add_field(
    name="<:NingguangStonks:1265470501707321344> Quests ➜ XP",
    value="-# Complete daily, weekly, and monthly quests to **earn XP** just by playing, winning, or gifting!",
    inline=True
).add_field(
    name="<:CharlotteHeart:1191594476263702528> XP ➜ Rewards",
    value="-# Earning XP moves you up the Progression Track to **unlock Mora boosts, chest upgrades, animated backgrounds**, and more!",
    inline=True
).add_field(
    name="<:MelonBread_KeqingNote:1342924552392671254> Track in One Place",
    value=f"-# Use {SlashCommand('mora')} to view **quests, XP, and rewards**. Each season's track lasts **3 months**!",
    inline=True
)

MINIGAME_TITLES = [
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
    "Grand Auction House",
    "Bank Heist",
    "Simple Math Game",
    "Tik Tac Tok"
] # also present in event.py 
# 1 --> self.minigame_mapping 
# 2 --> letter_to_event = dict(zip(LETTER_LIST, events))

LETTER_LIST = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"]
LETTER_EMOTES = ["🇦", "🇧", "🇨", "🇩", "🇪", "🇫", "🇬", "🇭", "🇮", "🇯", "🇰", "🇱", "🇲", "🇳", "🇴", "🇵", "🇶", "🇷", "🇸", "🇹", "🇺", "🇻", "🇼", "🇽", "🇾", "🇿"]

BOSSES = [
    "Stormterror Dvalin",
    "Andrius",
    "Childe",
    "Azhdaha",
    "La Signora",
    "Magatsu Mitake Narukami no Mikoto",
    "Everlasting Lord of Arcane Wisdom",
    "Guardian of Apep's Oasis",
    "All-Devouring Narwhal",
    "The Knave",
    "Lord of Eroded Primal Fire",
    "Geo Hypostasis",
    "Cryo Hypostasis",
    "Pyro Hypostasis",
    "Electro Hypostasis",
    "Anemo Hypostasis",
    "Hydro Hypostasis",
    "Cryo Regisvine",
    "Pyro Regisvine",
    "Oceanid",
    "Primo Geovishap",
    "Perpetual Mechanical Array",
    "Maguu Kenki",
    "Ruin Serpent",
    "Thunder Manifestation",
    "Golden Wolflord",
    "Bathysmal Vishap Herd",
    "Algorithm of Semi-Intransient Matrix of Overseer Network",
    "Aeonblight Drake",
    "Jadeplume Terrorshroom",
    "Electro Regisvine",
    "Pyro Scorpion",
    "Iniquitous Baptist",
    "Emperor of Fire and Iron",
    "Emperor of Wind and Frost",
    "Emperor of Pure Water",
    "Emperor of Lightning and Thunder",
    "Emperor of Earth and Stone",
    "Emperor of Ice and Snow",
    "Emperor of Flames and Ashes",
    "Emperor of Storms and Tempests",
    "Emperor of Shadows and Darkness",
    "Emperor of Light and Radiance",
    "Doomsday Beast",
    "Cocolia, Mother of Deception",
    "Phantylia the Undying",
    "Starcrusher Swarm King - Skaracabaz (Synthetic)",
    "Harmonious Choir - The Great Septimus",
    "Shadow of Feixiao and Ecliptic Inner Beast",
    "Abundant Ebon Deer",
    "Annihilator of Desolation Mistral",
    "Argenti (Boss)",
    "Blaznana Monkey Trick",
    "Borisin Warhead: Hoolay",
    "Savage God, Mad King, Incarnation of Strife",
    "The Giver, Master of Legions, Lance of Fury",
    "The Past, Present, and Eternal Show",
]
HSR_EMOJI_RIDDLE_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0pPz9A-wegeqpyIxYSjR-trCnP5ffIkOE-ThkVXhCC46pjgL9h5eEwOp42-oDce340eHYhO6TSbLl/pub?output=csv"
GENSHIN_EMOJI_RIDDLE_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTVeIY2FLhHODz6nyJ5D8IWBtDRRttfIZNkUKnRmqoTksaHXxZnckUD7ou4s5DKT_CDRZbMBs9tlnd8/pub?output=csv"
CURRENCY_EMOTES = [
    f"{MORA_EMOTE}",
    "<:PRIMOGEM:1364031230357540894>",
    "<:Polychrome:1316607903939035236>"
]
WORDS = [
   "albedo", "alhaitham", "aloy", "amber", "arataki", "ayaka", "ayato", "barbara", "beidou",
    "bennett", "candace", "chongyun", "collei", "cyno", "dehya", "diluc", "diona", "dori", "eula",
    "fischl", "focalors", "freminet", "ganyu", "gorou", "itto", "jean",
    "kaedehara", "kaeya", "kaveh", "keqing", "klee", "kokomi", "kuki", "layla", "lisa", "mika",
    "mona", "nahida", "nilou", "ningguang", "noelle", "qiqi", "raiden", "rosaria", "sara",
    "sayu", "shenhe", "shinobu", "sucrose", "tartaglia", "thoma", "tighnari", "venti", "wanderer", "xiangling",
    "xiao", "xingqiu", "xinyan", "yaoyao", "yelan", "yoimiya", "aether",
    "lumine", "paimon", "dainsleif", "kaiser", "mihoyo", "liyue", "mondstadt", "sumeru", "fontaine",
    "natlan", "hilichurl", "abyss", "archon", "vision", "delusion", "gnosis", "hilichurl",
    "treasure", "hoarder", "fatui", "harbinger", "adeptus", "yaksha", "cryo", "pyro", "hydro", "electro",
    "anemo", "dendro", "claymore", "sword", "polearm", "bow", "catalyst", "artifact", "talent",
    "constellation", "ascension", "resin", "primogem", "wish", "banner", "gacha", "spiral", "abyss", "domain",
    "ley", "line", "boss", "weekly", "event", "quest", "commission", "expedition", "teapot", "serenitea",
    "realm", "adeptal", "energy", "recharge", "critical", "rate", "damage", "attack", "defense",
    "elemental", "mastery", "burst", "skill", "cooldown", "stamina", "sprint", "dash", "glide", "climb",
    "swim", "dodge", "parry", "shield", "heal", "revive", "buff", "debuff", "crowd", "control",
    "single", "target", "damage", "physical", "resistance", "elemental", "reaction", "overload", "superconduct",
    "shatter", "swirl", "crystal", "burning", "bloom", "hyperbloom", "burgeon", "quicken", "aggravate",
    "spread", "cold", "melt", "vapor", "resonance", "synergy", "team", "composition", "meta", "build",
    "rotation", "combo", "chain", "artifact", "bonus", "refinement", "enhancement",
    "ascend", "level", "talent", "book", "material", "boss", "drop", "elite", "enemy",
    "common", "spawn", "respawn", "loot", "chest", "reward", "achievement", "trophy", "title",
    "namecard", "profile", "signature", "friend", "multiplayer", "world", "level", "rank", "adventure",
    "experience", "mora", "currency", "shop", "store", "purchase", "bundle", "pack", "offer",
    "discount", "sale", "promotion", "event", "banner", "update", "patch", "maintenance", "server", "downtime",
    "patch", "note", "announcement", "news", "forum", "community", "discussion",
    "guide", "tutorial", "walkthrough", "tips", "tricks", "strategy", "build", "review", "tier", "list",
    "ranking", "comparison", "analysis", "breakdown", "overview", "summary", "highlight", "spotlight", "feature", "preview",
    "teaser", "trailer", "demo", "beta", "test", "release", "launch", "download", "install", "uninstall",
    "update", "upgrade", "patch", "version", "compatibility", "requirement", "specification", "platform", "device",
    "console", "mobile", "android", "tablet", "smartphone", "emulator", "controller", "keyboard", "mouse",
    "touchscreen", "interface", "menu", "option", "setting", "configuration", "preference",
    "control", "scheme", "layout", "binding", "shortcut", "hotkey", "command", "input", "sensitivity",
    "calibration", "resolution", "graphics", "quality", "performance", "frame", "rate", "latency", "ping",
    "connection", "network", "server", "region", "ping", "delay", "disconnect", "reconnect", "sync",
    "cloud", "save", "load", "backup", "restore", "data", "progress", "account", "profile", "login",
    "logout", "register", "signup", "signin", "authentication", "verification", "security", "password", "username", "email",
    "notification", "alert", "message", "chat", "voice", "text", "communication", "social", "friend", "request",
    "invite", "party", "team", "guild", "clan", "alliance", "faction", "group", "community", "forum",
    "discussion", "thread", "post", "comment", "reply", "like", "share", "subscribe", "follow", "unfollow",
    "block", "report", "moderator", "admin", "server"
]
MEMORY_GAME_EMOJIS = [ "😄", "😊", "😃", "😉", "😍", "😘", "😚", "😗", "😙", "😜", "😝", "😛", "🤑", "🤓", "😎", "🤗", "🙂", "🤔", "😐", "😑", "😶", "🙄", "😏", "😒", "🤥", "😌", "😔", "😪", "🤤", "😴", "😷", "🤒", "🤕", "🤢", "🤧", "😢", "😭", "😰", "😥", "😓", "😈", "👿", "👹", "👺", "💩", "👻", "💀", "👽", "🤖", "🎃", "🎉", "🌟", "🔥", "❤️", "💙", "💜", "💛", "💚", "🖤", "💖", "💗", "💓", "💕", "💞", "💘", "💝", "💌", "💍", "💎", "🎀", "🌈", "👍", "👎", "👌", "✌", "🤞", "🤟", "🤘", "👏", "🙌", "🤲", "💪", "🙏", "👊", "🤛", "🤜", "💅", "👀", "👁", "👅", "🐶", "🐱", "🐭", "🐹", "🐰", "🦊", "🐻", "🐼", "🐨", "🐯", "🦁", "🐷", "🐸", "🐵", "🦄", "🐉", "🐲", "🐍", "🦎", "🐢", "🍕", "🌺", "📚", "⚽", "🎵", "🍔", "🍦", "🎂", "🎁", "🎈", "🎨", "🚀", "⌛", "💡", "🎮", "📷", "📱", "💻", "⭐", "🌙", "🍎", "🍉", "🍇", "🍓", "🥑", "🍩", "🥨", "🥗", "🍿", "🍰", "🚗", "🚕", "🚙", "🚌", "🚎", "🚜", "🚲", "✈", "🚁", "🛳", ]
TTOL_EMOJIS = ["<:Anemo:1364310439781072946>", "<:Pyro:1364310441949663274>", "<:Electro:1364310441014071345>"]
CROSS_EMOJI = "<:cross:1458355882940170280>"
CIRCLE_EMOJI = "<:circle:1458355853731168307>"

async def setup(bot):
    pass