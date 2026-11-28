import asyncio
import random
import time

import discord

from commands.Events.config import CURRENCY_EMOTES, MORA_EMOTE, NO_EMOTE, YES_EMOTE
from commands.Events.games.common import (
    count,
    delete_soon,
    earn,
    prize,
    took_part,
    user_and_title,
)

SECONDS = 300


def notice(title: str, description: str, color) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=color)


async def eggWalk(channel, client):
    reward = await prize(client, channel, 2000, 3000)
    start = time.time()
    message = await channel.send(
        embed=notice(
            "Eggwalk",
            f"**Users must alternate!** Start at 1 and count to 10. \nEach number you type will earn you {MORA_EMOTE} `{reward}` if successful.",
            discord.Color.dark_purple(),
        )
    )
    number = 1
    previous = None
    typed = {}
    earned = {}

    async def failed(answer, description: str) -> bool:
        """Marks a wrong message and says why the game ended; False when it could not be marked."""
        try:
            await answer.add_reaction(NO_EMOTE)
        except Exception:
            return False
        await answer.reply(embed=notice("Eggwalk", description, discord.Color.red()))
        return True

    while number <= 10:
        try:
            answer = await client.wait_for(
                "message",
                check=lambda sent: sent.channel == channel,
                timeout=max(start + SECONDS - time.time(), 0),
            )
        except asyncio.TimeoutError:
            return await message.edit(
                embed=notice(
                    "Eggwalk - Time Out!",
                    "⏳ The game is not finished in time!",
                    discord.Color.light_grey(),
                )
            )
        try:
            if not answer.content.isnumeric():
                continue
            if answer.content.strip() != str(number):
                if await failed(
                    answer,
                    f"Wrong number. Next number should be `{number}`! Better luck next time!",
                ):
                    break
                continue
            if answer.author == previous:
                if await failed(
                    answer,
                    f"{answer.author.mention} did not alternate! Good luck next time!",
                ):
                    break
                continue
            try:
                await answer.add_reaction(YES_EMOTE)
            except Exception:
                continue
            number += 1
            previous = answer.author
            typed[previous.id] = typed.get(previous.id, 0) + 1
        except Exception as error:
            print(f"Eggwalk: {error}")
            return

    if number <= 10:
        return await took_part(client, channel, typed)
    lines = []
    for uid, numbers in typed.items():
        text, earned[uid] = await earn(client, channel, uid, numbers * reward)
        name = await user_and_title(uid, channel.guild.id, client.pool)
        lines.append(f"-# - {name}: {numbers} numbers → {MORA_EMOTE} `{text}`")
    await message.reply(
        embed=notice(
            "Eggwalk - Success!",
            "Good job everyone! That is not an easy task!\n\n" + "\n".join(lines),
            discord.Color.green(),
        )
    )
    for uid in typed:
        await count(client, channel, uid, earned[uid], start)


class GuessNumberButton(discord.ui.Button):
    def __init__(self, number: int):
        super().__init__(
            label=str(number),
            style=discord.ButtonStyle.secondary,
            row=(number - 1) // 5,
        )
        self.number = number

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if view.winner_id:
            return await interaction.response.defer()
        view.participants.add(interaction.user.id)
        if self.number != view.target_number:
            self.style = discord.ButtonStyle.danger
            self.disabled = True
            return await interaction.response.edit_message(view=view)
        self.style = discord.ButtonStyle.success
        view.winner_id = interaction.user.id
        view.winner_text, view.earned = await earn(
            interaction.client, interaction.channel, view.winner_id, view.reward
        )
        for child in view.children:
            child.disabled = True
        view.stop()
        await interaction.response.defer()


class GuessNumberView(discord.ui.View):
    def __init__(self, target_number: int, reward: int):
        super().__init__(timeout=SECONDS)
        self.target_number = target_number
        self.reward = reward
        self.participants = set()
        self.winner_id = None
        self.earned = 0
        self.winner_text = ""
        for number in range(1, 11):
            self.add_item(GuessNumberButton(number))


async def guessTheNumber(channel, client):
    reward = await prize(client, channel, 3000, 5000)
    start = time.time()
    embed = notice(
        "Guess The Mystery Number",
        "First to guess what number in **between 1 and 10 (inclusive)** I am thinking of "
        f"will earn {MORA_EMOTE} `{reward}`.",
        discord.Color.dark_purple(),
    )
    view = GuessNumberView(random.randint(1, 10), reward)
    message = await channel.send(embed=embed, view=view)
    await view.wait()

    if view.winner_id:
        embed.color = discord.Color.green()
        name = await user_and_title(view.winner_id, channel.guild.id, client.pool)
        embed.description += (
            f"\n\n🏆 {name} got it and earned {MORA_EMOTE} `{view.winner_text}`."
        )
    else:
        embed = notice(
            "Guess The Mystery Number",
            "⏳ Was it really that hard to guess a number between 1 to 10?",
            discord.Color.light_grey(),
        )
        for child in view.children:
            child.disabled = True
    await message.edit(embed=embed, view=view)

    for uid in view.participants:
        if uid == view.winner_id:
            await count(client, channel, uid, view.earned, start)
        else:
            await count(client, channel, uid, won=False)


async def countingCurrency(channel, client):
    reward = await prize(client, channel, 3000, 5000)
    start = time.time()
    grid = [
        [
            random.choice(CURRENCY_EMOTES[:3]) if random.random() < 0.2 else None
            for _ in range(15)
        ]
        for _ in range(15)
    ]
    drawn = "".join("".join(cell or "ㅤ" for cell in row) + "\n" for row in grid)
    wanted = random.choice(CURRENCY_EMOTES[:3])
    number = sum(row.count(wanted) for row in grid)
    message = await channel.send(
        embed=notice(
            "Currency Counting",
            f"{drawn}\nFirst to count how many {wanted} there are wins {MORA_EMOTE} `{reward}`. Type the number in chat.",
            discord.Color.blue(),
        )
    )
    guessed = set()
    winner = None
    earned = 0

    while winner is None:
        try:
            answer = await client.wait_for(
                "message",
                check=lambda sent: sent.channel == channel and not sent.author.bot,
                timeout=max(start + SECONDS - time.time(), 0),
            )
        except asyncio.TimeoutError:
            await message.edit(
                embed=notice(
                    "Currency Counting - Time Out! ⌛",
                    f"{drawn}\n**Correct Count:** `{number}` {wanted}\n"
                    "No one answered in time!",
                    discord.Color.red(),
                )
            )
            break
        try:
            if not answer.content.isnumeric():
                continue
            guessed.add(answer.author.id)
            right = int(answer.content.strip()) == number
            try:
                await answer.add_reaction(YES_EMOTE if right else NO_EMOTE)
            except Exception:
                continue
            if not right:
                asyncio.create_task(delete_soon(answer))
                continue
            winner = answer.author.id
            text, earned = await earn(client, channel, winner, reward)
            name = await user_and_title(winner, channel.guild.id, client.pool)
            await answer.reply(
                embed=notice(
                    "Currency Counting",
                    f"{name} got it and earned {MORA_EMOTE} `{text}`.",
                    discord.Color.green(),
                )
            )
        except Exception as error:
            print(f"Currency Counting: {error}")
            return

    if winner:
        await count(client, channel, winner, earned, start)
    await took_part(client, channel, guessed, but={winner})


async def setup(bot) -> None:
    pass
