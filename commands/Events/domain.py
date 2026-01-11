import discord
from firebase_admin import db
from commands.Events.helperFunctions import get_guild_mora, addMora

BUILDINGS = {
    "schloss": {"name": "Schloss", "emoji": "🏰", "desc": "The royal castle.", "color": discord.ButtonStyle.blurple},
    "theater": {"name": "Theater", "emoji": "🎭", "desc": "Where tales are told.", "color": discord.ButtonStyle.grey},
    "bibliothek": {"name": "Bibliothek", "emoji": "📚", "desc": "Ancient wisdom.", "color": discord.ButtonStyle.success},
    "garten": {"name": "Garten", "emoji": "🌹", "desc": "Chance for double loot.", "color": discord.ButtonStyle.danger}
}

MORA_EMOTE = "<:MORA:1364030973611610205>"

def calculate_cost(level):
    return int(5000 * (1.1 ** level))

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

async def upgrade_building(user_id, guild_id, building_key, interaction):
    ref_path = f"/Kingdom/{guild_id}/{user_id}/buildings/{building_key}"
    current_level = db.reference(ref_path).get() or 0
    cost = calculate_cost(current_level)
    
    user_mora_ref = db.reference(f"/Mora/{user_id}")
    balance = get_guild_mora(user_mora_ref.get() or {}, str(guild_id))
    
    if balance < cost:
        return False, f"Need {MORA_EMOTE} `{cost:,}` to upgrade!"
        
    schloss_path = f"/Kingdom/{guild_id}/{user_id}/buildings/schloss"
    schloss_level = db.reference(schloss_path).get() or 0
    
    if building_key != "schloss" and current_level >= schloss_level:
        return False, f"**{BUILDINGS[building_key]['name']}** cannot exceed Schloss Level ({schloss_level})! Upgrade your Schloss first."

    await addMora(user_id, -cost, interaction.channel.id, interaction.guild.id, interaction.client)
    db.reference(ref_path).set(current_level + 1)
    
    stats_ref = db.reference(f"/User Events Stats/{guild_id}/{user_id}")
    
    if building_key == "garten":
        # Update Daily Chest Bonus Chance
        # Max 50% per level (1 per level)
        new_val = min(50, (current_level + 1))
        stats_ref.update({"realm_chest_bonus_chance": new_val})
        
    if building_key == "bibliothek":
        # Update XP Boost
        # Max 50% per level (1 per level)
        new_val = min(50, (current_level + 1))
        stats_ref.update({"realm_xp_boost": new_val})

    if building_key == "theater":
        # Update Encore Chance (Summon Refund)
        # Max 50% per level (1 per level)
        new_val = min(50, (current_level + 1))
        stats_ref.update({"realm_encore_chance": new_val})
        
    return True, f"Upgraded **{BUILDINGS[building_key]['name']}** to Level {current_level + 1}!"

def get_kingdom_embed(user, guild_id, custom_color=None):
    data = db.reference(f"/Kingdom/{guild_id}/{user.id}/buildings").get() or {}
    
    total_level = 0
    fields = []
    
    for key, info in BUILDINGS.items():
        lvl = data.get(key, 0)
        total_level += lvl
        next_cost = calculate_cost(lvl)
        
        func_desc = ""
        perk_val = ""
        
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
        
        fields.append({
            "name": f"{info['emoji']} {info['name']} `Lv. {lvl}`",
            "value": f"-# {func_desc}: {perk_val}\nNext: {MORA_EMOTE} `{next_cost:,}`",
            "inline": key != "schloss"
        })
        
    rank = get_rank_title(total_level)

    embed = discord.Embed(
        title=f"🏰 {user.display_name}'s Immernachtreich Domain",
        description=(
            f"**Noble Rank**: `{rank}`\n"
            f"**Realm Level**: `{total_level}`\n"
            "-# *Construct your eternal kingdom within the darkness.*"
        ),
        color=custom_color or discord.Color.purple()
    )
    embed.set_footer(text="+1% per level • Max rewards capped at Lv. 50")
    
    perks = []
    
    schloss_lv = data.get("schloss", 0)
    theater_lv = data.get("theater", 0)
    biblio_lv = data.get("bibliothek", 0)
    garten_lv = data.get("garten", 0)
        
    for f in fields:
        embed.add_field(**f)
        
    return embed

async def setup(bot):
    pass