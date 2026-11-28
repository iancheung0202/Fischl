import random

import discord

from commands.Events.config import MORA_EMOTE, NO_EMOTE, TTOL_EMOJIS, YES_EMOTE
from commands.Events.games.common import count, prize, user_and_title
from commands.Events.games.guess import GuessView, refusal

TITLE = "Two Truths, One Lie"


class TwoTruthAndALieModal(discord.ui.Modal, title="Enter your two truths and one lie"):
    truth1 = discord.ui.TextInput(
        label="Truth #1",
        style=discord.TextStyle.short,
        placeholder="Enter a TRUE statement about yourself.",
        max_length=256,
    )
    truth2 = discord.ui.TextInput(
        label="Truth #2",
        style=discord.TextStyle.short,
        placeholder="Enter another TRUE statement about yourself.",
        max_length=256,
    )
    lie = discord.ui.TextInput(
        label="Lie",
        style=discord.TextStyle.short,
        placeholder="Enter a FALSE statement about yourself.",
        max_length=256,
    )

    def __init__(self, seat):
        super().__init__()
        self.seat = seat

    async def on_submit(self, interaction: discord.Interaction):
        seat = self.seat
        if seat.submitted:
            return await interaction.response.send_message(
                f"{NO_EMOTE} This game session has expired!", ephemeral=True
            )
        seat.submitted = True
        seat.stop()
        statements = [str(self.truth1), str(self.truth2), str(self.lie)]
        random.shuffle(statements)
        lie = statements.index(str(self.lie))
        name = await user_and_title(seat.uid, seat.channel.guild.id, seat.client.pool)
        embed = discord.Embed(
            title=TITLE,
            description=(
                f"First to determine which of the following statement by "
                f"{name} "
                f"is a lie wins {MORA_EMOTE} `{seat.reward}`!\n\n"
                + "\n".join(
                    f'{emoji} "{statement}"'
                    for emoji, statement in zip(TTOL_EMOJIS, statements)
                )
            ),
        )

        def won(button, winner: str, text: str) -> discord.Embed:
            embed.color = discord.Color.green()
            embed.description += f"\n\n🏆 {winner} chose {button.emoji} correctly and earned {MORA_EMOTE} `{text}`!"
            return embed.set_footer(
                text="Now y'all know a little bit more about each other."
            )

        await seat.message.edit(
            embed=discord.Embed(title=TITLE, description=seat.intro), view=None
        )
        await interaction.response.send_message(f"{YES_EMOTE} Success", ephemeral=True)
        await count(seat.client, seat.channel, seat.uid, won=False)
        view = GuessView(
            seat.client,
            seat.channel,
            seat.reward,
            won,
            [
                (place == lie, {"emoji": emoji})
                for place, emoji in enumerate(TTOL_EMOJIS[:3])
            ],
            already=f"{NO_EMOTE} You have guessed once already. No second try!",
            barred=seat.uid,
            barred_text="You can't answer your own question smh",
            timed_out=None,
        )
        view.message = await seat.channel.send(embed=embed, view=view)


class HotSeatView(discord.ui.View):
    """The button with which the chosen member opens the form for their three statements."""

    def __init__(self, client, channel, uid: int, reward: int, intro: str):
        super().__init__()
        self.client = client
        self.channel = channel
        self.uid = uid
        self.reward = reward
        self.intro = intro
        self.message = None
        self.opened = False
        self.submitted = False

    @discord.ui.button(
        label="Enter your two truths and one lie",
        emoji="🤫",
        style=discord.ButtonStyle.grey,
    )
    async def enter(self, interaction: discord.Interaction, button):
        if interaction.user.id != self.uid:
            return await interaction.response.send_message(
                "You can't click this button!", ephemeral=True
            )
        if not self.opened:
            self.opened = True
            name = await user_and_title(
                self.uid, self.channel.guild.id, self.client.pool
            )
            await self.message.edit(
                embed=discord.Embed(
                    title=TITLE,
                    description=f"{self.intro}\n\n> *{name} is entering their truths and lies...*",
                )
            )
        await interaction.response.send_modal(TwoTruthAndALieModal(self))


async def twoTruthsAndALie(channel, client):
    reward = await prize(client, channel, 4000, 6000)
    user = None
    async for message in channel.history(limit=10):
        if not message.author.bot:
            user = message.author
            break
    if user is None:
        return await channel.send(
            embed=refusal("Not enough unique users for the game.")
        )
    name = await user_and_title(user.id, channel.guild.id, client.pool)
    intro = f"{name} will be entering their **three statements**. First to determine which statement is a lie wins {MORA_EMOTE} `{reward}`!"
    view = HotSeatView(client, channel, user.id, reward, intro)
    view.message = await channel.send(
        content=f"{user.mention}, you have been put in the hot seat!",
        embed=discord.Embed(
            title=TITLE, description=intro, color=discord.Color.blurple()
        ),
        view=view,
    )


async def setup(bot) -> None:
    pass
