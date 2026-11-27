"""`/leaderboard`: all-time rankings for mora, items, kingdom, wins, active days, prestige and sigils."""

import time

import discord
from discord import app_commands
from discord.ext import commands

from commands.Events.config import (
    CURRENCY_NAME,
    GLOBAL_MORA_EMOTE,
    GLOBAL_SIGIL_EMOTE,
    GUILD_MORA_EMOTE,
    GUILD_SIGIL_EMOTE,
    PRESTIGE_EMOTE,
    SIGIL_CURRENCY_NAME,
    get_rank_title,
)
from commands.Events.helperFunctions import (
    get_global_active_days_leaderboard,
    get_global_items_leaderboard,
    get_global_kingdom_leaderboard,
    get_global_leaderboard,
    get_global_minigame_wins_leaderboard,
    get_global_prestige_leaderboard,
    get_global_sigils_leaderboard,
    get_guild_active_days_leaderboard,
    get_guild_items_leaderboard,
    get_guild_kingdom_leaderboard,
    get_guild_leaderboard,
    get_guild_minigame_wins_leaderboard,
    get_guild_prestige_leaderboard,
    get_guild_sigils_leaderboard,
)
from utils.pagination import BasePaginationView

YOU = "<:you:1339737311319162890>"
# What each leaderboard reads (global, server) and how it is shown.
BOARDS = {
    "mora": {
        "rankings": (get_global_leaderboard, get_guild_leaderboard),
        "icons": (GLOBAL_MORA_EMOTE, GUILD_MORA_EMOTE),
        "colors": (0xFFD700, 0x2A7E19),
        "title": f"{CURRENCY_NAME} Leaderboard",
        "metric": f"their total {CURRENCY_NAME.lower()}",
    },
    "inventory": {
        "rankings": (get_global_items_leaderboard, get_guild_items_leaderboard),
        "icons": ("🏷️", "🏷️"),
        "colors": (0x6A0DAD, 0x6A0DAD),
        "title": "Inventory Leaderboard",
        "metric": "their total owned items",
    },
    "kingdom": {
        "rankings": (get_global_kingdom_leaderboard, get_guild_kingdom_leaderboard),
        "icons": ("🏰", "🏰"),
        "colors": (discord.Color.purple(), discord.Color.purple()),
        "title": "Kingdom Rankings",
        "metric": "their total Kingdom Level",
        "ranked": True,
    },
    "wins": {
        "rankings": (
            get_global_minigame_wins_leaderboard,
            get_guild_minigame_wins_leaderboard,
        ),
        "icons": ("✌️", "✌️"),
        "colors": (0x00D9FF, 0x00D9FF),
        "title": "Minigame Wins Leaderboard",
        "metric": "their total minigame wins",
    },
    "actively": {
        "rankings": (
            get_global_active_days_leaderboard,
            get_guild_active_days_leaderboard,
        ),
        "icons": ("😎", "😎"),
        "colors": (0x00D9FF, 0x00D9FF),
        "title": "Active Days Leaderboard",
        "metric": "unique days with minigame earnings",
    },
    "prestige": {
        "rankings": (get_global_prestige_leaderboard, get_guild_prestige_leaderboard),
        "icons": (PRESTIGE_EMOTE, PRESTIGE_EMOTE),
        "colors": (0xFFB6C1, 0xFFB6C1),
        "title": "Prestige Leaderboard",
        "metric": "total prestige earned",
    },
    "sigils": {
        "rankings": (get_global_sigils_leaderboard, get_guild_sigils_leaderboard),
        "icons": (GLOBAL_SIGIL_EMOTE, GUILD_SIGIL_EMOTE),
        "colors": (0x9B59B6, 0x9B59B6),
        "title": f"{SIGIL_CURRENCY_NAME} Leaderboard",
        "metric": "their total sigils earned",
    },
}


async def ranking(board, is_global, interaction):
    """Gives the (member, value) pairs in rank order, or nothing if the lookup fails."""
    pool = interaction.client.pool
    try:
        if is_global:
            return list(await board["rankings"][0](pool))
        return list(await board["rankings"][1](pool, interaction.guild.id))
    except Exception as e:
        print(f"[lb error] {e}")
        return []


def rank_of(entries, member):
    """Gives the member's place, or None when they are not ranked."""
    for place, (uid, _) in enumerate(entries, start=1):
        if uid == member:
            return place
    return None


def footer(rank, page):
    """Says the viewer's rank, and its page when that is another one."""
    if not rank:
        return ""
    own = (rank - 1) // 10 + 1
    return f"Your Rank: #{rank}" + (f" (Page {own})" if own != page else "")


def pages_of(board, is_global, entries, interaction):
    """Gives the leaderboard as embeds of ten places each."""
    guild, viewer = interaction.guild, interaction.user.id
    icon, color = board["icons"][not is_global], board["colors"][not is_global]
    title = ("Global " if is_global else f"{guild.name}'s ") + board["title"]
    scope = "across all servers" if is_global else "in this server"
    intro = f"An all-time ranking of users {scope} based on {board['metric']}."
    rank = rank_of(entries, viewer)

    lines = []
    for place, (uid, value) in enumerate(entries, start=1):
        suffix = f" *({get_rank_title(value)})*" if board.get("ranked") else ""
        you = f" {YOU}" if uid == viewer else ""
        lines.append(f"{place}. <@{uid}> - {icon} `{value:,}`{suffix}{you}")

    pages = []
    for start in range(0, len(lines), 10):
        embed = discord.Embed(
            title=title,
            description=f"{intro}\n\n" + "\n".join(lines[start : start + 10]),
            color=color,
        )
        if not is_global and guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.set_footer(text=footer(rank, start // 10 + 1))
        pages.append(embed)
    return pages or [
        discord.Embed(title=title, description="No data available", color=0x999999)
    ]


class Leaderboard(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="leaderboard",
        description="Check various leaderboards related to chat events",
    )
    @app_commands.describe(
        type="Type of leaderboard to view", scope="Scope of the leaderboard"
    )
    @app_commands.choices(
        type=[
            app_commands.Choice(name=CURRENCY_NAME, value="mora"),
            app_commands.Choice(name="Inventory", value="inventory"),
            app_commands.Choice(name="Kingdom", value="kingdom"),
            app_commands.Choice(name="Minigame Wins", value="wins"),
            app_commands.Choice(name="Active Days", value="actively"),
            app_commands.Choice(name="Prestige", value="prestige"),
            app_commands.Choice(name=SIGIL_CURRENCY_NAME, value="sigils"),
        ],
        scope=[
            app_commands.Choice(name="Global", value="global"),
            app_commands.Choice(name="Guild", value="server"),
        ],
    )
    async def lb(
        self,
        interaction: discord.Interaction,
        type: app_commands.Choice[str],
        scope: app_commands.Choice[str],
    ) -> None:
        start_time = time.perf_counter()
        await interaction.response.defer(thinking=True)
        board, is_global = BOARDS[type.value], scope.value == "global"
        entries = await ranking(board, is_global, interaction)
        pages = pages_of(board, is_global, entries, interaction)
        await interaction.followup.send(embed=pages[0], view=BasePaginationView(pages))
        end_time = time.perf_counter()
        print(f"Total /lb execution time: {end_time - start_time} seconds")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Leaderboard(bot))
