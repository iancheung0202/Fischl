import discord
import datetime
import random
import re

from firebase_admin import db
from discord import app_commands
from discord.ext import commands
from enkapy import Enka

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
            r"is requesting for.*", "no longer needs co-op help. <:resolved:1364813186028797984>", modifiedContent
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
        
        ref = db.reference("/Co-Op")
        coop = ref.get()
        for key, value in coop.items():
            if value["Server ID"] == interaction.guild.id:
                CO_OP_CHANNEL_ID = value["Co-op Channel ID"]
                NA_HELPER_ROLE_ID = value["NA Helper Role ID"]
                EU_HELPER_ROLE_ID = value["EU Helper Role ID"]
                ASIA_HELPER_ROLE_ID = value["Asia Helper Role ID"]
                SAR_HELPER_ROLE_ID = value["SAR Helper Role ID"]
                break

        coop_channel = interaction.client.get_channel(CO_OP_CHANNEL_ID)
        if "NA" in self.title:
            helperRole = interaction.guild.get_role(NA_HELPER_ROLE_ID)
            embedTitle = "NA Region Co-op Request"
            embedColor = 0x6161F9
        elif "EU" in self.title:
            helperRole = interaction.guild.get_role(EU_HELPER_ROLE_ID)
            embedTitle = "EU Region Co-op Request"
            embedColor = 0x50C450
        elif "Asia" in self.title:
            helperRole = interaction.guild.get_role(ASIA_HELPER_ROLE_ID)
            embedTitle = "Asia Region Co-op Request"
            embedColor = 0xF96262
        elif "SAR" in self.title:
            helperRole = interaction.guild.get_role(SAR_HELPER_ROLE_ID)
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
        try:
            embed.set_footer(icon_url=interaction.guild.icon.url, text=interaction.guild.name)
        except Exception:
            embed.set_footer(text=interaction.guild.name)
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)

        emote = random.choice(["<:yae_hi:1364813223307645000>", "<:lumine_hello:1364813205016412211>"])
        msg = await coop_channel.send(
            content=f"**{emote} {interaction.user.mention} is requesting for co-op** - {helperRole.mention}",
            embed=embed,
            view=CoOpView(),
        )
            
        await interaction.response.send_message(
            f"<:yes:1036811164891480194> [Co-op Request Sent]({msg.jump_url})",
            ephemeral=True,
        )
        thread = await msg.create_thread(
            name=f"{interaction.user.name} - {embedTitle}", auto_archive_duration=1440
        )
        
        ref = db.reference("/Co-Op Sticky Panel")
        stickies = ref.get()
        try:
            for key, val in stickies.items():
                if val["Channel ID"] == interaction.channel.id:
                    try:
                        oldMsg = await interaction.channel.fetch_message(
                            val["Message ID"]
                        )
                        await oldMsg.delete()
                    except Exception:
                        pass
                    db.reference("/Co-Op Sticky Panel").child(key).delete()
                    newMsg = await interaction.channel.send(
                        oldMsg.content,
                        embed=oldMsg.embeds[0],
                        view=CoOpButtonViewSystem(),
                    )

                    data = {
                        interaction.channel.id: {
                            "Channel ID": interaction.channel.id,
                            "Message ID": newMsg.id,
                        }
                    }

                    for key, value in data.items():
                        ref.push().set(value)
                    break
        except Exception as e:
            print(e)


class UnClaimButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Unclaim", style=discord.ButtonStyle.red, custom_id="unclaimsystem"
    )
    async def unclaimsystem(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        id = int(interaction.message.content.split("`")[1])
        ogMsg = await interaction.channel.fetch_message(id)
        embed = ogMsg.embeds[0]
        desc = embed.description
        if f"<:yes:1036811164891480194> *Claimed by {interaction.user.mention}* \n" not in desc:
            await interaction.response.send_message(
                content="<:no:1036810470860013639> You haven't claimed the request yet.", ephemeral=True
            )
            return
        desc = desc.replace(f"<:yes:1036811164891480194> *Claimed by {interaction.user.mention}* \n", "")
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
        label="Claim", style=discord.ButtonStyle.green, custom_id="accepthelpsystem"
    )
    async def accepthelpsystem(
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
                f"**You already claimed the request.** Click below to unclaim.\nID: `{interaction.message.id}`",
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

        ref = db.reference("/Co-Op")
        coop = ref.get()
        for key, value in coop.items():
            if value["Server ID"] == interaction.guild.id:
                NA_HELPER_ROLE_ID = value["NA Helper Role ID"]
                EU_HELPER_ROLE_ID = value["EU Helper Role ID"]
                ASIA_HELPER_ROLE_ID = value["Asia Helper Role ID"]
                SAR_HELPER_ROLE_ID = value["SAR Helper Role ID"]
                break

        correct = False
        if "NA" in interaction.message.embeds[0].description:
            for role in interaction.user.roles:
                if role.id == NA_HELPER_ROLE_ID:
                    correct = True
                    break
        elif "EU" in interaction.message.embeds[0].description:
            for role in interaction.user.roles:
                if role.id == EU_HELPER_ROLE_ID:
                    correct = True
                    break
        elif "Asia" in interaction.message.embeds[0].description:
            for role in interaction.user.roles:
                if role.id == ASIA_HELPER_ROLE_ID:
                    correct = True
                    break
        elif "SAR" in interaction.message.embeds[0].description:
            for role in interaction.user.roles:
                if role.id == SAR_HELPER_ROLE_ID:
                    correct = True
                    break
                    
        # LIYUE HARBOR: CARRY COMMITTEE
        if interaction.guild.id == 1073116154798809098:
            for role in interaction.user.roles:
                if role.id == 1145946099270549535:
                    correct = True
                    break
                    
        if not (correct):
            await interaction.response.send_message(
                "**<:no:1036810470860013639> Warning:** You cannot claim the request because you don't have the corresponding region co-op helper role. You can still coordinate with the member in the thread though.",
                ephemeral=True,
            )
            return

        await thread.send(f"Request claimed by {interaction.user.mention}. ")
        embed = interaction.message.embeds[0]
        newEmbedDescription = (
            f"<:yes:1036811164891480194> *Claimed by {interaction.user.mention}* \n{embed.description}"
        )
        embed.description = newEmbedDescription
        content = interaction.message.content
        await interaction.message.edit(content=content, embed=embed, view=CoOpView())
        await interaction.response.send_message(
            f"<:yes:1036811164891480194> **Request claimed.** Start discussing in {thread.mention}.\nID: `{interaction.message.id}`",
            view=UnClaimButton(),
            ephemeral=True,
        )

    @discord.ui.button(
        label="Close", style=discord.ButtonStyle.red, custom_id="closehelpsystem"
    )
    async def closehelp(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await closeCoOpRequest(interaction)

    @discord.ui.button(
        label="Copy UID",
        style=discord.ButtonStyle.grey,
        custom_id="copyrawuidsystem",
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
        custom_id="closehelpsystem",
        disabled=True,
    )
    async def resolved(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        pass


class CoOpButtonViewSystem(discord.ui.View):
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

    @discord.ui.button(
        label="NA", style=discord.ButtonStyle.blurple, custom_id="nasystem"
    )
    async def na(self, interaction: discord.Interaction, button: discord.ui.Button):
        ref = db.reference("/Co-Op")
        coop = ref.get()
        found = False
        for key, value in coop.items():
            if value["Server ID"] == interaction.guild.id:
                found = True
                break
        if not found:
            embed = discord.Embed(
                title="Co-op system not enabled!",
                description=f"This server doesn't have the co-op system enabled yet. Please ask the server admin to use </co-op setup:1254927191037317149> to setup the system!",
                colour=0xFF0000,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        uid, wl = await self.fetch_uid_and_wl(interaction)
        modal = CoOpHelpModal(
            title=f"Request Co-op Help - {button.label}",
            uid_default=uid,
            wl_default=str(wl) if wl is not None else None
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(
        label="EU", style=discord.ButtonStyle.blurple, custom_id="eusystem"
    )
    async def eu(self, interaction: discord.Interaction, button: discord.ui.Button):
        ref = db.reference("/Co-Op")
        coop = ref.get()
        found = False
        for key, value in coop.items():
            if value["Server ID"] == interaction.guild.id:
                found = True
                break
        if not found:
            embed = discord.Embed(
                title="Co-op system not enabled!",
                description=f"This server doesn't have the co-op system enabled yet. Please ask the server admin to use </co-op setup:1254927191037317149> to setup the system!",
                colour=0xFF0000,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        uid, wl = await self.fetch_uid_and_wl(interaction)
        modal = CoOpHelpModal(
            title=f"Request Co-op Help - {button.label}",
            uid_default=uid,
            wl_default=str(wl) if wl is not None else None
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(
        label="Asia", style=discord.ButtonStyle.blurple, custom_id="asiasystem"
    )
    async def asia(self, interaction: discord.Interaction, button: discord.ui.Button):
        ref = db.reference("/Co-Op")
        coop = ref.get()
        found = False
        for key, value in coop.items():
            if value["Server ID"] == interaction.guild.id:
                found = True
                break
        if not found:
            embed = discord.Embed(
                title="Co-op system not enabled!",
                description=f"This server doesn't have the co-op system enabled yet. Please ask the server admin to use </co-op setup:1254927191037317149> to setup the system!",
                colour=0xFF0000,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        uid, wl = await self.fetch_uid_and_wl(interaction)
        modal = CoOpHelpModal(
            title=f"Request Co-op Help - {button.label}",
            uid_default=uid,
            wl_default=str(wl) if wl is not None else None
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(
        label="SAR", style=discord.ButtonStyle.blurple, custom_id="sarsystem"
    )
    async def sar(self, interaction: discord.Interaction, button: discord.ui.Button):
        ref = db.reference("/Co-Op")
        coop = ref.get()
        found = False
        for key, value in coop.items():
            if value["Server ID"] == interaction.guild.id:
                found = True
                break
        if not found:
            embed = discord.Embed(
                title="Co-op system not enabled!",
                description=f"This server doesn't have the co-op system enabled yet. Please ask the server admin to use </co-op setup:1254927191037317149> to setup the system!",
                colour=0xFF0000,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        uid, wl = await self.fetch_uid_and_wl(interaction)
        modal = CoOpHelpModal(
            title=f"Request Co-op Help - {button.label}",
            uid_default=uid,
            wl_default=str(wl) if wl is not None else None
        )
        await interaction.response.send_modal(modal)


class CoOpRepEnableView(discord.ui.View):
    def __init__(self):
        super().__init__()

    @discord.ui.button(
        label="Enable/Edit Reputation System",
        style=discord.ButtonStyle.green,
        custom_id="enable_rep_system",
    )
    async def enable_rep_system(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        enableModal = CoOpRepEnableModal()
        await interaction.response.send_modal(enableModal)
        response = await enableModal.wait()

        if enableModal.embed is not None:
            await interaction.edit_original_response(embed=enableModal.embed)

        await enableModal.on_submit_interaction.response.send_message(
            "Updated", ephemeral=True
        )

    @discord.ui.button(
        label="Disable Reputation System",
        style=discord.ButtonStyle.red,
        custom_id="disable_rep_system",
    )
    async def disable_rep_system(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        ref = db.reference("/Global Reps System")
        coop = ref.get()
        found = False

        if coop:
            for key, value in coop.items():
                if value["Server ID"] == interaction.guild.id:
                    db.reference("/Global Reps System").child(key).delete()
                    found = True
                    break

        if found:
            embed = discord.Embed(
                title="Reputation System Disabled",
                description="The reputation system has been successfully disabled for this server.",
                color=0xFF0000,
            )
            await interaction.response.edit_message(embed=embed)
        else:
            embed = discord.Embed(
                title="Reputation System Not Enabled",
                description="This server does not have the reputation system enabled. No changes were made.",
                color=0xFF0000,
            )
            await interaction.response.edit_message(embed=embed)

    @discord.ui.button(
        label="Add Reward",
        style=discord.ButtonStyle.green,
        custom_id="addrepreward",
        row=1,
    )
    async def addrepreward(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        coop_ref = db.reference("/Co-Op")
        coop = coop_ref.get()
        rep_ref = db.reference("/Global Reps System")
        rep_system = rep_ref.get()

        coop_enabled = False
        rep_enabled = False

        if coop:
            for key, value in coop.items():
                if value["Server ID"] == interaction.guild.id:
                    coop_enabled = True
                    break

        if rep_system:
            for key, value in rep_system.items():
                if value["Server ID"] == interaction.guild.id:
                    max_rep = value["Max Rep"]
                    rep_enabled = True
                    break

        if coop_enabled and rep_enabled:
            addRewardModel = AddRewardModel(title="Add a Custom Reward")
            await interaction.response.send_modal(addRewardModel)
            response = await addRewardModel.wait()
            embed = discord.Embed(
                title="Reputation System",
                description=f"The reputation system is enabled. Users can only give a maximum of `{max_rep}` reputation points at once.",
                color=discord.Color.blurple(),
            )
            shop_lines = []
            if addRewardModel.roles is not None and not isinstance(
                addRewardModel.roles, str
            ):
                for idx, (role_id, cost) in enumerate(
                    sorted(addRewardModel.roles.items(), key=lambda x: x[1]), start=1
                ):
                    line = f"{idx}. <@&{role_id}> • {cost} reps \n"
                    shop_lines.append(line)
                shop = "".join(shop_lines)
            else:
                shop = "None"
            embed.add_field(name="Roles", value=str(shop), inline=False)
            await interaction.edit_original_response(
                embed=embed, view=CoOpRepEnableView()
            )
            await addRewardModel.on_submit_interaction.response.send_message(
                embed=addRewardModel.update, ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "<:no:1036810470860013639> Both co-op and reputation systems must be enabled to add a reward.",
                ephemeral=True,
            )

    @discord.ui.button(
        label="Remove Reward",
        style=discord.ButtonStyle.red,
        custom_id="removerepreward",
        row=1,
    )
    async def removerepreward(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        coop_ref = db.reference("/Co-Op")
        coop = coop_ref.get()
        rep_ref = db.reference("/Global Reps System")
        rep_system = rep_ref.get()

        coop_enabled = False
        rep_enabled = False

        if coop:
            for key, value in coop.items():
                if value["Server ID"] == interaction.guild.id:
                    coop_enabled = True
                    break

        if rep_system:
            for key, value in rep_system.items():
                if value["Server ID"] == interaction.guild.id:
                    rep_enabled = True
                    max_rep = value["Max Rep"]
                    break

        if coop_enabled and rep_enabled:
            removeRewardModel = RemoveRewardModel(title="Remove a Custom Reward")
            await interaction.response.send_modal(removeRewardModel)
            response = await removeRewardModel.wait()
            embed = discord.Embed(
                title="Reputation System",
                description=f"The reputation system is enabled. Users can only give a maximum of `{max_rep}` reputation points at once.",
                color=discord.Color.blurple(),
            )
            shop_lines = []
            if removeRewardModel.roles is not None and not isinstance(
                removeRewardModel.roles, str
            ):
                for idx, (role_id, cost) in enumerate(
                    sorted(removeRewardModel.roles.items(), key=lambda x: x[1]), start=1
                ):
                    line = f"{idx}. <@&{role_id}> • {cost} reps \n"
                    shop_lines.append(line)
                shop = "".join(shop_lines)
            else:
                shop = "None"
            embed.add_field(name="Roles", value=str(shop), inline=False)
            await interaction.edit_original_response(
                embed=embed, view=CoOpRepEnableView()
            )
            await removeRewardModel.on_submit_interaction.response.send_message(
                embed=removeRewardModel.update, ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "<:no:1036810470860013639> Both co-op and reputation systems must be enabled to remove a reward.",
                ephemeral=True,
            )


class AddRewardModel(discord.ui.Modal, title="Add a Custom Reward"):
    role_id = discord.ui.TextInput(
        label="Role ID",
        style=discord.TextStyle.short,
        placeholder="Enter the role ID",
        required=True,
        max_length=50,
    )
    cost = discord.ui.TextInput(
        label="Cost of Reward",
        style=discord.TextStyle.short,
        placeholder="Must be a reasonable integer",
        required=True,
        max_length=10,
    )

    async def on_submit(self, interaction: discord.Interaction):
        ref = db.reference("/Global Reps System")
        coop = ref.get()
        found = False
        server_key = None
        server_roles = {}

        try:
            import json

            for key, val in coop.items():
                if str(val["Server ID"]) == str(interaction.guild.id):
                    server_key = key
                    server_roles = val.get("Roles", {})
                    if isinstance(server_roles, str):
                        try:
                            server_roles = json.loads(server_roles)
                        except json.JSONDecodeError:
                            server_roles = {}
                    found = True
                    break

        except Exception:
            pass

        if not found:
            self.update = discord.Embed(
                description="Reputation system is not enabled for this server yet. Please enable it first.",
                color=discord.Color.red(),
            )
            self.on_submit_interaction = interaction
            self.stop()
            return

        try:
            cost = int(self.cost.value)
        except ValueError:
            self.update = discord.Embed(
                description="Cost must be a valid integer.",
                color=discord.Color.red(),
            )
            self.on_submit_interaction = interaction
            self.stop()
            return

        role_id = self.role_id.value.strip()
        if role_id in server_roles:
            self.update = discord.Embed(
                description="This role ID already exists as a reward in this server.",
                color=discord.Color.red(),
            )
            self.on_submit_interaction = interaction
            self.stop()
            return

        server_roles[role_id] = cost
        ref.child(server_key).update({"Roles": server_roles})

        self.update = discord.Embed(
            description=f"Added reward for role ID: `{role_id}` with a cost of {cost} reputation points.",
            color=discord.Color.green(),
        )
        self.roles = server_roles
        self.on_submit_interaction = interaction
        self.stop()


class RemoveRewardModel(discord.ui.Modal, title="Remove a Custom Reward"):
    role_id = discord.ui.TextInput(
        label="Role ID",
        style=discord.TextStyle.short,
        placeholder="Enter the role ID to remove",
        required=True,
        max_length=50,
    )

    async def on_submit(self, interaction: discord.Interaction):
        ref = db.reference("/Global Reps System")
        coop = ref.get()
        found = False
        server_key = None

        server_roles = {}
        try:
            import json

            for key, val in coop.items():
                if val["Server ID"] == interaction.guild.id:
                    server_roles = val.get("Roles", {})
                    if isinstance(server_roles, str):
                        try:
                            server_roles = json.loads(server_roles)
                        except json.JSONDecodeError:
                            server_roles = {}
                    server_key = key
                    found = True
                    break
        except Exception:
            pass

        if not found or not server_roles:
            self.update = discord.Embed(
                description="No rewards found for this server.",
                color=discord.Color.red(),
            )
            self.on_submit_interaction = interaction
            self.stop()
            return

        role_id = str(self.role_id)
        if role_id not in server_roles:
            self.update = discord.Embed(
                description="Role ID not found as a reward.",
                color=discord.Color.red(),
            )
            self.on_submit_interaction = interaction
            self.stop()
            return

        del server_roles[role_id]

        if not server_roles:
            server_roles = "None"

        ref.child(server_key).update({"Roles": server_roles})

        self.update = discord.Embed(
            description=f"Removed reward for role ID: `{role_id}`.",
            color=discord.Color.green(),
        )
        self.roles = server_roles
        self.on_submit_interaction = interaction
        self.stop()


class CoOpRepEnableModal(discord.ui.Modal, title="Enable/Edit Reputation System"):

    maxrep = discord.ui.TextInput(
        label="Maximum Reputation Points",
        style=discord.TextStyle.short,
        placeholder="Max reps at once (default: 999)",
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction):
        if str(self.maxrep):
            try:
                max_rep = int(str(self.maxrep))
            except ValueError:
                await interaction.response.send_message(
                    "Invalid input for maximum reputation. Please enter a valid integer.",
                    ephemeral=True,
                )
                return
        else:
            max_rep = 999  # Default value

        ref = db.reference("/Global Reps System")
        coop = ref.get()
        found = False
        roles = "None"
        if coop:
            for key, value in coop.items():
                if value["Server ID"] == interaction.guild.id:
                    roles = value["Roles"]
                    ref.child(key).update({"Max Rep": max_rep})
                    found = True
                    embed = discord.Embed(
                        title="Reputation System Updated",
                        description=f"The reputation system is updated with a maximum of `{max_rep}` reputation points.",
                        color=discord.Color.yellow(),
                    )
                    shop_lines = []
                    if roles is not None and not isinstance(roles, str):
                        for idx, (role_id, cost) in enumerate(
                            sorted(roles.items(), key=lambda x: x[1]), start=1
                        ):
                            line = f"{idx}. <@&{role_id}> • {cost} reps \n"
                            shop_lines.append(line)
                        shop = "".join(shop_lines)
                    else:
                        shop = "None"
                    embed.add_field(name="Roles", value=str(shop), inline=False)
                    self.embed = embed

        if not found:
            data = {
                interaction.guild.id: {
                    "Server ID": interaction.guild.id,
                    "Max Rep": max_rep,
                    "Roles": "None", 
                }
            }
            for key, value in data.items():
                ref.push().set(value)

            embed = discord.Embed(
                title="Reputation System Enabled",
                description=f"The reputation system is enabled. Users can only give a maximum of `{max_rep}` reputation points at once.",
                color=discord.Color.green(),
            )
            embed.add_field(name="Roles", value=str(roles), inline=False)
            self.embed = embed

        self.on_submit_interaction = interaction
        self.stop()


@app_commands.guild_only()
class CoOp(commands.GroupCog, name="co-op"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(
        name="disable", description="Disable co-op system in this server"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def coop_disable(self, interaction: discord.Interaction) -> None:
        coop = db.reference("/Co-Op").get()
        found = False
        for key, val in coop.items():
            if val["Server ID"] == interaction.guild.id:
                db.reference("/Co-Op").child(key).delete()
                found = True
                break
        if found:
            embed = discord.Embed(
                title="Co-op system successfully disabled",
                description=f"You can use </co-op setup:1254927191037317149> at anytime to setup the co-op system again.",
                colour=0xFFFF00,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(embed=embed)
        else:
            embed = discord.Embed(
                title="We could not find your server",
                description=f"Maybe you have already disabled the co-op system in your server, or you have never enabled co-op system in the first place. Anyways, no records found in our system.",
                colour=0xFF0000,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(embed=embed, ephemeral=True)
    @coop_disable.error
    async def coop_disable_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)

    @app_commands.command(
        name="panel", description="Creates a customized co-op request panel"
    )
    @app_commands.describe(
        is_sticky_panel="Want the panel to always be the last message in this channel?",
        message="The content of the message",
        title="Makes the title of the embed",
        description="Makes the description of the embed",
        color="Sets the color of the embed",
        thumbnail="Please provide a URL for the thumbnail of the embed (upper-right hand corner image)",
        image="Please provide a URL for the image of the embed (appears at the bottom of the embed)",
        footer="Sets the footer of the embed that appears at the bottom of the embed as small texts",
        footer_icon="Shows server icon in the footer of the embed? (Must have footer text first)",
        footer_time="Shows the time of the embed being sent?",
    )
    @app_commands.checks.bot_has_permissions(create_public_threads=True, send_messages_in_threads=True)
    @app_commands.checks.has_permissions(manage_messages=True, manage_guild=True)
    async def coop_panel(
        self,
        interaction: discord.Interaction,
        is_sticky_panel: bool,
        message: str = None,
        title: str = None,
        description: str = None,
        color: str = None,
        thumbnail: str = None,
        image: str = None,
        footer: str = None,
        footer_icon: str = None,
        footer_time: bool = None,
    ) -> None:
        embed = None
        if color is not None:
            try:
                color = await commands.ColorConverter().convert(interaction, color)
            except:
                color = None
        if color is None:
            color = discord.Color.default()
        if title is not None or description is not None:
            embed = discord.Embed(color=color)
        if title is not None:
            embed.title = title
        if description is not None:
            embed.description = description
        if thumbnail is not None:
            embed.set_thumbnail(url=thumbnail)
        if image is not None:
            embed.set_image(url=image)
        if footer is not None:
            if footer_icon is not None:
                embed.set_footer(text=footer, icon_url=interaction.guild.icon.url)
            else:
                embed.set_footer(text=footer)
        if footer_time is not None or footer_time == True:
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        msgContent = ""
        if message is not None:
            msgContent = message
        newMsg = await interaction.channel.send(
            content=msgContent, embed=embed, view=CoOpButtonViewSystem()
        )
        if is_sticky_panel:
            ref = db.reference("/Co-Op Sticky Panel")
            stickies = ref.get()
            try:
                for key, val in stickies.items():
                    if val["Channel ID"] == interaction.channel.id:
                        try:
                            oldMsg = await interaction.channel.fetch_message(
                                val["Message ID"]
                            )
                            await oldMsg.delete()
                        except Exception:
                            pass
                        db.reference("/Co-Op Sticky Panel").child(key).delete()
                        break
            except Exception:
                pass

            data = {
                interaction.channel.id: {
                    "Channel ID": interaction.channel.id,
                    "Message ID": newMsg.id,
                }
            }

            for key, value in data.items():
                ref.push().set(value)

        embed = discord.Embed(
            title="",
            description=f"**<:yes:1036811164891480194> Custom Co-op Panel Sent!** {'This panel will now always be the last message in the channel.' if is_sticky_panel else ''} \n\n*Sent in the wrong channel? Delete the panel and use </co-op panel:1254927191037317149> in the correct channel!*",
            colour=0x00FF00,
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    @coop_panel.error
    async def coop_panel_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)

    @app_commands.command(name="setup", description="Setup co-op system in the server")
    @app_commands.describe(
        co_op_channel="The channel for all co-op requests",
        na_helper_role="Co-Op NA Helper role",
        eu_helper_role="Co-Op EU Helper role",
        asia_helper_role="Co-Op Asia Helper role",
        sar_helper_role="Co-Op SAR Helper role",
    )
    @app_commands.checks.bot_has_permissions(create_public_threads=True, send_messages_in_threads=True, manage_channels=True)
    @app_commands.checks.has_permissions(manage_messages=True, manage_guild=True)
    async def coop_setup(
        self,
        interaction: discord.Interaction,
        co_op_channel: discord.TextChannel,
        na_helper_role: discord.Role,
        eu_helper_role: discord.Role,
        asia_helper_role: discord.Role,
        sar_helper_role: discord.Role,
    ) -> None:
        ref = db.reference("/Co-Op")
        coop = ref.get()
        for key, value in coop.items():
            if value["Server ID"] == interaction.guild.id:
                embed = discord.Embed(
                    title="Co-Op System already enabled!",
                    description=f'Your co-op channel is already set as <#{value["Co-op Channel ID"]}> `({value["Co-op Channel ID"]})`\n\nPlease use </co-op panel:1254927191037317149> to create your own customized co-op panel.\n\nIf you wish to disable the co-op system, please use </co-op disable:1246163431912898582>.',
                    colour=0xFF0000,
                )
                embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

        data = {
            interaction.guild.name: {
                "Server Name": interaction.guild.name,
                "Server ID": interaction.guild.id,
                "Co-op Channel ID": co_op_channel.id,
                "NA Helper Role ID": na_helper_role.id,
                "EU Helper Role ID": eu_helper_role.id,
                "Asia Helper Role ID": asia_helper_role.id,
                "SAR Helper Role ID": sar_helper_role.id,
            }
        }

        for key, value in data.items():
            ref.push().set(value)

        embed = discord.Embed(
            title="Co-op System Enabled Successfully!",
            description=(
                f"- The co-op channel has been set to <#{co_op_channel.id}> `({co_op_channel.id})`.\n"
                f"- **By default, all administrators can close any co-op requests for moderation purposes.**\n"
                f"- To create your own customized co-op panel, please use </co-op panel:1254927191037317149>.\n"
                f"- **Tip:** Make sure members cannot type in <#{co_op_channel.id}>. The system works best if only Fischl is able to send messages in that channel."
            ),
            colour=0x00FF00,
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await interaction.response.send_message(embed=embed)
    @coop_setup.error
    async def coop_setup_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)

    @app_commands.command(
        name="reputation",
        description="Enable, manage, or disable reputation system in the server",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def coop_reputation(
        self,
        interaction: discord.Interaction,
    ) -> None:
        ref = db.reference("/Global Reps System")
        coop = ref.get()
        enabled = False
        try:
            for key, value in coop.items():
                if value["Server ID"] == interaction.guild.id:
                    enabled = [value["Max Rep"], value["Roles"]]
                    break
        except Exception:
            pass

        if enabled is not False:  # If enabled
            max_rep, roles = enabled
            embed = discord.Embed(
                title="Reputation System",
                description=f"The reputation system is enabled. Users can only give a maximum of `{max_rep}` reputation points at once.",
                color=discord.Color.blurple(),
            )
            shop_lines = []
            if roles is not None and not isinstance(roles, str):
                for idx, (role_id, cost) in enumerate(
                    sorted(roles.items(), key=lambda x: x[1]), start=1
                ):
                    line = f"{idx}. <@&{role_id}> • {cost} reps \n"
                    shop_lines.append(line)
                shop = "".join(shop_lines)
            else:
                shop = "None"
            embed.add_field(name="Roles", value=str(shop), inline=False)
            await interaction.response.send_message(
                embed=embed, view=CoOpRepEnableView(), ephemeral=True
            )
        else:
            embed = discord.Embed(
                title="Reputation System Not Enabled",
                description="This server does not have the reputation system enabled. Click the button below to enable it.",
                color=0xFF0000,
            )
            await interaction.response.send_message(
                embed=embed, view=CoOpRepEnableView(), ephemeral=True
            )
    @coop_reputation.error
    async def coop_reputation_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CoOp(bot))
