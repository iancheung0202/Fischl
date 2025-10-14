import discord
import aiohttp
import re

from discord import app_commands
from discord.ext import commands
from discord.app_commands import checks


class Color(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        await self.session.close()

    def calculate_complementary(self, hex_clean: str) -> str:
        r = int(hex_clean[0:2], 16)
        g = int(hex_clean[2:4], 16)
        b = int(hex_clean[4:6], 16)
        
        complement_r = 255 - r
        complement_g = 255 - g
        complement_b = 255 - b
        
        return f"#{complement_r:02x}{complement_g:02x}{complement_b:02x}"

    @app_commands.command(name="color", description="Visualize a hex color with detailed information")
    @app_commands.describe(hex="The hex code of the color (3 or 6 characters, with/without #)")
    @checks.cooldown(3, 30)
    async def color(self, interaction: discord.Interaction, hex: str) -> None:
        hex_clean = hex.lstrip('#').lower()
        
        if not re.fullmatch(r'^([a-f0-9]{3}){1,2}$', hex_clean):
            embed = discord.Embed(
                title="⚠️ Invalid Hex Format",
                description="Please use a valid 3 or 6 character hex code (e.g., `#ff0000` or `f00`).",
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if len(hex_clean) == 3:
            hex_clean = ''.join([c * 2 for c in hex_clean])

        try:
            async with self.session.get("https://www.thecolorapi.com/id", params={"hex": hex_clean, "format": "json"}) as response:
                if response.status != 200:
                    return await interaction.response.send_message(f"⚠️ API Error (Status {response.status})", ephemeral=True)

                data = await response.json()

                if data.get("hex", {}).get("clean") == "000000" and hex_clean != "000000":
                    raise ValueError("Invalid color")

                complementary_hex = self.calculate_complementary(hex_clean)
                
                if data['contrast']['value'].upper() == "#FFFFFF":
                    contrast_color = "white"
                elif data['contrast']['value'].upper() == "#000000":
                    contrast_color = "black"
                else:
                    contrast_color = data['contrast']['value'].upper()
                
                embed = discord.Embed(
                    title=f"Information about {data['name']['value'].lower()}",
                    description=f"-# *{data['name']['exact_match_name'] and 'Exact match' or 'Closest named color'}: {data['name']['value'].lower()}*",
                    color=discord.Color(int(hex_clean, 16))
                )

                color_fields = [
                    ("HEX", f"[{data['hex']['value']}](https://colorhexa.com/{hex_clean})", True),
                    ("RGB", data['rgb']['value'], True),
                    ("HSL", data['hsl']['value'], True),
                    ("CMYK", data['cmyk']['value'], True),
                    ("HSV", data['hsv']['value'], True),
                    ("XYZ", data['XYZ']['value'], True),
                    ("Complementary", f"[{complementary_hex}](https://colorhexa.com/{complementary_hex.lstrip('#')})", True),
                    ("Contrast", f"Best with **{contrast_color}** text", True)
                ]

                for name, value, inline in color_fields:
                    embed.add_field(name=name, value=value, inline=inline)

                embed.set_thumbnail(url=f"https://dummyimage.com/200x200/{hex_clean}/{hex_clean}.png")
                
                await interaction.response.send_message(embed=embed)

        except (KeyError, ValueError):
            embed = discord.Embed(
                title="⚠️ Invalid Color Code",
                description="The provided hex code doesn't match any valid color.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(
                f"⚠️ An unexpected error occurred: {str(e)}", 
                ephemeral=True
            )

    @color.error
    async def color_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            return await interaction.response.send_message(
                f"⏳ Please wait {error.retry_after:.1f}s before using this command again.",
                ephemeral=True
            )
        raise error


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Color(bot))