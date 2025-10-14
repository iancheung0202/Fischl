import discord, firebase_admin, datetime, asyncio, time, emoji, aiohttp
from firebase_admin import db
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View
from PIL import Image, ImageEnhance
from commands.Welcome.createWelcomeMsg import createWelcomeMsg


def word(n):
    return str(n) + (
        "th" if 4 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    )


def script(string, user, guild):
    if "{mention}" in string:
        string = string.replace("{mention}", f"{user.mention}")
    if "{server}" in string:
        string = string.replace("{server}", f"{guild.name}")
    if "{user}" in string:
        string = string.replace("{user}", f"{user.name}")
    if "{count}" in string:
        string = string.replace("{count}", f"{guild.member_count}")
    if "{count-th}" in string:
        string = string.replace("{count-th}", f"{word(guild.member_count)}")
    return string


class embed_modal(discord.ui.Modal, title="Setup Embed Welcome Message"):

    msg = discord.ui.TextInput(
        label="Normal message content",
        style=discord.TextStyle.paragraph,
        placeholder="Visit bit.ly/fischlvariables for all dynamic variables",
        max_length=2000,
        required=False,
    )

    embedtitle = discord.ui.TextInput(
        label="Title of the embed",
        style=discord.TextStyle.paragraph,
        placeholder="Visit bit.ly/fischlvariables for all dynamic variables",
        max_length=256,
        required=False,
    )

    description = discord.ui.TextInput(
        label="Description of the embed",
        style=discord.TextStyle.paragraph,
        placeholder="Visit bit.ly/fischlvariables for all dynamic variables",
        max_length=4000,
        required=False,
    )

    color = discord.ui.TextInput(
        label="Color of the embed",
        style=discord.TextStyle.short,
        placeholder="Use hex code (e.g. #ff0000)",
        max_length=7,
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction):

        ref = db.reference("/Welcome Content")
        welcome = ref.get()

        for key, val in welcome.items():
            if val["Server ID"] == interaction.guild.id:
                db.reference("/Welcome Content").child(key).delete()
                break

        data = {
            interaction.guild.id: {
                "Server ID": interaction.guild.id,
                "Message Content": self.msg.value,
                "Title": self.embedtitle.value,
                "Description": self.description.value,
                "Color": self.color.value,
            }
        }

        for key, value in data.items():
            ref.push().set(value)

        ref = db.reference("/Welcome")
        welcome = ref.get()

        for key, val in welcome.items():
            if val["Server ID"] == interaction.guild.id:
                welcomeChannel = val["Welcome Channel ID"]
                break

        embed = discord.Embed(
            title="<:yes:1036811164891480194> Welcome message enabled!",
            description=f"Congratulations! Now the bot will send a welcome message to <#{welcomeChannel}> every time a new member joins the server!\n\n**To view a sample welcome message, use </welcome sample:1043590008667385876>.**",
            colour=0x00FF00,
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await interaction.response.send_message(embed=embed, ephemeral=True)


@app_commands.guild_only()
class Welcome(commands.GroupCog, name="welcome"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(
        name="setup", description="Initalize welcome function in the server"
    )
    @app_commands.describe(
        welcome_channel="The channel to send welcome messages",
        welcome_image_background="The background of every welcome image (only if you wish to enable welcome images)",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_setup(
        self,
        interaction: discord.Interaction,
        welcome_channel: discord.TextChannel,
        welcome_image_background: discord.Attachment = None,
    ) -> None:
        welcomeImageEnabled = False
        if welcome_image_background is not None:
            path = f"./assets/Welcome Image Background/{interaction.guild.id}.png"
            await welcome_image_background.save(path)
            image = Image.open(path)
            width = image.size[0]
            height = image.size[1]
            aspect = width / float(height)
            ideal_width = 1024
            ideal_height = 576
            ideal_aspect = ideal_width / float(ideal_height)
            if aspect > ideal_aspect:
                new_width = int(ideal_aspect * height)
                offset = (width - new_width) / 2
                resize = (offset, 0, width - offset, height)
            else:
                new_height = int(width / ideal_aspect)
                offset = (height - new_height) / 2
                resize = (0, offset, width, height - offset)
            thumb = image.crop(resize).resize(
                (ideal_width, ideal_height), Image.LANCZOS
            )
            thumb.save(path)
            image = Image.open(path)
            enhancer = ImageEnhance.Brightness(image)
            im_output = enhancer.enhance(0.6)
            im_output.save(path)
            welcomeImageEnabled = True

        await interaction.response.send_modal(embed_modal())

        ref = db.reference("/Welcome")
        welcome = ref.get()

        for key, val in welcome.items():
            if val["Server ID"] == interaction.guild.id:
                db.reference("/Welcome").child(key).delete()
                break

        data = {
            interaction.guild.id: {
                "Server ID": interaction.guild.id,
                "Welcome Channel ID": welcome_channel.id,
                "Welcome Image Enabled": welcomeImageEnabled,
            }
        }

        for key, value in data.items():
            ref.push().set(value)
    @welcome_setup.error
    async def welcome_setup_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)

    @app_commands.command(
        name="disable", description="Disable welcome function in the server"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_disable(self, interaction: discord.Interaction) -> None:

        ref = db.reference("/Welcome")
        welcome = ref.get()

        found = False

        for key, val in welcome.items():
            if val["Server ID"] == interaction.guild.id:
                db.reference("/Welcome").child(key).delete()
                found = True
                break

        ref2 = db.reference("/Welcome Content")
        welcomecontent = ref2.get()

        for key, val in welcomecontent.items():
            if val["Server ID"] == interaction.guild.id:
                db.reference("/Welcome Content").child(key).delete()
                found = True
                break

        if found:
            embed = discord.Embed(
                title="Welcome message disabled!",
                description=f"Sorry to see you go, but if you change your mind at anytime, use </welcome setup:1043590008667385876> again.",
                colour=0xFF0000,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(
                title="Welcome message not enabled!",
                description=f"Welcome function has never been enabled, or it has already been disabled. ",
                colour=0xFF0000,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(embed=embed, ephemeral=True)
    @welcome_disable.error
    async def welcome_disable_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)

    @app_commands.command(name="sample", description="Sends a sample welcome message")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_sample(
        self,
        interaction: discord.Interaction,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        ref = db.reference("/Welcome")
        welcome = ref.get()

        welcomeChannel = found = False
        file = embed = None

        for key, val in welcome.items():
            if val["Server ID"] == interaction.guild.id:
                welcomeChannel = val["Welcome Channel ID"]
                welcomeImageEnabled = val["Welcome Image Enabled"]
                break

        if welcomeChannel is not False:
            ref2 = db.reference("/Welcome Content")
            welcomecontent = ref2.get()

            for key, val in welcomecontent.items():
                if val["Server ID"] == interaction.guild.id:
                    if val["Title"] != "" or val["Description"] != "":
                        hex = val["Color"]
                        if hex.startswith("#"):
                            hex = hex[1:]
                        async with aiohttp.ClientSession() as session:
                            async with session.get(
                                "https://www.thecolorapi.com/id", params={"hex": hex}
                            ) as server:
                                if server.status == 200:

                                    js = await server.json()
                                    try:
                                        color = discord.Color(
                                            int(f"0x{js['hex']['clean']}", 16)
                                        )
                                    except:
                                        color = discord.Color.blurple()

                        embed = discord.Embed(
                            title=script(
                                val["Title"], interaction.user, interaction.guild
                            ),
                            description=script(
                                val["Description"], interaction.user, interaction.guild
                            ),
                            color=color,
                        )
                        if welcomeImageEnabled:
                            filename = await createWelcomeMsg(
                                interaction.user,
                                bg=f"./assets/Welcome Image Background/{interaction.guild.id}.png",
                            )
                            chn = self.bot.get_channel(1026904121237831700)
                            msg = await chn.send(file=discord.File(filename))
                            url = msg.attachments[0].proxy_url
                            embed.set_image(url=url)
                    elif val["Title"] == "" and val["Description"] == "":
                        if welcomeImageEnabled:
                            filename = await createWelcomeMsg(
                                interaction.user,
                                bg=f"./assets/Welcome Image Background/{interaction.guild.id}.png",
                            )
                            file = discord.File(filename)
                    # break

                    channel = self.bot.get_channel(welcomeChannel)
                    await channel.send(
                        script(
                            val["Message Content"], interaction.user, interaction.guild
                        ),
                        embed=embed,
                        file=file,
                    )
                    embed = discord.Embed(
                        description=f"<:yes:1036811164891480194> Sample message sent to <#{welcomeChannel}>",
                        colour=0x00FF00,
                    )
                    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    found = True
        if not found:
            embed = discord.Embed(
                title="Welcome message not enabled!",
                description=f"This server does not have welcome message enabled! Use </welcome setup:1043590008667385876> to enable first.",
                colour=0xFF0000,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.followup.send(embed=embed, ephemeral=True)
    @welcome_sample.error
    async def welcome_sample_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Welcome(bot))
