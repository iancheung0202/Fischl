import discord, firebase_admin, datetime, asyncio, time, emoji
from firebase_admin import db
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View

class FAQ(commands.GroupCog, name="faq"):
  def __init__(self, bot: commands.Bot) -> None:
    self.bot = bot
    super().__init__()

  @app_commands.command(
    name = "add",
    description = "Add a FAQ"
  )
  @app_commands.describe(
    question = 'The frequently asked question',
    answer = "The answer to that FAQ",
  )
  @app_commands.checks.has_permissions(administrator=True)
  async def faq_add(
    self,
    interaction: discord.Interaction,
    question: str,
    answer: str
  ) -> None:

    ref = db.reference("/FAQ")
    faqs = ref.get()

    # for key, val in faqs.items():
    #   if val['Server ID'] == interaction.guild.id and val["Question"] == question:
    #     db.reference('/FAQ').child(key).delete()
    #     break
  
    data = 0
  
    # for key, val in faqs.items():
    #   if val['Server ID'] == interaction.guild_id:
    #     data += 1


    if data < 25:
      data = {
        interaction.guild.id: {
          "Server ID": interaction.guild.id,
          "Question": question,
          "Answer": answer
        }
      }
  
      for key, value in data.items():
        ref.push().set(value)
  
      embed = discord.Embed(title="FAQ added!", description=f'Q: {question}\n\nA: {answer}', colour=0x00FF00)
      embed.timestamp = datetime.datetime.utcnow()
      await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
      embed = discord.Embed(title="Server Limit Exceeded!", description=f'Unfortunately, a server can only have 25 FAQs at a time due to overloading issues. This FAQ is not added as a result. ', colour=0xFF0000)
      embed.timestamp = datetime.datetime.utcnow()
      await interaction.response.send_message(embed=embed, ephemeral=True)

  @app_commands.command(
    name = "list",
    description = "List all the FAQs of the server"
  )
  @app_commands.checks.has_permissions(administrator=True)
  async def sticky_list(
    self,
    interaction: discord.Interaction
  ) -> None:
    ref = db.reference("/FAQ")
    faqs = ref.get()
  
    data = ""
  
    for key, val in faqs.items():
      if val['Server ID'] == interaction.guild_id:
        data = f"{data}Q: {val['Question']}\nA: {val['Answer']}\n\n"  
    list = []

    def function(data):
        if len(data)>0:
            a = 4096
            list.append(data[:a])
            function(data[a:])
        else:
            pass
    
    function(data)
    for item in list:
      if list[0] == item:
        embed = discord.Embed(title="List of FAQs", description=item, colour=0x00FF00)
        await interaction.response.send_message(embed=embed, ephemeral=True)
      else:
        embed = discord.Embed(title="", description=item, colour=0x00FF00)
        await interaction.followup.send(embed=embed, ephemeral=True)
    

async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(FAQ(bot))