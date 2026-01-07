import discord
import datetime
import os

from discord import app_commands
from discord.ext import commands
from firebase_admin import db
from PIL import Image, ImageEnhance, ImageSequence

MORA_EMOTE = "<:MORA:1364030973611610205>"

letter_emojis = [ "🇦", "🇧", "🇨", "🇩", "🇪", "🇫", "🇬", "🇭", "🇮", "🇯", "🇰", "🇱", "🇲", "🇳", "🇴", "🇵", "🇶", "🇷", "🇸", "🇹", "🇺", "🇻", "🇼", "🇽", "🇾", "🇿" ] 
letterList = [ "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z" ]
letterString = "".join(letterList)

minigame_titles = [
    "Boss Battle Blitz",
    "Quicktype Racer",
    "Egg Walk",
    "Match The Profile Picture",
    "Split or Steal",
    "Reverse Number Quicktype",
    "Pick Up Ice Cream",
    "Snatch The Watermelon",
    "Guess The Mystery Number",
    "Memory Game",
    "Who Said That",
    "Unscramble Words",
    "Two Truths, One Lie",
    "Currency Counting",
    "Rock Paper Scissors Duel",
    "Roll A Dice",
    "Teyvat Voiceline Quiz",
    "Teyvat Emoji Riddles",
    "Galaxy Emoji Riddles",
    "Double or Keep",
    "Know Your Members",
    "Hangman",
    "Mora Auction House",
    "Mora Heist",
    "Simple Math Game",
    "Tik Tac Tok"
]


class ToggleEventModal(discord.ui.Modal, title="Toggling Event"):

    letter = discord.ui.TextInput(
        label="The corresponding letter(s)",
        style=discord.TextStyle.short,
        placeholder="Type letters consecutively to toggle multiple games (no spaces please)",
        max_length=26,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        # await interaction.response.defer()
        channelID = int(str(self.title).split(":")[1].replace(")", "").strip())
        ref = db.reference("/Global Events System")
        stickies = ref.get()
        originalList = None
        try:
            for key, val in stickies.items():
                if val["Channel ID"] == channelID:
                    originalList = val.get("Events", [])
                    frequency = val["Frequency"]
                    break
        except Exception as e:
            print(e)

        for letter in list(str(self.letter)):
            self.toggleLetter = str(letter).upper()

            if self.toggleLetter in letterList and originalList is not None:
                if self.toggleLetter in originalList:
                    originalList.remove(self.toggleLetter)
                else:
                    originalList.append(self.toggleLetter)
                error = False
            else:
                error = True
                break

        if not (error):
            for key, val in stickies.items():
                if val["Channel ID"] == channelID:
                    db.reference("/Global Events System").child(key).delete()
                    break

            data = {
                channelID: {
                    "Channel ID": channelID,
                    "Frequency": frequency,
                    "Events": originalList,
                }
            }
            for key, value in data.items():
                ref.push().set(value)

            string = "\n> ".join(
                [
                    f"{emoji} - {title} <:yes:1036811164891480194>"
                    if self.toggleLetter in originalList
                    else f"{emoji} - {title} <:no:1036810470860013639>"
                    for self.toggleLetter, emoji, title in zip(
                        letterString, letter_emojis, minigame_titles
                    )
                ]
            )

            self.embed = discord.Embed(
                title="Customize which mini-games you'd like to enable",
                description=f"**Channel:** <#{channelID}>\n\n > {string}\n\nClick `Toggle Event` below and type in the **corresponding letter(s)** (i.e. `h` or `abdfm`) to **toggle** the mini-game(s). You can also edit the </shop:1345883946105311383> and </milestones:1380247962390888578> to customize further!",
                color=discord.Color.blurple(),
            )
            self.update = discord.Embed(
                description=f"Toggle successful :slight_smile:",
                color=discord.Color.green(),
            )
        else:
            self.embed = None
            self.update = discord.Embed(
                description=f"Invalid input. Please try again.",
                color=discord.Color.red(),
            )

        self.on_submit_interaction = interaction
        self.stop()


class ToggleEventButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Toggle Event", style=discord.ButtonStyle.blurple)

    async def callback(self, interaction: discord.Interaction):
        channelID = (
            interaction.message.embeds[0]
            .description.split("<#")[1]
            .split(">")[0]
            .strip()
        )

        toggleEventModal = ToggleEventModal(title=f"Toggle Event (ID: {channelID})")
        await interaction.response.send_modal(toggleEventModal)
        response = await toggleEventModal.wait()

        if toggleEventModal.embed is not None:
            await interaction.edit_original_response(embed=toggleEventModal.embed)
        await toggleEventModal.on_submit_interaction.response.send_message(
            embed=toggleEventModal.update, ephemeral=True
        )


class EnableEventButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Enable Events", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):
        channel_id = int(
            interaction.message.embeds[0]
            .description.split("<#")[1]
            .split(">")[0]
            .strip()
        )
        channel = interaction.guild.get_channel(channel_id)

        frequency_value = 50 # Uncommon (~2%)

        ref = db.reference("/Global Events System")
        data = {
            channel.id: {
                "Channel ID": channel.id,
                "Frequency": frequency_value,
                "Events": letterList,  # All enabled by default
            }
        }
        for key, value in data.items():
            ref.push().set(value)

        with open("./commands/Events/enabledChannels.py", "r") as file:
            lines = file.readlines()

        for i, line in enumerate(lines):
            if line.startswith("enabledChannels ="):
                existing_dict = eval(line.split("=", 1)[1].strip())
                existing_dict[channel.id] = frequency_value
                lines[i] = f"enabledChannels = {existing_dict}\n"
                break

        with open("./commands/Events/enabledChannels.py", "w") as file:
            file.writelines(lines)

        # Create settings embed
        string = "\n> ".join(
            [
                f"{emoji} - {title} <:yes:1036811164891480194>"
                if letter in letterList
                else f"{emoji} - {title} <:no:1036810470860013639>"
                for letter, emoji, title in zip(
                    letterString, letter_emojis, minigame_titles
                )
            ]
        )
        embed = discord.Embed(
            title="Customize which mini-games you'd like to enable",
            description=f"**Channel:** {channel.mention}\n**Status:** Enabled\n**Spawn Rate:** `{int(100/frequency_value)}%`\n\n**Enabled Games:**\n > {string}\n\nClick `Toggle Event` below and type in the **corresponding letter(s)** (i.e. `h` or `abdfm`) to **toggle** the mini-game(s). You can also edit the </shop:1345883946105311383> and </milestones:1380247962390888578> to customize further!",
            color=discord.Color.blurple(),
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)

        view = EventSettingsView(channel)
        await interaction.response.edit_message(embed=embed, view=view)

        success_embed = discord.Embed(
            title="Random events enabled!",
            description=f"Now, there will be a **{100//frequency_value}%** chance for every message sent in {channel.mention} to trigger a random event!",
            colour=0x00FF00,
        )
        success_embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await interaction.followup.send(embed=success_embed, ephemeral=True)


class DisableEventButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Disable Events", style=discord.ButtonStyle.red)

    async def callback(self, interaction: discord.Interaction):
        channel_id = int(
            interaction.message.embeds[0]
            .description.split("<#")[1]
            .split(">")[0]
            .strip()
        )
        channel = interaction.guild.get_channel(channel_id)

        ref = db.reference("/Global Events System")
        stickies = ref.get()

        for key, val in stickies.items():
            if val["Channel ID"] == channel.id:
                db.reference("/Global Events System").child(key).delete()
                break

        with open("./commands/Events/enabledChannels.py", "r") as file:
            lines = file.readlines()

        for i, line in enumerate(lines):
            if line.startswith("enabledChannels ="):
                existing_dict = eval(line.split("=", 1)[1].strip())
                if channel.id in existing_dict:
                    del existing_dict[channel.id]
                lines[i] = f"enabledChannels = {existing_dict}\n"
                break

        with open("./commands/Events/enabledChannels.py", "w") as file:
            file.writelines(lines)

        embed = discord.Embed(
            title="Event Settings",
            description=f"**Channel:** {channel.mention}\n**Status:** Disabled\n\nRandom events are not enabled in this channel.",
            colour=0xFFFF00,
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)

        view = EventSettingsView(channel)
        await interaction.response.edit_message(embed=embed, view=view)


class FrequencySelect(discord.ui.Select):
    def __init__(self, current_frequency=None):
        options = [
            discord.SelectOption(label="Very Frequent (~10%)", value="10", default=current_frequency == 10),
            discord.SelectOption(label="Frequent (~5%)", value="20", default=current_frequency == 20),
            discord.SelectOption(label="Occasional (~3%)", value="30", default=current_frequency == 30),
            discord.SelectOption(label="Uncommon (~2%)", value="50", default=current_frequency == 50),
            discord.SelectOption(label="Rare (~1%)", value="100", default=current_frequency == 100),
            discord.SelectOption(label="Very Rare (~0.5%)", value="200", default=current_frequency == 200),
        ]
        super().__init__(placeholder="Select frequency...", options=options)

    async def callback(self, interaction: discord.Interaction):
        channel_id = int(
            interaction.message.embeds[0]
            .description.split("<#")[1]
            .split(">")[0]
            .strip()
        )
        channel = interaction.guild.get_channel(channel_id)

        new_frequency = int(self.values[0])

        ref = db.reference("/Global Events System")
        stickies = ref.get()

        for key, val in stickies.items():
            if val["Channel ID"] == channel.id:
                db.reference("/Global Events System").child(key).update({"Frequency": new_frequency})
                break

        with open("./commands/Events/enabledChannels.py", "r") as file:
            lines = file.readlines()

        for i, line in enumerate(lines):
            if line.startswith("enabledChannels ="):
                existing_dict = eval(line.split("=", 1)[1].strip())
                existing_dict[channel.id] = new_frequency
                lines[i] = f"enabledChannels = {existing_dict}\n"
                break

        with open("./commands/Events/enabledChannels.py", "w") as file:
            file.writelines(lines)

        # Get current events
        events = []
        for key, val in stickies.items():
            if val["Channel ID"] == channel.id:
                events = val.get("Events", [])
                break

        # Create settings embed
        string = "\n> ".join(
            [
                f"{emoji} - {title} <:yes:1036811164891480194>"
                if letter in events
                else f"{emoji} - {title} <:no:1036810470860013639>"
                for letter, emoji, title in zip(
                    letterString, letter_emojis, minigame_titles
                )
            ]
        )
        embed = discord.Embed(
            title="Customize which mini-games you'd like to enable",
            description=f"**Channel:** {channel.mention}\n**Status:** Enabled\n**Spawn Rate:** `{int(100/new_frequency)}%`\n\n**Enabled Games:**\n > {string}\n\nClick `Toggle Event` below and type in the **corresponding letter(s)** (i.e. `h` or `abdfm`) to **toggle** the mini-game(s). You can also edit the </shop:1345883946105311383> and </milestones:1380247962390888578> to customize further!",
            color=discord.Color.blurple(),
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)

        view = EventSettingsView(channel)
        await interaction.response.edit_message(embed=embed, view=view)

        success_embed = discord.Embed(
            title="Frequency updated!",
            description=f"Spawn rate updated to **{100//new_frequency}%** for {channel.mention}.",
            colour=0x00FF00,
        )
        success_embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await interaction.followup.send(embed=success_embed, ephemeral=True)


class EventSettingsView(discord.ui.View):
    def __init__(self, channel):
        super().__init__()
        self.channel = channel

        ref = db.reference("/Global Events System")
        stickies = ref.get()
        enabled = False
        frequency = None
        events = []
        for key, val in stickies.items():
            if val["Channel ID"] == channel.id:
                enabled = True
                frequency = val.get("Frequency", 50)
                events = val.get("Events", [])
                break

        if enabled:
            self.add_item(FrequencySelect(current_frequency=frequency))
            self.add_item(ToggleEventButton())
            self.add_item(DisableEventButton())
        else:
            self.add_item(EnableEventButton())


@app_commands.guild_only()
class EventSystem(commands.GroupCog, name="events"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(
        name="settings",
        description="Customize the selection of random events in your server",
    )
    @app_commands.describe(
        channel="The text channel to customize event settings for (default: current channel)",
    )
    @app_commands.checks.has_permissions(manage_guild=True, manage_channels=True)
    async def events_settings(
        self, interaction: discord.Interaction, channel: discord.TextChannel = None
    ) -> None:
        if channel == None:
            channel = interaction.channel

        view = EventSettingsView(channel)

        ref = db.reference("/Global Events System")
        stickies = ref.get()
        enabled = False
        frequency = None
        events = []
        for key, val in stickies.items():
            if val["Channel ID"] == channel.id:
                enabled = True
                frequency = val.get("Frequency", 50)
                events = val.get("Events", [])
                break

        if enabled:
            string = "\n> ".join(
                [
                    f"{emoji} - {title} <:yes:1036811164891480194>"
                    if letter in events
                    else f"{emoji} - {title} <:no:1036810470860013639>"
                    for letter, emoji, title in zip(
                        letterString, letter_emojis, minigame_titles
                    )
                ]
            )

            embed = discord.Embed(
                title="Customize which mini-games you'd like to enable",
                description=f"**Channel:** {channel.mention}\n**Status:** Enabled\n**Spawn Rate:** `{int(100/frequency) if frequency else 0}%`\n\n**Enabled Games:**\n > {string}\n\nClick `Toggle Event` below and type in the **corresponding letter(s)** (i.e. `h` or `abdfm`) to **toggle** the mini-game(s). You can also edit the </shop:1345883946105311383> and </milestones:1380247962390888578> to customize further!",
                color=discord.Color.blurple(),
            )
        else:
            embed = discord.Embed(
                title="Event Settings",
                description=f"**Channel:** {channel.mention}\n**Status:** Disabled\n\nRandom events are not enabled in this channel.",
                colour=0xFFFF00,
            )

        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @events_settings.error
    async def events_settings_error(
        self, interaction: discord.Interaction, error: Exception
    ):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)
        
### Darken and resize an animated background GIF for profile cards ###
async def format_animated_background(ctx, gif_name): 
    if not gif_name.lower().endswith('.gif'):
        return await ctx.send("Please provide a GIF file!", delete_after=5)

    base_path = "./assets/Animated Mora Inventory Background/"
    input_path = os.path.join(base_path, gif_name)
    
    if not os.path.exists(input_path):
        return await ctx.send(f"File not found: {gif_name}", delete_after=10)
    
    try:
        with Image.open(input_path) as im:
            frames = []
            duration_info = []
            
            for frame in ImageSequence.Iterator(im):
                frame = frame.convert("RGBA")
                width, height = frame.size
                target_aspect = 720 / 256
                current_aspect = width / height
                
                if current_aspect > target_aspect:
                    new_width = int(target_aspect * height)
                    left = (width - new_width) // 2
                    frame = frame.crop((left, 0, left + new_width, height))
                else:
                    new_height = int(width / target_aspect)
                    top = (height - new_height) // 2
                    frame = frame.crop((0, top, width, top + new_height))
                
                frame = frame.resize((720, 256), Image.LANCZOS)
                
                enhancer = ImageEnhance.Brightness(frame)
                frame = enhancer.enhance(0.4)
                
                frames.append(frame)
                duration_info.append(frame.info.get('duration', 100))
            
            output_path = os.path.join(base_path, f"{gif_name}")
            frames[0].save(
                output_path,
                save_all=True,
                append_images=frames[1:],
                duration=duration_info,
                loop=0,
                disposal=2
            )
        
        await ctx.send(f"✅ Successfully formatted `{gif_name}`!", 
                       file=discord.File(output_path))
    
    except Exception as e:
        await ctx.send(f"❌ Error processing GIF: {str(e)}", delete_after=15)
        
class NewGameUpdate(commands.Cog):
    def __init__(self, bot):
        self.client = bot

    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author == self.client.user or message.author.bot == True:
            return

        if message.content.startswith("-format") and message.author.id == 692254240290242601:
            await format_animated_background(message.channel, message.content.split(":")[1])

        if message.content.startswith("-report "):
            uid = message.content.split(" ")[1].replace("<@", "").replace(">", "")
            ian = self.client.get_user(692254240290242601)
            await ian.send(f"User with ID `{message.author.id}` reported the inventory background of a user with ID `{uid}` in **{message.guild.name}**")
            await ian.send(file=discord.File(f"./assets/Mora Inventory Background/{uid}.png"))
            await message.add_reaction("<:yes:1036811164891480194>")

        if message.content.startswith("-newgameupdate") and message.author.id == 692254240290242601:
            LETTER = message.content.split(" ")[1].strip().upper()  # NEW GAME LETTER

            ref = db.reference("/Global Events System")
            stickies = ref.get()
            originalList = None
            count = 0

            for key, val in stickies.items():
                if ("beta" in message.content and 1303235296254759008 != val["Channel ID"]) or ("beta" not in message.content and 1303235296254759008 == val["Channel ID"]):
                    continue

                originalList = val["Events"]
                frequency = val["Frequency"]
                channelID = val["Channel ID"]
                originalList.append(LETTER)
                db.reference("/Global Events System").child(key).delete()

                data = {
                    channelID: {
                        "Channel ID": channelID,
                        "Frequency": frequency,
                        "Events": originalList,
                    }
                }

                for key, value in data.items():
                    ref.push().set(value)

                count += 1

                if "beta" in message.content and 1303235296254759008 == val["Channel ID"]:
                    await message.channel.send(f"<#{channelID}> updated with `{LETTER}` enabled by default.")
                    break

            await message.channel.send(f"`{count}` channels updated with `{LETTER}` enabled by default.")

        if message.content.startswith("-removegame") and message.author.id == 692254240290242601:
            LETTER = message.content.split(" ")[1].strip().upper()  # GAME LETTER TO REMOVE

            ref = db.reference("/Global Events System")
            stickies = ref.get()
            originalList = None
            count = 0
            
            for key, val in stickies.items():
                if ("beta" in message.content and 1303235296254759008 != val["Channel ID"]) or ("beta" not in message.content and 1303235296254759008 == val["Channel ID"]):
                    continue

                originalList = val["Events"]
                frequency = val["Frequency"]
                channelID = val["Channel ID"]

                if LETTER in originalList:
                    originalList.remove(LETTER)  # Remove only the first occurrence
                    db.reference("/Global Events System").child(key).delete()
                    data = {
                        channelID: {
                            "Channel ID": channelID,
                            "Frequency": frequency,
                            "Events": originalList,
                        }
                    }

                    for key, value in data.items():
                        ref.push().set(value)

                    count += 1

                    if "beta" in message.content and 1303235296254759008 == val["Channel ID"]:
                        await message.channel.send(f"<#{channelID}> updated with `{LETTER}` removed from the defaults.")
                        break

            await message.channel.send(f"`{count}` channels updated with `{LETTER}` removed from defaults.")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EventSystem(bot))
    await bot.add_cog(NewGameUpdate(bot))