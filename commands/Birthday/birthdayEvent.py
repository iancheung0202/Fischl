import datetime
import random

import discord
from discord.ext import commands, tasks

from commands.Birthday import birthdayStore as store
from commands.Birthday.birthdayTexts import characters, characters_dict

MINUTES = (0, 15, 30, 45)  # the minutes of an hour at which birthdays are checked
DATE = "%m-%d %H:%M"
CHOSEN = 'Use "/birthday set" to have your favorite character celebrate your birthday with you!'
RANDOM = (
    'Use "/birthday set" to update your birthday with timezones & favorite character!'
)


def readable(date):
    """Says whether a saved date can be read; Feb 29 cannot, and was never wished."""
    try:
        datetime.datetime.strptime(date, DATE)
    except ValueError:
        return False
    return True


class BirthdayCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.checked = None
        self.birthday_task.start()

    async def cog_load(self):
        """Makes the tables before the first check."""
        await store.create(self.bot.pool)

    def cog_unload(self):
        self.birthday_task.cancel()

    @tasks.loop(seconds=20)
    async def birthday_task(self):
        """Checks the birthdays once in every quarter of an hour."""
        now = datetime.datetime.now(datetime.timezone.utc)
        minute = now.strftime("%Y%m%d%H%M")
        if now.minute not in MINUTES or minute == self.checked:
            return
        self.checked = minute
        try:
            await self.check(now)
        except Exception as e:
            print(f"[Birthday] Check failed: {e}")

    @birthday_task.before_loop
    async def before_birthday_task(self):
        await self.bot.wait_until_ready()

    async def check(self, now):
        """Wishes birthdays starting this minute; takes the role back a day after."""
        starting = now.strftime(DATE)
        yesterday = f"{now.month:02d}-{now.day - 1:02d} {now.hour:02d}:"
        birthdays = await store.due(self.bot.pool, starting, yesterday)
        birthdays = [row for row in birthdays if readable(row["display_utc_date"])]
        if not birthdays:
            return
        places = await store.servers(self.bot.pool)
        for birthday in birthdays:
            act = self.wish if birthday["display_utc_date"] == starting else self.end
            for place in places:
                guild = self.bot.get_guild(place["server_id"])
                if guild is None:
                    continue
                try:
                    await act(guild, place, birthday)
                except Exception as e:
                    print(
                        f"[Birthday] Failed for {birthday['user_id']} in {guild.id}: {e}"
                    )

    async def wish(self, guild, place, birthday):
        """Posts the wish, opens its thread, gives the role and sends the DM."""
        try:
            member = await guild.fetch_member(birthday["user_id"])
        except discord.NotFound:
            return
        character, footer = birthday["fav_character"], CHOSEN
        if character == "None":
            character, footer = random.choice(characters), RANDOM
        icon = characters_dict[character]["icon"]
        line = characters_dict[character]["line"]
        embed = discord.Embed(
            description=line.replace("USER", f"**{member.display_name}**"),
            color=discord.Colour.random(),
        )
        embed.set_footer(text=footer)
        message = await self.post(guild, place, member, embed, character, icon)
        if message is not None and place["create_thread"]:
            try:
                await message.create_thread(
                    name=f"Wish {member.name} a Happy Birthday 🎉"
                )
            except Exception as e:
                print(f"[Birthday] Unable to create a thread in {guild.id}: {e}")

        role = guild.get_role(place["role_id"])
        if role is None:
            print(f"Birthday role not found in server {guild.id}")
            return
        try:
            await member.add_roles(role)
        except Exception as e:
            print(f"[Birthday] Unable to add {role.id} to {member.id}: {e}")
            return
        if message is None:
            return

        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.link,
                label=f"Read {character}'s Message",
                url=message.jump_url,
            )
        )
        embed = discord.Embed(
            title="Happy Birthday! 🎉🎂🥳",
            description=f"Happy birthday, {member.mention}! **{guild.name}** and its staff team wishes you a fantastic day. May your special day be as amazing as you are!\n\n*PS: **{character}** has something to say to you... :eyes:*",
            color=discord.Colour.random(),
        )
        embed.set_thumbnail(url=icon)
        embed.set_footer(
            text=f"You received this DM because you've set your birthday and {guild.name} has birthday notifications enabled!"
        )
        try:
            await member.send(embed=embed, view=view)
        except Exception as e:
            print(f"[Birthday] Cannot DM {member.id}: {e}")

    async def post(self, guild, place, member, embed, character, icon):
        """Sends the wish as the character and reacts to it; None if it was not sent."""
        try:
            webhook = await self.bot.fetch_webhook(place["webhook_id"])
            message = await webhook.send(
                content=f":birthday: Happy birthday to {member.mention}! Enjoy your special day!",
                embed=embed,
                username=character,
                avatar_url=icon,
                wait=True,
            )
        except Exception as e:
            print(f"[Birthday] Failed to send the wish in {guild.id}: {e}")
            return None
        try:
            await message.add_reaction("🎂")
        except Exception as e:
            print(f"[Birthday] Could not react to the wish in {guild.id}: {e}")
        return message

    async def end(self, guild, place, birthday):
        """Takes the birthday role back from a member who still has it."""
        role = guild.get_role(place["role_id"])
        if role is None:
            print(f"Birthday role not found in server {guild.id}")
            return
        try:
            member = await guild.fetch_member(birthday["user_id"])
        except discord.NotFound:
            return
        if role in member.roles:
            await member.remove_roles(role)


async def setup(bot):
    await bot.add_cog(BirthdayCog(bot))
