import asyncio
import random

import discord

from commands.Events.config import MORA_EMOTE
from commands.Events.games.common import count, earn
from commands.Events.helperFunctions import get_channel_mora_multiplier

SECONDS = 20


class BankHeistView(discord.ui.View):
    """One button; every press adds a random amount to what the member who pressed will be paid."""

    def __init__(self, multiplier: float, embed: discord.Embed):
        super().__init__(timeout=None)
        self.multiplier = multiplier
        self.embed = embed
        self.clicks = {}
        self.stolen = {}

    def ranked(self) -> list:
        """Gives the members by what they have stolen, most first."""
        return sorted(self.stolen, key=self.stolen.get, reverse=True)

    @discord.ui.button(
        style=discord.ButtonStyle.grey, emoji="💰", label="Click to Steal"
    )
    async def steal(self, interaction: discord.Interaction, button):
        uid = interaction.user.id
        self.clicks[uid] = self.clicks.get(uid, 0) + 1
        self.stolen[uid] = self.stolen.get(uid, 0) + int(
            random.randint(500, 600) * self.multiplier
        )
        self.embed.set_field_at(
            0,
            name=f"Leaderboard ({len(self.stolen)} participants)",
            value="\n".join(
                f"-# <@{member}>: {self.clicks[member]} clicks → {MORA_EMOTE} `{self.stolen[member]}`"
                for member in self.ranked()[:10]
            ),
            inline=False,
        )
        await interaction.response.edit_message(embed=self.embed)


async def end_heist(view, message, client) -> None:
    """Closes the heist after 20 seconds, pays everyone what they stole and counts the top member as winner."""
    await asyncio.sleep(SECONDS)
    view.stop()
    ranked = view.ranked()
    embed = view.embed
    embed.title = "⏳ Bank Heist - Finished!"
    embed.description = "Time's up! Rewards distributed below."
    embed.color = discord.Color.green()
    embed.set_footer(text="")
    embed.add_field(
        name="Final Results",
        value="\n".join(
            f"{rank}. <@{uid}>: {MORA_EMOTE} `{view.stolen[uid]}` ({view.clicks[uid]} clicks)"
            for rank, uid in enumerate(ranked, 1)
        )
        or "No participants",
        inline=False,
    )
    await message.edit(embed=embed, view=None)

    lines = []
    for uid, stolen in view.stolen.items():
        text, earned = await earn(client, message.channel, uid, stolen)
        lines.append(f"-# <@{uid}>: {MORA_EMOTE} `{text}`")
        await count(client, message.channel, uid, earned, won=uid == ranked[0])
    await message.reply(
        embed=discord.Embed(
            title="Rewards Distributed",
            description="\n".join(lines),
            color=discord.Color.green(),
        )
    )


async def bankHeist(channel, client):
    multiplier = await get_channel_mora_multiplier(client.pool, channel.id)
    embed = discord.Embed(
        title="Bank Heist! 💰 ",
        description=(
            "Click the button below as many times as you can in 20 seconds!\n"
            f"Each click earns you {MORA_EMOTE} `{int(500 * multiplier)}-{int(600 * multiplier)}` Mora!\n\n"
            "**Top participants will be shown here**"
        ),
        color=discord.Color.gold(),
    )
    embed.add_field(
        name="Leaderboard (0 participants)", value="No participants yet", inline=False
    )
    embed.set_footer(text="Game ends in 20 seconds")
    view = BankHeistView(multiplier, embed)
    message = await channel.send(embed=embed, view=view)
    asyncio.create_task(end_heist(view, message, client))


async def setup(bot) -> None:
    pass
