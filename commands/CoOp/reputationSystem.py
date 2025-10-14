import discord
import pandas as pd

from discord.ext import commands
from firebase_admin import db

class ReputationSystem(commands.Cog): 
    def __init__(self, bot):
        self.client = bot
    
    @commands.Cog.listener() 
    async def on_message(self, message):
        
        if message.author == self.client.user or message.author.bot == True: 
            return

        if message.guild.id == 717029019270381578:
            return

        if message.content.lower().startswith("-rep"):
            ref = db.reference("/Global Reps System")
            coop = ref.get()
            enabled = False
            if coop:
                for key, value in coop.items():
                    if (value["Server ID"] == message.guild.id):
                        enabled = True
                        break
            if not enabled:
                return
            try:
                id = int(message.content.split(" ")[1].replace("<@", "").replace(">", ""))
                username = (await message.guild.fetch_member(id)).name
            except Exception:
                id = message.author.id
                username = message.author.name

            ref = db.reference("/Global Reps")
            reps = ref.get() or {}

            ogrep = 0
            for key, val in reps.items():
                if id in val['Users']:
                    ogrep = val['Users'][id]
                    break

            await message.channel.send(f"**{username}**: **{ogrep}** rep")

        elif message.content.lower().startswith("-toprep"):
            ref = db.reference("/Global Reps System")
            coop = ref.get()
            enabled = False
            if coop:
                for key, value in coop.items():
                    if (value["Server ID"] == message.guild.id):
                        enabled = True
                        break
            if not enabled:
                return
            try:
                num = int(message.content.split(" ")[1])
                num = min(max(num, 1), 50)  # Ensures the number is between 1 and 50
            except Exception:
                num = 10

            ref = db.reference("/Global Reps")
            reps = ref.get() or {}

            list_data = []
            for key, val in reps.items():
                for user_id, points in val["Users"].items():
                    list_data.append({"user_id": user_id, "points": points})

            if not list_data:
                await message.channel.send("No reputation data found.")
                return

            df = pd.DataFrame(list_data)
            df_sorted = df.sort_values(by="points", ascending=False)
            top_users = df_sorted.head(num)

            desc = ""
            for count, (_, row) in enumerate(top_users.iterrows(), 1):
                user = await message.guild.fetch_member(row["user_id"])
                if user:
                    desc += f"{count}. **{user.name}** `({user.id})` - **{row['points']}**\n"

            embed = discord.Embed(title=f"Global Reputation Leaderboard - Top {num}", description=desc, color=0xEB7660)
            await message.channel.send(embed=embed)

        elif message.content.lower().startswith("-giverep"):
            ref = db.reference("/Global Reps System")
            coop = ref.get()
            enabled = False
            if coop:
                for key, value in coop.items():
                    if (value["Server ID"] == message.guild.id):
                        enabled = True
                        max_rep = value["Max Rep"]
                        roles = value["Roles"]
                        break
            if not enabled:
                return
            parts = message.content.split(" ")
            if len(parts) < 3:
                await message.reply("Command Usage: `-giverep @user amount`")
                return

            try:
                id = int(parts[1].replace("<@", "").replace(">", ""))
                rep = int(parts[2])
            except ValueError:
                await message.reply("<:no:1036810470860013639> Invalid format. Use `-giverep @user amount`")
                return

            if rep > max_rep:
                await message.reply(f"<:no:1036810470860013639> You can't give more than {max_rep} reps at once.")
                return
            elif id == message.author.id:
                await message.reply("<:no:1036810470860013639> You can't give yourself reps!")
                return
            elif rep <= 0:
                await message.reply("<:no:1036810470860013639> You must give at least 1 rep.")
                return

            username = (await message.guild.fetch_member(id)).name
            guild_id = str(message.guild.id)

            ref = db.reference("/Global Reps")
            reps = ref.get() or {}

            if guild_id not in reps:
                reps[guild_id] = {"Users": {}}

            ogrep = reps[guild_id]["Users"].get(id, 0)
            newrep = ogrep + rep
            reps[guild_id]["Users"][id] = newrep
            ref.set(reps)

            unlocked_roles = []
            embeds = []
            for role_id, cost in roles.items():
                if ogrep <= cost <= newrep:
                    unlocked_roles.append(role_id)
            for role_id in unlocked_roles:
                user = await message.guild.fetch_member(id)
                await user.add_roles(message.guild.get_role(int(role_id)))
                embeds.append(discord.Embed(description=f"**{username}** just earned a new role: **{message.guild.get_role(int(role_id)).mention}**", color=discord.Color.green()))
            await message.channel.send(f"<:yes:1036811164891480194> Gave `{rep}` Rep to **{username}** (current - `{newrep}`)", embeds=embeds)


async def setup(bot): 
  await bot.add_cog(ReputationSystem(bot))