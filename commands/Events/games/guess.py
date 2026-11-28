import asyncio
import random
import time

import discord

from commands.Events.config import MEMORY_GAME_EMOJIS, MORA_EMOTE, NO_EMOTE
from commands.Events.games.common import count, earn, prize, user_and_title

TIMED_OUT = "⏳ This game session has timed out"


class GuessButton(discord.ui.Button):
    def __init__(self, right: bool, **look):
        super().__init__(style=discord.ButtonStyle.grey, **look)
        self.right = right

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        uid = interaction.user.id
        if view.winner or uid in view.guessed:
            return await interaction.response.send_message(view.already, ephemeral=True)
        if uid == view.barred:
            return await interaction.response.send_message(
                view.barred_text, ephemeral=True
            )
        view.guessed.add(uid)
        if not self.right:
            await interaction.response.send_message(view.wrong, ephemeral=True)
            return await count(view.client, view.channel, uid, won=False)
        view.winner = uid
        view.stop()
        text, earned = await earn(view.client, view.channel, uid, view.reward)
        name = await user_and_title(uid, view.channel.guild.id, view.client.pool)
        for child in view.children:
            child.disabled = True
            child.style = (
                discord.ButtonStyle.success
                if child is self
                else discord.ButtonStyle.secondary
            )
        await interaction.response.edit_message(
            embed=view.won(self, name, text), view=view
        )
        await count(view.client, view.channel, uid, earned, view.since)


class GuessView(discord.ui.View):
    """Buttons of which one is right: each member guesses once and the first right guess is paid.

    The rules may name a member barred from guessing and replace the texts shown to members.
    """

    def __init__(self, client, channel, reward, won, options, **rules):
        super().__init__(timeout=300)
        self.client = client
        self.channel = channel
        self.reward = reward
        self.won = won
        self.wrong = rules.get("wrong", f"Wrong! {NO_EMOTE}")
        self.already = rules.get("already", f"{NO_EMOTE} You already guessed!")
        self.timed_out = rules.get("timed_out", TIMED_OUT)
        self.barred = rules.get("barred")
        self.barred_text = rules.get("barred_text")
        self.keep_buttons = rules.get("keep_buttons", False)
        self.since = time.time() if rules.get("fast_win", True) else None
        self.guessed = set()
        self.winner = None
        self.message = None
        for right, look in options:
            self.add_item(GuessButton(right, **look))

    async def on_timeout(self):
        try:
            await self.close()
        except discord.HTTPException:
            pass

    async def close(self) -> None:
        """Shows that the game ran out of time, in the way this game does."""
        if self.keep_buttons:
            for child in self.children:
                child.disabled = True
            return await self.message.edit(view=self)
        if not self.timed_out:
            return await self.message.edit(view=None)
        await self.message.edit(
            embed=discord.Embed(
                description=self.timed_out, color=discord.Color.dark_grey()
            ),
            view=None,
        )


def refusal(text: str) -> discord.Embed:
    return discord.Embed(description=f"{NO_EMOTE} {text}")


async def recent_authors(channel, client, messages: int, wanted: int) -> list:
    """Gives up to the wanted number of members, newest first and each once, who wrote the last messages of a channel."""
    authors = {}
    async for message in channel.history(limit=messages):
        author = message.author
        if not author.bot and author.id != client.user.id:
            authors.setdefault(author.id, author)
            if len(authors) == wanted:
                break
    return list(authors.values())


async def matchThePFP(channel, client):
    reward = await prize(client, channel, 3000, 5000)
    users = await recent_authors(channel, client, 200, 3)
    if len(users) < 3:
        return await channel.send(
            embed=refusal("Not enough unique users for the game.")
        )
    target = random.choice(users)
    avatar = (target.avatar or target.default_avatar).url

    def won(button, name: str, text: str) -> discord.Embed:
        embed = discord.Embed(
            title="Who's this?",
            description=f"{name} guessed **{button.label}** correctly and earned {MORA_EMOTE} `{text}`.",
            color=discord.Color.green(),
        )
        return embed.set_image(url=avatar)

    view = GuessView(
        client,
        channel,
        reward,
        won,
        [(user.id == target.id, {"label": user.display_name}) for user in users],
    )
    embed = discord.Embed(
        title="Who's this?",
        description=f"First to guess wins {MORA_EMOTE} `{reward}`. **You can only guess once!**",
        color=discord.Color.light_grey(),
    )
    embed.set_image(url=avatar)
    view.message = await channel.send(embed=embed, view=view)


async def recent_writers(channel, client) -> set:
    """Gives the IDs of the members who wrote text in the last ten messages."""
    return {
        message.author.id
        async for message in channel.history(limit=10)
        if message.author != client.user and not message.author.bot and message.content
    }


async def still_here(guild, ids) -> list:
    """Gives the members of a server among the IDs."""
    members = []
    for uid in ids:
        try:
            members.append(await guild.fetch_member(uid))
        except discord.NotFound:
            continue
    return members


def join_question(guild, members: list) -> tuple:
    """Picks a question about when two members joined; gives the question and the member who answers it."""
    mode = random.choice(["earlier", "later", "specific"])
    if mode == "earlier":
        return (
            f"Which user has been in **{guild.name}** longer?",
            min(members, key=lambda member: member.joined_at),
        )
    if mode == "later":
        return (
            f"Which user is newer in **{guild.name}**?",
            max(members, key=lambda member: member.joined_at),
        )
    right = random.choice(members)
    return (f"Which user joined on <t:{int(right.joined_at.timestamp())}:D>?", right)


async def knowYourMembers(channel, client):
    reward = await prize(client, channel, 3000, 5000)
    writers = await recent_writers(channel, client)
    if len(writers) < 2:
        return await channel.send(
            embed=refusal("Not enough unique recent messaging users for the game.")
        )
    members = await still_here(channel.guild, writers)
    if len(members) < 2:
        return await channel.send(
            embed=refusal("Not enough valid members for the game.")
        )
    selected = random.sample(members, 2)
    question, right = join_question(channel.guild, selected)
    joined = "\n".join(
        f"- **{member.display_name}**: <t:{int(member.joined_at.timestamp())}:D>"
        for member in selected
    )

    def won(button, name: str, text: str) -> discord.Embed:
        return discord.Embed(
            title="Know Your Members",
            description=f"**{question}**\n\n{name} answered correctly and earned {MORA_EMOTE} `{text}`!\n\n**Server Join Dates:**\n{joined}",
            color=discord.Color.green(),
        )

    view = GuessView(
        client,
        channel,
        reward,
        won,
        [
            (member.id == right.id, {"label": member.display_name})
            for member in selected
        ],
        wrong=f"Incorrect! {NO_EMOTE}",
    )
    view.message = await channel.send(
        embed=discord.Embed(
            title="Know Your Members",
            description=f"{question}\nFirst correct guess earns {MORA_EMOTE} `{reward}`",
            color=0x9DBFC4,
        ),
        view=view,
    )


async def memoryGame(channel, client):
    reward = await prize(client, channel, 5000, 7000)
    emojis = random.sample(MEMORY_GAME_EMOJIS, 3)
    column = random.randint(1, 3)
    asked = emojis[column - 1]
    embed = discord.Embed(
        title="Memory Game",
        description=f"Remember the following order of emotes. You will be asked to recall which column an emoji is from. **You can only guess once!**\n\nFirst to guess correctly wins {MORA_EMOTE} `{reward}`.",
        color=discord.Color.light_grey(),
    )
    for place, emoji in enumerate(emojis, start=1):
        embed.add_field(name=f"Column {place}", value=f"`{emoji}`", inline=True)
    shown = await channel.send(embed=embed)
    await asyncio.sleep(5)
    await shown.delete()

    def won(button, name: str, text: str) -> discord.Embed:
        return discord.Embed(
            title="Memory Game",
            description=f"**Which emote was in Column {column}?**\n\n{name} guessed correctly and earned {MORA_EMOTE} `{text}`.",
            color=discord.Color.green(),
        )

    random.shuffle(emojis)
    view = GuessView(
        client,
        channel,
        reward,
        won,
        [(emoji == asked, {"emoji": str(emoji)}) for emoji in emojis],
        already=f"{NO_EMOTE} You have guessed once already. No second try!",
    )
    view.message = await channel.send(
        embed=discord.Embed(
            title="Memory Game",
            description=f"Now, which of the following emote was in **Column {column}**? **You can only guess once!**\n\nFirst to guess correctly wins {MORA_EMOTE} `{reward}`.",
            color=discord.Color.light_grey(),
        ),
        view=view,
    )


async def setup(bot) -> None:
    pass
