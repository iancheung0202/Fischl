import discord
import time

from discord import app_commands
from discord.ext import commands
from firebase_admin import db

from commands.Events.domain import get_rank_title
from commands.Events.helperFunctions import (
    get_global_leaderboard, get_guild_leaderboard,
    get_global_items_leaderboard, get_guild_items_leaderboard,
    get_global_kingdom_leaderboard, get_guild_kingdom_leaderboard,
    get_global_minigame_wins_leaderboard, get_guild_minigame_wins_leaderboard,
    get_global_active_days_leaderboard, get_guild_active_days_leaderboard,
    get_global_prestige_leaderboard, get_guild_prestige_leaderboard
)
from utils.pagination import BasePaginationView

MORA_EMOTE = "<:MORA:1364030973611610205>"
        

class Leaderboard(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="leaderboard", description="Check various leaderboards related to chat events"
    )
    @app_commands.describe(
        type="Type of leaderboard to view",
        scope="Scope of the leaderboard"
    )
    @app_commands.choices(
        type=[
            app_commands.Choice(name="Mora", value="mora"),
            app_commands.Choice(name="Inventory", value="inventory"),
            app_commands.Choice(name="Kingdom", value="kingdom"),
            app_commands.Choice(name="Minigame Wins", value="wins"),
            app_commands.Choice(name="Active Days", value="actively"),
            app_commands.Choice(name="Prestige", value="prestige"),
        ],
        scope=[
            app_commands.Choice(name="Global", value="global"),
            app_commands.Choice(name="Guild", value="server"),
        ]
    )
    async def lb(
        self, interaction: discord.Interaction, 
        type: app_commands.Choice[str],
        scope: app_commands.Choice[str]
    ) -> None:
        start_time = time.perf_counter()
        await interaction.response.defer(thinking=True)
        
        try:
            leaderboard_types = {
                "mora": (get_global_leaderboard, get_guild_leaderboard),
                "inventory": (get_global_items_leaderboard, get_guild_items_leaderboard),
                "kingdom": (get_global_kingdom_leaderboard, get_guild_kingdom_leaderboard),
                "wins": (get_global_minigame_wins_leaderboard, get_guild_minigame_wins_leaderboard),
                "actively": (get_global_active_days_leaderboard, get_guild_active_days_leaderboard),
                "prestige": (get_global_prestige_leaderboard, get_guild_prestige_leaderboard),
            }
            
            if type.value in leaderboard_types:
                global_func, server_func = leaderboard_types[type.value]
                
                if scope.value == "global":
                    ranking = await global_func(interaction.client.pool)
                else:  # server
                    ranking = await server_func(interaction.client.pool, interaction.guild.id)
                
                dict_lb = [{"User ID": uid, "Value": value} for uid, value in ranking]
            else:
                dict_lb = []

        except Exception as e:
            print(f"[lb error] {e}")
            dict_lb = []

        user_rank = None
        for idx, entry in enumerate(dict_lb):
            if entry["User ID"] == interaction.user.id:
                user_rank = idx + 1
                break

        pages = []
        page_lines = []
        entries = dict_lb
        
        styling_config = {
            "mora": {
                "icon": MORA_EMOTE,
                "color_global": 0xFFD700,
                "color_server": 0x2A7E19,
                "title": "Mora Leaderboard",
                "metric": "their total mora",
                "has_rank_title": False,
            },
            "inventory": {
                "icon": "🏷️",
                "color_global": 0x6A0DAD,
                "color_server": 0x6A0DAD,
                "title": "Inventory Leaderboard",
                "metric": "their total owned items",
                "has_rank_title": False,
            },
            "kingdom": {
                "icon": "🏰",
                "color_global": discord.Color.purple(),
                "color_server": discord.Color.purple(),
                "title": "Kingdom Rankings",
                "metric": "their total Kingdom Level",
                "has_rank_title": True,
            },
            "wins": {
                "icon": "✌️",
                "color_global": 0x00D9FF,
                "color_server": 0x00D9FF,
                "title": "Minigame Wins Leaderboard",
                "metric": "their total minigame wins",
                "has_rank_title": False,
            },
            "actively": {
                "icon": "😎",
                "color_global": 0x00D9FF,
                "color_server": 0x00D9FF,
                "title": "Active Days Leaderboard",
                "metric": "unique days with minigame earnings",
                "has_rank_title": False,
            },
            "prestige": {
                "icon": "<:PRIMOGEM:1364031230357540894>",
                "color_global": 0xFFB6C1,
                "color_server": 0xFFB6C1,
                "title": "Prestige Leaderboard",
                "metric": "total prestige earned",
                "has_rank_title": False,
            },
        }
        
        config = styling_config.get(type.value, {})
        icon = config.get("icon", "")
        color = config.get("color_global") if scope.value == "global" else config.get("color_server")
        has_rank_title = config.get("has_rank_title", False)
        
        is_global = scope.value == "global"
        title_prefix = "Global " if is_global else f"{interaction.guild.name}'s "
        title = title_prefix + config.get("title", "")
        
        scope_text = "across all servers" if is_global else "in this server"
        metric = config.get("metric", "")
        description_intro = f"An all-time ranking of users {scope_text} based on {metric}."

        for idx, row in enumerate(entries, start=1):
            val = row["Value"]
            mention = f"<@{row['User ID']}>"
            
            suffix = ""
            if has_rank_title:
                rank_title = get_rank_title(val)
                suffix = f" *({rank_title})*"
                
            line = f"{idx}. {mention} - {icon} `{val:,}`{suffix}"
            if row["User ID"] == interaction.user.id:
                line += " <:you:1339737311319162890>"

            page_lines.append(line)

            if idx % 10 == 0 or idx == len(entries):
                current_page = (idx - 1) // 10 + 1
                total_pages = (len(entries) + 9) // 10
                
                footer_text = ""
                if user_rank:
                    user_page = (user_rank - 1) // 10 + 1
                    if user_page != current_page:
                        footer_text += f"Your Rank: #{user_rank} (Page {user_page})"
                    else:
                        footer_text += f"Your Rank: #{user_rank}"
                
                embed = discord.Embed(
                    title=title,
                    description=f"{description_intro}\n\n" + "\n".join(page_lines),
                    color=color
                )
                
                if scope.value == "server" and interaction.guild.icon:
                    embed.set_thumbnail(url=interaction.guild.icon.url)
                
                embed.set_footer(text=footer_text)
                pages.append(embed)
                page_lines = []

        if not pages:
            pages.append(discord.Embed(
                title=title,
                description="No data available",
                color=0x999999
            ))

        view = BasePaginationView(pages)
        await interaction.followup.send(embed=pages[0], view=view)
        end_time = time.perf_counter()
        print(f"Total /lb execution time: {end_time - start_time} seconds")
        

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Leaderboard(bot))