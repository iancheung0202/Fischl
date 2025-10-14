import discord
import re

from discord.ext import commands

roles = [1180400455105384528, 1176357434365841518, 1200204308570980422, 1178303001140666488, 1188174906060439726, 1239907587651276930]

class RefreshStaffViewCelestial(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="View Raw List",
        style=discord.ButtonStyle.blurple,
        custom_id="rawcelestial",
        emoji="🗒️",
    )
    async def refreshstaffview(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        msg = ""
        for roleID in roles:
            role = interaction.guild.get_role(roleID)
            if "On Break" in role.name:
                roleMention = f"`--------------------------------`\n\n{role.mention}"
            else:
                roleMention = role.mention
            msg = f"{msg}\n{roleMention} *(x{len(role.members)})*\n"
            for member in role.members:
                msg = f"{msg}- {member.mention} `({member.id})`\n"

        embed = discord.Embed(
            title="Staff Roster",
            description=f"**The following list consists of all our official staff members:**\n{msg}",
            colour=0x46E1EC,
        )
        embed.set_image(url="https://media.discordapp.net/attachments/1152640894328127539/1199936623949926472/CelestialBanner.png")
        embed.set_footer(text='Click "View Raw List" if text looks like <@692254240290242601>')
        edited = await interaction.message.edit(embed=embed, view=RefreshStaffViewCelestial())

        message = f"{edited.embeds[0].title}\n{edited.embeds[0].description}"
        pattern = r"`.*?`"
        cleaned_message = re.sub(pattern, "", message, flags=re.DOTALL)
        await interaction.response.send_message(cleaned_message, ephemeral=True)

    @discord.ui.button(
        label="Refresh",
        style=discord.ButtonStyle.grey,
        custom_id="refreshcelestial",
        emoji="<:refresh:1048779043287351408>",
    )
    async def refreshtt(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        msg = ""
        for roleID in roles:
            role = interaction.guild.get_role(roleID)
            if "On Break" in role.name:
                roleMention = f"`--------------------------------`\n\n{role.mention}"
            else:
                roleMention = role.mention
            msg = f"{msg}\n{roleMention} *(x{len(role.members)})*\n"
            for member in role.members:
                msg = f"{msg}- {member.mention} `({member.id})`\n"

        embed = discord.Embed(
            title="Staff Roster",
            description=f"**The following list consists of all our official staff members:**\n{msg}",
            colour=0x46E1EC,
        )
        embed.set_image(url="https://media.discordapp.net/attachments/1152640894328127539/1199936623949926472/CelestialBanner.png")
        embed.set_footer(text='Click "View Raw List" if text looks like <@692254240290242601>')
        await interaction.message.edit(embed=embed, view=RefreshStaffViewCelestial())
        await interaction.response.send_message("<:refresh:1048779043287351408> The staff list is successfully refreshed!", ephemeral=True)

class LeaksAccessCelestial(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Genshin Leaks",
        style=discord.ButtonStyle.red,
        custom_id="genshinleaksaccesscelestial",
    )
    async def genshinleaksaccesscelestial(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        alreadyHave = False
        for role in interaction.user.roles:
            if "Access Genshin Leaks" == role.name:
                alreadyHave = True
        role = discord.utils.get(interaction.guild.roles, name="Access Genshin Leaks")
        if alreadyHave:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message(
                "You **no longer** have the <@&1324391617938985023> role, and you can no longer access Genshin Impact leaks.",
                ephemeral=True,
            )
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(
                "You have **obtained** the <@&1324391617938985023> role. You can now access Genshin Impact leaks at <#1261243694468698112> and discuss them at <#1383774520032100352>!",
                ephemeral=True,
            )

    @discord.ui.button(
        label="HSR Leaks",
        style=discord.ButtonStyle.red,
        custom_id="hsrleaksaccesscelestial",
    )
    async def hsrleaksaccesscelestial(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        alreadyHave = False
        for role in interaction.user.roles:
            if "Access HSR Leaks" == role.name:
                alreadyHave = True
        role = discord.utils.get(interaction.guild.roles, name="Access HSR Leaks")
        if alreadyHave:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message(
                "You **no longer** have the <@&1324391720040923258> role, and you can no longer access Honkai: Star Rail leaks.",
                ephemeral=True,
            )
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(
                "You have **obtained** the <@&1324391720040923258> role. You can now access Honkai: Star Rail leaks at <#1310928513876099143> and discuss them at <#1383774549497221261>!",
                ephemeral=True,
            )

    @discord.ui.button(
        label="WuWa Leaks",
        style=discord.ButtonStyle.red,
        custom_id="wuwaleaksaccesscelestial",
    )
    async def wuwaleaksaccesscelestial(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        alreadyHave = False
        for role in interaction.user.roles:
            if "Access WuWa Leaks" == role.name:
                alreadyHave = True
        role = discord.utils.get(interaction.guild.roles, name="Access WuWa Leaks")
        if alreadyHave:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message(
                "You **no longer** have the <@&1360288374027583580> role, and you can no longer access Wuthering Waves leaks.",
                ephemeral=True,
            )
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(
                "You have **obtained** the <@&1360288374027583580> role. You can now access Wuthering Waves leaks at <#1357905859791032630> and discuss them at <#1383774575069761547>!",
                ephemeral=True,
            )

class StaffRoster(commands.Cog):
    def __init__(self, bot):
        self.client = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.client.user or message.author.bot == True:
            return

        if message.guild.id == 1168706427435622410 and message.content == "-staff":
            msg = ""
            for roleID in roles:
                role = message.guild.get_role(roleID)
                if "On Break" in role.name:
                    roleMention = (
                        f"`--------------------------------`\n\n{role.mention}"
                    )
                else:
                    roleMention = role.mention
                msg = f"{msg}\n{roleMention} *(x{len(role.members)})*\n"
                for member in role.members:
                    msg = f"{msg}- {member.mention} `({member.id})`\n"
            embed = discord.Embed(
                title="Staff Roster",
                description=f"**The following list consists of all our official staff members:**\n{msg}",
                colour=0x46E1EC,
            )
            embed.set_image(
                url="https://media.discordapp.net/attachments/1152640894328127539/1199936623949926472/CelestialBanner.png"
            )
            embed.set_footer(
                text='Click "View Raw List" if text looks like <@692254240290242601>'
            )
            await message.channel.send(embed=embed, view=RefreshStaffViewCelestial())
        
        if message.guild.id == 1168706427435622410 and message.content == "-leaksaccess":
            await message.delete()
            embed = discord.Embed(
                title="<:Raidenjoy:995502902271545407> Select below to gain access to leaks-related channels!",
                description="By selecting the button(s), you acknowledge that leaked content remains unverified, subject to changes, and is against Hoyoverse's and/or Kuro Games' Terms of Service. We kindly request maintaining a respectful manner when discussing leaks. Please do not spread misinformation or share any unauthorized leaks, as it may result in a permanent removal of your access to the leaks channel.\n\n> **If you wish to remove your access to the leaks channel, you can simply click on the button(s) again.**",
                color=0x2B2C31,
            )
            await message.channel.send(embed=embed, view=LeaksAccessCelestial())

async def setup(bot):
    await bot.add_cog(StaffRoster(bot))
