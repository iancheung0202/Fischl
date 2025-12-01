import discord
import random
import datetime

from discord import app_commands
from discord.ext import commands
from firebase_admin import db
from shared.Tickets.tickets import generate
import discord.ui

class TopicAcceptRejectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green, custom_id="accept_topic")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != 692254240290242601:
            await interaction.response.send_message("Only the owner can do this.", ephemeral=True)
            return
        description = interaction.message.embeds[0].description
        lines = description.split('\n')
        suggester_mention = lines[0].split(': ')[1]
        suggester_id = int(suggester_mention.strip('<@>'))
        topic = lines[1].split(': ')[1]
        modal = TopicModal(topic, suggester_id, interaction.message)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.red, custom_id="reject_topic")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != 692254240290242601:
            await interaction.response.send_message("Only the owner can do this.", ephemeral=True)
            return
        description = interaction.message.embeds[0].description
        lines = description.split('\n')
        topic = lines[1].split(': ')[1]
        embed = discord.Embed(title="Topic Suggestion Rejected", description=f"Topic: {topic}", color=0xFF0000)
        await interaction.message.edit(embed=embed, view=None)
        await interaction.response.defer()

class TopicModal(discord.ui.Modal, title="Edit Topic"):
    def __init__(self, topic, suggester_id, message):
        super().__init__()
        self.topic = topic
        self.suggester_id = suggester_id
        self.message = message
        self.topic_input = discord.ui.TextInput(label="Topic", default=topic, style=discord.TextStyle.paragraph)
        self.add_item(self.topic_input)

    async def on_submit(self, interaction: discord.Interaction):
        edited_topic = self.topic_input.value
        ref = db.reference("/Topics")
        topics = ref.get()
        for key, value in topics.items():
            if value["Topic Query"] == edited_topic:
                await interaction.response.send_message("This topic already exists!", ephemeral=True)
                return
        data = {
            "Topic Query": edited_topic,
            "Topic Suggester ID": self.suggester_id
        }
        ref.push().set(data)
        embed = discord.Embed(title="Topic Suggestion Accepted", description=f"Added: {edited_topic}", color=0x00FF00)
        await self.message.edit(embed=embed, view=None)
        await interaction.response.send_message("Topic added!", ephemeral=True)

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
    embed.set_footer(text="🆕 Use \"/add-topic\" to suggest freshly-baked topics to our developer!")
    await interaction.followup.send(embed=embed)

    
  @app_commands.command(
    name = "add-topic",
    description = "Adds a topic to our bot's database"
  )
  @app_commands.describe(
    topic = "ONE topic at a time",
  )
  async def topic_add(
    self,
    interaction: discord.Interaction,
    topic: str
  ) -> None:
    channel = self.bot.get_channel(1026867655468126249)
    ref = db.reference("/Topics")
    topics = ref.get()
    all_topics = [v["Topic Query"] for v in topics.values()]
    all_topics_str = '\n'.join(all_topics)
    prompt = f"""Your task is to compare the new topic with the list of existing topics.
    Identify any topics (maximum 5) that are duplicates or very similar to the new topic (except the new topic itself).

    - Output a numbered list of similar topics, ordered from most similar to least similar.
    - If no similar topics are found, output exactly: "No similar topics found."
    - Do not include any extra commentary or headings.

    New topic:
    {topic}

    Existing topics:
    {all_topics_str}
    """
    similar = await generate(prompt)
    embed = discord.Embed(title="New Topic Suggestion", description=f"Suggested by: {interaction.user.mention}\nTopic: {topic}\n\nSimilar topics:\n{similar}", color=0xFFFF00)
    ping = "<@692254240290242601>"
    view = TopicAcceptRejectView()
    await channel.send(ping, embed=embed, view=view)
    await interaction.response.send_message(f":white_check_mark: Your topic suggestion has been sent for review!\n\n> {topic}")

    
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