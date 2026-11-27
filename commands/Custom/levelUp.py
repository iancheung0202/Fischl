import asyncio
import io

import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont

from commands.Events.helperFunctions import addMora

FONT = "./assets/ja-jp.ttf"
WHITE = (255, 255, 255)
REPLY = "<:reply:1036792837821435976>"
MORA = "<:MORA:1364030973611610205>"

BULLETIN_BOT = 989173789482975262
BULLETIN_XP_LOGS = 1335828558190215259
BULLETIN_LEVEL_UP = 1281687605548945428
BULLETIN_ROLES = {
    100: "Wriothesley - Level 100",
    90: "Dainsleif - Level 90",
    80: "Tsaritsa - Level 80",
    69: "Mavuika - Level 69",
    60: "Neuvillette - Level 60",
    50: "Furina - Level 50",
    40: "Nahida - Level 40",
    30: "Raiden - Level 30",
    25: "Zhongli - Level 25",
    20: "Venti - Level 20",
    15: "M - Level 15",
    10: "Clorinde - Level 10",
    5: "Sigewinne - Level 5",
    3: "Melusine - Level 3",
    1: "Slime - Level 1",
}
BULLETIN_PERKS = {
    100: "Access to #exclusive chat & +1 entry in giveaways (6 total)",
    90: "Priority speaker in stage channels",
    80: "Request to speak in stage channels & +1 entry in giveaways (5 total)",
    69: "Ability to set custom voice channel status",
    60: "+1 entry in giveaways (4 entries total)",
    50: "Access to #xp-farm channel",
    40: "Send text-to-speech messages & +1 entry in giveaways (3 total)",
    30: "Ability to create private threads",
    25: "Ability to create public threads",
    20: "Qualified to apply for staff & +1 entry in giveaways (2 total)",
    15: "Ability to create polls",
    10: "Ability to send voice messages",
    5: "Access to embed links and GIFS in chats",
    3: "Access to upload attachments in chats",
    1: "Edit nickname & create invite",
}

JINHSI_BOT = 437808476106784770
JINHSI_XP_LOGS = 1356789459370119371
JINHSI_LEVEL_UP = 1197491635710332996


class ShowPerksBulletin(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="View Level Roles & Perks",
        style=discord.ButtonStyle.grey,
        custom_id="showPerksBulletin",
        emoji="<:info:1037445870469267638>",
    )
    async def showPerksBulletin(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        embed = discord.Embed(
            title=f"❤︎ Level Roles & Perks - {interaction.guild.name} ❤︎",
            description="""As you yap in this server, you gain points known as XP. The more points you get, the higher level you unlock and these levels unlock new perks you can use within the server.

<@&1286681773178097758>
<:reply:1036792837821435976> Create Nickname
<:reply:1036792837821435976> Create Invite

<@&1283012357379067957>
<:reply:1036792837821435976> Access to Upload Attachments/Files/Media

<@&1283012636266598441>
<:reply:1036792837821435976> Embed GIFs and Links in Chat

<@&1283012710099058761>
<:reply:1036792837821435976> Send Voice Messages

<@&1292799049744912415>
<:reply:1036792837821435976> Create Polls

<@&1283012776557547573>
<:reply:1036792837821435976> Qualification to Apply for Staff
<:reply:1036792837821435976> +1 Entry in Giveaways (2 entries total)

<@&1283013027528183808>
<:reply:1036792837821435976> Create Public Threads

<@&1283013419100012587>
<:reply:1036792837821435976> Create Private Thread

<@&1283013489878634497>
<:reply:1036792837821435976> Send Text to Speech Messages
<:reply:1036792837821435976> +1 Entry in Giveaways (3 entries total)

<@&1283013595004796978>
<:reply:1036792837821435976> Access to #👻〢xp-farm channel

<@&1283013665401999413>
<:reply:1036792837821435976> +1 Entry in Giveaways (4 entries total)

<@&1283013746486284359>
<:reply:1036792837821435976> Setup Voice Channel Status

<@&1283013850551287850>
<:reply:1036792837821435976> Request to Speak in Stage Channels
<:reply:1036792837821435976> +1 Entry in Giveaways (5 entries total)

<@&1283013913503338526>
<:reply:1036792837821435976> Priority Speaker in Stage Channels

<@&1283013992104595526>
<:reply:1036792837821435976> Access to #⭐〢exclusive Channel
<:reply:1036792837821435976> +1 Entry in Giveaways (6 entries total)""",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def picture(asset):
    """Downloads a Discord avatar or role icon as a still image."""
    return Image.open(io.BytesIO(await asset.with_static_format("png").read()))


def write(card, where, text, size, fill):
    """Writes one line of text on a card."""
    font = ImageFont.truetype(FONT, size)
    ImageDraw.Draw(card).text(where, text, font=font, fill=fill)


def hex_colour(member):
    """Gives the member's role colour the way the drawing code wants it."""
    return f"#{member.color.value:06X}"


def keep_going(level):
    """Gives the line at the bottom of a card that earned nothing new."""
    text = "Keep yapping to level up!" if level > 69 else "Keep chatting to level up!"
    return (570, 494), text, 29, WHITE


def draw(server, member, level, avatar, icon, title, footer):
    """Draws a level-up card and gives it as a file ready to send."""
    card = Image.open(f"./assets/{server}-levelbg.png")
    mask = Image.new("L", (avatar.size[0] * 2, avatar.size[1] * 2), 0)
    ImageDraw.Draw(mask).ellipse((0, 0) + mask.size, fill=255)
    avatar.putalpha(mask.resize(avatar.size, Image.LANCZOS))
    card.paste(avatar, (247, 87), avatar.convert("RGBA"))
    if icon:
        card.paste(icon, (755, 280), icon.convert("RGBA"))

    colour = hex_colour(member)
    write(card, (700, 150), "Level", 90, WHITE)
    write(card, (700, 90), title.upper(), 40, colour)
    write(card, (1000, 120), str(level), 275, colour)
    write(card, (362 - 11 * len(member.name), 387), member.name, 40, WHITE)
    write(card, *(footer or keep_going(level)))

    file = io.BytesIO()
    card.save(file, "PNG")
    file.seek(0)
    return discord.File(file, filename=f"{server}-levelup.png")


def level_role(member, word):
    """Gives the member's first role with the word in its name, if any."""
    return next((role for role in member.roles if word in role.name), None)


async def bulletin_card(member, level):
    """Draws Meropide Bulletin's card; it needs an avatar and a level role icon."""
    avatar = await picture(member.avatar.with_size(256))
    icon = await picture(level_role(member, "Level").icon)
    title = BULLETIN_ROLES[max(key for key in BULLETIN_ROLES if key <= level)]
    footer = None
    if level in BULLETIN_PERKS:
        text = f"Earned: {BULLETIN_PERKS[level]}"
        footer = (740 - 17 * (len(text) / 2), 494), text, 35, hex_colour(member)
    return await asyncio.to_thread(
        draw,
        "bulletin",
        member,
        level,
        avatar,
        icon,
        title.split("-")[0].strip(),
        footer,
    )


async def jinhsi_card(member, level):
    """Draws Jinhsi Mains' card, with a stand-in avatar and no icon if they fail."""
    role = level_role(member, "LV")
    try:
        avatar = await picture(member.avatar.with_size(256))
    except Exception as e:
        print(f"Error loading user avatar: {e}")
        avatar = Image.open("./assets/DefaultIcon.png")
    try:
        icon = await picture(role.icon)
        icon.load()
    except Exception as e:
        print(f"Error loading level role icon: {e}")
        icon = None
    title = role.name.split("(")[0].strip() if role else "Newbie"
    return await asyncio.to_thread(
        draw, "jinhsi", member, level, avatar, icon, title, None
    )


class LevelUpTrigger(commands.Cog):
    """Turns two servers' level-up notices into picture cards and Mora."""

    def __init__(self, bot):
        self.client = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        """Posts a card when a levelling bot announces a level-up."""
        if message.author == self.client.user:
            return
        if message.author.id == BULLETIN_BOT and message.channel.id == BULLETIN_XP_LOGS:
            await self.bulletin(message)
        if (
            message.author.id == JINHSI_BOT
            and message.channel.id == JINHSI_XP_LOGS
            and "has reached" in message.content
        ):
            await self.jinhsi(message)

    async def bulletin(self, message):
        """Posts Meropide Bulletin's card, the role earned and the Mora reward."""
        member = await message.guild.fetch_member(
            int(message.content.replace("<@", "").replace(">", ""))
        )
        said = message.embeds[0].description
        level = int(said.split("to ")[1].replace("!", "").strip())
        method = said.split("from")[1].split("level")[0].strip()
        await asyncio.sleep(3)
        card = await bulletin_card(member, level)
        await addMora(self.client.pool, member.id, level * 300, 2, message.guild.id)
        if level in BULLETIN_ROLES:
            earned = (
                f"*You've earned the **`{BULLETIN_ROLES[level]}`** role and {MORA} "
                f"`{level * 300}` for levelling up!*"
            )
        else:
            earned = f"*You've earned {MORA} `{level * 300}` for levelling up.*"
        await message.guild.get_channel(BULLETIN_LEVEL_UP).send(
            f"{message.content} has reached level **{level}** in {method}! GG!\n"
            f"{REPLY} {earned}",
            file=card,
            view=ShowPerksBulletin(),
        )

    async def jinhsi(self, message):
        """Reposts Jinhsi Mains' notice with a card and gives the Mora reward."""
        member = await message.guild.fetch_member(
            int(message.content.split("**")[1].replace("<@", "").replace(">", ""))
        )
        level = int(message.content.split("**")[3])
        await asyncio.sleep(2)
        card = await jinhsi_card(member, level)
        await addMora(self.client.pool, member.id, level * 300, 2, message.guild.id)
        await message.guild.get_channel(JINHSI_LEVEL_UP).send(
            message.content, file=card
        )


async def setup(bot):
    await bot.add_cog(LevelUpTrigger(bot))
