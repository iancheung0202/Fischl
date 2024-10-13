import discord
import time
import datetime
import aiohttp
from discord import app_commands
from discord.ext import commands

def rgb_to_hex(r, g, b):
    hex_code = "#{:02X}{:02X}{:02X}".format(r, g, b)
    return hex_code

class modal(discord.ui.Modal):
    def __init__(self, msgcontent, embedtitlehere, embeddescription, embedcolor, embedimage, title="Edit Embed Message"):
        super().__init__(title="Edit Embed Message")
        #self.msgidhere = msgidhere
        self.msgcontent = msgcontent
        self.embedtitlehere = embedtitlehere
        self.embeddescription = embeddescription
        self.embedcolor = embedcolor
        self.embedimage = embedimage
        self.msgid = int(title.split("-")[1].strip())
        
        #self.msgid = discord.ui.TextInput(label="Message ID", style=discord.TextStyle.paragraph, placeholder="Enter the 19-digit message ID", max_length=19, required=False, default=self.msgidhere)
        #self.add_item(self.msgid)
        
        self.msg = discord.ui.TextInput(label="Normal message content", style=discord.TextStyle.paragraph, placeholder="", max_length=2000, required=False, default=self.msgcontent)
        self.add_item(self.msg)
        
        self.embedtitle = discord.ui.TextInput(label="Title of the embed", style=discord.TextStyle.paragraph, placeholder="", max_length=256, required=False, default=self.embedtitlehere)
        self.add_item(self.embedtitle)
        
        self.description = discord.ui.TextInput(label="Description of the embed", style=discord.TextStyle.paragraph, placeholder="", max_length=4000, required=False, default=self.embeddescription)
        self.add_item(self.description)
        
        self.color = discord.ui.TextInput(label="Color of the embed", style=discord.TextStyle.short, placeholder="Use hex code (e.g. #ff0000)", max_length=7, required=False, default=rgb_to_hex(self.embedcolor.r, self.embedcolor.g, self.embedcolor.b))
        self.add_item(self.color)
        
        self.image = discord.ui.TextInput(label="Big image of the embed", style=discord.TextStyle.paragraph, placeholder="Put a permanent image link", required=False, default=self.embedimage)
        self.add_item(self.image)

    async def on_submit(self, interaction: discord.Interaction):
        tit = str(self.embedtitle)
        desc = str(self.description)
        image = str(self.image)
        color = discord.Color.blurple()
        if str(self.color) != "":
            hex = str(self.color)
            if hex.startswith('#'):
                hex = hex[1:]
            async with aiohttp.ClientSession() as session:
                async with session.get('https://www.thecolorapi.com/id', params={"hex": hex}) as server:
                    if server.status == 200:
                        js = await server.json()
                        try:
                            color = discord.Color(int(f"0x{js['hex']['clean']}", 16))
                        except:
                            color = discord.Color.blurple()

        if self.embedtitle == None and self.description == None and self.embedimage == None:
            embed = None
        else:
            embed = discord.Embed(title=tit, description=desc, color=color)
            if str(image) != "":
              embed.set_image(url=image)
        message = await interaction.channel.fetch_message(int(str(self.msgid)))
        await message.edit(content=str(self.msg), embed=embed)

        embed = discord.Embed(title="", description=f'**Custom embed message edited**\n*[Jump to Message]({message.jump_url})*', colour=0x00FF00)
        embed.timestamp = datetime.datetime.utcnow()
        await interaction.response.send_message(embed=embed, ephemeral=True)

class EditEmbed(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="editembed",
        description="Edits a custom embed message"
    )
    @app_commands.describe(
        id="The message ID of the embed",
        channel="The Discord text channel where the embed is located",
        thread="(Optional & Overrides) The thread where the embed is located",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def embed(
            self,
            interaction: discord.Interaction,
            id: str,
        	channel: discord.TextChannel,
            thread: discord.Thread = None
    ) -> None:
        if "-" in id:
            id = int(id.split("-")[1])
        else:
            id = int(id)
        if thread == None:
          msg = await channel.fetch_message(id)
        else:
          msg = await thread.fetch_message(id)

        if len(msg.embeds) == 0:
            await interaction.response.send_message(f"Your message doesn't have any embeds!", ephemeral=True)
        else:
            title = description = color = msgcontent = msgid = image = None
            title = msg.embeds[0].title
            description = msg.embeds[0].description
            color = msg.embeds[0].color
            image = msg.embeds[0].image.url
            msgcontent = msg.content
            msgid = msg.id
                
        await interaction.response.send_modal(modal(msgcontent=msgcontent, embedtitlehere=title, embeddescription=description, embedcolor=color, embedimage=image, title=f"Edit Embed Message - {msgid}"))
      


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EditEmbed(bot))
