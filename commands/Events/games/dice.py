import random
import time

import discord

from commands.Events.config import MORA_EMOTE, NO_EMOTE, YES_EMOTE
from commands.Events.games.common import count, earn, prize, took_part


class RollDiceView(discord.ui.View):
    def __init__(self, target, reward, client):
        super().__init__(timeout=45)
        self.target = target
        self.reward = reward
        self.client = client
        self.start_time = time.time()
        self.user_rolls = {}
        self.message = None

    @discord.ui.button(style=discord.ButtonStyle.blurple, label="Roll Dice", emoji="🎲")
    async def roll(self, interaction: discord.Interaction, button):
        rolls = self.user_rolls.setdefault(interaction.user.id, [])
        if len(rolls) >= 2:
            return await interaction.response.send_message(
                f"{NO_EMOTE} You've already rolled twice!", ephemeral=True
            )
        rolled = random.randint(1, 6)
        rolls.append(rolled)
        if len(rolls) == 1:
            text = (
                f"You rolled: **{rolled}**\n"
                f"Your current total: **{sum(rolls)}**\n"
                "Click again to roll your second dice!"
            )
        else:
            text = (
                f"You rolled: **{rolled}**\n"
                f"Your total: **{sum(rolls)}**\n"
                f"{YES_EMOTE} You've completed your two rolls! Wait patiently for the results!"
            )
        await interaction.response.send_message(
            embed=discord.Embed(description=text, color=discord.Color.green()),
            ephemeral=True,
        )

    async def on_timeout(self):
        """Pays whoever came closest to the target, double for hitting it, and posts the results."""
        if not self.user_rolls:
            return await self.message.edit(
                embed=discord.Embed(
                    title="Roll a Dice - Time's Up!",
                    description="No one rolled the dice in time!",
                    color=discord.Color.red(),
                ),
                view=None,
            )
        channel = self.message.channel
        await self.message.edit(view=None)
        totals = {uid: sum(rolls) for uid, rolls in self.user_rolls.items()}
        closest = min(abs(total - self.target) for total in totals.values())
        winners = [
            uid for uid, total in totals.items() if abs(total - self.target) == closest
        ]
        lines = []
        for uid in winners:
            exact = totals[uid] == self.target
            text, earned = await earn(
                self.client, channel, uid, self.reward * (2 if exact else 1)
            )
            lines.append(
                f"-# <@{uid}>: {MORA_EMOTE} `{text}` "
                f"({'Exact match! ' if exact else ''}Rolled: {totals[uid]})"
            )
            await count(self.client, channel, uid, earned, self.start_time)
        finished = [uid for uid, rolls in self.user_rolls.items() if len(rolls) == 2]
        await took_part(self.client, channel, finished, but=winners)
        await self.message.reply(
            embed=discord.Embed(
                title="Roll a Dice 🎲 - Results",
                description=(
                    f"Target number: **{self.target}**\n"
                    f"Base reward: {MORA_EMOTE} `{self.reward}`\n\n"
                    f"**Winners:**\n" + "\n".join(lines)
                ),
                color=discord.Color.green(),
            ),
            view=None,
        )


async def rollADice(channel, client):
    target = random.randint(2, 12)
    reward = await prize(client, channel, 4000, 6000)
    embed = discord.Embed(
        title="Roll a Dice 🎲",
        description=(
            f"Roll **a dice twice** and get as close as possible to **{target}**!\n"
            f"> Base reward: {MORA_EMOTE} `{reward}` | Exact match doubles your reward!\n"
        ),
        color=discord.Color.blurple(),
    )
    embed.set_footer(text="Game ends after no one rolls for 45 seconds")
    view = RollDiceView(target, reward, client)
    view.message = await channel.send(embed=embed, view=view)


async def setup(bot) -> None:
    pass
