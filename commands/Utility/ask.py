import discord, os, openai
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View
from ai import request

class AskAI(commands.Cog):
  def __init__(self, bot: commands.Bot) -> None:
    self.bot = bot

  @app_commands.command(
    name = "ask",
    description = "Asks the bot anything from writing a story, an essay, to answering complicated questions"
  )
  @app_commands.describe(
    query = "The query to be passed to the bot",
  )
  async def asks_ai(
    self,
    interaction: discord.Interaction,
    query: str
  ) -> None:
    await interaction.response.defer(thinking=True, ephemeral=True)
    try:
    
      answer = request(query,interaction.guild.id)
      await interaction.followup.send(embed=discord.Embed(title=query, description=answer))
    except Exception:
      await interaction.followup.send(embed=discord.Embed(title="RateLimitError", description="The bot has exceeded its current quota, so this command is unavailable as of now.", color=discord.Color.red()))
      
    

async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(AskAI(bot))