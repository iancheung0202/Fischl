import discord
from commands.Events.helperFunctions import subtractGuildMora, get_building_level, increment_building_level, apply_discount, get_domain_discount

from commands.Events.config import MORA_EMOTE, BUILDINGS, DOMAIN_NAME, DOMAIN_DESCRIPTION, get_rank_title, calculate_cost, perk_info

def format_domain_cost(original_cost: int, discounted_cost: int, discount_percent: int) -> str:
    if discount_percent <= 0 or discounted_cost >= original_cost:
        return f"{MORA_EMOTE} `{original_cost:,}`"

    return f"{MORA_EMOTE} ~~`{original_cost:,}`~~ ➜ `{discounted_cost:,}`"

async def upgrade_building(user_id, guild_id, building_key, interaction):
    pool = interaction.client.pool
    current_level = await get_building_level(pool, guild_id, user_id, building_key)
    discount = await get_domain_discount(pool, guild_id, user_id)
    cost = apply_discount(calculate_cost(current_level), discount)
    
    schloss_level = await get_building_level(pool, guild_id, user_id, "schloss")
    
    if building_key != next(iter(BUILDINGS)) and current_level >= schloss_level:
        return False, f"**{BUILDINGS[building_key]['name']}** cannot exceed {BUILDINGS[next(iter(BUILDINGS))]['name']} Level ({schloss_level})! Upgrade your {BUILDINGS[next(iter(BUILDINGS))]['name']} first."
    
    result = await subtractGuildMora(pool, user_id, cost, interaction.channel.id, guild_id)
    
    if result is False:
        return False, f"Insufficient balance! You need at least {MORA_EMOTE} `{cost:,}` to upgrade!"
    
    await increment_building_level(pool, guild_id, user_id, building_key)
    
    from commands.Events.quests import update_quest
    await update_quest(user_id, guild_id, interaction.channel.id, {"upgrade_buildings": 1}, interaction.client)
        
    return True, f"Upgraded **{BUILDINGS[building_key]['name']}** to Level {current_level + 1}!\nYou now have {MORA_EMOTE} `{result:,}` remaining."

async def get_kingdom_embed(user, guild_id, custom_color=None, pool=None):
    from commands.Events.helperFunctions import get_kingdom_buildings
    
    if pool is None:
        data = {}
    else:
        kb_data = await get_kingdom_buildings(pool, guild_id, user.id)
        data = kb_data
    
    total_level = 0
    fields = []
    discount = 0
    if pool is not None:
        discount = await get_domain_discount(pool, guild_id, user.id)
    
    for key, info in BUILDINGS.items():
        lvl = data.get(key, 0)
        total_level += lvl
        original_cost = calculate_cost(lvl)
        next_cost = apply_discount(original_cost, discount)
        next_cost_text = format_domain_cost(original_cost, next_cost, discount)
        
        func_desc = ""
        perk_val = ""
        
        func_desc, perk_val = perk_info(key, lvl)
        
        fields.append({
            "name": f"{info['emoji']} {info['name']} `Lv. {lvl}`",
            "value": f"-# {func_desc}: {perk_val}\nNext: {next_cost_text}",
            "inline": key != next(iter(BUILDINGS))
        })
        
    rank = get_rank_title(total_level)

    embed = discord.Embed(
        title=f"🏰 {user.display_name}'s {DOMAIN_NAME}",
        description=(
            f"**Rank**: `{rank}`\n"
            f"**Total Level**: `{total_level}`\n"
            f"-# *{DOMAIN_DESCRIPTION}*"
        ),
        color=custom_color or discord.Color.purple()
    )
    embed.set_footer(text="+1% per level • Max rewards capped at Lv. 50")
        
    for f in fields:
        embed.add_field(**f)
        
    return embed

async def setup(bot):
    pass