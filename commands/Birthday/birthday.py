import datetime
import io

import discord
import pytz
from discord import app_commands
from discord.ext import commands

from commands.Birthday import birthdayStore as store
from commands.Birthday.birthdayTexts import (
    characters,
    characters_dict,
    days,
    month_map,
    months,
    months_short,
    time_to_emoji,
    timezones,
)
from utils.commands import SlashCommand

NO = "<:no:1036810470860013639>"


def utc_start(month, day, timezone):
    """Gives when a birthday starts in UTC, written `MM-DD HH:MM`."""
    start = pytz.timezone(timezone).localize(datetime.datetime(2024, month, day))
    return start.astimezone(pytz.utc).strftime("%m-%d %H:%M")


def menu(options):
    """Makes an autocomplete offering up to 25 of the options that hold what was typed."""

    async def autocomplete(interaction: discord.Interaction, current: str):
        found = [str(x) for x in options if current.lower() in str(x).lower()]
        return [app_commands.Choice(name=x, value=x) for x in found[:25]]

    return autocomplete


async def refuse(interaction, problem):
    """Tells only the member what was wrong with what they entered."""
    await interaction.response.send_message(
        embed=discord.Embed(description=f"{NO} {problem}", color=0xFF0000),
        ephemeral=True,
    )


@app_commands.guild_only()
class Birthday(commands.GroupCog, name="birthday"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    async def cog_load(self):
        """Makes the tables before the first command."""
        await store.create(self.bot.pool)

    @app_commands.command(
        name="sync", description="Sync data from Birthday Bot (Admin only)"
    )
    @app_commands.describe(file="The TXT file exported from Birthday Bot")
    @app_commands.checks.has_permissions(administrator=True)
    async def birthday_sync(
        self, interaction: discord.Interaction, file: discord.Attachment
    ) -> None:
        """Adds the birthdays in the file that were not in the last file synced."""
        await interaction.response.defer()

        with open("./assets/BirthdayBotData.txt", "r") as old:
            known = [
                int(entry.split("-")[1].split(" ")[1])
                for entry in old.read().split("●")[1:]
            ]
        await file.save("./assets/BirthdayBotData.txt")
        with open("./assets/BirthdayBotData.txt", "r") as new:
            entries = new.read().split("●")[1:]

        count = 0
        for entry in entries:
            parts = entry.split("-")
            month = month_map.get(parts[0].strip())
            if month is None:
                continue
            day = int(parts[1].split(":")[0].strip())
            user_id = int(parts[1].split(" ")[1])
            if user_id in known:
                continue
            timezone = "Atlantic/Azores"
            if "Time zone:" in entry:
                timezone = entry.split("Time zone: ")[1].strip()
                if timezone == "GMT":
                    timezone = "Atlantic/Azores"
            start = utc_start(month, day, timezone)
            if await store.find(self.bot.pool, user_id):
                continue
            await store.save(
                self.bot.pool, user_id, month, day, timezone, start, "None"
            )
            count += 1
        await interaction.followup.send(f"Added **{count}** birthday records.")

    @app_commands.command(name="set", description="Set your birth date and timezone")
    @app_commands.choices(
        month=[
            app_commands.Choice(name="January", value="1"),
            app_commands.Choice(name="February", value="2"),
            app_commands.Choice(name="March", value="3"),
            app_commands.Choice(name="April", value="4"),
            app_commands.Choice(name="May", value="5"),
            app_commands.Choice(name="June", value="6"),
            app_commands.Choice(name="July", value="7"),
            app_commands.Choice(name="August", value="8"),
            app_commands.Choice(name="September", value="9"),
            app_commands.Choice(name="October", value="10"),
            app_commands.Choice(name="November", value="11"),
            app_commands.Choice(name="December", value="12"),
        ]
    )
    @app_commands.autocomplete(
        day=menu(days),
        timezone=menu(timezones),
        character=menu(characters),
    )
    @app_commands.describe(
        month="The month of your birth date",
        day="The day of your birth date",
        timezone="The timezone of your birth location (go to https://arilyn.cc to find your timezone)",
        character="Your favorite Genshin character who will wish you a happy birthday",
    )
    async def birthday_set(
        self,
        interaction: discord.Interaction,
        month: app_commands.Choice[str],
        day: str,
        timezone: str,
        character: str,
    ) -> None:
        """Saves the member's birthday after checking each thing they entered."""
        monthName = month.name
        month = int(month.value)

        if timezone not in timezones:
            return await refuse(
                interaction,
                "**Invalid timezone.** Please search and select from the menu or refer to https://arilyn.cc/.",
            )
        if int(day) not in days:
            return await refuse(
                interaction, "**Invalid day.** Please search and select from the menu."
            )
        if character not in characters and character != "None":
            return await refuse(
                interaction,
                "**Invalid character.** Please search and select from the menu.",
            )
        day = int(day)
        if day > (29 if month == 2 else 30 if month in [4, 6, 9, 11] else 31):
            return await refuse(
                interaction, "The date you specified is not a valid calendar date."
            )
        display_utc_date = utc_start(month, day, timezone)
        await store.save(
            self.bot.pool,
            interaction.user.id,
            month,
            day,
            timezone,
            display_utc_date,
            character,
        )

        embed = discord.Embed(
            title="✅ Birthday Saved",
            description=f":birthday: You have set your birthday to **{monthName} {day}** *({timezone})*. \n*<:YanfeiNote:1335644122253623458> Your birthday in UTC time is **{display_utc_date}** {time_to_emoji(display_utc_date.split(' ')[1])}*",
            color=0x04C607,
        )
        if character != "None" and character in characters_dict:
            icon_link = characters_dict[character]["icon"]
            embed.set_thumbnail(url=icon_link)

        embed.set_footer(
            text="Missing your favorite character? Join discord.gg/BXkc8CC4uJ and let us know!"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="get", description="Get the birthday of a member")
    @app_commands.describe(
        user="The member you wish to get the birthday of",
    )
    async def birthday_get(
        self, interaction: discord.Interaction, user: discord.Member = None
    ) -> None:
        """Shows a member's birthday, or says that none is saved."""
        if user is None:
            user = interaction.user

        saved = await store.find(self.bot.pool, user.id)
        if saved is None:
            if user == interaction.user:
                problem = f"We don't have your birthday in our database. Use {SlashCommand('birthday set')} to set your birthday!"
            else:
                problem = f"We don't have {user.mention}'s birthday in our database."
            return await refuse(interaction, problem)
        month, day, timezone = saved["month"], saved["day"], saved["timezone"]
        display_utc_date, character = saved["display_utc_date"], saved["fav_character"]

        if user == interaction.user:
            embed = discord.Embed(
                description=f":birthday: Your birthday is **{months[month-1]} {day}** *({timezone})*.\n Your birthday in UTC time is **{display_utc_date}** {time_to_emoji(display_utc_date.split(' ')[1])}",
                color=0xF1EE0C,
            )
        else:
            embed = discord.Embed(
                description=f":birthday: {user.mention}'s birthday is **{months[month-1]} {day}** *({timezone})*.\n In UTC time, it is **{display_utc_date}** {time_to_emoji(display_utc_date.split(' ')[1])}",
                color=0xF1EE0C,
            )

        if character != "None" and character in characters_dict:
            icon_link = characters_dict[character]["icon"]
            embed.set_thumbnail(url=icon_link)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="remove", description="Remove your birthday from the database"
    )
    async def birthday_remove(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Forgets the member's birthday."""
        found = await store.remove(self.bot.pool, interaction.user.id)

        if not found:
            embed = discord.Embed(
                title="We could not find your birthday",
                description=f"Maybe you have already removed your birthday, or you have never set one in the first place. Anyways, no records found in our database.\n\n*What are you doing anyways, go **set your birthday** by using {SlashCommand('birthday set')}!*",
                color=0xCDCB20,
            )
        else:
            embed = discord.Embed(
                title="Birthday Removed :pensive:",
                description=f"It's sad to see you go ~ your birthday is a very important milestone, and we want to celebrate it with you! Please consider changing your mind and **set your birthday** by using {SlashCommand('birthday set')}.",
                color=0xE35417,
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="export",
        description="Exports all birthdays of your server members (Admin only)",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def birthday_export(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Sends a file of every saved birthday whose member is in this server."""
        await interaction.response.defer(thinking=True)
        dated = []
        for saved in await store.everyone(self.bot.pool):
            try:
                date = datetime.datetime.strptime(
                    saved["display_utc_date"], "%m-%d %H:%M"
                )
            except ValueError:
                print(f"Invalid date found: {saved['display_utc_date']}")
                continue
            dated.append((date, saved))

        content = f"Birthdays in {interaction.guild.name}\n\n"
        for _, saved in sorted(dated, key=lambda pair: pair[0]):
            try:
                member = await interaction.guild.fetch_member(saved["user_id"])
            except Exception:
                continue
            content += f"● {months_short[saved['month']-1]}-{saved['day']} ({saved['timezone']}): {saved['user_id']} {member.name} | {saved['display_utc_date']} | {saved['fav_character']}\n"

        file = discord.File(io.BytesIO(content.encode()), "birthday_export.txt")
        await interaction.followup.send(file=file)

    @app_commands.command(
        name="enable", description="Enable birthday wishes in a channel"
    )
    @app_commands.describe(
        channel="The channel to send birthday wishes in",
        role="The role to given those who are celebrating their birthdays",
        create_birthday_thread="Whether if a thread is created for each birthday wish",
    )
    @app_commands.checks.bot_has_permissions(
        manage_roles=True, create_public_threads=True, manage_webhooks=True
    )
    @app_commands.checks.has_permissions(
        manage_guild=True, manage_channels=True, manage_webhooks=True
    )
    async def birthday_enable(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        role: discord.Role,
        create_birthday_thread: bool = False,
    ) -> None:
        """Turns wishes on for the server, with a new webhook in the channel."""
        if role == interaction.guild.default_role:
            return await interaction.response.send_message(
                "<:no:1036810470860013639> You have specified an unknown role!",
                ephemeral=True,
            )

        await store.disable(self.bot.pool, interaction.guild.id)
        webhook = await channel.create_webhook(
            name="Birthday Wishes", reason=f"Created by user ID: {interaction.user.id}"
        )
        await store.enable(
            self.bot.pool,
            interaction.guild.id,
            channel.id,
            webhook.id,
            role.id,
            create_birthday_thread,
        )

        embed = discord.Embed(
            title="Birthday wishes enabled!",
            description=f"If a member in your server has set their birthday in this bot using {SlashCommand('birthday set')}, then I will wish them a happy birthday when the day comes in {channel.mention} and grant them the {role.mention} temporarily.\n\n-# **Make sure that {role.mention} is below my bot role**! Otherwise, I cannot add/remove {role.mention} when the day comes.",
            colour=0x00FF00,
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="disable", description="Disable birthday wishes in the server"
    )
    @app_commands.checks.has_permissions(manage_guild=True, manage_channels=True)
    async def birthday_disable(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Turns wishes off for the server."""
        found = await store.disable(self.bot.pool, interaction.guild.id)

        if found:
            embed = discord.Embed(
                title="Birthday Wishes disabled!",
                description=f"Sad to see you go. If you change your mind at anytime, you could use {SlashCommand('birthday enable')} to enable birthday wishes again.",
                colour=0xFF0000,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(embed=embed)
        else:
            embed = discord.Embed(
                title="Birthday Wishes is not enabled!",
                description=f"What are you thinking? Birthday wishes are even enabled in this server in the first place. To enable the function, use {SlashCommand('birthday enable')}.",
                colour=0xFFFF00,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @birthday_sync.error
    @birthday_set.error
    @birthday_get.error
    @birthday_remove.error
    @birthday_export.error
    @birthday_enable.error
    @birthday_disable.error
    async def birthday_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Birthday(bot))
