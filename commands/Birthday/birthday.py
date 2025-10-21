import discord
import datetime
import pytz

from firebase_admin import db
from discord import app_commands
from discord.ext import commands
from commands.Birthday.birthdayTexts import characters, characters_dict, timezones, months, days, time_to_emoji, month_map, months_short

async def timezone_autocomplete(
    interaction: discord.Interaction,
    current: str,
):
    if current == "":
        return [
            app_commands.Choice(name=timezones[x], value=timezones[x])
            for x in range(25)
        ]
    else:
        list = []
        for tz in timezones:
            if current.lower() in tz.lower():
                list.append(tz)
        list = list[:25]
        return [app_commands.Choice(name=x, value=x) for x in list]


async def day_autocomplete(
    interaction: discord.Interaction,
    current: str,
):
    if current == "":
        return [app_commands.Choice(name=str(days[x]), value=str(days[x])) for x in range(25)]
    else:
        list = []
        for day in days:
            if current.lower() in day.lower():
                list.append(day)
        list = list[:25]
        return [app_commands.Choice(name=str(x), value=str(x)) for x in list]


async def character_autocomplete(
    interaction: discord.Interaction,
    current: str,
):
    if current == "":
        return [
            app_commands.Choice(name=characters[x], value=characters[x])
            for x in range(25)
        ]
    else:
        list = []
        for char in characters:
            if current.lower() in char.lower():
                list.append(char)
        list = list[:25]
        return [app_commands.Choice(name=x, value=x) for x in list]


@app_commands.guild_only()
class Birthday(commands.GroupCog, name="birthday"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(
        name="sync", description="Sync data from Birthday Bot (Admin only)"
    )
    @app_commands.describe(file="The TXT file exported from Birthday Bot")
    @app_commands.checks.has_permissions(administrator=True)
    async def birthday_sync(
        self, interaction: discord.Interaction, file: discord.Attachment
    ) -> None:
        await interaction.response.defer()

        oldFile = open("./assets/BirthdayBotData.txt", "r")
        oldfileContent = oldFile.read()
        oldbirthdays = oldfileContent.split("●")
        oldbirthdays.pop(0)
        ids = []
        for obday in oldbirthdays:
            id = int(obday.split("-")[1].split(" ")[1])
            ids.append(id)

        await file.save("./assets/BirthdayBotData.txt")
        f = open("./assets/BirthdayBotData.txt", "r")
        fileContent = f.read()

        birthdays = fileContent.split("●")
        birthdays.pop(0)
        count = 0
        for bday in birthdays:
            x = bday.split("-")
            month = x[0].strip()
            month = month_map.get(month, "Invalid abbr")
            if month == "Invalid abbr":
                continue
            day = int(x[1].split(":")[0].strip())
            id = int(x[1].split(" ")[1])
            if id in ids:
                continue
            if "Time zone:" in bday:
                timezone = bday.split("Time zone: ")[1].strip()
                if timezone == "GMT":
                    timezone = "Atlantic/Azores"
            else:
                timezone = "Atlantic/Azores"

            birth_date = datetime.datetime(2024, month, day, 0, 0, 0)
            birth_timezone = pytz.timezone(timezone)
            localized_birth_date = birth_timezone.localize(birth_date)
            utc_birth_date = localized_birth_date.astimezone(pytz.utc)
            display_utc_date = utc_birth_date.strftime("%m-%d %H:%M")

            existed = False
            ref = db.reference("/Birthday")
            bday = ref.get()
            for key, value in bday.items():
                if value["User ID"] == id:
                    existed = True
                    break

            if existed:
                continue

            data = {
                interaction.guild.name: {
                    "User ID": id,
                    "Month": month,
                    "Day": day,
                    "Timezone": timezone,
                    "Display UTC Date": display_utc_date,
                    "Fav Character": "None",
                }
            }

            for key, value in data.items():
                ref.push().set(value)
            count += 1
        await interaction.followup.send(f"Added **{count}** birthday records.")
    @birthday_sync.error
    async def birthday_sync_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)

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
        day=day_autocomplete,
        timezone=timezone_autocomplete,
        character=character_autocomplete,
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
        monthName = month.name
        month = int(month.value)

        if timezone not in timezones:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="<:no:1036810470860013639> **Invalid timezone.** Please search and select from the menu or refer to https://arilyn.cc/.",
                    color=0xFF0000,
                ),
                ephemeral=True,
            )
            return
        if monthName not in months:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="<:no:1036810470860013639> **Invalid month.** Please search and select from the menu.",
                    color=0xFF0000,
                ),
                ephemeral=True,
            )
            return
        if day not in days:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="<:no:1036810470860013639> **Invalid day.** Please search and select from the menu.",
                    color=0xFF0000,
                ),
                ephemeral=True,
            )
            return
        if character not in characters and character != "None":
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="<:no:1036810470860013639> **Invalid character.** Please search and select from the menu.",
                    color=0xFF0000,
                ),
                ephemeral=True,
            )
            return

        day = int(day)
        if (
            (month == 2 and day > 29)
            or (month in [4, 6, 9, 11] and day > 30)
            or (month in [1, 3, 5, 7, 8, 10, 12] and day > 31)
        ):
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="<:no:1036810470860013639> The date you specified is not a valid calendar date.",
                    color=0xFF0000,
                ),
                ephemeral=True,
            )
            return
        birth_date = datetime.datetime(2024, month, day, 0, 0, 0)
        birth_timezone = pytz.timezone(timezone)
        localized_birth_date = birth_timezone.localize(birth_date)
        utc_birth_date = localized_birth_date.astimezone(pytz.utc)
        display_utc_date = utc_birth_date.strftime("%m-%d %H:%M")

        ref = db.reference("/Birthday")
        bday = ref.get()
        for key, value in bday.items():
            if value["User ID"] == interaction.user.id:
                db.reference("/Birthday").child(key).delete()
                break

        data = {
            interaction.guild.name: {
                "User ID": interaction.user.id,
                "Month": month,
                "Day": day,
                "Timezone": timezone,
                "Display UTC Date": display_utc_date,
                "Fav Character": character,
            }
        }

        for key, value in data.items():
            ref.push().set(value)

        embed = discord.Embed(
            title="✅ Birthday Saved",
            description=f":birthday: You have set your birthday to **{monthName} {day}** *({timezone})*. \n*<:YanfeiNote:1335644122253623458> Your birthday in UTC time is **{display_utc_date}** {time_to_emoji(display_utc_date.split(' ')[1])}*",
            color=0x04C607,
        )
        icon_link = characters_dict[character]['icon']
        embed.set_thumbnail(url=icon_link)

        await interaction.response.send_message(embed=embed)
    @birthday_set.error
    async def birthday_set_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)

    @app_commands.command(name="get", description="Get the birthday of a member")
    @app_commands.describe(
        user="The member you wish to get the birthday of",
    )
    async def birthday_get(
        self, interaction: discord.Interaction, user: discord.Member = None
    ) -> None:
        if user is None:
            user = interaction.user

        ref = db.reference("/Birthday")
        bday = ref.get()
        month = day = timezone = display_utc_date = None
        for key, value in bday.items():
            if value["User ID"] == user.id:
                month = value["Month"]
                day = value["Day"]
                timezone = value["Timezone"]
                display_utc_date = value["Display UTC Date"]
                character = value["Fav Character"]
                break

        if month is None or day is None or timezone is None or display_utc_date is None:
            if user == interaction.user:
                embed = discord.Embed(
                    description=f"<:no:1036810470860013639> We don't have your birthday in our database. Use </birthday set:1246958872502075463> to set your birthday!",
                    color=0xFF0000,
                )
            else:
                embed = discord.Embed(
                    description=f"<:no:1036810470860013639> We don't have {user.mention}'s birthday in our database.",
                    color=0xFF0000,
                )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

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
        icon_link = characters_dict[character]['icon']
        embed.set_thumbnail(url=icon_link)
        await interaction.response.send_message(embed=embed)
    @birthday_get.error
    async def birthday_get_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)

    @app_commands.command(
        name="remove", description="Remove your birthday from the database"
    )
    async def birthday_remove(
        self,
        interaction: discord.Interaction,
    ) -> None:
        found = False
        ref = db.reference("/Birthday")
        bday = ref.get()
        for key, value in bday.items():
            if value["User ID"] == interaction.user.id:
                db.reference("/Birthday").child(key).delete()
                found = True
                break

        if not found:
            embed = discord.Embed(
                title="We could not find your birthday",
                description=f"Maybe you have already removed your birthday, or you have never set one in the first place. Anyways, no records found in our database.\n\n*What are you doing anyways, go **set your birthday** by using </birthday set:1246958872502075463>!*",
                color=0xCDCB20,
            )
        else:
            embed = discord.Embed(
                title="Birthday Removed :pensive:",
                description=f"It's sad to see you go ~ your birthday is a very important milestone, and we want to celebrate it with you! Please consider changing your mind and **set your birthday** by using </birthday set:1246958872502075463>.",
                color=0xE35417,
            )

        await interaction.response.send_message(embed=embed)
    @birthday_remove.error
    async def birthday_remove_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)

    @app_commands.command(
        name="export",
        description="Exports all birthdays of your server members (Admin only)",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def birthday_export(
        self,
        interaction: discord.Interaction,
    ) -> None:
        await interaction.response.defer(thinking=True)
        list = []
        ref = db.reference("/Birthday")
        bday = ref.get()
        for x in bday.items():
            list.append(x)
        data_items = list
        data_items_with_dates = []
        for key, value in data_items:
            try:
                date = datetime.datetime.strptime(
                    value["Display UTC Date"], "%m-%d %H:%M"
                )
                data_items_with_dates.append((key, value, date))
            except ValueError:
                print(f"Invalid date found: {value['Display UTC Date']} for key {key}")
        
        sorted_data_items = sorted(data_items_with_dates, key=lambda x: x[2])
        sorted_data_items_final = [
            (key, value) for key, value, date in sorted_data_items
        ]

        content = f"Birthdays in {interaction.guild.name}\n\n"
        for key, value in sorted_data_items_final:
            try:
                content = f"{content}● {months_short[value['Month']-1]}-{value['Day']} ({value['Timezone']}): {value['User ID']} {(await interaction.guild.fetch_member(value['User ID'])).name} | {value['Display UTC Date']} | {value['Fav Character']}\n"
            except Exception:
                pass

        filename = "./assets/birthday_export.txt"
        with open(filename, "w") as file:
            file.write(content)

        await interaction.followup.send(file=discord.File(filename))
    @birthday_export.error
    async def birthday_export_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)

    @app_commands.command(
        name="enable", description="Enable birthday wishes in a channel"
    )
    @app_commands.describe(
        channel="The channel to send birthday wishes in",
        role="The role to given those who are celebrating their birthdays",
        create_birthday_thread="Whether if a thread is created for each birthday wish"
    )
    @app_commands.checks.bot_has_permissions(manage_roles=True, create_public_threads=True, manage_webhooks=True)
    @app_commands.checks.has_permissions(manage_guild=True, manage_channels=True, manage_webhooks=True)
    async def birthday_enable(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        role: discord.Role,
        create_birthday_thread: bool = False
    ) -> None:
        
        if role == interaction.guild.default_role:
            return await interaction.response.send_message("<:no:1036810470860013639> You have specified an unknown role!", ephemeral=True)

        ref = db.reference("/Birthday System")
        bs = ref.get()

        try:
            for key, val in bs.items():
                if val["Server ID"] == interaction.guild.id:
                    db.reference("/Birthday System").child(key).delete()
                    break
        except Exception:
            pass

        webhook = await channel.create_webhook(
            name="Birthday Wishes", reason=f"Created by user ID: {interaction.user.id}"
        )

        data = {
            channel.id: {
                "Channel ID": channel.id,
                "Webhook ID": webhook.id,
                "Server ID": interaction.guild.id,
                "Server Name": interaction.guild.name,
                "Role ID": role.id,
                "Create Birthday Thread": create_birthday_thread
            }
        }

        for key, value in data.items():
            ref.push().set(value)

        embed = discord.Embed(
            title="Birthday wishes enabled!",
            description=f"If a member in your server has set their birthday in this bot using </birthday set:1254927191129456640>, then I will wish them a happy birthday when the day comes in {channel.mention} and grant them the {role.mention} temporarily.\n\n-# **Make sure that {role.mention} is below my bot role**! Otherwise, I cannot add/remove {role.mention} when the day comes.",
            colour=0x00FF00,
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await interaction.response.send_message(embed=embed)
    @birthday_enable.error
    async def birthday_enable_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)

    @app_commands.command(
        name="disable", description="Disable birthday wishes in the server"
    )
    @app_commands.checks.has_permissions(manage_guild=True, manage_channels=True)
    async def birthday_disable(
        self,
        interaction: discord.Interaction,
    ) -> None:

        ref = db.reference("/Birthday System")
        bs = ref.get()

        found = False
        for key, val in bs.items():
            if val["Server ID"] == interaction.guild.id:
                db.reference("/Birthday System").child(key).delete()
                found = True
                break

        if found:
            embed = discord.Embed(
                title="Birthday Wishes disabled!",
                description=f"Sad to see you go. If you change your mind at anytime, you could use </birthday enable:1036382520033415196> to enable birthday wishes again.",
                colour=0xFF0000,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(embed=embed)
        else:
            embed = discord.Embed(
                title="Birthday Wishes is not enabled!",
                description=f"What are you thinking? Birthday wishes are even enabled in this server in the first place. To enable the function, use </birthday enable:1036382520033415196>.",
                colour=0xFFFF00,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(embed=embed, ephemeral=True)
    @birthday_disable.error
    async def birthday_disable_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Birthday(bot))