DAILY_GAMES = {
    "memory": {
        "name": "Memory Game",
        "description": "Remember 5 emojis and their positions",
        "reward": 5000,
        "icon": "🧠",
        "time_limit": 10
    },
    "math": {
        "name": "Quick Math",
        "description": "Solve simple addition problems in under 5 seconds",
        "reward": 7000,
        "icon": "🔢",
        "time_limit": 5
    },
    "hangman": {
        "name": "Hangman",
        "description": "Guess a word with 7 tries in 30 seconds per guess (hoyoverse-themed)",
        "reward": 8000,
        "icon": "📝",
        "time_limit": 30
    },
    "coinflip": {
        "name": "Fate's Choice",
        "description": "50/50 chance - flip the coin in 10 seconds",
        "reward": 10000,
        "icon": "🪙",
        "time_limit": 10
    },
    "unscramble": {
        "name": "Word Unscramble",
        "description": "Unscramble a word in 5 minutes (hoyoverse-themed)",
        "reward": 6000,
        "icon": "🔤",
        "time_limit": 300
    },
    "shapes": {
        "name": "Emoji Counter",
        "description": "Count the number of a specific emoji in 5 seconds",
        "reward": 5500,
        "icon": "🔺",
        "time_limit": 5
    },
    "typing": {
        "name": "Perfect Typing",
        "description": "Type a short phrase exactly (hoyoverse-themed) in 15 seconds",
        "reward": 7500,
        "icon": "⌨️",
        "time_limit": 15
    }
}

HANGMAN_WORDS = [
    # Genshin characters
    "AYAKA", "AYATO", "ALBEDO", "ARATAKI", "BARBARA", "BEIDOU", "BENNETT", "CHILDE", "CYNOS", "DILUC",
    "EULA", "FISCHL", "GANYU", "HUTAO", "ITTO", "JEAN", "KEQING", "KLEE", "LISA", "LYNEY",
    "LUMINE", "PAIMON", "KAZUHA", "RAIDEN", "XIANGLING", "XINGQIU", "XINYAN", "ZHONGLI", "YAE", "YELAN",
    "KOKOMI", "GOROU", "SARA", "THOMA", "ALHAITHAM", "TIGHNARI", "COLLEI", "FARUZAN", "LYNETTE", "NAVIA",
    "CHIORI", "FREMINET", "NEUVILLETTE", "SIGEWINNE", "ARLECCHINO", "WRIOTHESLEY", "BAIZHU", "CANDACE", "KAVEH", "DEHYA",

    # Regions & locations
    "MONDSTADT", "LIYUE", "INAZUMA", "SUMERU", "FONTAINE", "NATLAN", "SNEZHNAYA", "CELESTIA",
    "CHASM", "ENKANOMIYA", "WATATSUMI", "PORTORMOS", "MEROPIDE", "SANGONOMIYA",

    # Elements
    "ANEMO", "GEO", "ELECTRO", "HYDRO", "PYRO", "CRYO", "DENDRO",

    # Misc game words
    "VISION", "ARCHON", "TRAVELER", "ADVENTURER", "GLIDING", "PRIMOGEM", "ARTIFACT", "DOMAIN", "DENDRO", "GACHA",
    "WISHING", "COMMISSIONS", "STAMINA", "TEAPOT", "RESIN", "EXPEDITION", "ASCENSION",

    # Enemies and bosses
    "HILICHURL", "ABYSS", "FATUI"
]

UNSCRAMBLE_WORDS = [
    # Character-related
    "PAIMON", "TRAVELER", "ZHONGLI", "VENTI", "NAHIDA", "RAIDEN", "YAE", "KOKOMI", "ITTO", "ALBEDO",
    "KEQING", "HU TAO", "TARTAGLIA", "LYNEY", "LYNETTE", "NAVIA", "NEUVILLETTE", "ARLECCHINO", "SIGEWINNE", "FREMINET",

    # Places
    "MONDSTADT", "LIYUE", "INAZUMA", "SUMERU", "FONTAINE", "TEYVAT", "SNEZHNAYA", "NATLAN", "KHAENRIAH", "CELESTIA",

    # Common game terms
    "VISION", "ARCHON", "PRIMOGEM", "ARTIFACT", "WISH", "GACHA", "RESONANCE", "ADVENTURE", "COMMISSION", "DOMAIN",
    "COOP", "TEAPOT", "COOKING", "EXPEDITION", "PARTY", "TEAM", "ASCENSION", "DAMAGE", "ELEMENTAL", "BURST",

    # Enemies / bosses
    "HILICHURL", "FATUI", "CHASM",

    # Other HoYoverse (Star Rail / Honkai)
    "MARCH", "DANHENG", "BLADE", "BRONYA", "SEELE", "KAFKA", "LUOCHA", "SPARKLE",
    "HIMEKO", "WELT", "POMPOM"
]

TYPING_PHRASES = [
    # Genshin general
    "paimon is not emergency food",
    "welcome to teyvat traveler",
    "collect anemoculus and geoculus to increase stamina",
    "the adventurers guild has daily commissions",
    "artifacts can greatly boost your characters stats",
    "resin is used to claim rewards from bosses and domains",
    "you can cook food to heal and buff your party",
    "the seven nations of teyvat each have their own archon",
    "elemental reactions are the key to strong team combos",
    "gliding champions are born from patience and skill",

    # Character-based
    "zhongli demands respect and mora",
    "venti enjoys freedom and apple cider",
    "raiden shogun seeks eternity for inazuma",
    "nahida loves learning and guiding the people of sumeru",
    "hutao runs the wangsheng funeral parlor with a smile",
    "yae miko is always one step ahead with her clever tricks",
    "itto is loud proud and a little bit reckless",
    "keqing believes that humans shape their own destiny",
    "kokomi is a brilliant strategist from watatsumi island",
    "albedo studies alchemy in dragonspine with great curiosity",

    # Game mechanics
    "primogems are used to wish for characters and weapons",
    "you can craft enhancement ores at the blacksmith",
    "use elemental sight to reveal hidden clues",
    "domains reward valuable artifacts and ascension materials",
    "weekly bosses reset every monday morning",
    "use fragile resin wisely during events and grind sessions",
    "friendship levels unlock special character voice lines",
    "battlepass missions help you earn more rewards each season",
    "some characters scale better with elemental mastery than attack",
    "co op mode lets you explore teyvat with your friends",

    # HoYoverse flavor
    "honkai star rail takes place aboard the astral express",
    "march 7th loves taking photos of everything she sees",
    "kafka always finishes what she starts with style",
    "silver wolf hacks her way through every battle",
    "trailblazers are destined to follow the aeons path",
    "in honkai impact the valkyries fight to protect humanity",
    "himeko guides the crew with wisdom and caffeine",
    "jing yuan commands the clouds with grace and power",
    "pom pom maintains the express with boundless enthusiasm",
    "the universe is vast and full of stories yet to be told"
]
