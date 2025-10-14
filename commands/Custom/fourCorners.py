import discord
import datetime
import asyncio, time
import random

from discord.ext import commands

GAME_CHANNEL_ID = 1380114290706743347
PARTICIPANT_ROLE_ID = 1379369770188669039
GAME_HOST_ID = 885217186468229140
SERVER_ID = 1344543366372655164

# GAME_CHANNEL_ID = 1026867655468126249
# PARTICIPANT_ROLE_ID = 1389352993136316456
# GAME_HOST_ID = 692254240290242601
# SERVER_ID = 783528750474199041

active_four_corners_game = None
SIGIL_EMOTE = "<a:sigils:1402736987902967850>"
NO_EMOTE = "<:no:1036810470860013639>"

class FourCornersGame:
    LOG_FILE = "assets/four_corners.txt"

    def __init__(self, guild, entry_fee=0):
        self.guild = guild
        self.participants = []
        self.eliminated = []
        self.round = 1
        self.phase = "registration"
        self.choices = {}
        self.channel = None
        self.announcement_msg = None
        self.game_channel_id = GAME_CHANNEL_ID
        self.participant_role_id = PARTICIPANT_ROLE_ID
        self.colors = ["🟥 Red", "🟦 Blue", "🟩 Green", "🟨 Yellow"]
        self.color_emojis = {
            "🟥 Red": "🟥",
            "🟦 Blue": "🟦",
            "🟩 Green": "🟩",
            "🟨 Yellow": "🟨"
        }
        self.entry_fee = entry_fee
        
    def check_for_winner(self):
        active_players = [uid for uid in self.participants if uid not in self.eliminated]
        if len(active_players) == 1:
            return active_players[0]
        return None

    def log_action(self, text: str):
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        with open(self.LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {text}\n")

    async def start_game(self):
        self.log_action("Game started.")
        self.phase = "playing"
        self.channel = self.guild.get_channel(self.game_channel_id)
        role = self.guild.get_role(self.participant_role_id)
        
        fee_info = ""
        if self.entry_fee > 0:
            fee_info = f"\n\nEntry fee of {SIGIL_EMOTE} **{self.entry_fee}** Sigils will be deducted from participants!"
        
        await self.channel.send(
            content=f"<@&{PARTICIPANT_ROLE_ID}> The Four Corners game is starting! Gather up!{fee_info}",
            embed=discord.Embed(
                description=f"**Round 1** begins <t:{int(time.time()) + 45}:R>...", 
                color=discord.Color.blurple()
            )
        )
        
        self.log_action(f"Announcement sent to <#{self.game_channel_id}>. Participants role: {role.name} (ID: {role.id})")
        await asyncio.sleep(45)
        await self.start_round()
        
    async def start_round(self):
        self.log_action(f"Round {self.round} started.")
        role = self.guild.get_role(self.participant_role_id)
        valid_participants = []
        for uid in self.participants:
            member = await self.guild.fetch_member(uid)
            if member and role in member.roles:
                valid_participants.append(uid)

        self.participants = valid_participants

        self.choices = {}

        active_players = [p for p in self.participants if p not in self.eliminated]
        self.log_action(f"Participants not eliminated: {active_players}")
        timeout_seconds = 30 if len(active_players) < 10 else 60
        timeout_label = f"{timeout_seconds} seconds" + (" (:warning: shortened timer)" if timeout_seconds == 30 else "")

        view = CornerSelectView(["🟥 Red", "🟦 Blue", "🟩 Green", "🟨 Yellow"])
        embed = discord.Embed(
            title=f"Round {self.round} - Choose Your Corner!",
            description=f"Select your corner for this round. You must choose in **{timeout_label}**!",
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"{len(active_players)} non-eliminated players remaining")
        msg = await self.channel.send(content=f"<@&{PARTICIPANT_ROLE_ID}>", embed=embed, view=view)
        self.log_action("Corner selection message sent.")

        await asyncio.sleep(timeout_seconds)
        await msg.edit(view=None)
        self.log_action("Corner selection ended.")

        non_choosers = [p for p in active_players if p not in self.choices]
        if non_choosers:
            self.eliminated.extend(non_choosers)
            mentions = ", ".join([f"{uid}" for uid in non_choosers])
            await self.channel.send(embed=discord.Embed(
                description=f"Eliminated for not choosing a corner: {', '.join(f'<@{uid}>' for uid in non_choosers)}",
                color=discord.Color.red()
            ))
            self.log_action(f"Players eliminated for not choosing a corner: {mentions}")
            if winner := self.check_for_winner():
                await self.announce_winner(winner)
                return
                
        await self.random_elimination()

    async def random_elimination(self):
        self.log_action(f"Round {self.round} elimination started.")
        active_players = [uid for uid in self.participants if uid not in self.eliminated]
        players_with_choices = [uid for uid in active_players if uid in self.choices]
        if len(players_with_choices) == 0:
            await self.end_game()
            return
            
        occupied_corners = list(set(
            self.choices[uid] for uid in players_with_choices
        ))
        
        if not occupied_corners:
            self.log_action("No occupied corners, ending game.")
            await self.end_game()
            return
            
        eliminated_corner = random.choice(occupied_corners)
        eliminated_players = [
            uid for uid, color in self.choices.items()
            if color == eliminated_corner and uid not in self.eliminated
        ]
        
        self.eliminated.extend(eliminated_players)
        self.log_action(f"Randomly eliminated corner: {eliminated_corner}, players eliminated: {eliminated_players}")

        eliminated_mentions = ", ".join([f"<@{uid}>" for uid in eliminated_players]) if eliminated_players else "No one"
        embed = discord.Embed(
            title=f"Round {self.round} Results",
            description=f"The {eliminated_corner} corner was randomly selected for elimination!\n"
                        f"**Eliminated players:** {eliminated_mentions}",
            color=discord.Color.red()
        )
        await self.channel.send(embed=embed)

        active_players = [uid for uid in self.participants if uid not in self.eliminated]
        if len(active_players) <= 1:
            await self.end_game()
        else:
            self.round += 1
            await asyncio.sleep(5)
            await self.channel.send(embed=discord.Embed(
                description=f"**Round {self.round}** will start <t:{int(time.time()) + 45}:R>...", 
                color=discord.Color.blurple()
            ))
            self.log_action(f"Round {self.round} will start soon.")
            await asyncio.sleep(45)
            await self.start_round()

    async def announce_winner(self, winner_id):
        self.log_action(f"Winner announced: User ID {winner_id}")
        embed = discord.Embed(
            title="🏆 Game Over - Winner! 🏆",
            description=f"<@{winner_id}> is the last one standing and wins the Welkin Moon!",
            color=discord.Color.gold()
        )
        await self.channel.send(embed=embed)

        role = self.guild.get_role(self.participant_role_id)
        for uid in self.participants:
            member = await self.guild.fetch_member(uid)
            if member and role in member.roles:
                await member.remove_roles(role)
                self.log_action(f"Removed participant role from User ID {uid}")

        global active_four_corners_game
        active_four_corners_game = None
        self.log_action("Game ended and cleaned up.")

    async def end_game(self):
        active_players = [uid for uid in self.participants if uid not in self.eliminated]
        self.log_action(f"End game check. Active players: {active_players}")

        if len(active_players) == 1:
            await self.announce_winner(active_players[0])
        elif len(active_players) > 1:
            await self.channel.send(embed=discord.Embed(
                title="🏁 Final Round Tie!",
                description="More than one player remains. Restarting the round to determine a winner...",
                color=discord.Color.orange()
            ))
            self.log_action("Final round tie, restarting round.")
            await asyncio.sleep(5)
            await self.start_round()
        else:
            embed = discord.Embed(
                title="Game Over",
                description="All players have been eliminated due to not picking! There is no winner.",
                color=discord.Color.dark_grey()
            )
            await self.channel.send(embed=embed)
            self.log_action("No winner: all players eliminated.")

            role = self.guild.get_role(self.participant_role_id)
            for uid in self.participants:
                member = await self.guild.fetch_member(uid)
                if member and role in member.roles:
                    await member.remove_roles(role)
                    self.log_action(f"Removed participant role from User ID {uid}")

            global active_four_corners_game
            active_four_corners_game = None
            self.log_action("Game ended and cleaned up.")

        # Send the log file as Discord file
        try:
            with open(self.LOG_FILE, "rb") as f:
                discord_file = discord.File(f, filename="four_corners_log.txt")
                await self.channel.send("Here is the full game log for transparency purposes.", file=discord_file)
        except Exception as e:
            self.log_action(f"Failed to send log file: {e}")

class CornerSelectView(discord.ui.View):
    def __init__(self, available_colors):  # Take available colors as parameter
        super().__init__(timeout=60)
        for color in available_colors:  # Only show available corners
            self.add_item(CornerButton(color))

class CornerButton(discord.ui.Button):
    def __init__(self, color):
        super().__init__(label=color.split()[1], style=discord.ButtonStyle.secondary, emoji=color.split()[0])
        self.color = color
    
    async def callback(self, interaction: discord.Interaction):
        if not active_four_corners_game:
            await interaction.response.send_message("No active game!", ephemeral=True)
            return
            
        user_id = interaction.user.id
        if user_id not in active_four_corners_game.participants:
            await interaction.response.send_message("You're not in the game!", ephemeral=True)
            return
        
        if user_id in active_four_corners_game.eliminated:
            await interaction.response.send_message("You've been eliminated!", ephemeral=True)
            return
        
        prev = active_four_corners_game.choices.get(user_id)
        active_four_corners_game.choices[user_id] = self.color

        user = interaction.user
        active_four_corners_game.log_action(f"{user.name} ({user.id}) selected corner {self.color} (previous: {prev})")

        if prev and prev != self.color:
            await interaction.response.send_message(f"Corner updated from **{prev}** to **{self.color}**!", ephemeral=True)
        else:
            await interaction.response.send_message(f"You've chosen the {self.color} corner!", ephemeral=True)

class ReviveView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.used = False

    @discord.ui.button(label="Revive Me!", style=discord.ButtonStyle.green, custom_id="revive_click")
    async def revive_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        global active_four_corners_game

        if not active_four_corners_game:
            await interaction.response.send_message("No active game!", ephemeral=True)
            return

        if self.used:
            await interaction.response.send_message("Revive already claimed!", ephemeral=True)
            return

        user_id = interaction.user.id
        username = interaction.user.name
        if user_id not in active_four_corners_game.eliminated:
            await interaction.response.send_message("You are not eliminated!", ephemeral=True)
            return

        active_four_corners_game.eliminated.remove(user_id)
        active_four_corners_game.log_action(f"User {username} ({user_id}) has been revived.")
        self.used = True
        button.disabled = True
        await interaction.response.edit_message(content=f"<@{user_id}> has been revived! ⚡", view=self)
        await interaction.channel.send(embed=discord.Embed(
            description=f"✨ <@{user_id}> has returned from the abyss! Let’s see if they survive this time...",
            color=discord.Color.green()
        ))
        await asyncio.sleep(10)

class GameAnnounceView(discord.ui.View):
    def __init__(self, entry_fee=0):
        super().__init__(timeout=None)
        self.entry_fee = entry_fee
    
    @discord.ui.button(label="Join Game", style=discord.ButtonStyle.green, custom_id="fourcorners_join")
    async def join_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        global active_four_corners_game
        
        if not active_four_corners_game:
            await interaction.response.send_message("No active game!", ephemeral=True)
            return
        
        user = interaction.user
        if active_four_corners_game.phase != "registration":
            await interaction.response.send_message("The game has already started! No new players can join.", ephemeral=True)
            if active_four_corners_game:
                active_four_corners_game.log_action(f"{user.name} ({user.id}) tried to join but game already started.")
            return
            
        role = interaction.guild.get_role(active_four_corners_game.participant_role_id)
        
        if role in user.roles:
            await interaction.response.send_message("You've already joined the game!", ephemeral=True)
            active_four_corners_game.log_action(f"{user.name} ({user.id}) tried to join but was already a participant.")
            return
            
        if self.entry_fee > 0:
            sigil_cog = interaction.client.get_cog("SigilSystem")
            if not sigil_cog:
                return await interaction.response.send_message(
                    f"{NO_EMOTE} Sigil system not available. Cannot process entry fee.",
                    ephemeral=True
                )
                
            balance = await sigil_cog.get_balance(interaction.guild.id, user.id)
            if balance < self.entry_fee:
                return await interaction.response.send_message(
                    f"{NO_EMOTE} You need {SIGIL_EMOTE} **{self.entry_fee}** Sigils to join! (You have: `{balance}`)",
                    ephemeral=True
                )
            
            if not await sigil_cog.deduct_sigils(interaction.guild.id, user.id, self.entry_fee):
                return await interaction.response.send_message(
                    f"{NO_EMOTE} Failed to deduct Sigils. Please try again.",
                    ephemeral=True
                )
        
        await user.add_roles(role)
        if user.id not in active_four_corners_game.participants:
            active_four_corners_game.participants.append(user.id)
            
        fee_info = f" and paid {SIGIL_EMOTE} **{self.entry_fee}** Sigils" if self.entry_fee > 0 else ""
        await interaction.response.send_message(
            f"You've joined the game{fee_info}! You've been given the {role.mention} role.\n"
            f"Head over to <#{GAME_CHANNEL_ID}> and wait for the game host to start!", 
            ephemeral=True
        )
        active_four_corners_game.log_action(
            f"{user.name} ({user.id}) joined the game{fee_info} and was given participant role."
        )
    
    @discord.ui.button(label="View Participants", style=discord.ButtonStyle.blurple, custom_id="fourcorners_view")
    async def view_participants(self, interaction: discord.Interaction, button: discord.ui.Button):
        global active_four_corners_game
        
        user = interaction.user
        if not active_four_corners_game:
            await interaction.response.send_message("No active game!", ephemeral=True)
            return
            
        participants = [f"- <@{uid}>" for uid in active_four_corners_game.participants]
        
        if not participants:
            await interaction.response.send_message("No participants yet!", ephemeral=True)
            if active_four_corners_game:
                active_four_corners_game.log_action(f"{user.name} ({user.id}) viewed participants: none yet.")
            return
            
        embed = discord.Embed(
            title="List of Current Four Corners Participants",
            description="\n".join(participants),
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        if active_four_corners_game:
            active_four_corners_game.log_action(f"{user.name} ({user.id}) viewed participant list ({len(participants)} total).")
    
    @discord.ui.button(label="Start Game", style=discord.ButtonStyle.red, custom_id="fourcorners_start")
    async def start_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        global active_four_corners_game

        user = interaction.user
        if not active_four_corners_game:
            await interaction.response.send_message("No active game!", ephemeral=True)
            return

        if user.id != GAME_HOST_ID:
            await interaction.response.send_message("Only the game host can start the game!", ephemeral=True)
            if active_four_corners_game:
                active_four_corners_game.log_action(f"{user.name} ({user.id}) attempted to start the game but was not host.")
            return

        if active_four_corners_game.phase != "registration":
            await interaction.response.send_message("The game has already started!", ephemeral=True)
            if active_four_corners_game:
                active_four_corners_game.log_action(f"{user.name} ({user.id}) tried to start the game but it was already in progress.")
            return

        if len(active_four_corners_game.participants) < 1:
            await interaction.response.send_message("You need at least 1 participant to start, though at least 4 is encouraged.", ephemeral=True)
            if active_four_corners_game:
                active_four_corners_game.log_action(f"{user.name} ({user.id}) tried to start game with insufficient participants ({len(active_four_corners_game.participants)}).")
            return

        await interaction.response.send_message("Starting the game now!", ephemeral=True)
        if active_four_corners_game:
            active_four_corners_game.log_action(f"{user.name} ({user.id}) started the game.")
        await active_four_corners_game.start_game()


class FourCorners(commands.Cog):
    def __init__(self, bot):
        self.client = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        global active_four_corners_game
        if message.author == self.client.user or message.author.bot:
            return
                                  
        if message.guild.id != SERVER_ID or message.author.id != GAME_HOST_ID:
            return

        if message.content.startswith("-announcegame"):
            parts = message.content.split()
            entry_fee = 0
            
            if len(parts) > 1:
                try:
                    entry_fee = max(0, int(parts[1])) 
                except ValueError:
                    entry_fee = 0

            if active_four_corners_game:
                await message.reply("A game is already in progress!")
                active_four_corners_game.log_action(f"{message.author.name} ({message.author.id}) tried to start a new game but one is in progress.")
                return

            active_four_corners_game = FourCornersGame(message.guild, entry_fee)

            with open(active_four_corners_game.LOG_FILE, "w", encoding="utf-8") as f:
                f.write(f"--- Four Corners Game Log started at {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} ---\n")

            active_four_corners_game.log_action(f"{message.author.name} ({message.author.id}) started a new game with entry fee: {entry_fee}.")

            fee_info = ""
            if entry_fee > 0:
                fee_info = f"\n\n🎟️ **Entry Fee:** {SIGIL_EMOTE} {entry_fee} Sigils will be deducted when joining!"

            embed = discord.Embed(
                title="🌍 Four Corners of the World",
                description=(
                    "Prepare for an exhilarating game of luck and strategy!\n\n"
                    "**How to Play:**\n"
                    "1. Choose your corner: 🟥 Red, 🟦 Blue, 🟩 Green, or 🟨 Yellow.\n"
                    "2. Each round, a corner will be randomly eliminated.\n"
                    "3. If you're standing in that corner... you're OUT! 💥\n"
                    "4. Survive the rounds and outlast the rest.\n\n"
                    "🏆 **Prize:**\n"
                    "The last participant standing wins a Welkin Moon!\n\n"
                    "🎟️ Click the button below to join and receive the Participant role. "
                    "Get ready to play!{fee_info}\n\n"
                    "Brought to you by Miss Xianyun~\n"
                    "May the winds guide your fate... or not XD"
                ).format(fee_info=fee_info),
                color=discord.Color.green()
            )
            view = GameAnnounceView(entry_fee)
            await message.channel.send(embed=embed, view=view)
            return

        if message.content == "-endgame":
            if not active_four_corners_game:
                await message.reply("There is no active game running right now!")
                return

            if message.author.id != GAME_HOST_ID:
                await message.reply("Only the game host can force end the game!")
                if active_four_corners_game:
                    active_four_corners_game.log_action(f"{message.author.name} ({message.author.id}) tried to force end the game but was not host.")
                return

            await active_four_corners_game.channel.send(
                embed=discord.Embed(
                    title="🚨 Game Forcefully Ended",
                    description=f"The game has been ended early by <@{GAME_HOST_ID}>.",
                    color=discord.Color.red()
                )
            )

            role = message.guild.get_role(active_four_corners_game.participant_role_id)
            for uid in active_four_corners_game.participants:
                member = await message.guild.fetch_member(uid)
                if member and role in member.roles:
                    await member.remove_roles(role)
                    active_four_corners_game.log_action(f"Removed participant role from User ID {uid}")

            active_four_corners_game.log_action(f"Game was forcefully ended by host {message.author.name} ({message.author.id}).")
            active_four_corners_game = None
            return

        if message.content == "-revive":
            if not active_four_corners_game:
                await message.reply("There's no active game to revive anyone into!")
                return

            eliminated = [uid for uid in active_four_corners_game.eliminated]
            if not eliminated:
                await message.reply("Nobody is eliminated right now!")
                if active_four_corners_game:
                    active_four_corners_game.log_action(f"{message.author.name} ({message.author.id}) tried to revive but no eliminated players.")
                return

            active_four_corners_game.log_action(f"{message.author.name} ({message.author.id}) requested a revive prompt.")
            await message.reply(
                embed=discord.Embed(
                    title="🩺 One-time Revival!",
                    description="The first eliminated player to click the button below will be revived.",
                    color=discord.Color.green()
                ),
                view=ReviveView()
            )

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FourCorners(bot))