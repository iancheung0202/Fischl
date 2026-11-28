import asyncio
import datetime
import logging
import random
import re
import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

from commands.Events.chat import DailySigilSystem
from commands.Events.chests import DailyChestSystem
from commands.Events.config import (
    LETTER_LIST,
    MORA_EMOTE,
    NO_EMOTE,
    TIPS,
    profile_link_button,
)
from commands.Events.games.auction import grandAuctionHouse
from commands.Events.games.blackjack import groupBlackjack
from commands.Events.games.boss import defeatTheBoss
from commands.Events.games.common import OWNER, add_xp, report_crash
from commands.Events.games.counting import countingCurrency, eggWalk, guessTheNumber
from commands.Events.games.dice import rollADice
from commands.Events.games.double import doubleOrKeep
from commands.Events.games.duel import rockPaperScissors, splitOrSteal
from commands.Events.games.guess import knowYourMembers, matchThePFP, memoryGame
from commands.Events.games.hangman import hangmanGame
from commands.Events.games.heist import bankHeist
from commands.Events.games.maths import simpleMathGame
from commands.Events.games.pickup import pickUpIceCream, pickUpTheWatermelon
from commands.Events.games.quiz import genshinEmojiRiddle, hsrEmojiRiddle
from commands.Events.games.tictactoe import ticTacTok
from commands.Events.games.truths import twoTruthsAndALie
from commands.Events.games.typed import quicktype, reverseQuicktype, unscrambleWords
from commands.Events.games.whosaid import whoSaidIt
from commands.Events.helperFunctions import (
    MORA_ENTRY,
    get_encore_chance,
    get_user_minigame_settings,
    get_user_stats,
)
from commands.Events.quests import update_quest
from commands.Events.trackData import check_tier_rewards

# The order is saved data: a channel's list of minigames names them by their letter in LETTER_LIST.
EVENTS = [
    defeatTheBoss,
    quicktype,
    eggWalk,
    matchThePFP,
    splitOrSteal,
    reverseQuicktype,
    pickUpIceCream,
    pickUpTheWatermelon,
    guessTheNumber,
    memoryGame,
    whoSaidIt,
    unscrambleWords,
    twoTruthsAndALie,
    countingCurrency,
    rockPaperScissors,
    rollADice,
    groupBlackjack,
    genshinEmojiRiddle,
    hsrEmojiRiddle,
    doubleOrKeep,
    knowYourMembers,
    hangmanGame,
    grandAuctionHouse,
    bankHeist,
    simpleMathGame,
    ticTacTok,
]
LETTER_TO_EVENT = dict(zip(LETTER_LIST, EVENTS))
MORA_ADMINS = (OWNER, 1251949796210638989, 885217186468229140)
IGNORED_MEMBER = 1006694571167719527
MANUAL_CHANNEL = 10
USE_SUMMON = """
    UPDATE minigame_progression
    SET minigame_summons = minigame_summons - 1, updated_at = CURRENT_TIMESTAMP
    WHERE gid = $1 AND uid = $2 AND minigame_summons > 0
    RETURNING minigame_summons
"""

active_channels = set()


def display_name(event) -> str:
    """Gives a minigame's name as members read it, such as "Defeat the Boss"."""
    words = re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", event.__name__)
    name = words.replace("The", "the").title().replace("The", "the")
    return name.replace("Pfp", "PFP").replace("Hsr", "HSR")


class ChannelCache:
    """Every channel's minigame settings, read from the database at most once a minute."""

    TTL = 60

    def __init__(self, pool):
        self.pool = pool
        self.channels = {}
        self.read_at = 0
        self.reading = asyncio.Lock()

    async def get_channel(self, channel_id: int):
        """Gives a channel's saved settings, or None for a channel with none."""
        async with self.reading:
            if time.time() - self.read_at >= self.TTL:
                rows = await self.pool.fetch("SELECT * FROM minigame_settings")
                self.channels = {row["channel_id"]: dict(row) for row in rows}
                self.read_at = time.time()
        return self.channels.get(channel_id)

    def invalidate_all(self) -> None:
        self.read_at = 0


class UserFlags:
    """Which of chests, minigames and Sigils each member turned off, remembered for a while."""

    TTL = 6000

    def __init__(self, pool):
        self.pool = pool
        self.flags = {}

    async def get(self, guild_id: int, user_id: int) -> dict:
        key = (guild_id, user_id)
        cached = self.flags.get(key)
        if cached and time.time() - cached[0] < self.TTL:
            return cached[1]
        settings = await get_user_minigame_settings(self.pool, guild_id, user_id)
        self.flags[key] = (time.time(), settings)
        return settings

    def invalidate(self, guild_id: int, user_id: int) -> None:
        self.flags.pop((guild_id, user_id), None)


class TheEventItself(commands.Cog):
    def __init__(self, bot):
        self.client = bot
        self.cache = ChannelCache(bot.pool)
        self.user_flags = UserFlags(bot.pool)
        self.pending_chests = set()
        self.chest_system = DailyChestSystem(self.user_flags)
        self.sigil_system = DailySigilSystem(bot.pool)
        self.daily_reset.start()

    def cog_unload(self):
        self.daily_reset.cancel()

    @tasks.loop(time=datetime.time(0, 0, tzinfo=datetime.timezone.utc))
    async def daily_reset(self):
        self.chest_system.reset_daily_states()
        self.sigil_system.forget()
        self.user_flags.flags.clear()

    async def add_mora(self, message) -> None:
        """Runs `-addMora <member> <amount>`: adds exactly that much, outside any channel."""
        if message.author.id not in MORA_ADMINS:
            return await message.add_reaction(NO_EMOTE)
        words = message.content.split()
        uid = int(words[1].strip("<@!>"))
        mora = int(words[2])
        await self.client.pool.execute(
            MORA_ENTRY, uid, message.guild.id, MANUAL_CHANNEL, int(time.time()), mora
        )
        await message.reply(
            f"Added exactly {MORA_EMOTE} `{mora:,}` to <@{uid}>'s inventory. \n-# This is not boosted and doesn't count towards quest progression."
        )

    async def add_xp(self, message) -> None:
        """Runs `-addXP <member> <amount>`: adds the XP and gives the tier rewards it reaches."""
        if message.author.id != OWNER:
            return await message.add_reaction(NO_EMOTE)
        if not message.mentions:
            return await message.channel.send("Mention a user!")
        user = message.mentions[0]
        try:
            amount = int(message.content.split()[2])
            tier, old_xp, new_xp = await add_xp(
                user.id, message.guild.id, amount, self.client
            )
            await check_tier_rewards(
                guild_id=message.guild.id,
                user_id=user.id,
                old_xp=old_xp,
                new_xp=new_xp,
                channel=message.channel,
                client=self.client,
                pool=self.client.pool,
            )
            await message.channel.send(
                f"Added `{amount}` XP to {user.mention}. Reached tier `{tier}`!"
            )
        except Exception as e:
            await message.channel.send(f"Error: {e}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        if message.content.startswith("-addMora"):
            return await self.add_mora(message)
        if message.content.startswith("-addXP"):
            return await self.add_xp(message)
        settings = await self.cache.get_channel(message.channel.id)
        if not settings or message.author.id == IGNORED_MEMBER:
            return
        if settings["chests_enabled"]:
            await self.chest_system.process_message(message, self)
        if settings["chat_enabled"]:
            flags = await self.user_flags.get(message.guild.id, message.author.id)
            if not flags.get("sigils_disabled", False):
                await self.sigil_system.process_chat_sigils(
                    message, settings, self.client
                )
        if settings["minigames_enabled"]:
            await self.maybe_drop(message, settings)

    async def maybe_drop(self, message, settings: dict) -> None:
        """Starts a random minigame on every so-manyth message, unless one ran here lately or is running."""
        channel = message.channel
        frequency = settings["minigames_frequency"]
        if not frequency or message.id % frequency != 0:
            return
        eligible = [
            LETTER_TO_EVENT[letter]
            for letter in settings["minigames_list"] or []
            if letter in LETTER_TO_EVENT
        ]
        if not eligible:
            return
        flags = await self.user_flags.get(message.guild.id, message.author.id)
        if flags.get("minigame_disabled", False):
            return
        async for recent in channel.history(limit=frequency):
            if recent.embeds and recent.author.id == self.client.user.id:
                return
        if channel.id in active_channels:
            return
        active_channels.add(channel.id)
        event = random.choice(eligible)
        place = f"#{channel.name} ({channel.id}) in {message.guild.name} ({message.guild.id})"
        try:
            view = discord.ui.View()
            view.add_item(profile_link_button())
            await channel.send(
                embed=discord.Embed(
                    description=f"Since chat is relatively active, I'm dropping a random event in `3 seconds`.\n-# ***Tip:** {random.choice(TIPS)}*",
                    color=discord.Color.orange(),
                ),
                view=view,
            )
            await asyncio.sleep(2.4)
            logging.warning(f"<{event.__name__}>: {place}")
            await event(channel, self.client)
        except Exception as e:
            logging.exception("Event crashed")
            await report_crash(self.client, channel, e)
        finally:
            active_channels.discard(channel.id)
            logging.info(f"<{event.__name__}>: {place} has ended")


class Summon(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.minigame_mapping = {event.__name__: event for event in EVENTS}
        self.names = {event.__name__: display_name(event) for event in EVENTS}

    async def minigame_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=name, value=value)
            for value, name in self.names.items()
            if current.lower() in name.lower()
        ][:25]

    async def spend(self, pool, gid: int, uid: int):
        """Uses one summon, or none on an encore; gives (summons left, encore), or None with no summon to use."""
        left = (await get_user_stats(pool, gid, uid)).get("minigame_summons") or 0
        if left < 1:
            return None
        chance = min(50, await get_encore_chance(pool, gid, uid))
        if random.random() * 100 < chance:
            return (left, True)
        left = await pool.fetchval(USE_SUMMON, gid, uid)
        return None if left is None else (left, False)

    @app_commands.command(
        name="summon", description="Start a minigame using your summons"
    )
    @app_commands.autocomplete(minigame=minigame_autocomplete)
    @app_commands.describe(minigame="Choose a minigame to start")
    async def summon(self, interaction: discord.Interaction, minigame: str):
        await interaction.response.defer()
        event = self.minigame_mapping.get(minigame)
        if not event:
            return await interaction.followup.send(
                f"{NO_EMOTE} Invalid minigame selection!"
            )
        spent = await self.spend(
            interaction.client.pool, interaction.guild.id, interaction.user.id
        )
        if not spent:
            return await interaction.followup.send(
                f"{NO_EMOTE} You don't have any minigame summons left!"
            )
        left, encore = spent
        footer = f"You have {left} summon{'s' if left != 1 else ''} remaining"
        if encore:
            footer += " | 🎭 Encore! This summon is not consumed."
        embed = discord.Embed(
            title=":magnet: Minigame Summoned!",
            description=f"{interaction.user.mention} successfully started the **{self.names[minigame]}** minigame.",
            color=discord.Color.green(),
        )
        embed.set_footer(text=footer)
        await interaction.followup.send(embed=embed)
        await update_quest(
            interaction.user.id,
            interaction.guild.id,
            interaction.channel.id,
            {"summon_minigame": 1},
            interaction.client,
        )
        await event(interaction.channel, interaction.client)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TheEventItself(bot))
    await bot.add_cog(Summon(bot))
