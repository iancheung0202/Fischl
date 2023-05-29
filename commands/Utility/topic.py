import discord, firebase_admin, random, datetime
from discord import app_commands
from discord.ext import commands
from firebase_admin import db
from ai import simple_get

class Topic(commands.Cog):
  def __init__(self, bot: commands.Bot) -> None:
    self.bot = bot

  @app_commands.command(
    name = "topic",
    description = "Get a random Genshin topic to chat on"
  )
  async def topic_get(
    self,
    interaction: discord.Interaction
  ) -> None:
    await interaction.response.defer()
    # try:
    #   returned_val = simple_get("Write a topic or an open-ended question for the chat to talk about in the Genshin Impact Discord servers. The topic should be related to anything in Genshin Impact, such as individual characters, a category of characters, vision, places, maps, weapons, bosses, nations, game modes, what-if questions, co-op, etc. Then write an explanation or elaboration on the question you wrote separated by |")
    #   question = returned_val.split("|")[0]
    #   explanation = returned_val.split("|")[1]
    #   color = 0x00B0FF
    # except Exception:
    #   question = "Service Unavailable"
    #   explanation = "We are currently experiencing a high volume of traffic and is unable to process your request at this time. Please try again.\n\nError Code: `503`"
    #   color = 0xFF0000
    ref = db.reference("/Topics")
    topics = ref.get()
    key, val = random.choice(list(topics.items()))
    embed = discord.Embed(title=val["Topic Query"], color=0x00B0FF)
    # embed = discord.Embed(title=question, description=explanation, color=color)
    embed.set_footer(text="You can always use \"/topic\" slash command again to get a new topic")
    await interaction.followup.send(embed=embed)

    
  # @app_commands.command(
  #   name = "add",
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
  #       embed.timestamp = datetime.datetime.utcnow()
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
  #   embed.timestamp = datetime.datetime.utcnow()
  #   await interaction.response.send_message(embed=embed)
  

async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(Topic(bot))