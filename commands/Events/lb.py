import discord
import time

from discord import app_commands
from discord.ext import commands
from firebase_admin import db

from commands.Events.domain import get_rank_title
from commands.Events.helperFunctions import get_global_leaderboard, get_guild_leaderboard

MORA_EMOTE = "<:MORA:1364030973611610205>"

class LeaderboardPageView(discord.ui.View):
    def __init__(self, pages):
        super().__init__()
        self.page = 0
        self.pages = pages

    @discord.ui.button(
        style=discord.ButtonStyle.grey,
        custom_id="super_prev_lb",
        emoji="<:fastbackward:1351972112696479824>",
    )
    async def super_prev_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.page = 0
        embed = self.pages[self.page]
        embed.set_footer(text=f"Page {self.page + 1} of {len(self.pages)}")
        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(
        style=discord.ButtonStyle.grey,
        custom_id="prev_lb",
        emoji="<:backarrow:1351972111010369618>",
    )
    async def prev_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.page > 0:
            self.page -= 1
        else:
            self.page = len(self.pages) - 1
        embed = self.pages[self.page]
        embed.set_footer(text=f"Page {self.page + 1} of {len(self.pages)}")
        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(
        style=discord.ButtonStyle.grey,
        custom_id="next_lb",
        emoji="<:rightarrow:1351972116819480616>",
    )
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.page < len(self.pages) - 1:
            self.page += 1
        else:
            self.page = 0
        embed = self.pages[self.page]
        embed.set_footer(text=f"Page {self.page + 1} of {len(self.pages)}")
        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(
        style=discord.ButtonStyle.grey,
        custom_id="super_next_lb",
        emoji="<:fastforward:1351972114433048719>",
    ) 
    async def super_next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.page = len(self.pages) - 1
        embed = self.pages[self.page]
        embed.set_footer(text=f"Page {self.page + 1} of {len(self.pages)}")
        await interaction.response.edit_message(embed=embed)
        

class Leaderboard(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="lb", description="Check the global or server leaderboard"
    )
    @app_commands.describe(type="Specify which type of leaderboard you want to view")
    @app_commands.choices(
        type=[
            app_commands.Choice(name="Global Mora Leaderboard", value="global"),
            app_commands.Choice(name="Server-specific Mora Leaderboard", value="server"),
            app_commands.Choice(name="Role/Title Leaderboard", value="server_items"),
            app_commands.Choice(name="Server-specific Kingdom Leaderboard", value="kingdom"),
        ]
    )
    async def lb(
        self, interaction: discord.Interaction, type: app_commands.Choice[str]
    ) -> None:
        start_time = time.perf_counter()
        await interaction.response.defer(thinking=True)
        dict_lb = []

        try:
            if type.value == "kingdom":
                from commands.Events.helperFunctions import get_guild_kingdom_leaderboard
                ranking = await get_guild_kingdom_leaderboard(interaction.client.pool, interaction.guild.id, limit=100)
                ranking = [{"User ID": uid, "Level": level} for uid, level in ranking]
                
                # Fetch members
                for member_data in ranking[:50]:
                    try:
                        if await interaction.guild.fetch_member(member_data["User ID"]):
                            dict_lb.append(member_data)
                    except (discord.NotFound, discord.HTTPException):
                        continue

            elif type.value == "server_items":
                ref_inv = db.reference("/User Events Inventory")
                inventories = ref_inv.get() or {}
                
                potential_members = []
                for _, val in inventories.items():
                    uid = val["User ID"]
                    count = sum(1 for item in val.get("Items", [])
                                if len(item) > 3 and item[3] == interaction.guild.id)
                    if count > 0:
                        potential_members.append({"User ID": uid, "Count": count})
                
                potential_members.sort(key=lambda x: x["Count"], reverse=True)
                
                for member_data in potential_members[:50]:
                    uid = member_data["User ID"]
                    try:
                        if await interaction.guild.fetch_member(uid):
                            dict_lb.append(member_data)
                    except discord.NotFound:
                        continue
                    except discord.HTTPException:
                        continue

            else:
                if type.value == "global":
                    leaderboard = await get_global_leaderboard(interaction.client.pool, limit=50)
                    for uid, mora in leaderboard:
                        dict_lb.append({"User ID": uid, "Mora": mora})

                elif type.value == "server":
                    leaderboard = await get_guild_leaderboard(interaction.client.pool, interaction.guild.id, limit=50)
                    for uid, mora in leaderboard:
                        dict_lb.append({"User ID": uid, "Mora": mora})

            if type.value == "server_items":
                dict_lb.sort(key=lambda x: x["Count"], reverse=True)
            elif type.value == "kingdom":
                dict_lb.sort(key=lambda x: x["Level"], reverse=True)

        except Exception as e:
            print(f"[lb error] {e}")
            dict_lb = []

        pages = []
        page_lines = []
        entries = dict_lb
        max_entries = 50 if type.value == "global" else len(entries)
        for idx, row in enumerate(entries[:max_entries], start=1):
            val = row["Count"] if type.value == "server_items" else row["Level"] if type.value == "kingdom" else row["Mora"]
            mention = f"<@{row['User ID']}>"
            icon = "🏷️" if type.value=="server_items" else "🏰" if type.value=="kingdom" else MORA_EMOTE
            
            # Add Rank Title for Kingdom
            suffix = ""
            if type.value == "kingdom":
                rank_title = get_rank_title(val)
                suffix = f" *({rank_title})*"
                
            line = f"{idx}. {mention} - {icon} `{val:,}`{suffix}"
            if row["User ID"] == interaction.user.id:
                line += " <:you:1339737311319162890>"

            page_lines.append(line)

            if idx % 10 == 0 or idx == max_entries:
                title = (
                    "Global Leaderboard (Top 50)"
                    if type.value == "global"
                    else f"{interaction.guild.name}'s Leaderboard"
                    if type.value == "server"
                    else f"{interaction.guild.name}'s Kingdom Rankings"
                    if type.value == "kingdom"
                    else f"{interaction.guild.name}'s Item Leaderboard"
                )
                desc_intro = (
                    "A ranking of users from all servers based on their total mora."
                    if type.value=="global"
                    else "A ranking of users within this server based on their current total mora."
                    if type.value=="server"
                    else "A ranking of noble domains within this server based on total Kingdom Level."
                    if type.value=="kingdom"
                    else "A ranking of users within this server based on their total owned roles/titles."
                )
                embed = discord.Embed(
                    title=title,
                    description=f"{desc_intro}\n\n" + "\n".join(page_lines),
                    color=(
                        0xFFD700
                        if type.value=="global"
                        else 0x2A7E19
                        if type.value=="server"
                        else discord.Color.purple()
                        if type.value=="kingdom"
                        else 0x6A0DAD
                    )
                )
                if type.value in ("server", "server_items") and interaction.guild.icon:
                    embed.set_thumbnail(url=interaction.guild.icon.url)

                pages.append(embed)
                page_lines = []

        if not pages:
            pages.append(discord.Embed(
                title="Leaderboard",
                description="No data available",
                color=0x999999
            ))

        for i, pg in enumerate(pages, start=1):
            pg.set_footer(text=f"Page {i} of {len(pages)}")

        await interaction.followup.send(embed=pages[0], view=LeaderboardPageView(pages))
        end_time = time.perf_counter()
        print(f"Total /lb execution time: {end_time - start_time} seconds")
        

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Leaderboard(bot))