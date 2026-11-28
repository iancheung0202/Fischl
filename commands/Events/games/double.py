import time

import discord

from commands.Events.config import MORA_EMOTE, NO_EMOTE
from commands.Events.games.common import count, earn, prize, took_part, user_and_title

TITLE = "Double or Keep"
EXPIRED = f"{NO_EMOTE} This game session has expired!"


def offer(reward: int, times: int) -> discord.Embed:
    return discord.Embed(
        title=TITLE,
        description=f"You can either keep {MORA_EMOTE} `{reward}`, or double it and give it to the next person **({times} times remaining)**.",
        color=0xADD8E6,
    )


class ClaimButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Claim Reward",
            style=discord.ButtonStyle.red,
            custom_id="claim_reward_",
        )

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if await view.refused(
            interaction, "You can't claim the reward for someone else!"
        ):
            return
        await view.finish(interaction, view.current_user, "has claimed the current")


class UserSelect(discord.ui.Select):
    def __init__(self, users, current_user):
        super().__init__(
            placeholder="Select a user",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label=user.display_name, value=str(user.id))
                for user in users or []
                if user.id != current_user.id
            ],
            custom_id="userSelectEvent",
        )

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if await view.refused(interaction, "You're not allowed to make this choice."):
            return
        chosen = next(
            user for user in view.valid_users if user.id == int(self.values[0])
        )
        view.previous_user = view.current_user
        view.reward *= 2
        view.times_remaining -= 1
        if view.times_remaining <= 0:
            return await view.finish(interaction, chosen, "receives the final")
        embed = offer(view.reward, view.times_remaining)
        embed.set_footer(text=f"Last doubled by {view.current_user.display_name}")
        await interaction.message.delete()
        await interaction.channel.send(
            content=chosen.mention,
            embed=embed,
            view=UserSelectView(
                view.valid_users,
                view.reward,
                view.times_remaining,
                chosen,
                view.current_user,
                view.start_time,
                view.participant_ids,
            ),
        )


class UserSelectView(discord.ui.View):
    """One round: the member whose turn it is keeps the reward or doubles it for someone else.

    Made with no arguments it only answers presses on rounds from before a restart.
    """

    def __init__(
        self,
        valid_users=None,
        reward=None,
        times_remaining=None,
        current_user=None,
        previous_user=None,
        start_time=None,
        participant_ids=None,
    ):
        super().__init__(timeout=None)
        self.valid_users = valid_users
        self.reward = reward
        self.times_remaining = times_remaining
        self.current_user = current_user
        self.previous_user = previous_user
        self.start_time = start_time
        self.participant_ids = participant_ids if participant_ids is not None else set()
        self.done = current_user is None
        self.add_item(UserSelect(valid_users, current_user))
        self.add_item(ClaimButton())

    async def refused(self, interaction: discord.Interaction, not_yours: str) -> bool:
        """Answers a press that may not go on; False for the first press of the member whose turn it is."""
        if self.done:
            await interaction.response.send_message(EXPIRED, ephemeral=True)
        elif interaction.user.id != self.current_user.id:
            await interaction.response.send_message(not_yours, ephemeral=True)
        else:
            self.done = True
            self.participant_ids.add(interaction.user.id)
            return False
        return True

    async def finish(self, interaction: discord.Interaction, winner, how: str) -> None:
        """Pays the reward to the winner and replaces the round with the result."""
        client, channel = interaction.client, interaction.channel
        text, earned = await earn(client, channel, winner.id, self.reward)
        name = await user_and_title(winner.id, interaction.guild.id, client.pool)
        await interaction.message.delete()
        embed = discord.Embed(
            title=TITLE,
            description=f"{name} {how} reward of {MORA_EMOTE} `{text}`!",
            color=discord.Color.green(),
        )
        if self.previous_user:
            embed.set_footer(text=f"Last doubled by {self.previous_user.display_name}")
        await channel.send(embed=embed)
        await count(client, channel, winner.id, earned, self.start_time)
        await took_part(client, channel, self.participant_ids, but={winner.id})


async def recent_members(channel, messages: int) -> list:
    """Gives the members still in the server, newest first, who wrote the last messages of a channel."""
    members = {}
    async for message in channel.history(limit=messages):
        author = message.author
        if author.bot or author.id in members:
            continue
        try:
            members[author.id] = await channel.guild.fetch_member(author.id)
        except discord.NotFound:
            members[author.id] = None
    return [member for member in members.values() if member]


async def doubleOrKeep(channel, client):
    reward = await prize(client, channel, 300, 500)
    users = await recent_members(channel, 20)
    if len(users) < 2:
        return await channel.send(
            embed=discord.Embed(
                description=f"{NO_EMOTE} Not enough unique recent messaging users for the game."
            )
        )
    await channel.send(
        content=users[0].mention,
        embed=offer(reward, 5),
        view=UserSelectView(users, reward, 5, users[0], None, time.time()),
    )


async def setup(bot) -> None:
    pass
