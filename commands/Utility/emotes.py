import discord

from discord import app_commands
from discord.ext import commands

class PaginationView(discord.ui.View):
  def __init__(self, pages):
    super().__init__()
    self.page = 0
    self.pages = pages

  @discord.ui.button(emoji="<:fastbackward:1351972112696479824>", style=discord.ButtonStyle.blurple, custom_id="super_prev")
  async def super_prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
    self.page = 0
    embed = self.pages[self.page]
    embed.set_footer(text=f"Page {self.page + 1} of {len(self.pages)}")
    await interaction.response.edit_message(embed=embed)

  @discord.ui.button(emoji="<:backarrow:1351972111010369618>", style=discord.ButtonStyle.blurple, custom_id="prev")
  async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
    if self.page > 0:
      self.page -= 1
    else:
      self.page = len(self.pages) - 1
    embed = self.pages[self.page]
    embed.set_footer(text=f"Page {self.page + 1} of {len(self.pages)}")
    await interaction.response.edit_message(embed=embed)

  @discord.ui.button(emoji="<:rightarrow:1351972116819480616>", style=discord.ButtonStyle.blurple, custom_id="next")
  async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
    if self.page < len(self.pages) - 1:
      self.page += 1
    else:
      self.page = 0
    embed = self.pages[self.page]
    embed.set_footer(text=f"Page {self.page + 1} of {len(self.pages)}")
    await interaction.response.edit_message(embed=embed)

  @discord.ui.button(emoji="<:fastforward:1351972114433048719>", style=discord.ButtonStyle.blurple, custom_id="super_next")
  async def super_next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
    self.page = len(self.pages) - 1
    embed = self.pages[self.page]
    embed.set_footer(text=f"Page {self.page + 1} of {len(self.pages)}")
    await interaction.response.edit_message(embed=embed)

@app_commands.guild_only()
class Emote(commands.GroupCog, name="emotes"):
  def __init__(self, bot: commands.Bot) -> None:
    self.bot = bot
    super().__init__()

  @app_commands.command(
    name = "all",
    description = "Shows all the emojis in the server"
  )
  async def emote_all(
    self,
    interaction: discord.Interaction
  ) -> None:
    emojis = interaction.guild.emojis
    numOfEmoji = 1
    pages = []
    string = ""
    while numOfEmoji <= len(emojis):
      emoji = emojis[numOfEmoji - 1]
      if emoji.animated:
        string = f"{string}{emoji} `<a:{emoji.name}:{emoji.id}>`\n"
      else:
        string = f"{string}{emoji} `<:{emoji.name}:{emoji.id}>`\n"
      if numOfEmoji % 25 == 0 or numOfEmoji == len(emojis):
        pages.append(discord.Embed(title=f"Emotes in {interaction.guild.name}", description=string))
        string = ""
      numOfEmoji += 1
    x = 0
    embed = pages[x]
    embed.set_footer(text=f"Page {x + 1} of {len(pages)}")
    await interaction.response.send_message(embed=pages[0], view=PaginationView(pages))


async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(Emote(bot))