import discord
import asyncio
import datetime
import random

from discord.ext import commands, tasks
from firebase_admin import db
from commands.Birthday.birthdayTexts import characters, characters_dict

class BirthdayCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._birthday_sent_cache = {}
        self.birthday_task.start()

    def cog_unload(self):
        self.birthday_task.cancel()

    @tasks.loop()
    async def birthday_task(self):
        current_time = datetime.datetime.now(datetime.timezone.utc)
        minutes_to_test = [0, 7, 15, 30, 45]
        if current_time.minute in minutes_to_test:
            ref = db.reference("/Birthday")
            bday = ref.get()
            ref2 = db.reference("/Birthday System")
            bs = ref2.get()
            minute_key = current_time.strftime("%Y%m%d%H%M")
            
            for key, value in bday.items():
                for k, v in bs.items():
                    try:
                        server = self.bot.get_guild(v["Server ID"])
                    except Exception:
                        print("Cannot fetch server")
                        continue
                    if server is None:
                        continue
                    try:
                        birthday_role = server.get_role(v["Role ID"])
                    except Exception:
                        print("Cannot fetch birthday role")
                        continue
                    
                    display_utc_date = value["Display UTC Date"]
                    try:
                        utc_date_object = datetime.datetime.strptime(
                            display_utc_date, "%m-%d %H:%M"
                        )
                    except ValueError as e:
                        continue
                    
                    cache_key = (value["User ID"], v["Server ID"], minute_key)
                    if cache_key in self._birthday_sent_cache:
                        continue
                    
                    if (
                        utc_date_object.month == current_time.month
                        and utc_date_object.day == current_time.day
                        and utc_date_object.hour == current_time.hour
                        and utc_date_object.minute == current_time.minute
                    ):
                        member = await server.fetch_member(value["User ID"])
                        if member is None:
                            continue
                        
                        print("Fetched some birthday")
                        character = value["Fav Character"]
                        footer = 'Use "/birthday set" to have your favorite character celebrate your birthday with you!'
                        if character == "None":
                            character = random.choice(characters)
                            footer = 'Use "/birthday set" to update your birthday with timezones & favorite character!'
                        icon_link = characters_dict[character]['icon']
                        webhook = await self.bot.fetch_webhook(v["Webhook ID"])
                        embed = discord.Embed(
                            description=f"{characters_dict[character]['line'].replace('USER', f'**{member.display_name}**')}",
                            color=discord.Colour.random(),
                        )
                        embed.set_footer(text=footer)
                        msg = await webhook.send(
                            content=f":birthday: Happy birthday to {member.mention}! Enjoy your special day!",
                            embed=embed,
                            username=character,
                            avatar_url=icon_link,
                            wait=True,
                        )
                        await msg.add_reaction("🎂")
                        
                        try:
                            if v["Create Birthday Thread"]:
                                await msg.create_thread(
                                    name=f"Wish {member.name} a Happy Birthday 🎉"
                                )
                        except Exception as e:
                            print(f"Unable to create thread for the birthday of {member.name} ({member.id}) in {server.name} ({server.id})\n{e}")
                        
                        try:
                            await member.add_roles(birthday_role)
                        except Exception as e:
                            print(f"Unable to add role {birthday_role.name} ({birthday_role.id}) to member {member.name} ({member.id}) in {server.name} ({server.id})\n{e}")
                            continue
                        
                        try:
                            button = discord.ui.Button(
                                style=discord.ButtonStyle.link,
                                label=f"Read {character}'s Message",
                                url=f"{msg.jump_url}",
                            )
                            view = discord.ui.View()
                            view.add_item(button)
                            await member.send(
                                f"Happy birthday, {member.mention}! **{server.name}** and its staff team wishes you a fantastic day. May your special day be as amazing as you are! 🎉🎂🥳\n\n*PS: **{character}** has something to say to you... :eyes:*",
                                view=view,
                            )
                        except Exception as e:
                            print(f"Cannot send happy birthday DM to member to member {member.name} ({member.id}) in {server.name} ({server.id})\n{e}")
                        
                        self._birthday_sent_cache[cache_key] = True
                    
                    elif (
                        utc_date_object.month == current_time.month
                        and utc_date_object.day == current_time.day
                    ):
                        pass # It's their birthday, so do nothing!

                    elif (
                        utc_date_object.month == current_time.month
                        and utc_date_object.day + 1 == current_time.day 
                        and utc_date_object.hour == current_time.hour
                    ):
                        if birthday_role is None:
                            continue

                        member = await server.fetch_member(value["User ID"])
                        if member is not None and birthday_role in member.roles:
                            try:
                                await member.remove_roles(birthday_role)
                            except Exception as e:
                                print(f"Unable to remove role {birthday_role.name} ({birthday_role.id}) from member {member.name} ({member.id}) in {server.name} ({server.id}) {e}")
                                continue

            keys_to_remove = [k for k in self._birthday_sent_cache if k[2] != minute_key]
            for k in keys_to_remove:
                del self._birthday_sent_cache[k]
            await asyncio.sleep(60)
        else:
            await asyncio.sleep(20)

    @birthday_task.before_loop
    async def before_birthday_task(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(BirthdayCog(bot))