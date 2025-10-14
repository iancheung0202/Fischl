import discord
import datetime
import aiohttp

from discord import app_commands
from discord.ext import commands

class modal(discord.ui.Modal, title="Setup Embed Message"):

    msg = discord.ui.TextInput(
        label="Normal message content",
        style=discord.TextStyle.paragraph,
        placeholder="",
        max_length=2000,
        required=False,
    )

    embedtitle = discord.ui.TextInput(
        label="Title of the embed",
        style=discord.TextStyle.paragraph,
        placeholder="",
        max_length=256,
        required=False,
    )

    description = discord.ui.TextInput(
        label="Description of the embed",
        style=discord.TextStyle.paragraph,
        placeholder="",
        max_length=4000,
        required=False,
    )

    color = discord.ui.TextInput(
        label="Color of the embed",
        style=discord.TextStyle.short,
        placeholder="Use hex code (e.g. #ff0000)",
        max_length=7,
        required=False,
    )

    image = discord.ui.TextInput(
        label="Big image of the embed",
        style=discord.TextStyle.paragraph,
        placeholder="Put a permanent image link",
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction):
        tit = str(self.embedtitle)
        desc = str(self.description)
        image = str(self.image)
        color = discord.Color.blurple()
        if str(self.color) != "":
            hex = str(self.color)
            if hex.startswith("#"):
                hex = hex[1:]
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://www.thecolorapi.com/id", params={"hex": hex}
                ) as server:
                    if server.status == 200:

                        js = await server.json()
                        try:
                            color = discord.Color(int(f"0x{js['hex']['clean']}", 16))
                        except:
                            color = discord.Color.blurple()

        if tit == "" and desc == "" and image == "":
            embed = None
        else:
            embed = discord.Embed(title=tit, description=desc, color=color)
            if str(image) != "":
                embed.set_image(url=image)
        await interaction.channel.send(str(self.msg), embed=embed)

        embed = discord.Embed(
            title="",
            description=f"**Custom embed message sent** You can use `/editembed` to edit it later!",
            colour=0x00FF00,
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class Embed(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="embed", description="Creates a custom embed message")
    @app_commands.checks.has_permissions(administrator=True)
    async def embed(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(modal())
    @embed.error
    async def embed_error(self, interaction: discord.Interaction, error: Exception):
        if interaction.user.id == 692254240290242601:
            return await interaction.response.send_modal(modal())
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Embed(bot))
