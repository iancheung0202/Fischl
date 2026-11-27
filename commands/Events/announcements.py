"""The notice shown to members with their minigame rewards."""

import discord

from commands.Events.config import MONEYDANCE_EMOTE

announcement_embed = discord.Embed(
    title="",
    description=(
        "## <:PaimonWow:1188553806456291489> **Shhhhh...** <:HuTaoEvil:1350630212617896120>\n"
        f"Your favorite Genshin characters have been getting *restless*... {MONEYDANCE_EMOTE}\n"
        "### <:CharlotteHeart:1191594476263702528> **Go see for yourself:** https://fischl.app/profile\n"
        "-# *This is just the beginning...* <:AyakaShine:1191592023946432522>"
    ),
    color=discord.Color.gold(),
)


async def setup(bot):
    pass
