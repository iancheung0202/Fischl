import discord
import datetime
import random
import re

from discord.ext import commands

CO_OP_CHANNEL_ID = 1242625641669595156

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
        modifiedContent = re.sub(emote_pattern, "✅", content)
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
            ":x: Only the user who requested for this help can perform this action.",
            ephemeral=True,
        )


class CoOpHelpModalWuwa(discord.ui.Modal, title="Request Co-op Help"):

    uid = discord.ui.TextInput(
        label="Your UID",
        style=discord.TextStyle.short,
        placeholder="Your UID",
        required=True,
    )
    wl = discord.ui.TextInput(
        label="Your Union Level",
        style=discord.TextStyle.short,
        placeholder="Your union level",
        required=True,
    )
    request = discord.ui.TextInput(
        label="Your Help Request",
        style=discord.TextStyle.long,
        placeholder="What do you need help on?",
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        coop_channel = interaction.client.get_channel(CO_OP_CHANNEL_ID)
        if "NA" in self.title:
            helperRole = interaction.guild.get_role(1243801662682955818)
            embedTitle = "NA Region Co-op Request"
            embedColor = 0x6161F9
        elif "EU" in self.title:
            helperRole = interaction.guild.get_role(1243801705666183271)
            embedTitle = "EU Region Co-op Request"
            embedColor = 0x50C450
        elif "Asia" in self.title:
            helperRole = interaction.guild.get_role(1243801752508170313)
            embedTitle = "Asia Region Co-op Request"
            embedColor = 0xF96262
        elif "SEA" in self.title:
            helperRole = interaction.guild.get_role(1243801803032760320)
            embedTitle = "SEA Region Co-op Request"
            embedColor = 0xD935FD
        elif "HMT" in self.title:
            helperRole = interaction.guild.get_role(1243801856879235112)
            embedTitle = "HMT Region Co-op Request"
            embedColor = 0xF7D31A

        embed = discord.Embed(
            description=f"### {embedTitle}\n-# - Coordinate with each other in the **thread** below\n-# - Click on **`Claim`** if you are intending to help. \n-# - If you are the requester and **no longer need help**, press **`Close`**.",
            color=embedColor,
        )
        embed.add_field(name="UID", value=f"> {str(self.uid)}", inline=True)
        embed.add_field(name="World Level", value=f"> WL{str(self.wl)}", inline=True)
        embed.add_field(name="Request", value=str(self.request), inline=False)
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)

        emote = random.choice(
            ["<:yae_hi:1364813223307645000>", "<:lumine_hello:1364813205016412211>"]
        )
        msg = await coop_channel.send(
            content=f"**{emote} {interaction.user.mention} is requesting for co-op** - {helperRole.mention}",
            embed=embed,
            view=CoOpViewWuwa(),
        )
        await msg.create_thread(
            name=f"{interaction.user.name} - {embedTitle}", auto_archive_duration=1440
        )
        await interaction.response.send_message(
            f"[Co-op Request Sent ✅]({msg.jump_url})", ephemeral=True
        )
        async for msge in interaction.channel.history(limit=5):
            if (
                msge.author == interaction.client.user
                and msge.embeds[0].title is not None
                and "Welcome to Wuthering Waves co-op!" in msge.embeds[0].title
            ):
                await msge.delete()

        newembed = discord.Embed(
            title="Welcome to Wuthering Waves co-op! 🎉",
            description=f"### Select a region below to request for co-op. \n\n- Type `thanks @user` in your threads to give a <a:cuteblossom:1180277907277492326> rep point per help request.\n- *Getting annoyed by pings? Remove your co-op helper role [here](https://discord.com/channels/1197491630807199834/1197491632841429029)!*",
            color=0x09AEC5,
        )
        newembed.set_image(
            url="https://media.discordapp.net/attachments/957252297501577276/965133143365550090/unknown.png"
        )
        newembed.set_footer(
            text=f"{interaction.guild.name} • #{interaction.channel.name}",
            icon_url=interaction.guild.icon.url,
        )
        await interaction.channel.send(embed=newembed, view=CoOpButtonViewWuwa())


class UnClaimButtonWuwa(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Unclaim", style=discord.ButtonStyle.red, custom_id="unclaimwuwa"
    )
    async def unclaimwuwa(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        id = int(interaction.message.content.split("`")[1])
        ogMsg = await interaction.channel.fetch_message(id)
        embed = ogMsg.embeds[0]
        desc = embed.description
        if f":star: *Claimed by {interaction.user.mention}* \n" not in desc:
            await interaction.response.send_message(
                content=":x: You haven't claimed the request yet.", ephemeral=True
            )
            return
        desc = desc.replace(f":star: *Claimed by {interaction.user.mention}* \n", "")
        embed.description = desc
        content = ogMsg.content
        await ogMsg.edit(content=content, embed=embed, view=CoOpViewWuwa())
        thread = await interaction.guild.fetch_channel(id)
        await thread.send(f"{interaction.user.mention} unclaimed the request.")
        await interaction.response.send_message(
            content="✅ Unclaimed co-op request", ephemeral=True
        )


class CoOpViewWuwa(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Claim", style=discord.ButtonStyle.green, custom_id="accepthelpwuwa"
    )
    async def accepthelpwuwa(
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
                view=UnClaimButtonWuwa(),
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
        newEmbedDescription = (
            f":star: *Claimed by {interaction.user.mention}* \n{embed.description}"
        )
        embed.description = newEmbedDescription
        content = interaction.message.content
        await interaction.message.edit(
            content=content, embed=embed, view=CoOpViewWuwa()
        )
        await interaction.response.send_message(
            f"✅ **Request claimed.** Start discussing in {thread.mention}.\nID: `{interaction.message.id}`",
            view=UnClaimButtonWuwa(),
            ephemeral=True,
        )

    @discord.ui.button(
        label="Close Request", style=discord.ButtonStyle.red, custom_id="closehelpwuwa"
    )
    async def closehelp(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await closeCoOpRequest(interaction)

    @discord.ui.button(
        label="Copy Raw UID", style=discord.ButtonStyle.grey, custom_id="copyrawuidwuwa"
    )
    async def copyrawuid(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        uid = "".join([char for char in str(interaction.message.embeds[0].fields[0]) if char.isdigit()])
        await interaction.response.send_message(uid, ephemeral=True)


class CoOpViewResolved(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Co-op Resolved",
        style=discord.ButtonStyle.grey,
        custom_id="closehelpwuwa",
        disabled=True,
    )
    async def resolved(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        pass


class CoOpButtonViewWuwa(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="NA", style=discord.ButtonStyle.blurple, custom_id="nacoopwuwa"
    )
    async def na(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            CoOpHelpModalWuwa(title=f"Request Co-op Help - {str(button.label)}")
        )

    @discord.ui.button(
        label="EU", style=discord.ButtonStyle.blurple, custom_id="eucoopwuwa"
    )
    async def eu(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            CoOpHelpModalWuwa(title=f"Request Co-op Help - {str(button.label)}")
        )

    @discord.ui.button(
        label="Asia", style=discord.ButtonStyle.blurple, custom_id="asiacoopwuwa"
    )
    async def asia(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            CoOpHelpModalWuwa(title=f"Request Co-op Help - {str(button.label)}")
        )

    @discord.ui.button(
        label="SEA", style=discord.ButtonStyle.blurple, custom_id="seacoopwuwa"
    )
    async def sea(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            CoOpHelpModalWuwa(title=f"Request Co-op Help - {str(button.label)}")
        )

    @discord.ui.button(
        label="HMT", style=discord.ButtonStyle.blurple, custom_id="hmtcoopwuwa"
    )
    async def hmt(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            CoOpHelpModalWuwa(title=f"Request Co-op Help - {str(button.label)}")
        )

    @discord.ui.button(
        label="What are rep points?",
        style=discord.ButtonStyle.grey,
        custom_id="repsystemcoopwuwa",
    )
    async def howToUseCoOp(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        embed = discord.Embed(
            title="",
            description="### **After someone helps you in co-op, be sure to thank them by giving them <a:cuteblossom:1180277907277492326> reputations!**\n\n\n- You can use `-giverep @(user) (rep points)` or say `thanks @user`\n- **ONE <a:cuteblossom:1180277907277492326> reputation per help request ONLY**\n- You can use **`-rep`** to check your current reputations.",
            color=0x1DC220,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class CoOpSendViewWuwa(commands.Cog):
    def __init__(self, bot):
        self.client = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.client.user or message.author.bot == True:
            return

        if message.content == "-cooppanel" and message.guild.id == 1197491630807199834:
            embed = discord.Embed(
                title="Welcome to Wuthering Waves co-op! 🎉",
                description=f"### Select a region below to request for co-op. \n\n- Type `thanks @user` in your threads to give a <a:cuteblossom:1180277907277492326> rep point per help request.\n- *Getting annoyed by pings? Remove your co-op helper role [here](https://discord.com/channels/1197491630807199834/1197491632841429029)!*",
                color=0x09AEC5,
            )
            embed.set_image(
                url="https://media.discordapp.net/attachments/957252297501577276/965133143365550090/unknown.png"
            )
            embed.set_footer(
                text=f"{message.guild.name} • #{message.channel.name}",
                icon_url=message.guild.icon.url,
            )
            await message.channel.send(embed=embed, view=CoOpButtonViewWuwa())


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CoOpSendViewWuwa(bot))
