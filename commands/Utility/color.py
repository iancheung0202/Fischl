import re

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands


def complementary(hex_clean):
    """Gives the hex code of the opposite colour."""
    return f"#{0xFFFFFF - int(hex_clean, 16):06x}"


def warning(title, description):
    """Builds the red embed for a hex code that can't be shown."""
    return discord.Embed(
        title=title, description=description, color=discord.Color.red()
    )


def details(hex_clean, data):
    """Builds the embed describing a colour from the colour site's answer."""
    if data.get("hex", {}).get("clean") == "000000" and hex_clean != "000000":
        raise ValueError("Invalid color")
    opposite = complementary(hex_clean)
    contrast = data["contrast"]["value"].upper()
    contrast = {"#FFFFFF": "white", "#000000": "black"}.get(contrast, contrast)
    name = data["name"]["value"].lower()
    match = data["name"]["exact_match_name"] and "Exact match" or "Closest named color"
    embed = discord.Embed(
        title=f"Information about {name}",
        description=f"-# *{match}: {name}*",
        color=discord.Color(int(hex_clean, 16)),
    )
    fields = {
        "HEX": f"[{data['hex']['value']}](https://colorhexa.com/{hex_clean})",
        "RGB": data["rgb"]["value"],
        "HSL": data["hsl"]["value"],
        "CMYK": data["cmyk"]["value"],
        "HSV": data["hsv"]["value"],
        "XYZ": data["XYZ"]["value"],
        "Complementary": f"[{opposite}](https://colorhexa.com/{opposite.lstrip('#')})",
        "Contrast": f"Best with **{contrast}** text",
    }
    for label, value in fields.items():
        embed.add_field(name=label, value=value, inline=True)
    embed.set_thumbnail(
        url=f"https://dummyimage.com/200x200/{hex_clean}/{hex_clean}.png"
    )
    return embed


class Color(commands.Cog):
    """The command that describes a colour."""

    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        await self.session.close()

    async def describe(self, interaction, hex_clean):
        """Looks the colour up and sends what the colour site says about it."""
        async with self.session.get(
            "https://www.thecolorapi.com/id",
            params={"hex": hex_clean, "format": "json"},
        ) as response:
            if response.status != 200:
                return await interaction.response.send_message(
                    f"⚠️ API Error (Status {response.status})", ephemeral=True
                )
            embed = details(hex_clean, await response.json())
            await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="color", description="Visualize a hex color with detailed information"
    )
    @app_commands.describe(
        hex="The hex code of the color (3 or 6 characters, with/without #)"
    )
    @app_commands.checks.cooldown(3, 30)
    async def color(self, interaction: discord.Interaction, hex: str) -> None:
        """Shows a colour's name, its codes in every format and a swatch."""
        hex_clean = hex.lstrip("#").lower()
        if not re.fullmatch(r"^([a-f0-9]{3}){1,2}$", hex_clean):
            embed = warning(
                "⚠️ Invalid Hex Format",
                "Please use a valid 3 or 6 character hex code (e.g., `#ff0000` or `f00`).",
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        if len(hex_clean) == 3:
            hex_clean = "".join(letter * 2 for letter in hex_clean)

        try:
            await self.describe(interaction, hex_clean)
        except (KeyError, ValueError):
            embed = warning(
                "⚠️ Invalid Color Code",
                "The provided hex code doesn't match any valid color.",
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(
                f"⚠️ An unexpected error occurred: {str(e)}", ephemeral=True
            )

    @color.error
    async def color_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        """Tells a member who is on cooldown how long to wait."""
        if isinstance(error, app_commands.CommandOnCooldown):
            return await interaction.response.send_message(
                f"⏳ Please wait {error.retry_after:.1f}s before using this command again.",
                ephemeral=True,
            )
        raise error


async def setup(bot):
    await bot.add_cog(Color(bot))
