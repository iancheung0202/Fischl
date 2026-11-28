import random
import time

import discord

from commands.Events.config import MORA_EMOTE
from commands.Events.games.common import count, earn, prize, user_and_title

MELON = "Snatch the watermelon - :watermelon:"
ICE_CREAM = "A wild 🍦 has appeared."
SICK = ["having tooth decay", "having a brain freeze", "catching a cold", "melt"]


class PickUpView(discord.ui.View):
    """One button the first member to press it wins; `expired` is shown when nobody does."""

    def __init__(self, emoji: str, reward: int, expired: discord.Embed, picked):
        super().__init__(timeout=300)
        self.reward = reward
        self.expired = expired
        self.picked = picked
        self.start_time = time.time()
        self.message = None
        self.pick.emoji = emoji

    @discord.ui.button(style=discord.ButtonStyle.grey)
    async def pick(self, interaction: discord.Interaction, button):
        if self.is_finished():
            return await interaction.response.defer()
        self.stop()
        button.disabled = True
        embed, earned, won = await self.picked(self, interaction)
        await interaction.response.edit_message(content="", embed=embed, view=self)
        await count(
            interaction.client,
            interaction.channel,
            interaction.user.id,
            earned,
            self.start_time,
            won,
        )

    async def on_timeout(self):
        self.pick.disabled = True
        try:
            await self.message.edit(embed=self.expired, view=self)
        except discord.NotFound:
            pass


async def melon_picked(view, interaction) -> tuple:
    """Pays whoever took the watermelon; gives the embed saying so, the Mora counted and True for a win."""
    client, channel, uid = interaction.client, interaction.channel, interaction.user.id
    text, earned = await earn(client, channel, uid, view.reward)
    name = await user_and_title(uid, interaction.guild.id, client.pool)
    embed = discord.Embed(
        title=MELON,
        description=f"{name} picked up the `🍉` watermelon and earned {MORA_EMOTE} `{text}`.",
        color=discord.Color.gold(),
    )
    return (embed, earned, True)


async def ice_cream_picked(view, interaction) -> tuple:
    """Pays or charges whoever ate the ice cream, on a coin toss; gives the same three as the watermelon."""
    client, channel, user = interaction.client, interaction.channel, interaction.user
    amount = random.randint(min(3000, view.reward), view.reward)
    if random.choice(["pos", "neg"]) == "pos":
        text, earned = await earn(client, channel, user.id, amount)
        name = await user_and_title(user.id, interaction.guild.id, client.pool)
        embed = discord.Embed(
            title=ICE_CREAM,
            description=f"{name} enjoyed the `🍦` while earning {MORA_EMOTE} `{text}`.",
            color=discord.Color.green(),
        )
        return (embed, earned, True)
    reason = random.choice(SICK)
    text, earned = await earn(client, channel, user.id, -amount)
    name = await user_and_title(user.id, interaction.guild.id, client.pool)
    lost = f"lost {MORA_EMOTE} `{text}`"
    if reason == "melt":
        description = f"Unfortunately, {user.mention} did not eat the `🍦` in time. The ice cream melted and {name} {lost}."
    else:
        description = f"Unfortunately, {name} ate the `🍦` and {lost} for {reason}."
    embed = discord.Embed(
        title=ICE_CREAM, description=description, color=discord.Color.red()
    )
    return (embed, earned, False)


async def pickUpTheWatermelon(channel, client):
    reward = await prize(client, channel, 3000, 5000)
    expired = discord.Embed(
        title=MELON,
        description="⏳ This watermelon expired as no one picked it up in time!",
        color=discord.Color.light_grey(),
    )
    view = PickUpView("🍉", reward, expired, melon_picked)
    view.message = await channel.send(
        embed=discord.Embed(
            title=MELON,
            description=f"First to react to the `🍉` emoji earns {MORA_EMOTE} `{reward}`.",
            color=discord.Color.fuchsia(),
        ),
        view=view,
    )


async def pickUpIceCream(channel, client):
    most = await prize(client, channel, 5000, 8000)
    expired = discord.Embed(
        title=ICE_CREAM,
        description="⏳ The ice cream melted before anyone could eat it!",
        color=discord.Color.light_grey(),
    )
    view = PickUpView("🍦", most, expired, ice_cream_picked)
    view.message = await channel.send(
        embed=discord.Embed(
            title=ICE_CREAM,
            description=f"First to eat can earn **up to** {MORA_EMOTE} `{most}`, **BUT** you can also lose up to that amount. \nIt's simply a 50/50 chance.",
            color=discord.Color.fuchsia(),
        ),
        view=view,
    )


async def setup(bot) -> None:
    pass
