import asyncio
import random
import time

import discord

from commands.Events.config import MORA_EMOTE, NO_EMOTE
from commands.Events.games.common import count, earn, prize, took_part

DECK = [
    (rank, suit)
    for rank in ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
    for suit in ["♠", "♥", "♦", "♣"]
]
SUIT_EMOJIS = {"♠": "♠️", "♥": "♥️", "♦": "♦️", "♣": "♣️"}
JOIN_SECONDS = 120


def hand_value(cards) -> int:
    """Gives the blackjack value of a hand, counting an ace as 1 when 11 would go over 21."""
    value = aces = 0
    for rank, _ in cards:
        if rank in ("J", "Q", "K"):
            value += 10
        elif rank == "A":
            aces += 1
            value += 11
        else:
            value += int(rank)
    while value > 21 and aces:
        value -= 10
        aces -= 1
    return value


def shown(cards, hide_first: bool = False) -> str:
    """Gives a hand as text, with the first card face down when asked."""
    return " ".join(
        "`??`" if hide_first and place == 0 else f"`{rank}{SUIT_EMOJIS[suit]}`"
        for place, (rank, suit) in enumerate(cards)
    )


def lobby_embed(reward: int, last_line: str) -> discord.Embed:
    return discord.Embed(
        title="🃏 Group Blackjack Event!",
        description=(
            f"A blackjack table just opened! Click the button below to start **your own game**.\n\n"
            f"**Win:** {MORA_EMOTE} `{reward:,}` • **Natural BJ:** {MORA_EMOTE} `{int(reward * 1.5):,}` (1.5×)\n\n"
            f"-# {last_line}"
        ),
        color=0x1A6635,
    )


class EventBlackjackGameView(discord.ui.View):
    """One member's hand against the dealer, shown only to that member."""

    def __init__(
        self,
        client,
        channel,
        user_id,
        reward,
        dealer_cards,
        player_cards,
        active_players,
    ):
        super().__init__(timeout=60)
        self.client = client
        self.channel = channel
        self.user_id = user_id
        self.reward = reward
        self.dealer_cards = dealer_cards
        self.player_cards = player_cards
        self.active_players = active_players
        self.game_over = False
        self.message = None
        self.start_time = time.time()

    def draw(self):
        """Gives a card that is in neither hand."""
        used = self.dealer_cards + self.player_cards
        return random.choice([card for card in DECK if card not in used])

    def hands(self, embed: discord.Embed) -> discord.Embed:
        """Adds both hands to an embed; the dealer's first card stays hidden until the game is over."""
        if self.game_over:
            dealer = (
                f"{shown(self.dealer_cards)} (Value: {hand_value(self.dealer_cards)})"
            )
        else:
            dealer = f"{shown(self.dealer_cards, hide_first=True)} (Value: ?)"
        embed.add_field(name="🎩 Dealer", value=dealer, inline=False)
        embed.add_field(
            name="🎲 Your Hand",
            value=f"{shown(self.player_cards)} (Value: {hand_value(self.player_cards)})",
            inline=False,
        )
        return embed

    def embed(self, title, description, color) -> discord.Embed:
        embed = self.hands(
            discord.Embed(title=title, description=description, color=color)
        )
        embed.add_field(
            name="🏆 Reward",
            value=f"{MORA_EMOTE} `{self.reward:,}` if you win!",
            inline=False,
        )
        return embed

    def close(self) -> None:
        self.game_over = True
        self.active_players.discard(self.user_id)
        self.clear_items()
        self.stop()

    async def pay(self, amount: int) -> str:
        """Pays the member and counts the win; gives the amount as shown."""
        text, earned = await earn(self.client, self.channel, self.user_id, amount)
        await count(
            self.client,
            self.channel,
            self.user_id,
            earned,
            self.start_time,
            joined=False,
        )
        return text

    async def finish(self, interaction, title, description, color, amount=0) -> None:
        self.close()
        await interaction.response.edit_message(
            embed=self.embed(title, description, color), view=self
        )
        if amount > 0:
            await self.pay(amount)

    async def resolve(self, interaction) -> None:
        """Draws for the dealer up to 17 and settles the hand."""
        while hand_value(self.dealer_cards) < 17:
            self.dealer_cards.append(self.draw())
        dealer = hand_value(self.dealer_cards)
        player = hand_value(self.player_cards)
        if dealer > 21 or player > dealer:
            reason = "Dealer busted!" if dealer > 21 else "You beat the dealer!"
            await self.finish(
                interaction,
                "🎉 You Win!",
                f"{reason} You win {MORA_EMOTE} `{self.reward:,}`!",
                discord.Color.green(),
                self.reward,
            )
        elif dealer > player:
            await self.finish(
                interaction,
                "💔 You Lose!",
                "Dealer wins! Better luck next time.",
                discord.Color.red(),
            )
        else:
            consolation = self.reward // 4
            await self.finish(
                interaction,
                "🤝 Push!",
                f"It's a tie! You receive a consolation of {MORA_EMOTE} `{consolation:,}`.",
                discord.Color.yellow(),
                consolation,
            )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This isn't your game!", ephemeral=True
            )
            return False
        if self.game_over:
            await interaction.response.defer()
            return False
        return True

    @discord.ui.button(
        label="Hit", style=discord.ButtonStyle.primary, emoji="🎯", row=0
    )
    async def hit_button(self, interaction: discord.Interaction, button):
        self.player_cards.append(self.draw())
        value = hand_value(self.player_cards)
        if value > 21:
            await self.finish(
                interaction,
                "💥 Bust!",
                "You went over 21! No reward this time.",
                discord.Color.red(),
            )
        elif value == 21:
            await self.resolve(interaction)
        else:
            embed = self.embed(
                "🎲 Blackjack — Your Turn", "Hit or Stand?", discord.Color.blue()
            )
            embed.set_footer(text="You have 60 seconds to make each move!")
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(
        label="Stand", style=discord.ButtonStyle.green, emoji="✋", row=0
    )
    async def stand_button(self, interaction: discord.Interaction, button):
        await self.resolve(interaction)

    @discord.ui.button(
        label="Double Down", style=discord.ButtonStyle.red, emoji="💵", row=0
    )
    async def double_down_button(self, interaction: discord.Interaction, button):
        self.reward *= 2
        self.player_cards.append(self.draw())
        if hand_value(self.player_cards) > 21:
            await self.finish(
                interaction,
                "💥 Bust!",
                "You went over 21 after doubling down! No reward.",
                discord.Color.red(),
            )
        else:
            await self.resolve(interaction)

    @discord.ui.button(
        label="Surrender", style=discord.ButtonStyle.grey, emoji="🏳️", row=1
    )
    async def surrender_button(self, interaction: discord.Interaction, button):
        consolation = self.reward // 4
        await self.finish(
            interaction,
            "🏳️ Surrendered",
            f"You surrendered and receive a consolation of {MORA_EMOTE} `{consolation:,}`.",
            discord.Color.orange(),
            consolation,
        )

    async def on_timeout(self):
        if self.game_over or not self.message:
            return
        self.close()
        embed = self.hands(
            discord.Embed(
                title="⏰ Game Timeout!",
                description="You took too long! Your game has ended without a reward.",
                color=discord.Color.red(),
            )
        )
        try:
            await self.message.edit(embed=embed, view=self)
        except Exception:
            pass


class EventBlackjackLobbyView(discord.ui.View):
    """The table: each member may start one game of their own until the deadline."""

    def __init__(self, client, channel, reward):
        super().__init__(timeout=None)
        self.client = client
        self.channel = channel
        self.reward = reward
        self.active_players = set()
        self.all_participants = set()
        self.deadline = time.time() + JOIN_SECONDS
        self.game_msg = None

    def refusal(self, uid: int):
        """Gives why a member may not start a game, or None when they may."""
        if time.time() > self.deadline:
            return "The blackjack table is closed! No new games can be started."
        if uid in self.active_players:
            return "You already have an active game!"
        if uid in self.all_participants:
            return "You've already played your game for this event!"

    async def deal(self, interaction, game) -> None:
        """Shows a member their first two cards, settling at once on a natural blackjack."""
        player = hand_value(game.player_cards)
        dealer = hand_value(game.dealer_cards)
        if player != 21 and dealer != 21:
            embed = game.embed(
                "🃏 Blackjack — Your Turn!", "Hit or Stand?", discord.Color.blue()
            )
            embed.set_footer(
                text="You have 60 seconds per move • Double Down & Surrender available!"
            )
            await interaction.response.send_message(
                embed=embed, view=game, ephemeral=True
            )
            game.message = await interaction.original_response()
            return
        game.game_over = True
        self.active_players.discard(game.user_id)
        game.stop()
        if dealer != 21:
            text, earned = await earn(
                self.client, self.channel, game.user_id, int(self.reward * 1.5)
            )
            embed = game.embed(
                "🎰 Natural Blackjack!",
                f"You got blackjack! You win {MORA_EMOTE} `{text}`! (1.5× bonus)",
                discord.Color.gold(),
            )
        elif player == 21:
            embed = game.embed(
                "🤝 Push!",
                "Both you and the dealer got blackjack! No reward.",
                discord.Color.yellow(),
            )
        else:
            embed = game.embed(
                "💔 Dealer Blackjack!",
                "The dealer got natural blackjack! Better luck next time.",
                discord.Color.red(),
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        if dealer != 21:
            await count(
                self.client,
                self.channel,
                game.user_id,
                earned,
                game.start_time,
                joined=False,
            )

    @discord.ui.button(
        label="Play Blackjack", style=discord.ButtonStyle.green, emoji="🃏"
    )
    async def join_button(self, interaction: discord.Interaction, button):
        uid = interaction.user.id
        refusal = self.refusal(uid)
        if refusal:
            return await interaction.response.send_message(
                f"{NO_EMOTE} {refusal}", ephemeral=True
            )
        self.active_players.add(uid)
        self.all_participants.add(uid)
        deck = list(DECK)
        random.shuffle(deck)
        game = EventBlackjackGameView(
            self.client,
            self.channel,
            uid,
            self.reward,
            [deck[1], deck[3]],
            [deck[0], deck[2]],
            self.active_players,
        )
        await self.deal(interaction, game)
        players = len(self.all_participants)
        embed = lobby_embed(
            self.reward, "New games close in 2 minutes from start • One game per player"
        )
        embed.set_footer(
            text=f"{players} player{'s' if players != 1 else ''} playing so far!"
        )
        try:
            await self.game_msg.edit(embed=embed, view=self)
        except Exception:
            pass


async def groupBlackjack(channel, client):
    reward = await prize(client, channel, 3000, 5000)
    embed = lobby_embed(
        reward,
        "New games close in 2 minutes • One game per player • Beat the dealer to win!",
    )
    embed.set_footer(text="Hit, Stand, Double Down or Surrender!")
    lobby = EventBlackjackLobbyView(client, channel, reward)
    lobby.game_msg = await channel.send(embed=embed, view=lobby)
    await asyncio.sleep(JOIN_SECONDS)

    lobby.join_button.disabled = True
    players = len(lobby.all_participants)
    try:
        await lobby.game_msg.edit(
            embed=discord.Embed(
                title="🃏 Group Blackjack — Table Closed",
                description=(
                    f"The blackjack table has closed. No new games can be started.\n\n"
                    f"**{players}** player{'s' if players != 1 else ''} participated!"
                ),
                color=discord.Color.greyple(),
            ),
            view=lobby,
        )
    except Exception:
        pass
    await asyncio.sleep(30)
    lobby.stop()
    await took_part(client, channel, lobby.all_participants)


async def setup(bot) -> None:
    pass
