import discord
import datetime

from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View


class CopyPasteButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Copy & Paste",
            style=discord.ButtonStyle.blurple,
            custom_id="CopyPasteButton",
        )

    async def callback(self, interaction: discord.Interaction):
        parts = interaction.message.embeds[0].description.split("`")
        filtered_parts = [part for part in parts if "|" not in part and ":" not in part]
        z = 1
        for part in filtered_parts:
            if z == 1:
                await interaction.response.send_message(part, ephemeral=True)
            else:
                await interaction.followup.send(part, ephemeral=True)
            z += 1


class CopyPasteView(discord.ui.View):
    def __init__(self, *, timeout=None):
        super().__init__(timeout=timeout)
        self.add_item(CopyPasteButton())


class SendCodes(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="sendcodes",
        description="Sends a message for redemption codes with links and buttons.",
    )
    @app_commands.choices(
        game=[
            app_commands.Choice(name="Genshin Impact", value="genshin"),
            app_commands.Choice(name="Honkai: Star Rail", value="hsr"),
            app_commands.Choice(name="Zenless Zone Zero", value="zzz"),
        ]
    )
    @app_commands.describe(
        game="The game that the codes belong",
        codes="The redemption codes you wish to send, each separated by a comma",
        role="The role you would like to ping alongside this message",
        reward="Optional description the rewards, each separated by a comma",
        separate_msg="Whether to send separate messages afterwards for copy & pasting (default: False)",
        image="One optional image of the reward, inserted in the embed"
    )
    @app_commands.guild_only()
    async def sendcode(
        self,
        interaction: discord.Interaction,
        game: app_commands.Choice[str],
        codes: str,
        role: discord.Role = None,
        reward: str = None,
        separate_msg: bool = False,
        image: discord.Attachment = None,
    ) -> None:
        listOfCodes = codes.split(",")
        if reward is not None:
            listOfRewards = reward.split(",")
            if len(listOfCodes) != len(listOfRewards):
                await interaction.response.send_message(
                    f":x: Number of codes `({len(listOfCodes)})` and reward descriptions `({len(listOfRewards)})` do not match. Please double check.",
                    ephemeral=True,
                )
                return
        codeString = ""
        view = View()
        if game.value == "genshin":
            for code in listOfCodes:
                c = code.strip()
                if reward is not None:
                    desc = listOfRewards[listOfCodes.index(code)].strip()
                else:
                    desc = ""
                codeString += f"<:yes:1036811164891480194> {f'**{desc}:** ' if reward is not None else ''}`{c}` | **[Direct Link](https://genshin.hoyoverse.com/en/gift?code={c})**\n"
                button = Button(
                    label=f"{c if desc == '' else desc}",
                    style=discord.ButtonStyle.link,
                    emoji="<:PRIMOGEM:1364031230357540894>",
                    url=f"https://genshin.hoyoverse.com/en/gift?code={c}",
                )
                view.add_item(button)

            embed = discord.Embed(
                title="Latest Genshin Impact Redemption Codes",
                description=f"""<:link:943068848058413106> ***[Redeem by clicking on the buttons below!](https://genshin.mihoyo.com/en/gift)***
<:MelonBread_KeqingNote:1342924552392671254> **Note:** Codes expire quickly, so make sure to redeem them as soon as possible!

<:code1:1108803434141982751><:code2:1108803491171934218><:code3:1108803565331431454>
{codeString}""",
                color=discord.Color.blurple(),
            )
        elif game.value == "hsr":
            for code in listOfCodes:
                c = code.strip()
                if reward is not None:
                    desc = listOfRewards[listOfCodes.index(code)].strip()
                else:
                    desc = ""
                codeString += f"<:yes:1036811164891480194> {f'**{desc}:** ' if reward is not None else ''}`{c}` | **[Direct Link](https://hsr.hoyoverse.com/gift?code={c}&lang=en-us)**\n"
                button = Button(
                    label=f"{c if desc == '' else desc}",
                    style=discord.ButtonStyle.link,
                    emoji="<:Jade:1222617029815832657>",
                    url=f"https://hsr.hoyoverse.com/gift?code={c}&lang=en-us",
                )
                view.add_item(button)

            embed = discord.Embed(
                title="Latest Honkai: Star Rail Redemption Codes",
                description=f"""<:link:943068848058413106> ***[Redeem by clicking on the buttons below!](https://hsr.hoyoverse.com/gift?lang=en-us)***
<:MelonBread_KeqingNote:1342924552392671254> **Note:** Codes expire quickly, so make sure to redeem them as soon as possible!

<:code1:1108803434141982751><:code2:1108803491171934218><:code3:1108803565331431454>
{codeString}""",
                color=discord.Color.blurple(),
            )
        elif game.value == "zzz":
            for code in listOfCodes:
                c = code.strip()
                if reward is not None:
                    desc = listOfRewards[listOfCodes.index(code)].strip()
                else:
                    desc = ""
                codeString += f"<:yes:1036811164891480194> {f'**{desc}:** ' if reward is not None else ''}`{c}` | **[Direct Link](https://zenless.hoyoverse.com/redemption?code={c})**\n"
                button = Button(
                    label=f"{c if desc == '' else desc}",
                    style=discord.ButtonStyle.link,
                    emoji="<:Polychrome:1316607903939035236>",
                    url=f"https://zenless.hoyoverse.com/redemption?code={c}",
                )
                view.add_item(button)

            embed = discord.Embed(
                title="Latest Zenless Zone Zero Redemption Codes",
                description=f"""<:link:943068848058413106> ***[Redeem by clicking on the buttons below!](https://zenless.hoyoverse.com/redemption)***
<:MelonBread_KeqingNote:1342924552392671254> **Note:** Codes expire quickly, so make sure to redeem them as soon as possible!

<:code1:1108803434141982751><:code2:1108803491171934218><:code3:1108803565331431454>
{codeString}""",
                color=discord.Color.blurple(),
            )

        if image is None:
            embed.set_image(url="https://media.discordapp.net/attachments/957252297501577276/965133143365550090/unknown.png")
        else:
            path = f"./assets/sendcodes.png"
            await image.save(path)
            chn = interaction.client.get_channel(1026968305208131645)
            msg = await chn.send(file=discord.File(path))
            url = msg.attachments[0].proxy_url
            embed.set_image(url=url)

        try:
            embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url)
        except Exception:
            embed.set_footer(text=interaction.guild.name)
            
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)

        if role is not None:
            if not(interaction.user.guild_permissions.mention_everyone):
                return await interaction.response.send_message("<:no:1036810470860013639> You don't have permissions to mention `@everyone`, `@here`, or other roles!", ephemeral=True)
            await interaction.channel.send(f"<:blurplemic:1108805037230129302> {role.mention} **• Redeemable Codes**", embed=embed, view=view)
        else:
            await interaction.channel.send(f"<:blurplemic:1108805037230129302> **• Redeemable Codes**", embed=embed, view=view)

        if separate_msg:
            await interaction.channel.send("-# <:BunnyNerd:1224838490743767121> For copy and pasting ⬇️")
            for code in listOfCodes:
                await interaction.channel.send(code.strip())

        await interaction.response.send_message("<:yes:1036811164891480194> Sent!", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SendCodes(bot))
