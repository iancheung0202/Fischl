import asyncio
import random
import time

import discord

from commands.Events.config import MORA_EMOTE, NO_EMOTE, YES_EMOTE
from commands.Events.games.common import count, earn, took_part
from commands.Events.helperFunctions import get_channel_mora_multiplier, get_guild_mora

SECONDS = 90


def note(title: str, description: str, color=discord.Color.red()) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=color)


class BidModal(discord.ui.Modal):
    def __init__(self, auction):
        super().__init__(title="Place Your Bid")
        self.auction = auction
        self.bid_amount = discord.ui.TextInput(
            label="Bid Amount (between 1000 and 15000)",
            placeholder="Enter your mora bid...",
            min_length=4,
            max_length=5,
        )
        self.add_item(self.bid_amount)

    async def refusal(self, interaction: discord.Interaction, bid):
        """Gives the embed saying why a bid is not taken, or None when it is."""
        if self.auction.closed:
            return note(f"Bid Failed {NO_EMOTE}", "This auction has closed!")
        if interaction.user.id in self.auction.bids:
            return note(
                f"Already Bid! {NO_EMOTE}", "You can only bid **once** per auction!"
            )
        if bid is None or not 1000 <= bid <= 15000:
            return note(
                f"Invalid Bid {NO_EMOTE}",
                "Please enter a number between **1000** and **15000**!",
            )
        owned = await get_guild_mora(
            interaction.client.pool, interaction.user.id, interaction.guild.id
        )
        if bid > owned:
            return note(
                f"Bid Failed {NO_EMOTE}",
                f"{MORA_EMOTE} **Insufficient Funds!**\n"
                f"You only have: {MORA_EMOTE} {owned}",
            )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            bid = int(self.bid_amount.value)
        except ValueError:
            bid = None
        refusal = await self.refusal(interaction, bid)
        if refusal:
            return await interaction.response.send_message(
                embed=refusal, ephemeral=True
            )
        self.auction.bids[interaction.user.id] = bid
        await interaction.response.send_message(
            embed=note(
                f"Bid Placed {YES_EMOTE}",
                f"You've bid {MORA_EMOTE} **{bid}**!\n*This will only be deducted if you win the box!*",
                discord.Color.green(),
            ),
            ephemeral=True,
        )
        await interaction.channel.send(
            embed=discord.Embed(
                description=f"📈 Total bids received: **{len(self.auction.bids)}**",
                color=0x2B2D31,
            ),
            delete_after=5,
        )


class AuctionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.bids = {}
        self.closed = False

    @discord.ui.button(label="Place Bid", style=discord.ButtonStyle.blurple, emoji="💰")
    async def bid_button(self, interaction: discord.Interaction, button):
        if interaction.user.id in self.bids:
            return await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"{NO_EMOTE} You've already bid!",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
        await interaction.response.send_modal(BidModal(self))


async def grandAuctionHouse(channel, client):
    multiplier = await get_channel_mora_multiplier(client.pool, channel.id)
    start = time.time()
    embed = discord.Embed(
        title="Grand Auction House 🏛️",
        description=(
            f"A mysterious box worth anywhere **between {MORA_EMOTE} `{int(5000 * multiplier)}` and `{int(15000 * multiplier)}`** spawned! "
            f"**Closest bid UNDER the value of the box wins!** Auction ends <t:{int(start) + SECONDS}:R>"
        ),
        color=0x3498DB,
    )
    view = AuctionView()
    message = await channel.send(embed=embed, view=view)
    await asyncio.sleep(SECONDS)

    view.closed = True
    view.stop()
    embed.description = embed.description.replace("ends", "ended")
    embed.description += "\n\n**Auction Closed!** 🔒"
    await message.edit(embed=embed, view=None)

    value = int(random.randint(5000, 15000) * multiplier)
    if not view.bids:
        return await message.reply(
            embed=discord.Embed(
                description=f"{NO_EMOTE} Auction ended with no bids.",
                color=discord.Color.red(),
            )
        )
    under = {uid: bid for uid, bid in view.bids.items() if bid <= value}
    if not under:
        await message.reply(
            embed=note(
                "Auction Failed! 🏚️",
                f"**Box Value:** {MORA_EMOTE} `{value}`\n\n"
                "Everyone overbid! No one takes the box home.",
            )
        )
        return await took_part(client, channel, view.bids)

    winner = max(under, key=under.get)
    text, earned = await earn(client, channel, winner, value - under[winner])
    await message.reply(
        embed=note(
            "Auction Results! 🎉",
            f"### 🏆 Winner: <@{winner}>\n"
            f"**Box Value:** {MORA_EMOTE} `{value}`\n"
            f"**Winning Bid:** {MORA_EMOTE} `{under[winner]}`\n"
            f"**Net Profit:** {MORA_EMOTE} `{text}`",
            discord.Color.green(),
        )
    )
    await count(client, channel, winner, earned if earned > 0 else None)
    await took_part(client, channel, view.bids, but={winner})


async def setup(bot) -> None:
    pass
