import random
import time

import discord

from commands.Events.config import MORA_EMOTE, NO_EMOTE, WORDS, YES_EMOTE
from commands.Events.games.common import count, earn, took_part, user_and_title
from commands.Events.helperFunctions import get_channel_mora_multiplier

LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXY"


def choose_word() -> str:
    """Gives a random word that can be spelled with the 25 letter buttons."""
    words = [word for word in WORDS if "z" not in word.lower()]
    return random.choice(words).lower() if words else "error"


def update_word(word: str, guessed_letters) -> str:
    """Gives the word with each letter not yet guessed as an underscore."""
    return "".join(letter if letter in guessed_letters else "_" for letter in word)


def format_guess_dict(guesses: dict) -> str:
    """Lists each member with the letters they guessed."""
    return (
        "\n".join(
            f"- <@{uid}>: {', '.join(sorted(letters))}"
            for uid, letters in guesses.items()
        )
        or "`None`"
    )


class HangmanButton(discord.ui.Button):
    def __init__(self, letter: str, row: int):
        super().__init__(label=letter, style=discord.ButtonStyle.secondary, row=row)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        letter = self.label.lower()
        uid = interaction.user.id
        if view.winner_id or view.tries <= 0:
            return await interaction.response.defer()
        view.participants.add(uid)
        self.disabled = True
        if letter in view.word:
            self.style = discord.ButtonStyle.success
            view.guessed_letters.add(letter)
            view.correct_letters.setdefault(uid, set()).add(letter)
        else:
            self.style = discord.ButtonStyle.danger
            view.tries -= 1
            view.incorrect_letters.setdefault(uid, set()).add(letter)

        solved = "_" not in update_word(view.word, view.guessed_letters)
        if not solved and view.tries > 0:
            view.board(view.embed.clear_fields())
            return await interaction.response.edit_message(embed=view.embed, view=view)
        if solved:
            view.winner_id = uid
            view.winner_text, view.earned = await earn(
                interaction.client, interaction.channel, uid, view.bonus_reward
            )
        for child in view.children:
            child.disabled = True
        view.stop()
        await interaction.response.defer()


class HangmanView(discord.ui.View):
    def __init__(
        self, word: str, embed, tries: int, word_reward: int, bonus_reward: int
    ):
        super().__init__(timeout=300)
        self.word = word
        self.embed = embed
        self.tries = tries
        self.guessed_letters = set()
        self.correct_letters = {}
        self.incorrect_letters = {}
        self.participants = set()
        self.winner_id = None
        self.earned = 0
        self.winner_text = ""
        self.word_reward = word_reward
        self.bonus_reward = bonus_reward
        for place, letter in enumerate(LETTERS):
            self.add_item(HangmanButton(letter, row=place // 5))

    def board(self, embed: discord.Embed) -> discord.Embed:
        """Adds the word so far, each member's letters and the tries left to an embed."""
        embed.add_field(
            name="Word:",
            value=f"`{update_word(self.word, self.guessed_letters)}`",
            inline=False,
        )
        embed.add_field(
            name=YES_EMOTE + " Correct letters:",
            value=format_guess_dict(self.correct_letters),
        )
        embed.add_field(
            name=NO_EMOTE + " Incorrect letters:",
            value=format_guess_dict(self.incorrect_letters),
        )
        return embed.add_field(name="Tries remaining:", value=f"`{self.tries}`")


async def ending(view, channel, client) -> discord.Embed:
    """Gives the embed for how the game ended: solved, out of tries or out of time."""
    if view.winner_id:
        name = await user_and_title(view.winner_id, channel.guild.id, client.pool)
        return discord.Embed(
            title="Hangman Game",
            description=f"Success! Everyone got {MORA_EMOTE} **`{view.word_reward}`** per correct letter. {name} earned an extra {MORA_EMOTE} **`{view.winner_text}`**.",
            color=discord.Color.green(),
        )
    lost = view.tries <= 0
    for child in view.children:
        child.disabled = True
    return discord.Embed(
        title="Hangman Game" if lost else "Hangman - Time Out! ⌛",
        description=f"Game over! The word was `{view.word}`. Better luck next time!",
        color=discord.Color.red() if lost else discord.Color.light_grey(),
    )


async def hangmanGame(channel, client):
    multiplier = await get_channel_mora_multiplier(client.pool, channel.id)
    word_reward = int(1500 * multiplier)
    bonus_reward = int(3000 * multiplier)
    word = choose_word()
    start = time.time()
    embed = discord.Embed(
        title="Hangman Game",
        description=f"**Guess a letter!** Earn {MORA_EMOTE} **{word_reward}** per correct letter and an extra {MORA_EMOTE} **{bonus_reward}** for completing the word.",
        color=discord.Color.blurple(),
    )
    view = HangmanView(
        word, embed, round(5 + 0.4 * len(word)), word_reward, bonus_reward
    )
    view.board(embed).set_footer(text="Click a letter to guess • 5-minute time limit")
    message = await channel.send(embed=embed, view=view)
    await view.wait()

    final = view.board(await ending(view, channel, client))
    for uid, letters in view.correct_letters.items():
        found = sum(word.count(letter) for letter in letters)
        await earn(client, channel, uid, found * word_reward)
    await message.edit(embed=final, view=view)
    if view.winner_id:
        await count(client, channel, view.winner_id, view.earned, start)
    await took_part(client, channel, view.participants, but={view.winner_id})


async def setup(bot) -> None:
    pass
