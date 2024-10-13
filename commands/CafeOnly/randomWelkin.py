import discord, firebase_admin, datetime, asyncio, time, emoji, random, os, string
from firebase_admin import db
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View

class RandomWelkin(commands.Cog): 
  def __init__(self, bot):
    self.client = bot
  
  @commands.Cog.listener() 
  async def on_message(self, message):
    if message.author == self.client.user or message.author.bot == True: 
        return
    
    eventChannelIDs = [1104212482312122388, 1083850546676498462, 1104556774423547964, 1181237921756487760, 1083737514944254023, 1083788035864404039, 1083738044173139999, 1196982873287311501, 1237653103772172288, 1205677453922799668, 1196990772088668160, 1196988766972281003, 1181785348452384768, 1196982949783011338]
    #eventChannelIDs = [1083650021351751700]
    if (message.channel.id in eventChannelIDs and message.id % 1200 == 0):
        ref = db.reference("/Random Welkin")
        randomwelkin = ref.get()
        count = 0
        ogpeople = []
        try:
          for key, val in randomwelkin.items():
            if val['Server ID'] == message.guild.id:
              count = val['Count']
              ogpeople = val['People']
              db.reference('/Random Welkin').child(key).delete()
              break
        except Exception as e:
          print(e)
        count += 1
        people = ogpeople.copy()
        people.append(message.author.id)
        data = {
          "Random Welkin": {
            "Server ID": message.guild.id,
            "Count": count,
            "People": people
          }
        }

        for key, value in data.items():
          ref.push().set(value)
        if message.author.id in ogpeople:
          raise Exception("Already won welkin once")
        if count <= 4:
          ian = message.guild.get_member(692254240290242601)
          await ian.send(message.jump_url)
          await message.add_reaction("👀")
          await message.reply(embed=discord.Embed(title="🎉 Congratulations, you won a x1 welkin just by chatting. 🎉", description="<a:moneydance:1227425759077859359> You are one of the lucky few!!! **You must create a ticket in <#1083745974402420846> within 30 minutes indicating that you wish to claim the prize.** Your chance will be automatically forfeited if you did not create a ticket within 30 mins.\n\nTo successfully claim your prize, screenshot **this message** and send it in the ticket.", color=discord.Colour.random()), content=f"**Winner:** {message.author.mention} `({message.author.id})`\n**Reference Code:** 0453-5414")
          await ian.send(f"{message.id}")
        

async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(RandomWelkin(bot))