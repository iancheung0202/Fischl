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
        minutes_to_test = [0, 15, 30, 45]
        if current_time.minute in minutes_to_test:
            print(f"🎂 Running birthday check...")
            ref = db.reference("/Birthday")
            bday = ref.get()
            ref2 = db.reference("/Birthday System")
            bs = ref2.get()
            minute_key = current_time.strftime("%Y%m%d%H%M")
            
            count_1 = 0
            for key, value in bday.items():
                count_2 = 0
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
                    try:
                        utc_date_object = utc_date_object.replace(year=current_time.year)
                    except Exception:
                        pass
                    
                    cache_key = (value["User ID"], v["Server ID"], minute_key)
                    if cache_key in self._birthday_sent_cache:
                        continue
                    
                    if (
                        utc_date_object.month == current_time.month
                        and utc_date_object.day == current_time.day
                        and utc_date_object.hour == current_time.hour
                        and utc_date_object.minute == current_time.minute
                    ):
                        # It's their birthday!
                        try:
                            member = await server.fetch_member(value["User ID"])
                        except discord.NotFound:
                            # print(f"Member {value['User ID']} not found in server {server.id}, skipping birthday send.")
                            continue
                        print(f"Successfully fetched {member} for birthday send in server {server.id}")
                        
                        character = value["Fav Character"]
                        footer = 'Use "/birthday set" to have your favorite character celebrate your birthday with you!'
                        if character == "None":
                            character = random.choice(characters)
                            footer = 'Use "/birthday set" to update your birthday with timezones & favorite character!'
                        icon_link = characters_dict[character]['icon']
                        try:
                            webhook = await self.bot.fetch_webhook(v["Webhook ID"])
                        except Exception as e:
                            print(f"Unable to fetch webhook {v.get('Webhook ID')}: {e}")
                            webhook = None

                        embed = discord.Embed(
                            description=f"{characters_dict[character]['line'].replace('USER', f'**{member.display_name}**')}",
                            color=discord.Colour.random(),
                        )
                        embed.set_footer(text=footer)

                        msg = None
                        if webhook is None:
                            print(f"No webhook available for server {server.id}, skipping send.")
                        else:
                            try:
                                sent = await webhook.send(
                                    content=f":birthday: Happy birthday to {member.mention}! Enjoy your special day!",
                                    embed=embed,
                                    username=character,
                                    avatar_url=icon_link,
                                    wait=True,
                                )
                                msg = sent
                                if msg is None:
                                    print("Webhook.send returned None (no message object). Reaction/thread may not be possible.")
                                else:
                                    try:
                                        await msg.add_reaction("🎂")
                                    except Exception as e:
                                        print(f"Could not add reaction to webhook message: {e}")
                            except Exception as e:
                                print(f"Failed to send webhook message in {server.name} ({server.id}): {e}")
                        
                        try:
                            if v["Create Birthday Thread"]:
                                if msg is not None:
                                    try:
                                        await msg.create_thread(
                                            name=f"Wish {member.name} a Happy Birthday 🎉"
                                        )
                                    except Exception as e:
                                        print(f"Unable to create thread (message exists but thread creation failed): {e}")
                                else:
                                    print("Skipping thread creation because message object is not available from webhook.send().")
                        except Exception as e:
                            print(f"Unable to create thread for the birthday of {member.name} ({member.id}) in {server.name} ({server.id})\n{e}")
                        
                        try:
                            if birthday_role is None:
                                print(f"Birthday role not found in server {server.id}")
                                continue
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
                            embed = discord.Embed(
                                title="Happy Birthday! 🎉🎂🥳",
                                description=f"Happy birthday, {member.mention}! **{server.name}** and its staff team wishes you a fantastic day. May your special day be as amazing as you are!\n\n*PS: **{character}** has something to say to you... :eyes:*",
                                color=discord.Colour.random(),
                            )
                            embed.set_thumbnail(url=icon_link)
                            embed.set_footer(text=f"You received this DM because you've set your birthday and {server.name} has birthday notifications enabled!")
                            await member.send(
                                embed=embed,
                                view=view,
                            )
                        except Exception as e:
                            print(f"Cannot send happy birthday DM to member to member {member.name} ({member.id}) in {server.name} ({server.id})\n{e}")
                        
                        self._birthday_sent_cache[cache_key] = True
                    
                    elif (
                        utc_date_object.month == current_time.month
                        and utc_date_object.day == current_time.day
                    ):
                        pass # It's their birthday right now, so do nothing!

                    elif (
                        utc_date_object.month == current_time.month
                        and utc_date_object.day + 1 == current_time.day 
                        and utc_date_object.hour == current_time.hour
                    ):
                        # It's the day after their birthday, remove the role
                        if birthday_role is None:
                            print(f"Birthday role not found in server {server.id}")
                            continue

                        try:
                            member = await server.fetch_member(value["User ID"])
                        except discord.NotFound:
                            # print(f"Member {value['User ID']} not found in server {server.id}, cannot remove birthday role.")
                            continue
                        if birthday_role in member.roles:
                            try:
                                await member.remove_roles(birthday_role)
                            except Exception as e:
                                print(f"Unable to remove role {birthday_role.name} ({birthday_role.id}) from member {member.name} ({member.id}) in {server.name} ({server.id}) {e}")
                                continue
                    count_2 += 1
                count_1 += 1
            print(f"Processed {count_1} users with birthdays.")

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