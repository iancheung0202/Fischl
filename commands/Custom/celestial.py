import re

import discord
from discord.ext import commands

CELESTIAL = 1168706427435622410
STAFF_ROLES = [
    1180400455105384528,
    1176357434365841518,
    1200204308570980422,
    1178303001140666488,
    1188174906060439726,
    1239907587651276930,
]
BANNER = (
    "https://media.discordapp.net/attachments/1152640894328127539/"
    "1199936623949926472/CelestialBanner.png"
)
REFRESH = "<:refresh:1048779043287351408>"

# Button name, role id, game, channel with the leaks, channel to discuss them
LEAKS = [
    (
        "Genshin",
        1324391617938985023,
        "Genshin Impact",
        1261243694468698112,
        1383774520032100352,
    ),
    (
        "HSR",
        1324391720040923258,
        "Honkai: Star Rail",
        1310928513876099143,
        1383774549497221261,
    ),
    (
        "WuWa",
        1360288374027583580,
        "Wuthering Waves",
        1357905859791032630,
        1383774575069761547,
    ),
    (
        "ZZZ",
        1428330808174841918,
        "Zenless Zone Zero",
        1428330534093983744,
        1428824981114060844,
    ),
]
LEAKS_RULES = (
    "By selecting the button(s), you acknowledge that leaked content remains "
    "unverified, subject to changes, and is against Hoyoverse's and/or Kuro Games' "
    "Terms of Service. We kindly request maintaining a respectful manner when "
    "discussing leaks. Please do not spread misinformation or share any unauthorized "
    "leaks, as it may result in a permanent removal of your access to the leaks "
    "channel.\n\n> **If you wish to remove your access to the leaks channel, you can "
    "simply click on the button(s) again.**"
)


def roster(guild):
    """Gives the staff roster embed: each staff role and the members seen holding it."""
    lines = ""
    for role in map(guild.get_role, STAFF_ROLES):
        divider = "`--------------------------------`\n\n" * ("On Break" in role.name)
        lines += f"\n{divider}{role.mention} *(x{len(role.members)})*\n"
        for member in role.members:
            lines += f"- {member.mention} `({member.id})`\n"
    embed = discord.Embed(
        title="Staff Roster",
        description="**The following list consists of all our official staff "
        f"members:**\n{lines}",
        colour=0x46E1EC,
    )
    embed.set_image(url=BANNER)
    embed.set_footer(
        text='Click "View Raw List" if text looks like <@692254240290242601>'
    )
    return embed


class RefreshStaffViewCelestial(discord.ui.View):
    """The two buttons under the staff roster."""

    def __init__(self):
        super().__init__(timeout=None)

    async def redraw(self, interaction):
        """Puts a fresh roster in the message and gives the message back."""
        return await interaction.message.edit(
            embed=roster(interaction.guild), view=RefreshStaffViewCelestial()
        )

    @discord.ui.button(
        label="View Raw List",
        style=discord.ButtonStyle.blurple,
        custom_id="rawcelestial",
        emoji="🗒️",
    )
    async def refreshstaffview(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        shown = (await self.redraw(interaction)).embeds[0]
        raw = re.sub(
            r"`.*?`", "", f"{shown.title}\n{shown.description}", flags=re.DOTALL
        )
        await interaction.response.send_message(raw, ephemeral=True)

    @discord.ui.button(
        label="Refresh",
        style=discord.ButtonStyle.grey,
        custom_id="refreshcelestial",
        emoji=REFRESH,
    )
    async def refreshtt(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.redraw(interaction)
        await interaction.response.send_message(
            f"{REFRESH} The staff list is successfully refreshed!", ephemeral=True
        )


class LeakButton(discord.ui.Button):
    """Gives or takes back one game's leaks role."""

    def __init__(self, name, role_id, game, leaks, talk):
        super().__init__(
            label=f"{name} Leaks",
            style=discord.ButtonStyle.red,
            custom_id=f"{name.lower()}leaksaccesscelestial",
        )
        self.role_name = f"Access {name} Leaks"
        self.role_id, self.game, self.leaks, self.talk = role_id, game, leaks, talk

    async def callback(self, interaction: discord.Interaction):
        member = interaction.user
        has = any(role.name == self.role_name for role in member.roles)
        role = discord.utils.get(interaction.guild.roles, name=self.role_name)
        if has:
            await member.remove_roles(role)
            reply = (
                f"You **no longer** have the <@&{self.role_id}> role, and you can no "
                f"longer access {self.game} leaks."
            )
        else:
            await member.add_roles(role)
            reply = (
                f"You have **obtained** the <@&{self.role_id}> role. You can now access "
                f"{self.game} leaks at <#{self.leaks}> and discuss them at <#{self.talk}>!"
            )
        await interaction.response.send_message(reply, ephemeral=True)


class LeaksAccessCelestial(discord.ui.View):
    """One button per game whose leaks channels a member can open."""

    def __init__(self):
        super().__init__(timeout=None)
        for leak in LEAKS:
            self.add_item(LeakButton(*leak))


class StaffRoster(commands.Cog):
    """Celestial's `-staff` roster and `-leaksaccess` panel."""

    def __init__(self, bot):
        self.client = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        """Posts the roster or the leaks panel when a member asks for it."""
        if message.author.bot or not message.guild or message.guild.id != CELESTIAL:
            return
        if message.content == "-staff":
            await message.guild.chunk()
            await message.channel.send(
                embed=roster(message.guild), view=RefreshStaffViewCelestial()
            )
        if message.content == "-leaksaccess":
            await message.delete()
            embed = discord.Embed(
                title="<:RaidenJam:1343391073439060028> Select below to gain access "
                "to leaks-related channels!",
                description=LEAKS_RULES,
                color=0x2B2C31,
            )
            await message.channel.send(embed=embed, view=LeaksAccessCelestial())


async def setup(bot):
    await bot.add_cog(StaffRoster(bot))
