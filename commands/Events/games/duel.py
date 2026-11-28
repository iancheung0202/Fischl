import random
import time

import discord

from commands.Events.config import MORA_EMOTE, NO_EMOTE
from commands.Events.games.common import count, earn, prize, user_and_title

BEATS = {"Rock": "Scissors", "Scissors": "Paper", "Paper": "Rock"}
RPS_EMOJIS = {"Rock": "🪨", "Paper": "📄", "Scissors": "✂️"}


async def last_two(channel, messages: int) -> list:
    """Gives the two members who wrote most recently in a channel, or fewer when there are not two."""
    players = {}
    async for message in channel.history(limit=messages):
        if not message.author.bot:
            players.setdefault(message.author.id, message.author)
        if len(players) == 2:
            break
    return list(players.values())


class DuelView(discord.ui.View):
    """Two members each make one hidden choice; the game settles when both have chosen."""

    changed = "You already made your choice!"
    timed_out = "⌛ This game session has timed out"

    def __init__(self, client, channel, players, reward):
        super().__init__(timeout=300)
        self.client = client
        self.channel = channel
        self.players = players
        self.reward = reward
        self.choices = {}
        self.message = None
        self.start_time = time.time()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        uid = interaction.user.id
        if uid not in (player.id for player in self.players):
            refusal = "You're not part of this game!"
        elif uid in self.choices:
            refusal = self.changed
        else:
            return True
        await interaction.response.send_message(refusal, ephemeral=True)
        return False

    async def name(self, player) -> str:
        return await user_and_title(player.id, self.channel.guild.id, self.client.pool)

    async def choose(self, interaction: discord.Interaction, choice: str) -> bool:
        """Records a choice; True when it was the second one, after taking the buttons off."""
        self.choices[interaction.user.id] = choice
        if len(self.choices) < 2:
            return False
        self.stop()
        await interaction.response.defer()
        await self.message.edit(view=None)
        return True

    async def paid(self, player, amount: int) -> tuple:
        return await earn(self.client, self.channel, player.id, amount)

    async def won(self, player, earned: int) -> None:
        await count(
            self.client, self.channel, player.id, earned, self.start_time, duel=True
        )

    async def lost(self, player) -> None:
        await count(self.client, self.channel, player.id, won=False)

    async def on_timeout(self):
        await self.message.edit(
            embed=discord.Embed(
                description=self.timed_out, color=discord.Color.dark_grey()
            ),
            view=None,
        )


class SplitOrStealView(DuelView):
    changed = "You can't change your selection!"
    timed_out = "🕒 This game session has timed out"

    async def choose(self, interaction: discord.Interaction, choice: str) -> None:
        if await super().choose(interaction, choice):
            return await self.settle()
        other = next(
            player for player in self.players if player.id != interaction.user.id
        )
        await interaction.response.send_message(
            f"Waiting for {await self.name(other)} to choose...", ephemeral=True
        )

    @discord.ui.button(label="Split", emoji="🤝", style=discord.ButtonStyle.green)
    async def split(self, interaction: discord.Interaction, button):
        await self.choose(interaction, "Split")

    @discord.ui.button(label="Steal", emoji="🤑", style=discord.ButtonStyle.red)
    async def steal(self, interaction: discord.Interaction, button):
        await self.choose(interaction, "Steal")

    async def both_split(self) -> None:
        a, b = self.players
        half = int(self.reward / 2)
        text_a, earned_a = await self.paid(a, half)
        text_b, earned_b = await self.paid(b, half)
        name_a, name_b = await self.name(a), await self.name(b)
        if earned_a == earned_b:
            each = f"You each won {MORA_EMOTE} `{text_a}`!"
        else:
            each = f"{name_a} won {MORA_EMOTE} `{text_a}` and {name_b} won {MORA_EMOTE} `{text_b}`!"
        await self.message.reply(
            embed=discord.Embed(
                title="Split Success! 🎉",
                description=f"Congrats, both {name_a} and {name_b} chose Split. {each}",
                color=discord.Color.green(),
            )
        )
        await self.won(a, earned_a)
        await self.won(b, earned_b)

    async def both_steal(self) -> None:
        a, b = self.players
        await self.message.reply(
            embed=discord.Embed(
                title=random.choice(
                    [
                        "Both Got Nothing :person_shrugging:",
                        "Greed Leaves You With Nothing 💸",
                    ]
                ),
                description=f"Both {await self.name(a)} and {await self.name(b)} chose Steal. No money for y'all.",
                color=discord.Color.red(),
            )
        )
        await self.lost(a)
        await self.lost(b)

    async def one_stole(self, stealer, other) -> None:
        text, earned = await self.paid(stealer, self.reward)
        await self.message.reply(
            embed=discord.Embed(
                title="It's a Steal! 💰",
                description=f"{await self.name(stealer)} stole all the money and won {MORA_EMOTE} `{text}`!",
                color=discord.Color.yellow(),
            )
        )
        await self.won(stealer, earned)
        await self.lost(other)

    async def settle(self) -> None:
        a, b = self.players
        stole_a, stole_b = (self.choices[player.id] == "Steal" for player in (a, b))
        if stole_a and stole_b:
            await self.both_steal()
        elif stole_a:
            await self.one_stole(a, b)
        elif stole_b:
            await self.one_stole(b, a)
        else:
            await self.both_split()


async def splitOrSteal(channel, client):
    reward = await prize(client, channel, 10000, 14000)
    players = await last_two(channel, 10)
    if len(players) < 2:
        return await channel.send(
            embed=discord.Embed(
                description=f"{NO_EMOTE} Not enough unique recent messaging users for the game."
            )
        )
    view = SplitOrStealView(client, channel, players, reward)
    view.message = await channel.send(
        content=f"{players[0].mention} vs {players[1].mention}",
        embed=discord.Embed(
            title=f"Choose to **Split or Steal** {MORA_EMOTE} `{reward}`!",
            color=0x7F00FF,
        ),
        view=view,
    )


class RPSView(DuelView):
    async def choose(self, interaction: discord.Interaction, choice: str) -> None:
        if await super().choose(interaction, choice):
            return await self.settle()
        await interaction.response.defer()

    @discord.ui.button(label="Rock", emoji="🪨", style=discord.ButtonStyle.red)
    async def rock(self, interaction: discord.Interaction, button):
        await self.choose(interaction, "Rock")

    @discord.ui.button(label="Paper", emoji="📄", style=discord.ButtonStyle.green)
    async def paper(self, interaction: discord.Interaction, button):
        await self.choose(interaction, "Paper")

    @discord.ui.button(label="Scissors", emoji="✂️", style=discord.ButtonStyle.grey)
    async def scissors(self, interaction: discord.Interaction, button):
        await self.choose(interaction, "Scissors")

    async def tie(self, choice: str) -> None:
        share = int(self.reward / 7)
        parts = []
        for player in self.players:
            text, earned = await self.paid(player, share)
            await count(self.client, self.channel, player.id, earned, won=False)
            parts.append(f"{player.mention} earned {MORA_EMOTE} `{text}`")
        await self.message.reply(
            embed=discord.Embed(
                title=f"Both of you chose {RPS_EMOJIS[choice]}!",
                description=f"It's a tie! {' and '.join(parts)}!",
                color=discord.Color.yellow(),
            )
        )

    async def settle(self) -> None:
        a, b = self.players
        choice_a, choice_b = self.choices[a.id], self.choices[b.id]
        if choice_a == choice_b:
            return await self.tie(choice_a)
        winner, loser = (a, b) if BEATS[choice_a] == choice_b else (b, a)
        text, earned = await self.paid(winner, self.reward)
        await self.message.reply(
            embed=discord.Embed(
                description=(
                    f"### {await self.name(winner)} wins {MORA_EMOTE} `{text}`!\n"
                    f"-# {a.mention} chose {RPS_EMOJIS[choice_a]}\n"
                    f"-# {b.mention} chose {RPS_EMOJIS[choice_b]}"
                ),
                color=discord.Color.green(),
            )
        )
        await self.won(winner, earned)
        await self.lost(loser)


async def rockPaperScissors(channel, client):
    reward = await prize(client, channel, 5000, 7000)
    players = await last_two(channel, 50)
    if len(players) < 2:
        return await channel.send(f"{NO_EMOTE} Not enough players for the game.")
    view = RPSView(client, channel, players, reward)
    view.message = await channel.send(
        content=f"{players[0].mention} vs {players[1].mention}",
        embed=discord.Embed(
            title="Choose **Rock, Paper, or Scissors!**",
            description=f"Winner gets {MORA_EMOTE} `{reward}`.",
            color=0xFF5349,
        ),
        view=view,
    )


async def setup(bot) -> None:
    pass
