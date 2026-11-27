import asyncio
import datetime
import io
import re

import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageFont

FONT = "./assets/ja-jp.ttf"
SIZE = (3500, 250)
BACKGROUND = (0, 0, 1)
TOO_LONG = ":warning: Your text length must not be longer than **30 characters** or else in most cases we cannot fit your text in the image! Please try again by separating your text and do the command multiple times!"
BAD_HEX = "Hey! It looks like you have given me an invalid hex code. \n\nHex code uses the letters A-F, in addition to the digits 0-9, for a total of 16 symbols. If you have trouble finding the hex code, you could visit [this website](https://https://htmlcolorcodes.com/) to get help."


def draw(colour, phrase):
    """Draws the phrase on a see-through strip and gives it as a file to send."""
    strip = Image.new("RGB", SIZE, BACKGROUND)
    font = ImageFont.truetype(FONT, 200)
    ImageDraw.Draw(strip).text((20, 0), phrase, font=font, fill=colour)

    inked = Image.new("L", SIZE, 0)
    for band, empty in zip(strip.split(), BACKGROUND):
        changed = band.point(lambda value, empty=empty: 255 * (value != empty))
        inked = ImageChops.lighter(inked, changed)
    picture = Image.new("RGBA", SIZE, (255, 255, 255, 0))
    picture.paste(strip, mask=inked)

    file = io.BytesIO()
    picture.save(file, "PNG")
    file.seek(0)
    return discord.File(file, filename="text.png")


async def refuse(interaction, title, description, colour):
    """Tells the member what was wrong with their input, then stops the command."""
    embed = discord.Embed(title=title, description=description, colour=colour)
    embed.set_author(name=interaction.user.name, icon_url=interaction.user.avatar.url)
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
    embed.set_footer(text="Action terminated")
    await interaction.followup.send(embed=embed, ephemeral=True)
    raise Exception()


class Text(commands.Cog):
    """The command that writes a phrase in the Genshin font."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="text", description="Generates texts with Genshin-styled font"
    )
    @app_commands.describe(
        color="The hex code of the color of the text (Format: #ffffff)",
        phrase="Words to be written",
    )
    async def text(
        self, interaction: discord.Interaction, color: str, phrase: str
    ) -> None:
        """Sends the phrase as a picture in the chosen colour."""
        await interaction.response.defer(ephemeral=True)
        if len(phrase) > 30:
            await refuse(interaction, "Too long!", TOO_LONG, 0x93A7ED)
        if color[0] != "#":
            color = "#" + color
        if not re.search(r"^#(?:[0-9a-fA-F]{3}){1,2}$", color):
            red = discord.Color.red()
            await refuse(interaction, "⚠️ Invalid hex code", BAD_HEX, red)

        colour = ImageColor.getcolor(color, "RGB")
        file = await asyncio.to_thread(draw, colour, phrase)
        await interaction.followup.send(file=file)


async def setup(bot):
    await bot.add_cog(Text(bot))
