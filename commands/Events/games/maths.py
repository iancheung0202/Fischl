import random

import discord

from commands.Events.config import MORA_EMOTE
from commands.Events.games.common import prize
from commands.Events.games.guess import GuessView

SIGNS = "+-*/"


def worked_out(numbers: list, signs: list):
    """Gives the whole-number result of three numbers joined by two signs, or None when it has none."""
    try:
        result = eval(f"{numbers[0]} {signs[0]} {numbers[1]} {signs[1]} {numbers[2]}")
    except ZeroDivisionError:
        return None
    return int(result) if int(result) == result else None


def question() -> tuple:
    """Makes a sum with an answer from 0 to 1000; gives its numbers, signs and answer."""
    while True:
        numbers = [random.randint(1, 20) for _ in range(3)]
        signs = [random.choice(SIGNS) for _ in range(2)]
        answer = worked_out(numbers, signs)
        if answer is not None and 0 <= answer <= 1000:
            return (numbers, signs, answer)


def wrong_answers(numbers: list, answer: int) -> set:
    """Gives four wrong answers, where possible the same numbers worked out with other signs."""
    wrong = set()
    for _ in range(50):
        if len(wrong) == 4:
            break
        other = worked_out(numbers, [random.choice(SIGNS) for _ in range(2)])
        if other is not None and other != answer:
            wrong.add(other)
    while len(wrong) < 4:
        other = random.randint(0, 1000)
        if other != answer:
            wrong.add(other)
    return wrong


async def simpleMathGame(channel, client):
    reward = await prize(client, channel, 4000, 6000)
    numbers, signs, answer = question()
    options = list(wrong_answers(numbers, answer)) + [answer]
    random.shuffle(options)
    shown = [sign.replace("*", "×").replace("/", "÷") for sign in signs]
    asked = f"Calculate the result:\n# {numbers[0]} {shown[0]} {numbers[1]} {shown[1]} {numbers[2]}"

    def won(button, name: str, text: str) -> discord.Embed:
        return discord.Embed(
            title="Simple Math Game 🧮",
            description=f"{asked}\n:nerd: <@{view.winner}> solved it correctly and earned {MORA_EMOTE} `{text}`!",
            color=discord.Color.green(),
        )

    view = GuessView(
        client,
        channel,
        reward,
        won,
        [(option == answer, {"label": str(option)}) for option in options],
        wrong="That is incorrect!",
        already="You have already guessed!",
        keep_buttons=True,
    )
    view.message = await channel.send(
        embed=discord.Embed(
            title="Simple Math Game 🧮",
            description=f"{asked}\nFirst to answer correctly wins {MORA_EMOTE} `{reward}`. One try per person!",
            color=discord.Color.gold(),
        ),
        view=view,
    )


async def setup(bot) -> None:
    pass
