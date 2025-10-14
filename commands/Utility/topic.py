import discord
import random
import datetime

from discord import app_commands
from discord.ext import commands
from firebase_admin import db

class Topic(commands.Cog):
  def __init__(self, bot: commands.Bot) -> None:
    self.bot = bot


  @app_commands.command(
    name = "topic",
    description = "Get a random Genshin topic to chat on"
  )
  @app_commands.guild_only()
  async def topic_get(
    self,
    interaction: discord.Interaction
  ) -> None:
    await interaction.response.defer()
    ref = db.reference("/Topics")
    topics = ref.get()
    key, val = random.choice(list(topics.items()))
    embed = discord.Embed(title=val["Topic Query"], color=0x00B0FF)
    embed.set_footer(text="You can always use \"/topic\" slash command again to get a new topic")
    await interaction.followup.send(embed=embed)

    
  # @app_commands.command(
  #   name = "add-topic",
  #   description = "Adds a topic to our bot's database"
  # )
  # @app_commands.describe(
  #   topic = "ONE topic at a time",
  # )
  # async def topic_add(
  #   self,
  #   interaction: discord.Interaction,
  #   topic: str
  # ) -> None:
  #   ref = db.reference("/Topics")
  #   topics = ref.get()
  #   for key, value in topics.items():
  #     if (value["Topic Query"] == topic):
  #       embed = discord.Embed(title="Topic already existed!", description=f'Surprisingly, the topic you suggested already existed in our database! Feel free to suggest other topics!', colour=0xFF0000)
  #       embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
  #       await interaction.response.send_message(embed=embed, ephemeral=True)
  #       raise Exception("Already existed!")

  #   data = {
  #       topic: {
  #         "Topic Query": topic,
  #         "Topic Suggester ID": interaction.user.id
  #       }
  #     }

  #   for key, value in data.items():
  #     ref.push().set(value)

  #   embed = discord.Embed(title="Topic successfully added!", description=f'The following topic has been added to our database:\n```{topic}```', colour=0x00FF00)
  #   embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
  #   await interaction.response.send_message(embed=embed)

    
  # @app_commands.command(
  #   name = "get-topics",
  #   description = "Gets all topics from our bot's database"
  # )
  # async def topic_add(
  #   self,
  #   interaction: discord.Interaction,
  # ) -> None:
  #   ref = db.reference("/Topics")
  #   topics = ref.get()
  #   string = ""
  #   for key, value in topics.items():
  #     string += value["Topic Query"] + "\n"
  #   f = open(f"./assets/allTopics.txt", "w")
  #   f.write(string)
  #   f.close()
  #   await interaction.response.send_message( file=discord.File(f"./assets/allTopics.txt"))
  

async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(Topic(bot))