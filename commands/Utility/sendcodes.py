import discord
from discord import app_commands
from discord.ext import commands

from commands.Utility import posting

# Per game: its full name, its redeem page, the link for one code, the button emoji.
GAMES = {
    "genshin": (
        "Genshin Impact",
        "https://genshin.mihoyo.com/en/gift",
        "https://genshin.hoyoverse.com/en/gift?code={}",
        "<:PRIMOGEM:1364031230357540894>",
    ),
    "hsr": (
        "Honkai: Star Rail",
        "https://hsr.hoyoverse.com/gift?lang=en-us",
        "https://hsr.hoyoverse.com/gift?code={}&lang=en-us",
        "<:Jade:1222617029815832657>",
    ),
    "zzz": (
        "Zenless Zone Zero",
        "https://zenless.hoyoverse.com/redemption",
        "https://zenless.hoyoverse.com/redemption?code={}",
        "<:Polychrome:1316607903939035236>",
    ),
}
DEFAULT_IMAGE = "https://media.discordapp.net/attachments/957252297501577276/965133143365550090/unknown.png"
MISMATCH = ":x: Number of codes `({})` and reward descriptions `({})` do not match. Please double check."


def announcement(game, codes, rewards):
    """Builds the embed listing every code and the view with a button for each."""
    name, page, link, emoji = GAMES[game]
    lines = ""
    view = discord.ui.View()
    for code in codes:
        reward = rewards[codes.index(code)].strip() if rewards else ""
        code = code.strip()
        label = f"**{reward}:** " if rewards else ""
        lines += f"<:yes:1036811164891480194> {label}`{code}` | **[Direct Link]({link.format(code)})**\n"
        view.add_item(
            discord.ui.Button(
                label=reward or code,
                style=discord.ButtonStyle.link,
                emoji=emoji,
                url=link.format(code),
            )
        )
    embed = discord.Embed(
        title=f"Latest {name} Redemption Codes",
        description=f"""<:link:943068848058413106> ***[Redeem by clicking on the buttons below!]({page})***
<:MelonBread_KeqingNote:1342924552392671254> **Note:** Codes expire quickly, so make sure to redeem them as soon as possible!

<:code1:1108803434141982751><:code2:1108803491171934218><:code3:1108803565331431454>
{lines}""",
        color=discord.Color.blurple(),
    )
    return embed, view


class SendCodes(commands.Cog):
    """The command that announces a game's redemption codes."""

    def __init__(self, bot):
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
        image="One optional image of the reward, inserted in the embed",
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
        """Posts the codes with a redeem button each, then plain copies if asked."""
        codes = codes.split(",")
        rewards = reward.split(",") if reward is not None else None
        if rewards and len(codes) != len(rewards):
            await interaction.response.send_message(
                MISMATCH.format(len(codes), len(rewards)), ephemeral=True
            )
            return

        embed, view = announcement(game.value, codes, rewards)
        if image is None:
            embed.set_image(url=DEFAULT_IMAGE)
        else:
            embed.set_image(url=await posting.hosted(interaction, image, "sendcodes"))
        posting.sign(embed, interaction.guild)

        headline = "**• Redeemable Codes**"
        if not await posting.post(interaction, headline, role, embed, view):
            return
        if separate_msg:
            await interaction.channel.send(
                "-# <:BunnyNerd:1224838490743767121> For copy and pasting ⬇️"
            )
            for code in codes:
                await interaction.channel.send(code.strip())
        await interaction.response.send_message(posting.SENT, ephemeral=True)


async def setup(bot):
    await bot.add_cog(SendCodes(bot))
