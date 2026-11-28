import asyncio
import io
import random
import time
from collections import Counter
from pathlib import Path

import discord
from PIL import Image, ImageDraw, ImageFont

from commands.Events.config import (
    MORA_EMOTE,
    NO_EMOTE,
    TYPERACER_BG_PATH,
    TYPERACER_FONT_PATH,
    WORDS,
    YES_EMOTE,
)
from commands.Events.games.common import count, earn, prize, took_part, user_and_title

IMAGE_CHANNEL = 1026968305208131645
REVERSE_BG_PATH = "./assets/94e3fe.png"
SECONDS = 300
# Quicktype phrases, made once with essential_generators; loading that library took 300 MB.
PHRASES = Path(__file__).with_name("phrases.txt")


def draw(text: str, background: str) -> io.BytesIO:
    """Gives a PNG of the text written on a background picture."""
    image = Image.open(background)
    font = ImageFont.truetype(TYPERACER_FONT_PATH, 55)
    ImageDraw.Draw(image).text((120, 60), text, font=font, fill=(0, 0, 0))
    picture = io.BytesIO()
    image.save(picture, "PNG")
    picture.seek(0)
    return picture


async def picture_url(client, text: str, background: str = TYPERACER_BG_PATH) -> str:
    """Uploads the text as a picture and gives the link to it."""
    picture = await asyncio.to_thread(draw, text, background)
    upload = await client.get_channel(IMAGE_CHANNEL).send(
        file=discord.File(picture, filename="typeracer.png")
    )
    return upload.attachments[0].proxy_url


async def race(client, channel, message, reward, right, near, won, lost, label) -> None:
    """Runs a typing race for five minutes: the first right message wins, near misses count as taking part."""
    start = time.time()
    close = set()
    winner = None

    def here(typed) -> bool:
        return typed.channel == channel and not typed.author.bot

    while True:
        try:
            answer = await client.wait_for(
                "message", check=here, timeout=max(start + SECONDS - time.time(), 0)
            )
        except asyncio.TimeoutError:
            await message.edit(embed=lost)
            break
        try:
            if right(answer.content):
                try:
                    await answer.add_reaction(YES_EMOTE)
                except Exception:
                    continue
                winner = answer.author.id
                text, earned = await earn(client, channel, winner, reward)
                name = await user_and_title(winner, channel.guild.id, client.pool)
                await message.edit(embed=won(name, text))
                await count(client, channel, winner, earned, start)
                break
            if near(answer.content):
                close.add(answer.author.id)
                try:
                    await answer.add_reaction(NO_EMOTE)
                except Exception:
                    continue
        except Exception as error:
            print(f"{label} error: {error}")
            return
    await took_part(client, channel, close, but={winner})


def embed(title: str, description: str, color, url: str = None) -> discord.Embed:
    """Gives an embed, with a picture when there is a link to one."""
    made = discord.Embed(title=title, description=description, color=color)
    if url:
        made.set_image(url=url)
    return made


def matches(typed: str, wanted: str) -> int:
    """Counts the places where two texts have the same character."""
    return sum(1 for one, other in zip(typed, wanted) if one == other)


async def quicktype(channel, client):
    reward = await prize(client, channel, 4000, 6000)
    wanted = random.choice(PHRASES.read_text(encoding="utf-8").splitlines())
    url = await picture_url(client, wanted)
    title = "Quicktype Racer"
    message = await channel.send(
        embed=embed(
            title,
            f"First to type the following phrase in chat wins {MORA_EMOTE} `{reward}`.",
            discord.Color.blurple(),
            url,
        )
    )
    await race(
        client,
        channel,
        message,
        reward,
        lambda typed: typed.strip() == wanted,
        lambda typed: matches(typed.strip(), wanted) >= 10,
        lambda name, text: embed(
            title,
            f"{name} won {MORA_EMOTE} `{text}`.",
            discord.Color.brand_green(),
            url,
        ),
        embed(
            "Quicktype Racer - Time Out! ⌛",
            f"No one typed the phrase in time!\n**Correct answer:** `{wanted}`",
            discord.Color.light_grey(),
            url,
        ),
        "Type Racer",
    )


async def reverseQuicktype(channel, client):
    reward = await prize(client, channel, 3000, 5000)
    digits = "".join(str(random.randint(0, 9)) for _ in range(8))
    wanted = digits[::-1]
    url = await picture_url(client, digits, REVERSE_BG_PATH)
    title = "Reverse Number Quicktype"
    message = await channel.send(
        embed=embed(
            title,
            f"First to type the following numbers **IN REVERSE** in chat wins {MORA_EMOTE} `{reward}`.",
            discord.Color.blurple(),
            url,
        )
    )
    await race(
        client,
        channel,
        message,
        reward,
        lambda typed: typed.strip() == wanted,
        lambda typed: matches(typed.strip(), wanted) >= 5,
        lambda name, text: embed(
            title,
            f"{name} won {MORA_EMOTE} `{text}`.",
            discord.Color.brand_green(),
            url,
        ),
        embed(
            "Reverse Quicktype - Time Out! ⌛",
            f"**Original Numbers:** `{digits}`\n**Reversed Answer:** `{wanted}`\nNo one answered in time!",
            discord.Color.light_grey(),
            url,
        ),
        "Reverse Quicktype",
    )


def scramble_string(word: str) -> str:
    """Gives the letters of a word in another order than the word has them."""
    letters = list(word)
    random.shuffle(letters)
    while letters == list(word):
        random.shuffle(letters)
    return "".join(letters)


async def unscrambleWords(channel, client):
    reward = await prize(client, channel, 3000, 5000)
    word = random.choice(WORDS).strip().lower()
    scrambled = scramble_string(word)
    title = "Unscramble the Scrambled"
    opening = embed(
        title,
        f"First to unscramble the following word wins {MORA_EMOTE} `{reward}`.",
        discord.Color.blurple(),
    )
    opening.add_field(name="Scrambled Word", value=f"`{scrambled}`", inline=True)
    message = await channel.send(embed=opening)
    await race(
        client,
        channel,
        message,
        reward,
        lambda typed: typed.lower().strip() == word,
        lambda typed: not Counter(scrambled) - Counter(typed.lower().strip()),
        lambda name, text: embed(
            title,
            f"{name} won {MORA_EMOTE} `{text}`.\n\n"
            f"**Scrambled:** `{scrambled}`\n"
            f"**Correct:** `{word}`",
            discord.Color.brand_green(),
        ),
        embed(
            "Unscramble - Time Out! ⌛",
            f"**Scrambled:** `{scrambled}`\n"
            f"**Correct Answer:** `{word}`\n"
            "No one guessed in time!",
            discord.Color.light_grey(),
        ),
        "Unscramble",
    )


async def setup(bot) -> None:
    pass
