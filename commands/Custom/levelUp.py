import discord
import asyncio

from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
from commands.Events.event import addMora

def rgb_to_hex(r, g, b):
    hex_code = "#{:02X}{:02X}{:02X}".format(r, g, b)
    return hex_code

### ------ LEVEL UP IMAGE CARD HOYO'S CAFE ------ ###

async def createLevelImage(
    user, level, levelRole, bg="./assets/levelbg.png", filename="./assets/levelup.png"
):
    try:
        await user.avatar.with_static_format("png").with_size(256).save(filename)
        im1 = Image.open(bg)
        im2 = Image.open(filename)
        await levelRole.icon.with_static_format("png").save(
            "./assets/leveluproleicon.png"
        )
        im3 = Image.open("./assets/leveluproleicon.png")
    except Exception as e:
        print(e)
        im1 = Image.open(bg)
        im2 = Image.open("./assets/DefaultIcon.png")
        im3 = None

    bigsize = (int(im2.size[0] * 2), int(im2.size[1] * 2))
    mask = Image.new("L", bigsize, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0) + bigsize, fill=255)
    mask = mask.resize(im2.size, Image.LANCZOS)
    im2.putalpha(mask)
    im1.paste(im2, (247, 87), im2.convert("RGBA"))

    ### ROLE ICON
    im1.paste(im3, (755, 280), im3.convert("RGBA"))

    ### TEXT "LEVEL"
    font = ImageFont.truetype("./assets/ja-jp.ttf", 90)
    d1 = ImageDraw.Draw(im1)
    d1.text((700, 150), "Level", font=font, fill=(255, 255, 255))
    im1.save(filename)

    ### LEVEL ROLE NAME
    color = rgb_to_hex(user.color.r, user.color.g, user.color.b)
    name = levelRole.name.split("-")[1].strip()
    font = ImageFont.truetype("./assets/ja-jp.ttf", 40)
    d5 = ImageDraw.Draw(im1)
    d5.text((700, 90), f"{name.upper()}", font=font, fill=color)
    im1.save(filename)

    ### ACTUAL LEVEL
    font = ImageFont.truetype("./assets/ja-jp.ttf", 275)
    d2 = ImageDraw.Draw(im1)
    d2.text((1000, 120), f"{level}", font=font, fill=color)
    im1.save(filename)

    ### USER NAME
    font = ImageFont.truetype("./assets/ja-jp.ttf", 40)
    text = f"{user.name}"
    textLen = len(text)
    d3 = ImageDraw.Draw(im1)
    d3.text(
        (((724 / 2) - (22 * (textLen / 2))), 387), text, font=font, fill=(255, 255, 255)
    )
    im1.save(filename)

    ### PERK
    perks = {
        100: "Access to #exclusive-chat",
        90: "Access to Archived Channels",
        75: "One custom profile picture or banner",
        69: "Priority in events like talks hosted by voice actors",
        50: "Qualification to become a leader for existing or new team",
        40: "Access to #manage-your-vc",
        35: "Ability to create polls in the server",
        20: "Qualification to apply for staff in #applications",
        10: "Access to embed links and GIFs in chats",
        5: "Access to upload attachments in #chill-chat",
        3: "Qualification to join a team in ⁠#select-your-team",
        1: "Access to ⁠#Join here to create VC",
    }

    try:
        font = ImageFont.truetype("./assets/ja-jp.ttf", 35)
        text = f"Earned: {perks[int(level)]}"
        textLen = len(text)
        d4 = ImageDraw.Draw(im1)
        d4.text((((740) - (17 * (textLen / 2))), 494), text, font=font, fill=color)
        im1.save(filename)
    except KeyError:
        font = ImageFont.truetype("./assets/ja-jp.ttf", 29)
        if level > 69:
            text = f"Keep yapping to level up!"
        else:
            text = f"Keep chatting to level up!"
        d4 = ImageDraw.Draw(im1)
        d4.text((570, 494), text, font=font, fill=(255, 255, 255))
        im1.save(filename)

    return filename

### ------ LEVEL UP IMAGE CARD CELESTIAL ------ ###

async def createLevelImageCelestial(
    user,
    level,
    levelRole,
    bg="./assets/celestial-levelbg.png",
    filename="./assets/celestial-levelup.png",
):
    try:
        await user.avatar.with_static_format("png").with_size(256).save(filename)
        im1 = Image.open(bg)
        im2 = Image.open(filename)
        await levelRole.icon.with_static_format("png").save(
            "./assets/leveluproleicon.png"
        )
        im3 = Image.open("./assets/leveluproleicon.png")
    except Exception as e:
        print(e)
        im1 = Image.open(bg)
        im2 = Image.open("./assets/DefaultIcon.png")
        im3 = None

    bigsize = (int(im2.size[0] * 2), int(im2.size[1] * 2))
    mask = Image.new("L", bigsize, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0) + bigsize, fill=255)
    mask = mask.resize(im2.size, Image.LANCZOS)
    im2.putalpha(mask)
    im1.paste(im2, (247, 87), im2.convert("RGBA"))

    ### ROLE ICON
    im1.paste(im3, (755, 280), im3.convert("RGBA"))

    ### TEXT "LEVEL"
    font = ImageFont.truetype("./assets/ja-jp.ttf", 90)
    d1 = ImageDraw.Draw(im1)
    d1.text((700, 150), "Level", font=font, fill=(255, 255, 255))
    im1.save(filename)

    ### LEVEL ROLE NAME
    color = rgb_to_hex(user.color.r, user.color.g, user.color.b)
    name = levelRole.name.split("-")[1].strip()
    font = ImageFont.truetype("./assets/ja-jp.ttf", 40)
    d5 = ImageDraw.Draw(im1)
    d5.text((700, 90), f"{name.upper()}", font=font, fill=color)
    im1.save(filename)

    ### ACTUAL LEVEL
    font = ImageFont.truetype("./assets/ja-jp.ttf", 275)
    d2 = ImageDraw.Draw(im1)
    d2.text((1000, 120), f"{level}", font=font, fill=color)
    im1.save(filename)

    ### USER NAME
    font = ImageFont.truetype("./assets/ja-jp.ttf", 40)
    text = f"{user.name}"
    textLen = len(text)
    d3 = ImageDraw.Draw(im1)
    d3.text(
        (((724 / 2) - (22 * (textLen / 2))), 387), text, font=font, fill=(255, 255, 255)
    )
    im1.save(filename)

    ### FOOTER
    font = ImageFont.truetype("./assets/ja-jp.ttf", 29)
    if level > 69:
        text = f"Keep yapping to level up!"
    else:
        text = f"Keep chatting to level up!"
    d4 = ImageDraw.Draw(im1)
    d4.text((570, 494), text, font=font, fill=(255, 255, 255))
    im1.save(filename)

    return filename

### ------ LEVEL UP IMAGE CARD MEROPIDE BULLETIN ------ ###

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

async def createLevelImageBulletin(
    user,
    level,
    levelRole,
    bg="./assets/bulletin-levelbg.png",
    filename="./assets/bulletin-levelup.png",
):
    try:
        await user.avatar.with_static_format("png").with_size(256).save(filename)
        im1 = Image.open(bg)
        im2 = Image.open(filename)
        await levelRole.icon.with_static_format("png").save(
            "./assets/leveluproleicon.png"
        )
        im3 = Image.open("./assets/leveluproleicon.png")
    except Exception as e:
        print(e)
        im1 = Image.open(bg)
        im2 = Image.open("./assets/DefaultIcon.png")
        im3 = None

    bigsize = (int(im2.size[0] * 2), int(im2.size[1] * 2))
    mask = Image.new("L", bigsize, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0) + bigsize, fill=255)
    mask = mask.resize(im2.size, Image.LANCZOS)
    im2.putalpha(mask)
    im1.paste(im2, (247, 87), im2.convert("RGBA"))

    ### ROLE ICON
    im1.paste(im3, (755, 280), im3.convert("RGBA"))

    ### TEXT "LEVEL"
    font = ImageFont.truetype("./assets/ja-jp.ttf", 90)
    d1 = ImageDraw.Draw(im1)
    d1.text((700, 150), "Level", font=font, fill=(255, 255, 255))
    im1.save(filename)

    ### LEVEL ROLE NAME
    roles = {
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

    color = rgb_to_hex(user.color.r, user.color.g, user.color.b)
    closest_level = max(k for k in roles if k <= level)  # Find the highest key <= level
    name = roles[int(closest_level)].split("-")[0].strip()
    font = ImageFont.truetype("./assets/ja-jp.ttf", 40)
    d5 = ImageDraw.Draw(im1)
    d5.text((700, 90), f"{name.upper()}", font=font, fill=color)
    im1.save(filename)

    ### ACTUAL LEVEL
    font = ImageFont.truetype("./assets/ja-jp.ttf", 275)
    d2 = ImageDraw.Draw(im1)
    d2.text((1000, 120), f"{level}", font=font, fill=color)
    im1.save(filename)

    ### USER NAME
    font = ImageFont.truetype("./assets/ja-jp.ttf", 40)
    text = f"{user.name}"
    textLen = len(text)
    d3 = ImageDraw.Draw(im1)
    d3.text(
        (((724 / 2) - (22 * (textLen / 2))), 387), text, font=font, fill=(255, 255, 255)
    )
    im1.save(filename)

    ### PERK
    perks = {
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

    try:
        font = ImageFont.truetype("./assets/ja-jp.ttf", 35)
        text = f"Earned: {perks[int(level)]}"
        textLen = len(text)
        d4 = ImageDraw.Draw(im1)
        d4.text((((740) - (17 * (textLen / 2))), 494), text, font=font, fill=color)
        im1.save(filename)
    except KeyError:
        font = ImageFont.truetype("./assets/ja-jp.ttf", 29)
        if level > 69:
            text = f"Keep yapping to level up!"
        else:
            text = f"Keep chatting to level up!"
        d4 = ImageDraw.Draw(im1)
        d4.text((570, 494), text, font=font, fill=(255, 255, 255))
        im1.save(filename)

    return filename

### ------ LEVEL UP IMAGE CARD TEVYAT TIMES ------ ###

async def createLevelImageTevyatTimes(
    user,
    level,
    levelRole,
    method,
    bg="./assets/levelbg.png",
    filename="./assets/levelup.png",
):
    try:
        await user.avatar.with_static_format("png").with_size(256).save(filename)
        im1 = Image.open(bg)
        im2 = Image.open(filename)
        await levelRole.icon.with_static_format("png").save(
            "./assets/leveluproleicon.png"
        )
        im3 = Image.open("./assets/leveluproleicon.png")
    except Exception as e:
        print(e)
        im1 = Image.open(bg)
        im2 = Image.open("./assets/DefaultIcon.png")
        im3 = None

    bigsize = (int(im2.size[0] * 2), int(im2.size[1] * 2))
    mask = Image.new("L", bigsize, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0) + bigsize, fill=255)
    mask = mask.resize(im2.size, Image.LANCZOS)
    im2.putalpha(mask)
    im1.paste(im2, (247, 87), im2.convert("RGBA"))

    ### ROLE ICON
    im1.paste(im3, (755, 280), im3.convert("RGBA"))

    ### TEXT "LEVEL"
    font = ImageFont.truetype("./assets/ja-jp.ttf", 90)
    d1 = ImageDraw.Draw(im1)
    d1.text((700, 150), "Level", font=font, fill=(255, 255, 255))
    im1.save(filename)

    ### LEVEL ROLE NAME
    color = rgb_to_hex(user.color.r, user.color.g, user.color.b)
    # name = levelRole.name.split("-")[0].strip()
    name = "Tevyat Times"
    font = ImageFont.truetype("./assets/ja-jp.ttf", 40)
    d5 = ImageDraw.Draw(im1)
    d5.text((700, 90), f"{name.upper()}", font=font, fill=color)
    im1.save(filename)

    ### ACTUAL LEVEL
    font = ImageFont.truetype("./assets/ja-jp.ttf", 275)
    d2 = ImageDraw.Draw(im1)
    d2.text((1000, 120), f"{level}", font=font, fill=color)
    im1.save(filename)

    ### USER NAME
    font = ImageFont.truetype("./assets/ja-jp.ttf", 40)
    text = f"{user.name}"
    textLen = len(text)
    d3 = ImageDraw.Draw(im1)
    d3.text(
        (((724 / 2) - (22 * (textLen / 2))), 387), text, font=font, fill=(255, 255, 255)
    )
    im1.save(filename)

    roles = {
        100: "Zhongli - Level 100",
        90: "Neuvillette - Level 90",
        75: "Xiao - Level 75",
        69: "Wanderer - Level 69",
        45: "Hu Tao - Level 45",
        35: "Kazuha - Level 35",
        20: "Lynette - Level 20",
        10: "Xingqiu - Level 10",
        5: "Barbara - Level 5",
        3: "Amber - Level 3",
    }
    try:
        if method.lower().strip() != "text":
            raise KeyError()
        font = ImageFont.truetype("./assets/ja-jp.ttf", 35)
        text = f"New Role Earned: {roles[int(level)]}"
        textLen = len(text)
        d4 = ImageDraw.Draw(im1)
        d4.text((((740) - (17 * (textLen / 2))), 494), text, font=font, fill=color)
        im1.save(filename)
    except KeyError:
        font = ImageFont.truetype("./assets/ja-jp.ttf", 29)
        text = f"Keep chatting to level up in {method}!"
        d4 = ImageDraw.Draw(im1)
        d4.text((500, 494), text, font=font, fill=(255, 255, 255))
        im1.save(filename)

    return filename

### ------ LEVEL UP IMAGE CARD JINHSI MAINS ------ ###

async def createLevelImageJinhsi(
    user,
    level,
    levelRole,
    bg="./assets/jinhsi-levelbg.png",
    filename="./assets/jinhsi-levelup.png",
):
    try:
        im1 = Image.open(bg)
    except Exception as e:
        print(f"Error loading bg: {e}")
        im1 = None

    try:
        await user.avatar.with_static_format("png").with_size(256).save(filename)
        im2 = Image.open(filename)
    except Exception as e:
        print(f"Error loading user avatar: {e}")
        im2 = Image.open("./assets/DefaultIcon.png")

    try:
        await levelRole.icon.with_static_format("png").save(
            "./assets/leveluproleicon.png"
        )
        im3 = Image.open("./assets/leveluproleicon.png")
    except Exception as e:
        print(f"Error loading level role icon: {e}")
        im3 = None

    bigsize = (int(im2.size[0] * 2), int(im2.size[1] * 2))
    mask = Image.new("L", bigsize, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0) + bigsize, fill=255)
    mask = mask.resize(im2.size, Image.LANCZOS)
    im2.putalpha(mask)
    im1.paste(im2, (247, 87), im2.convert("RGBA"))

    ### ROLE ICON
    try:
        im1.paste(im3, (755, 280), im3.convert("RGBA"))
    except Exception:
        pass

    ### TEXT "LEVEL"
    font = ImageFont.truetype("./assets/ja-jp.ttf", 90)
    d1 = ImageDraw.Draw(im1)
    d1.text((700, 150), "Level", font=font, fill=(255, 255, 255))
    im1.save(filename)

    ### LEVEL ROLE NAME
    color = rgb_to_hex(user.color.r, user.color.g, user.color.b)
    if levelRole is not None:
        name = levelRole.name.split("(")[0].strip()
    else:
        name = "Newbie"
    font = ImageFont.truetype("./assets/ja-jp.ttf", 40)
    d5 = ImageDraw.Draw(im1)
    d5.text((700, 90), f"{name.upper()}", font=font, fill=color)
    im1.save(filename)

    ### ACTUAL LEVEL
    font = ImageFont.truetype("./assets/ja-jp.ttf", 275)
    d2 = ImageDraw.Draw(im1)
    d2.text((1000, 120), f"{level}", font=font, fill=color)
    im1.save(filename)

    ### USER NAME
    font = ImageFont.truetype("./assets/ja-jp.ttf", 40)
    text = f"{user.name}"
    textLen = len(text)
    d3 = ImageDraw.Draw(im1)
    d3.text(
        (((724 / 2) - (22 * (textLen / 2))), 387), text, font=font, fill=(255, 255, 255)
    )
    im1.save(filename)

    ### FOOTER
    font = ImageFont.truetype("./assets/ja-jp.ttf", 29)
    if level > 69:
        text = f"Keep yapping to level up!"
    else:
        text = f"Keep chatting to level up!"
    d4 = ImageDraw.Draw(im1)
    d4.text((570, 494), text, font=font, fill=(255, 255, 255))
    im1.save(filename)

    return filename

class LevelUpTrigger(commands.Cog):
    def __init__(self, bot):
        self.client = bot

    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author == self.client.user:
            return

        ### CAFE LEVELLING UP CARD ###
        if (
            message.author.id == 437808476106784770
            and message.channel.id == 1229161238274244749
            and "has reached" in message.content
        ):
            id = int(message.content.split("**")[1].replace("<@", "").replace(">", ""))
            member = await message.guild.fetch_member(id)
            level = int(message.content.split("**")[3])
            await asyncio.sleep(2)
            for role in member.roles:
                if "Level" in role.name:
                    levelRole = role
                    break

            filename = await createLevelImage(member, level, levelRole)
            chn = message.guild.get_channel(1229165255318569011)
            await addMora(member.id, level * 300, 2, message.guild.id)
            if message.content.strip()[-1] == "!":
                msg = f"{message.content}\n<:reply:1036792837821435976> *You've earned <:MORA:1364030973611610205> `{level * 300}` for levelling up.*"
            else:
                msg = f"{message.content} and <:MORA:1364030973611610205> `{level * 300}` for levelling up!*"
            await chn.send(msg, file=discord.File(filename))

        ### CELESTIAL LEVELLING UP CARD ###
        if (
            message.author.id == 645343657075146772
            and message.channel.id == 1338340021295644703
            and "Congratulations" in message.content
        ):
            id = int(message.content.split("**")[1].replace("<@", "").replace(">", ""))
            member = await message.guild.fetch_member(id)
            level = int(message.content.split("**")[3])
            await asyncio.sleep(2)
            for role in member.roles:
                if "Level" in role.name:
                    levelRole = role
                    break

            filename = await createLevelImageCelestial(member, level, levelRole)
            chn = message.guild.get_channel(1178423103521566872)
            await chn.send(message.content, file=discord.File(filename))

        ### MEROPIDE BULLETIN LEVELLING UP CARD ###
        if (
            message.author.id == 989173789482975262
            and message.channel.id == 1335828558190215259
        ):
            id = int(message.content.replace("<@", "").replace(">", ""))
            member = await message.guild.fetch_member(id)
            level = int(
                message.embeds[0].description.split("to ")[1].replace("!", "").strip()
            )
            method = (
                message.embeds[0].description.split("from")[1].split("level")[0].strip()
            )
            await asyncio.sleep(3)
            for role in member.roles:
                if "Level" in role.name:
                    levelRole = role
                    break

            filename = await createLevelImageBulletin(member, level, levelRole)
            chn = message.guild.get_channel(1281687605548945428)
            roles = {
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

            # await message.delete()
            await addMora(member.id, level * 300, 2, message.guild.id)
            try:
                roleName = roles[int(level)]
                await chn.send(
                    f"{message.content} has reached level **{level}** in {method}! GG!\n<:reply:1036792837821435976> *You've earned the **`{roleName}`** role and <:MORA:1364030973611610205> `{level * 300}` for levelling up!*",
                    file=discord.File(filename),
                    view=ShowPerksBulletin(),
                )
            except KeyError:
                await chn.send(
                    f"{message.content} has reached level **{level}** in {method}! GG!\n<:reply:1036792837821435976> *You've earned <:MORA:1364030973611610205> `{level * 300}` for levelling up.*",
                    file=discord.File(filename),
                    view=ShowPerksBulletin(),
                )

        ### JINHSI LEVELLING UP CARD ###
        if (
            message.author.id == 437808476106784770
            and message.channel.id == 1356789459370119371
            and "has reached" in message.content
        ):
            id = int(message.content.split("**")[1].replace("<@", "").replace(">", ""))
            member = await message.guild.fetch_member(id)
            level = int(message.content.split("**")[3])
            await asyncio.sleep(2)
            levelRole = None
            for role in member.roles:
                if "LV" in role.name:
                    levelRole = role
                    break

            filename = await createLevelImageJinhsi(member, level, levelRole)
            chn = message.guild.get_channel(1197491635710332996)
            await addMora(member.id, level * 300, 2, message.guild.id)
            await chn.send(message.content, file=discord.File(filename))

        ### TEVYAT TIMES LEVELLING UP CARD ###
        if (
            message.channel.id == 1253526260844335124
        ):  #  and message.author.id == 989173789482975262
            # member = message.author
            id = int(message.content.replace("<@", "").replace(">", ""))
            member = await message.guild.fetch_member(id)
            level = int(
                message.embeds[0].description.split("to ")[1].replace("!", "").strip()
            )
            method = (
                message.embeds[0].description.split("from")[1].split("level")[0].strip()
            )
            for role in member.roles:
                if "Level" in role.name:
                    levelRole = role
                    break

            filename = await createLevelImageTevyatTimes(
                member, level, levelRole, method
            )
            chn = message.guild.get_channel(1206124237513957416)
            roles = {
                100: "Zhongli - Level 100",
                90: "Neuvillette - Level 90",
                75: "Xiao - Level 75",
                69: "Wanderer - Level 69",
                45: "Hu Tao - Level 45",
                35: "Kazuha - Level 35",
                20: "Lynette - Level 20",
                10: "Xingqiu - Level 10",
                5: "Barbara - Level 5",
                3: "Amber - Level 3",
            }
            try:
                roleName = roles[int(level)]
                await chn.send(
                    f"{message.content} has reached level **{level}** in {method}! GG!\nYou've earned the `{roleName}` role!",
                    file=discord.File(filename),
                )
            except KeyError:
                await chn.send(
                    f"{message.content} has reached level **{level}** in {method}! GG!",
                    file=discord.File(filename),
                )


class RemoveLevelZeroRole(commands.Cog):
    def __init__(self, bot):
        self.client = bot

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if (
            after.guild.id == 717029019270381578
            and discord.utils.get(after.guild.roles, name="Level 1 - Slime")
            in after.roles
            and discord.utils.get(after.guild.roles, name="Level 1 - Slime")
            not in before.roles
        ):
            levelRole = discord.utils.get(after.guild.roles, name="Level 0 - Newbie")
            await after.remove_roles(levelRole)

async def setup(bot):
    await bot.add_cog(LevelUpTrigger(bot))
    await bot.add_cog(RemoveLevelZeroRole(bot))
