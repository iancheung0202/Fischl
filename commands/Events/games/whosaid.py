import asyncio
import random

import discord

from commands.Events.config import MORA_EMOTE, NO_EMOTE, YES_EMOTE
from commands.Events.games.common import count, earn, prize, user_and_title
from commands.Events.games.guess import GuessView

MAX_SUBMISSIONS = 5
SUBMISSION_WINDOW = 60
EXPIRED = f"{NO_EMOTE} This game session has expired!"
SUBMITTED = f"{NO_EMOTE} You've already submitted a phrase!"
TIMED_OUT = "⌛ This game session has timed out"


def submission_embed(reward: int, submissions: int) -> discord.Embed:
    return discord.Embed(
        title="Who Said That?",
        description=(
            f"Click below to submit a phrase! Once **{MAX_SUBMISSIONS} submissions** "
            f"come in or after **1 minute** passes with 2+ entries, a random phrase gets revealed and the "
            f"first to guess who said it wins {MORA_EMOTE} `{reward}`!\n\n**Submissions:** `{submissions}`"
        ),
        color=0x27F5B4,
    )


class WhoSaidThatModal(discord.ui.Modal, title="Who Said That?"):
    phrase_input = discord.ui.TextInput(
        label="Enter a phrase about yourself",
        style=discord.TextStyle.short,
        placeholder="e.g. I've never broken a bone in my life",
        max_length=200,
    )

    def __init__(self, game):
        super().__init__()
        self.game = game

    async def on_submit(self, interaction: discord.Interaction):
        game = self.game
        uid = interaction.user.id
        if game.closed:
            return await interaction.response.send_message(EXPIRED, ephemeral=True)
        if uid in game.submissions:
            return await interaction.response.send_message(SUBMITTED, ephemeral=True)
        game.submissions[uid] = str(self.phrase_input)
        full = len(game.submissions) >= MAX_SUBMISSIONS
        if full:
            game.close()
        await interaction.response.send_message(
            f"{YES_EMOTE} Your phrase has been recorded!", ephemeral=True
        )
        await count(game.client, game.channel, uid, won=False)
        try:
            await game.message.edit(
                embed=submission_embed(game.reward, len(game.submissions))
            )
        except discord.NotFound:
            return
        if full:
            await game.reveal()


class WhoSaidItView(discord.ui.View):
    """Collects one phrase per member for a minute, then asks who wrote one of them."""

    def __init__(self, client, channel, reward):
        super().__init__(timeout=None)
        self.client = client
        self.channel = channel
        self.reward = reward
        self.submissions = {}
        self.closed = False
        self.message = None

    def close(self) -> None:
        self.closed = True
        self.stop()

    @discord.ui.button(
        label="Submit a Phrase", emoji="✍️", style=discord.ButtonStyle.blurple
    )
    async def submit(self, interaction: discord.Interaction, button):
        if self.closed:
            return await interaction.response.send_message(EXPIRED, ephemeral=True)
        if interaction.user.id in self.submissions:
            return await interaction.response.send_message(SUBMITTED, ephemeral=True)
        await interaction.response.send_modal(WhoSaidThatModal(self))

    async def name(self, uid: int) -> str:
        """Gives a member's display name, or "Unknown User" for one who has left."""
        guild = self.channel.guild
        try:
            member = guild.get_member(uid) or await guild.fetch_member(uid)
        except discord.NotFound:
            return "Unknown User"
        return member.display_name

    async def reveal(self) -> None:
        """Shows one of the phrases with a button for each member who sent one."""
        author, phrase = random.choice(list(self.submissions.items()))
        authors = list(self.submissions)
        random.shuffle(authors)
        embed = discord.Embed(
            title="Who Said That?",
            description=f"Someone submitted this phrase:\n\n> {phrase}\n\nFirst to guess who said it wins {MORA_EMOTE} `{self.reward}`!",
            color=discord.Color.light_grey(),
        )

        def won(button, name: str, text: str) -> discord.Embed:
            embed.color = discord.Color.green()
            embed.description += f"\n\n🏆 {name} guessed **{button.label}** correctly and earned {MORA_EMOTE} `{text}`!"
            return embed

        view = GuessView(
            self.client,
            self.channel,
            self.reward,
            won,
            [(uid == author, {"label": await self.name(uid)}) for uid in authors],
            barred=author,
            barred_text=f"{NO_EMOTE} Unfortunately, your phrase is chosen, so you are not allowed to guess! Don't spoil the fun!",
            timed_out=TIMED_OUT,
            fast_win=False,
        )
        view.message = self.message
        await self.message.edit(embed=embed, view=view)

    async def window(self) -> None:
        """Waits out the minute for phrases, then ends it."""
        await asyncio.sleep(SUBMISSION_WINDOW)
        await self.time_up()

    async def time_up(self) -> None:
        """Ends the minute for phrases: a guess round for two or more, a default win for one."""
        if self.closed:
            return
        self.close()
        if len(self.submissions) >= 2:
            return await self.reveal()
        if not self.submissions:
            return await self.message.edit(
                embed=discord.Embed(
                    description=TIMED_OUT, color=discord.Color.dark_grey()
                ),
                view=None,
            )
        (uid,) = self.submissions
        text, earned = await earn(self.client, self.channel, uid, self.reward)
        name = await user_and_title(uid, self.channel.guild.id, self.client.pool)
        await self.message.edit(
            embed=discord.Embed(
                title="Who Said That?",
                description=(
                    f"Not enough players joined in time! Since {name} was the only one who submitted "
                    f"a phrase, they win {MORA_EMOTE} `{text}` by default."
                ),
                color=discord.Color.green(),
            ),
            view=None,
        )
        await count(self.client, self.channel, uid, earned)


async def whoSaidIt(channel, client):
    reward = await prize(client, channel, 3000, 5000)
    view = WhoSaidItView(client, channel, reward)
    view.message = await channel.send(embed=submission_embed(reward, 0), view=view)
    asyncio.create_task(view.window())


async def setup(bot) -> None:
    pass
