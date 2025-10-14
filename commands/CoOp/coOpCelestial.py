import discord
import datetime
import random
import re

from firebase_admin import db
from discord.ext import commands
from enkapy import Enka

CO_OP_CHANNEL_ID = 1230900481023541258

async def closeCoOpRequest(interaction):
    match = re.search(r"<@(\d+)>", interaction.message.content)
    if match:
        userID = match.group(1)
    else:
        userID = " "
    if (
        str(userID) == str(interaction.user.id)
        or interaction.user.guild_permissions.administrator
    ):
        embed = interaction.message.embeds[0]
        content = interaction.message.content
        emote_pattern = r"<:[^:]+:[0-9]+>"
        modifiedContent = re.sub(emote_pattern, "<:yes:1036811164891480194>", content)
        modifiedContent = re.sub(
            r"is requesting for.*",
            "no longer needs co-op help. <:resolved:1364813186028797984>",
            modifiedContent,
        )
        modifiedContent = modifiedContent.replace("**", "")
        await interaction.response.edit_message(
            content=modifiedContent, embed=embed, view=CoOpViewResolved()
        )
    else:
        await interaction.response.send_message(
            "<:no:1036810470860013639> Only the user who requested for this help can perform this action.",
            ephemeral=True,
        )


class CoOpHelpModal(discord.ui.Modal):

    def __init__(self, title="Request Co-op Help", uid_default=None, wl_default=None):
        super().__init__(title=title, timeout=None)
        self.uid = discord.ui.TextInput(
            label="Your UID",
            style=discord.TextStyle.short,
            placeholder="Enter your UID",
            required=True,
            default=str(uid_default) if uid_default else "",
            max_length=10
        )
        self.wl = discord.ui.TextInput(
            label="Your World Level",
            style=discord.TextStyle.short,
            placeholder="Enter only a number",
            required=True,
            default=str(wl_default) if wl_default else "",
            max_length=1
        )
        self.runs = discord.ui.TextInput(
            label="Number of Runs",
            style=discord.TextStyle.short,
            placeholder="Enter only a number",
            required=True,
            max_length=2
        )
        self.request = discord.ui.TextInput(
            label="Your Help Request",
            style=discord.TextStyle.long,
            placeholder="What do you need help on?",
            required=True,
            max_length=2000
        )
        self.add_item(self.uid)
        self.add_item(self.wl)
        self.add_item(self.runs)
        self.add_item(self.request)

    async def on_submit(self, interaction: discord.Interaction):
        # Save the UID to Firebase
        user_id = str(interaction.user.id)
        uid_value = self.uid.value.strip()
        if uid_value:
            ref = db.reference("/Co-Op-UID")
            ref.child(user_id).update({'UID': uid_value})
                
        coop_channel = interaction.client.get_channel(CO_OP_CHANNEL_ID)
        if "NA" in self.title:
            helperRole = interaction.guild.get_role(1324388256166580294)
            embedTitle = "NA Region Co-op Request"
            embedColor = 0x6161F9
        elif "EU" in self.title:
            helperRole = interaction.guild.get_role(1324388110469042240)
            embedTitle = "EU Region Co-op Request"
            embedColor = 0x50C450
        elif "Asia" in self.title:
            helperRole = interaction.guild.get_role(1324388341566673007)
            embedTitle = "Asia Region Co-op Request"
            embedColor = 0xF96262
        elif "SAR" in self.title:
            helperRole = interaction.guild.get_role(1324388413163704363)
            embedTitle = "SAR Region Co-op Request"
            embedColor = 0xF7D31A

        embed = discord.Embed(
            description=f"### {embedTitle}\n-# - Coordinate with each other in the **thread** below\n-# - Click on **`Claim`** if you are intending to help. \n-# - If you are the requester and **no longer need help**, press **`Close`**.",
            color=embedColor,
        )
        embed.add_field(name="UID", value=f"> {self.uid.value}", inline=True)
        embed.add_field(name="World Level", value=f"> WL{self.wl.value}", inline=True)
        embed.add_field(name="Runs", value=f"> {self.runs.value} run{'s' if self.runs.value.isdigit() and int(self.runs.value) > 1 else ''}", inline=True)
        embed.add_field(name="Request", value=f"> {self.request.value}", inline=False)
        embed.set_footer(icon_url=interaction.guild.icon.url, text=interaction.guild.name)
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)

        emote = random.choice(
            ["<:yae_hi:1364813223307645000>", "<:lumine_hello:1364813205016412211>"]
        )
        msg = await coop_channel.send(
            content=f"**{emote} {interaction.user.mention} is requesting for co-op** - {helperRole.mention}",
            embed=embed,
            view=CoOpView(),
        )
        await msg.create_thread(
            name=f"{interaction.user.name} - {embedTitle}", auto_archive_duration=1440
        )
        await interaction.response.send_message(
            f"<:yes:1036811164891480194> [Co-op Request Sent]({msg.jump_url})!",
            ephemeral=True,
        )
        async for msge in interaction.channel.history(limit=10):
            if (
                msge.author == interaction.client.user
                and msge.embeds[0].title is not None
                and "Welcome to Genshin Impact co-op!" in msge.embeds[0].title
            ):
                await msge.delete()

        newembed = discord.Embed(
            title="Welcome to Genshin Impact co-op! 🎉",
            description=f"### Select a region below to request for co-op. \n\n- Type `thanks @user` in your threads to give a <a:cuteblossom:1180277907277492326> rep point per help request.\n- Users with **25+ rep** will earn the <@&1233873593268703292> role <:cuteribbon:1180277888168247316>\n- :new: **Auto saves your UID and WL. Faster and easier!**\n- *Getting annoyed by pings? Remove your co-op helper role [here](https://discord.com/channels/{interaction.guild.id}/customize-community)!*",
            color=0x09AEC5,
        )
        newembed.set_image(
            url="https://media.discordapp.net/attachments/957252297501577276/965133143365550090/unknown.png"
        )
        newembed.set_footer(
            text=f"{interaction.guild.name} • #{interaction.channel.name}",
            icon_url=interaction.guild.icon.url,
        )
        await interaction.channel.send(embed=newembed, view=CoOpButtonView())


class UnClaimButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Unclaim", style=discord.ButtonStyle.red, custom_id="unclaimcelestial"
    )
    async def unclaimcelestial(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        id = int(interaction.message.content.split("`")[1])
        ogMsg = await interaction.channel.fetch_message(id)
        embed = ogMsg.embeds[0]
        desc = embed.description
        if (
            f"<:yes:1036811164891480194> *Claimed by {interaction.user.mention}* \n"
            not in desc
        ):
            await interaction.response.send_message(
                content="<:no:1036810470860013639> You haven't claimed the request yet.",
                ephemeral=True,
            )
            return
        desc = desc.replace(
            f"<:yes:1036811164891480194> *Claimed by {interaction.user.mention}* \n", ""
        )
        embed.description = desc
        content = ogMsg.content
        await ogMsg.edit(content=content, embed=embed, view=CoOpView())
        thread = await interaction.guild.fetch_channel(id)
        await thread.send(f"{interaction.user.mention} unclaimed the request.")
        await interaction.response.send_message(
            content="<:yes:1036811164891480194> Unclaimed co-op request", ephemeral=True
        )


class CoOpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Claim", style=discord.ButtonStyle.green, custom_id="accepthelpcelestial"
    )
    async def accepthelpcelestial(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        thread = await interaction.guild.fetch_channel(interaction.message.id)
        match = re.search(r"<@(\d+)>", interaction.message.content)
        if match:
            userID = match.group(1)
        else:
            userID = " "
        if str(userID) == str(interaction.user.id):
            await interaction.response.send_message(
                "You want to help yourself? :joy:", ephemeral=True
            )
            return

        if str(interaction.user.id) in interaction.message.embeds[0].description:
            await interaction.response.send_message(
                f"You already claimed the request. Click below to unclaim.\n**ID:** `{interaction.message.id}`",
                view=UnClaimButton(),
                ephemeral=True,
            )
            return

        oldembed = interaction.message.embeds[0]
        if oldembed.description.count("Claimed by") >= 3:
            await interaction.response.send_message(
                "The maximum of 3 users have already claimed this request.",
                ephemeral=True,
            )
            return

        correct = False
        if "NA" in interaction.message.embeds[0].description:
            for role in interaction.user.roles:
                if role.id == 1324388256166580294:
                    correct = True
                    break
        elif "EU" in interaction.message.embeds[0].description:
            for role in interaction.user.roles:
                if role.id == 1324388110469042240:
                    correct = True
                    break
        elif "Asia" in interaction.message.embeds[0].description:
            for role in interaction.user.roles:
                if role.id == 1324388341566673007:
                    correct = True
                    break
        elif "SAR" in interaction.message.embeds[0].description:
            for role in interaction.user.roles:
                if role.id == 1324388413163704363:
                    correct = True
                    break
        if not (correct):
            await interaction.response.send_message(
                "**:warning: Warning:** You don't have the corresponding region co-op helper role, but you can still coordinate with the member. You can obtain the **region co-op helper roles** at <id:customize> if you haven't already done so!",
                ephemeral=True,
            )
            return

        await thread.send(f"Request claimed by {interaction.user.mention}. ")
        embed = interaction.message.embeds[0]
        newEmbedDescription = f"<:yes:1036811164891480194> *Claimed by {interaction.user.mention}* \n{embed.description}"
        embed.description = newEmbedDescription
        content = interaction.message.content
        await interaction.message.edit(content=content, embed=embed, view=CoOpView())
        await interaction.response.send_message(
            f"<:yes:1036811164891480194> **Request claimed.** Start discussing in {thread.mention}.\nID: `{interaction.message.id}`",
            view=UnClaimButton(),
            ephemeral=True,
        )

    @discord.ui.button(
        label="Close Request",
        style=discord.ButtonStyle.red,
        custom_id="closehelpcelestial",
    )
    async def closehelp(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await closeCoOpRequest(interaction)

    @discord.ui.button(
        label="Copy UID",
        style=discord.ButtonStyle.grey,
        custom_id="copyrawuidcelestial",
    )
    async def copyrawuid(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        uid = "".join(
            [
                char
                for char in str(interaction.message.embeds[0].fields[0])
                if char.isdigit()
            ]
        )
        await interaction.response.send_message(uid, ephemeral=True)


class CoOpViewResolved(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Co-op Resolved",
        style=discord.ButtonStyle.grey,
        custom_id="closehelpcelestial",
        disabled=True,
    )
    async def resolved(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        pass


class CoOpButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def fetch_uid_and_wl(self, interaction):
        user_id = str(interaction.user.id)
        ref = db.reference("/Co-Op-UID")
        try:
            uid = int(ref.child(user_id).get()['UID'])
        except Exception:
            uid = None
        
        wl = None
        if uid:
            try:
                client = Enka()
                await client.load_lang()
                user = await client.fetch_user(uid)
                wl = user.player.worldLevel
            except Exception as e:
                print(f"Error fetching Enka data: {e}")
                wl = None
        return uid, wl

    @discord.ui.button(label='NA', style=discord.ButtonStyle.blurple, custom_id='nacoopcelestial')
    async def na(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid, wl = await self.fetch_uid_and_wl(interaction)
        modal = CoOpHelpModal(
            title=f"Request Co-op Help - {button.label}",
            uid_default=uid,
            wl_default=str(wl) if wl is not None else None
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='EU', style=discord.ButtonStyle.blurple, custom_id='eucoopcelestial')
    async def eu(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid, wl = await self.fetch_uid_and_wl(interaction)
        modal = CoOpHelpModal(
            title=f"Request Co-op Help - {button.label}",
            uid_default=uid,
            wl_default=str(wl) if wl is not None else None
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='Asia', style=discord.ButtonStyle.blurple, custom_id='asiacoopcelestial')
    async def asia(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid, wl = await self.fetch_uid_and_wl(interaction)
        modal = CoOpHelpModal(
            title=f"Request Co-op Help - {button.label}",
            uid_default=uid,
            wl_default=str(wl) if wl is not None else None
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='SAR', style=discord.ButtonStyle.blurple, custom_id='sarcoopcelestial')
    async def sar(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid, wl = await self.fetch_uid_and_wl(interaction)
        modal = CoOpHelpModal(
            title=f"Request Co-op Help - {button.label}",
            uid_default=uid,
            wl_default=str(wl) if wl is not None else None
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(
        label="What are rep points?",
        style=discord.ButtonStyle.grey,
        custom_id="repsystemcoopcelestial",
    )
    async def howToUseCoOp(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        embed = discord.Embed(
            title="",
            description="### **After someone helps you in co-op, be sure to thank them by giving them <a:cuteblossom:1180277907277492326> reputations!**\n\n\n- You can use `-giverep @(user) (rep points)` or say `thanks @user`\n- **ONE <a:cuteblossom:1180277907277492326> reputation per help request ONLY**\n- You can use **`-rep`** to check your current reputations.\n- Users with **25+ rep** can earn the <@&1233873593268703292> role by creating a ticket <:cuteribbon:1180277888168247316>",
            color=0x1DC220,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class CoOpSendViewCelestial(commands.Cog):
    def __init__(self, bot):
        self.client = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.client.user or message.author.bot == True:
            return

        if message.content == "-cooppanel" and message.guild.id == 1168706427435622410:
            embed = discord.Embed(
                title="Welcome to Genshin Impact co-op! 🎉",
                description=f"### Select a region below to request for co-op. \n\n- Type `thanks @user` in your threads to give a <a:cuteblossom:1180277907277492326> rep point per help request.\n- Users with **25+ rep** will earn the <@&1233873593268703292> role <:cuteribbon:1180277888168247316>\n- *Getting annoyed by pings? Remove your co-op helper role [here](https://discord.com/channels/{message.guild.id}/customize-community)!*",
                color=0x09AEC5,
            )
            embed.set_image(
                url="https://media.discordapp.net/attachments/957252297501577276/965133143365550090/unknown.png"
            )
            embed.set_footer(
                text=f"{message.guild.name} • #{message.channel.name}",
                icon_url=message.guild.icon.url,
            )
            await message.channel.send(embed=embed, view=CoOpButtonView())


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CoOpSendViewCelestial(bot))
