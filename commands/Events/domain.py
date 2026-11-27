"""The kingdom: its embed, and upgrading one of its buildings."""

import discord

from commands.Events.config import (
    BUILDINGS,
    DOMAIN_DESCRIPTION,
    DOMAIN_NAME,
    MORA_EMOTE,
    calculate_cost,
    get_rank_title,
    perk_info,
)
from commands.Events.helperFunctions import (
    apply_discount,
    get_building_level,
    get_domain_discount,
    get_kingdom_buildings,
    increment_building_level,
    subtractGuildMora,
)
from commands.Events.quests import update_quest

CASTLE = next(iter(BUILDINGS))


def format_domain_cost(
    original_cost: int, discounted_cost: int, discount_percent: int
) -> str:
    """Gives the price, with the full price struck through when a discount applies."""
    if discount_percent <= 0 or discounted_cost >= original_cost:
        return f"{MORA_EMOTE} `{original_cost:,}`"

    return f"{MORA_EMOTE} ~~`{original_cost:,}`~~ ➜ `{discounted_cost:,}`"


async def upgrade_building(user_id, guild_id, building_key, interaction):
    """Buys the building's next level; gives whether it worked and what to tell the member."""
    pool = interaction.client.pool
    current_level = await get_building_level(pool, guild_id, user_id, building_key)
    discount = await get_domain_discount(pool, guild_id, user_id)
    cost = apply_discount(calculate_cost(current_level), discount)
    castle_level = await get_building_level(pool, guild_id, user_id, "schloss")
    name, castle = BUILDINGS[building_key]["name"], BUILDINGS[CASTLE]["name"]

    if building_key != CASTLE and current_level >= castle_level:
        return (
            False,
            f"**{name}** cannot exceed {castle} Level ({castle_level})! Upgrade your {castle} first.",
        )

    result = await subtractGuildMora(
        pool, user_id, cost, interaction.channel.id, guild_id
    )
    if result is False:
        return (
            False,
            f"Insufficient balance! You need at least {MORA_EMOTE} `{cost:,}` to upgrade!",
        )

    await increment_building_level(pool, guild_id, user_id, building_key)
    await update_quest(
        user_id,
        guild_id,
        interaction.channel.id,
        {"upgrade_buildings": 1},
        interaction.client,
    )
    return (
        True,
        f"Upgraded **{name}** to Level {current_level + 1}!\nYou now have {MORA_EMOTE} `{result:,}` remaining.",
    )


async def get_kingdom_embed(user, guild_id, custom_color=None, pool=None):
    """Gives the embed showing every building's level, perk and next price."""
    levels, discount = {}, 0
    if pool is not None:
        levels = await get_kingdom_buildings(pool, guild_id, user.id)
        discount = await get_domain_discount(pool, guild_id, user.id)

    total_level = sum(levels.get(key, 0) for key in BUILDINGS)
    embed = discord.Embed(
        title=f"🏰 {user.display_name}'s {DOMAIN_NAME}",
        description=(
            f"**Rank**: `{get_rank_title(total_level)}`\n"
            f"**Total Level**: `{total_level}`\n"
            f"-# *{DOMAIN_DESCRIPTION}*"
        ),
        color=custom_color or discord.Color.purple(),
    )
    embed.set_footer(text="+1% per level • Max rewards capped at Lv. 50")

    for key, info in BUILDINGS.items():
        level = levels.get(key, 0)
        cost = calculate_cost(level)
        price = format_domain_cost(cost, apply_discount(cost, discount), discount)
        does, perk = perk_info(key, level)
        embed.add_field(
            name=f"{info['emoji']} {info['name']} `Lv. {level}`",
            value=f"-# {does}: {perk}\nNext: {price}",
            inline=key != CASTLE,
        )
    return embed


async def setup(bot):
    pass
