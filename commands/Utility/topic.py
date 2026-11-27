import discord
import discord.ui
from discord import app_commands
from discord.ext import commands

from commands.Utility import topicStore as store
from shared.Tickets.tickets import generate

OWNER = 692254240290242601  # the only one who may accept or reject a topic
REVIEW_CHANNEL = 1026867655468126249  # where suggestions wait for the owner


class TopicAcceptRejectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Accept", style=discord.ButtonStyle.green, custom_id="accept_topic"
    )
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Opens the suggestion for the owner to edit before it is saved."""
        if interaction.user.id != OWNER:
            await interaction.response.send_message(
                "Only the owner can do this.", ephemeral=True
            )
            return
        description = interaction.message.embeds[0].description
        lines = description.split("\n")
        suggester_mention = lines[0].split(": ")[1]
        suggester_id = int(suggester_mention.strip("<@>"))
        topic = lines[1].split(": ")[1]
        modal = TopicModal(topic, suggester_id, interaction.message)
        await interaction.response.send_modal(modal)

    @discord.ui.button(
        label="Reject", style=discord.ButtonStyle.red, custom_id="reject_topic"
    )
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Marks the suggestion as rejected."""
        if interaction.user.id != OWNER:
            await interaction.response.send_message(
                "Only the owner can do this.", ephemeral=True
            )
            return
        description = interaction.message.embeds[0].description
        lines = description.split("\n")
        topic = lines[1].split(": ")[1]
        embed = discord.Embed(
            title="Topic Suggestion Rejected",
            description=f"Topic: {topic}",
            color=0xFF0000,
        )
        await interaction.message.edit(embed=embed, view=None)
        await interaction.response.defer()


class TopicModal(discord.ui.Modal, title="Edit Topic"):
    def __init__(self, topic, suggester_id, message):
        super().__init__()
        self.topic = topic
        self.suggester_id = suggester_id
        self.message = message
        self.topic_input = discord.ui.TextInput(
            label="Topic", default=topic, style=discord.TextStyle.paragraph
        )
        self.add_item(self.topic_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Saves the edited topic unless that exact text is already saved."""
        edited_topic = self.topic_input.value
        pool = interaction.client.pool
        if await store.has(pool, edited_topic):
            await interaction.response.send_message(
                "This topic already exists!", ephemeral=True
            )
            return
        await store.add(pool, edited_topic, self.suggester_id)
        embed = discord.Embed(
            title="Topic Suggestion Accepted",
            description=f"Added: {edited_topic}",
            color=0x00FF00,
        )
        await self.message.edit(embed=embed, view=None)
        await interaction.response.send_message("Topic added!", ephemeral=True)


class Topic(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self):
        """Makes the table before the first command."""
        await store.create(self.bot.pool)

    @app_commands.command(
        name="topic", description="Get a random Genshin topic to chat on"
    )
    @app_commands.guild_only()
    async def topic_get(self, interaction: discord.Interaction) -> None:
        """Posts one random topic."""
        await interaction.response.defer()
        embed = discord.Embed(title=await store.pick(self.bot.pool), color=0x00B0FF)
        embed.set_footer(
            text='🆕 Use "/add-topic" to suggest freshly-baked topics to our developer!'
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="add-topic", description="Adds a topic to our bot's database"
    )
    @app_commands.describe(
        topic="ONE topic at a time",
    )
    async def topic_add(self, interaction: discord.Interaction, topic: str) -> None:
        """Sends a suggestion, with the saved topics most like it, to the owner."""
        channel = self.bot.get_channel(REVIEW_CHANNEL)
        all_topics_str = "\n".join(await store.queries(self.bot.pool))
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
        embed = discord.Embed(
            title="New Topic Suggestion",
            description=f"Suggested by: {interaction.user.mention}\nTopic: {topic}\n\nSimilar topics:\n{similar}",
            color=0xFFFF00,
        )
        ping = f"<@{OWNER}>"
        view = TopicAcceptRejectView()
        await channel.send(ping, embed=embed, view=view)
        await interaction.response.send_message(
            f":white_check_mark: Your topic suggestion has been sent for review!\n\n> {topic}"
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Topic(bot))
