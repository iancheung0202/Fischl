import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from commands.Utility import posting


async def embed_colour(color):
    """Has the colour site read a hex code; blurple if none is given or it can't."""
    if color is None:
        return discord.Color.blurple()
    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://www.thecolorapi.com/id", params={"hex": color.removeprefix("#")}
        ) as answer:
            if answer.status != 200:
                raise NameError("name 'embedColor' is not defined")
            found = await answer.json()
            try:
                return discord.Color(int(found["hex"]["clean"], 16))
            except Exception:
                return discord.Color.blurple()


class WebEvent(commands.Cog):
    """The command that announces a game's web event."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="send-webevent", description="Sends a message for web event in embed"
    )
    @app_commands.choices(
        game=[
            app_commands.Choice(name="Genshin Impact", value="genshin"),
            app_commands.Choice(name="Honkai: Star Rail", value="hsr"),
            app_commands.Choice(name="Zenless Zone Zero", value="zzz"),
        ]
    )
    @app_commands.describe(
        game="The game that the web event belongs",
        link="Link to the event",
        role="The role you would like to ping alongside this message",
        title="Event title",
        details="Event description/details",
        image="Embed image",
        color="Embed color in hex code format (e.g. #FFF000)",
    )
    @app_commands.guild_only()
    async def webevent(
        self,
        interaction: discord.Interaction,
        game: app_commands.Choice[str],
        link: str,
        role: discord.Role = None,
        title: str = None,
        details: str = None,
        image: discord.Attachment = None,
        color: str = None,
    ) -> None:
        """Posts the event as an embed with a link button."""
        embed = discord.Embed(
            title=title, description=details, url=link, color=await embed_colour(color)
        )
        if image is not None:
            embed.set_image(url=await posting.hosted(interaction, image, "webevent"))
        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                label=title,
                style=discord.ButtonStyle.link,
                emoji="<:link:943068848058413106>",
                url=link,
            )
        )
        posting.sign(embed, interaction.guild)

        headline = f"**• New {game.name} Web Event**"
        if await posting.post(interaction, headline, role, embed, view):
            await interaction.response.send_message(posting.SENT, ephemeral=True)


async def setup(bot):
    await bot.add_cog(WebEvent(bot))
