import csv
import io
import random
import time

import aiohttp
import discord

from commands.Events.config import (
    GENSHIN_EMOJI_RIDDLE_CSV_URL,
    HSR_EMOJI_RIDDLE_CSV_URL,
    MORA_EMOTE,
)
from commands.Events.games.common import (
    count,
    earn,
    prize,
    report_crash,
    took_part,
    user_and_title,
)

RIDDLES = {
    "hsr": {
        "url": HSR_EMOJI_RIDDLE_CSV_URL,
        "title": "Galaxy *Emojified* Riddles | HSR Character",
        "game": "Honkai: Star Rail",
        "credits": "Credits: schaeffly, treble4tea_03755, rubi134",
        "won_credits": "Credits: schaeffly, treble4tea_03755, rubi134, maraudersacrusader, fishyfishery",
        "timeout": "HSR Emoji Riddle - Time Out! ⌛",
    },
    "genshin": {
        "url": GENSHIN_EMOJI_RIDDLE_CSV_URL,
        "title": "Teyvat *Emojified* Riddles | Genshin Character",
        "game": "Genshin Impact",
        "credits": "Credits: schaeffly, treble4tea_03755",
        "won_credits": "Credits: schaeffly, treble4tea_03755",
        "timeout": "Genshin Emoji Riddle - Time Out! ⌛",
    },
}


class QuizButton(discord.ui.Button):
    def __init__(self, label):
        super().__init__(style=discord.ButtonStyle.primary, label=label)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        uid = interaction.user.id
        if view.winner_id:
            return await interaction.response.defer()
        if uid in view.participants:
            return await interaction.response.send_message(
                "You have already answered!", ephemeral=True
            )
        view.participants.add(uid)
        if self.label != view.answer:
            return await interaction.response.send_message(
                "That is incorrect!", ephemeral=True
            )
        view.winner_id = uid
        await interaction.response.defer()
        for child in view.children:
            child.disabled = True
            child.style = (
                discord.ButtonStyle.success
                if child.label == view.answer
                else discord.ButtonStyle.secondary
            )
        view.stop()
        text, earned = await earn(view.client, view.channel, uid, view.reward)
        name = await user_and_title(uid, view.channel.guild.id, view.client.pool)
        await view.game_msg.edit(embed=view.won(name, text), view=view)
        await count(view.client, view.channel, uid, earned, view.start_time)


class QuizView(discord.ui.View):
    """One button per option; the first member to press the answer wins, and each member answers once."""

    def __init__(self, answer, options, reward, client, channel, won, lost):
        super().__init__(timeout=300)
        self.answer = answer
        self.reward = reward
        self.client = client
        self.channel = channel
        self.won = won
        self.lost = lost
        self.game_msg = None
        self.winner_id = None
        self.participants = set()
        self.start_time = time.time()
        random.shuffle(options)
        for option in options:
            self.add_item(QuizButton(option))

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.game_msg:
            await self.game_msg.edit(embed=self.lost, view=self)


async def characters(url: str):
    """Gives each character's emojis from the sheet, or the HTTP status when it cannot be read."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=10) as response:
            if response.status != 200:
                return response.status
            sheet = await response.text()
    return {
        row["Character Name"]: row["Emojis"]
        for row in csv.DictReader(io.StringIO(sheet))
    }


async def riddle(channel, client, kind: str) -> None:
    """Shows the emojis of one character with five names to pick from; the first right pick wins."""
    words = RIDDLES[kind]
    reward = await prize(client, channel, 3000, 5000)
    emojis = await characters(words["url"])
    if isinstance(emojis, int):
        return await report_crash(
            client, channel, f"Failed to fetch minigame data (HTTP {emojis})"
        )
    names = list(emojis)
    character = random.choice(names)
    shown = emojis[character]
    options = [character] + random.sample(
        [name for name in names if name != character], 4
    )

    def won(name: str, text: str) -> discord.Embed:
        embed = discord.Embed(
            title=words["title"],
            description=(
                f"```{shown}```\n"
                f"{name} answered `{character}` and won {MORA_EMOTE} `{text}`."
            ),
            color=discord.Color.brand_green(),
        )
        return embed.set_footer(text=words["won_credits"])

    lost = discord.Embed(
        title=words["timeout"],
        description=(
            f"**Emojis:** ```{shown}```\n"
            f"**Correct Answer:** `{character}`\n"
            "No one guessed in time!"
        ),
        color=discord.Color.light_grey(),
    )
    embed = discord.Embed(
        title=words["title"],
        description=(
            f"The following emojis describe a **{words['game']}** character. "
            f"First to guess wins {MORA_EMOTE} `{reward}`.\n\n```{shown}```"
        ),
        color=0xFFEB20,
    )
    embed.set_footer(text=f"{words['credits']} • 5-minute time limit")
    view = QuizView(character, options, reward, client, channel, won, lost)
    view.game_msg = await channel.send(embed=embed, view=view)
    await view.wait()
    await took_part(client, channel, view.participants, but={view.winner_id})


async def hsrEmojiRiddle(channel, client):
    await riddle(channel, client, "hsr")


async def genshinEmojiRiddle(channel, client):
    await riddle(channel, client, "genshin")


async def setup(bot) -> None:
    pass
