import discord
import datetime
from discord import app_commands
from discord.ext import commands

def rgb_to_hex(r, g, b):
    return "#{:02X}{:02X}{:02X}".format(r, g, b)

class modal(discord.ui.Modal):
    def __init__(self, msgcontent, embedtitlehere, embeddescription, embedcolor, embedimage, message: discord.Message, title="Edit Embed Message"):
        super().__init__(title=title)
        self.msgcontent = msgcontent
        self.embedtitlehere = embedtitlehere
        self.embeddescription = embeddescription
        self.embedcolor = embedcolor
        self.embedimage = embedimage
        self.message = message 

        self.msg = discord.ui.TextInput(
            label="Normal message content",
            style=discord.TextStyle.paragraph,
            placeholder="",
            max_length=2000,
            required=False,
            default=self.msgcontent
        )
        self.add_item(self.msg)

        self.embedtitle = discord.ui.TextInput(
            label="Title of the embed",
            style=discord.TextStyle.paragraph,
            placeholder="",
            max_length=256,
            required=False,
            default=self.embedtitlehere
        )
        self.add_item(self.embedtitle)

        self.description = discord.ui.TextInput(
            label="Description of the embed",
            style=discord.TextStyle.paragraph,
            placeholder="",
            max_length=4000,
            required=False,
            default=self.embeddescription
        )
        self.add_item(self.description)

        self.color = discord.ui.TextInput(
            label="Color of the embed",
            style=discord.TextStyle.short,
            placeholder="Use hex code (e.g. #ff0000)",
            max_length=7,
            required=False,
            default=rgb_to_hex(self.embedcolor.r, self.embedcolor.g, self.embedcolor.b) if self.embedcolor else None
        )
        self.add_item(self.color)

        self.image = discord.ui.TextInput(
            label="Big image of the embed",
            style=discord.TextStyle.paragraph,
            placeholder="Put a permanent image link",
            required=False,
            default=self.embedimage
        )
        self.add_item(self.image)

    async def on_submit(self, interaction: discord.Interaction):
        msg_content = self.msg.value.strip()
        tit = self.embedtitle.value.strip()
        desc = self.description.value.strip()
        color_input = self.color.value.strip()
        image_url = self.image.value.strip()

        color = discord.Color.blurple()
        if color_input:
            hex_code = color_input.lstrip('#')
            if len(hex_code) == 6:
                try:
                    color = discord.Color(int(hex_code, 16))
                except ValueError:
                    pass  

        has_embed = tit or desc or image_url
        embed = None
        if has_embed:
            embed = discord.Embed(
                title=tit or None,
                description=desc or None,
                color=color
            )
            if image_url:
                embed.set_image(url=image_url)
            if not any([embed.title, embed.description, embed.image, embed.thumbnail, embed.fields, embed.author, embed.footer]):
                embed = None

        await self.message.edit(content=msg_content or None, embed=embed)

        embed_confirm = discord.Embed(
            description=f'**Custom embed message edited**\n*[Jump to Message]({self.message.jump_url})*',
            colour=0x00FF00,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        await interaction.response.send_message(embed=embed_confirm, ephemeral=True)

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
    async def editembed(
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
        msg = await (thread or channel).fetch_message(id)

        title = msg.embeds[0].title if msg.embeds else None
        description = msg.embeds[0].description if msg.embeds else None
        color = msg.embeds[0].color if msg.embeds else None
        image = msg.embeds[0].image.url if msg.embeds and msg.embeds[0].image else None
        msgcontent = msg.content

        await interaction.response.send_modal(
            modal(
                msgcontent=msgcontent,
                embedtitlehere=title,
                embeddescription=description,
                embedcolor=color,
                embedimage=image,
                message=msg
            )
        )

    @editembed.error
    async def editembed_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)

@app_commands.context_menu(name="Edit Embed")
@app_commands.checks.has_permissions(administrator=True)
async def edit_embed_context_menu(interaction: discord.Interaction, message: discord.Message):
    if message.author != interaction.client.user:
        return await interaction.response.send_message(
            "❌ You can only edit messages sent by this bot!",
            ephemeral=True
        )

    embed = message.embeds[0] if message.embeds else None
    title = embed.title if embed else None
    description = embed.description if embed else None
    color = embed.color if embed else None
    image = embed.image.url if embed and embed.image else None

    await interaction.response.send_modal(
        modal(
            msgcontent=message.content,
            embedtitlehere=title,
            embeddescription=description,
            embedcolor=color,
            embedimage=image,
            message=message
        )
    )

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EditEmbed(bot))
    bot.tree.add_command(edit_embed_context_menu)
