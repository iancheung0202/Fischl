import time

import discord

from commands.Events.config import CIRCLE_EMOJI, CROSS_EMOJI, MORA_EMOTE
from commands.Events.games.common import count, earn, prize, took_part
from commands.Events.games.guess import recent_authors

LINES = (
    [[(row, column) for column in range(3)] for row in range(3)]
    + [[(row, column) for row in range(3)] for column in range(3)]
    + [[(0, 0), (1, 1), (2, 2)], [(0, 2), (1, 1), (2, 0)]]
)


class TicTacTokButton(discord.ui.Button):
    def __init__(self, x: int, y: int):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=x)
        self.x = x
        self.y = y

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if view.winner_id:
            return await interaction.response.defer()
        if interaction.user.id != view.current_player:
            mine = interaction.user.id in view.players
            return await interaction.response.send_message(
                "It's not your turn!" if mine else "You are not part of this game!",
                ephemeral=True,
            )
        self.disabled = True
        self.label = ""
        self.emoji = view.mark()
        view.board[self.x][self.y] = view.current_player
        view.moved.add(view.current_player)
        line = view.winning_line()
        if line:
            return await view.win(interaction, line)
        if all(cell for row in view.board for cell in row):
            return await view.close(interaction, "It's a draw!")
        view.current_player = next(
            player for player in view.players if player != view.current_player
        )
        content, embed = view.get_game_state()
        await interaction.response.edit_message(content=content, embed=embed, view=view)


class TicTacTokView(discord.ui.View):
    """A 3x3 board for two members who take turns; three in a line is paid."""

    def __init__(self, player1, player2, reward, start_time=None):
        super().__init__(timeout=300)
        self.players = {player1.id: player1, player2.id: player2}
        self.marks = {player1.id: CROSS_EMOJI, player2.id: CIRCLE_EMOJI}
        self.reward = reward
        self.start_time = start_time
        self.current_player = player1.id
        self.board = [[None] * 3 for _ in range(3)]
        self.moved = set()
        self.winner_id = None
        self.message = None
        for row in range(3):
            for column in range(3):
                self.add_item(TicTacTokButton(row, column))

    def mark(self) -> str:
        """Gives the emoji of the member whose turn it is."""
        return self.marks[self.current_player]

    def get_game_state(self) -> tuple:
        """Gives the line saying whose turn it is and the embed naming the two members."""
        listed = "\n".join(
            f"{self.marks[uid]} {member.mention}"
            for uid, member in self.players.items()
        )
        embed = discord.Embed(
            title="Tik Tac Tok",
            description=f"First to match 3 symbols in a line wins {MORA_EMOTE} `{self.reward}`.\n\n{listed}",
            color=discord.Color.blurple(),
        )
        return (f"It's {self.mark()} <@{self.current_player}>'s turn!", embed)

    def winning_line(self) -> list:
        """Gives the three squares of a finished line, or an empty list."""
        for line in LINES:
            owners = {self.board[row][column] for row, column in line}
            if len(owners) == 1 and None not in owners:
                return line
        return []

    async def close(self, interaction: discord.Interaction, content: str) -> None:
        """Ends the game with every square greyed out and the result as the message text."""
        self.stop()
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content=content, view=self)
        await took_part(
            interaction.client, interaction.channel, self.moved, but={self.winner_id}
        )

    async def win(self, interaction: discord.Interaction, line: list) -> None:
        """Pays the member who finished a line and shows that line in green."""
        self.winner_id = winner = interaction.user.id
        for child in self.children:
            if (child.x, child.y) in line:
                child.style = discord.ButtonStyle.success
        client, channel = interaction.client, interaction.channel
        text, earned = await earn(client, channel, winner, self.reward)
        await self.close(
            interaction,
            f"🎉 <@{winner}> won the Tik Tac Tok match and earned {MORA_EMOTE} `{text}`!",
        )
        await count(client, channel, winner, earned, self.start_time, duel=True)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        try:
            await self.message.edit(view=self)
        except discord.HTTPException:
            pass


async def ticTacTok(channel, client):
    players = await recent_authors(channel, client, 50, 2)
    if len(players) < 2:
        return
    reward = await prize(client, channel, 5000, 7000)
    view = TicTacTokView(*players, reward, start_time=time.time())
    content, embed = view.get_game_state()
    view.message = await channel.send(content=content, embed=embed, view=view)


async def setup(bot) -> None:
    pass
