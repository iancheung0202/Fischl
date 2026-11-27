from discord.ext import commands


class PresenceFilter(commands.Cog):
    """Skips presence updates discord.py would end up discarding anyway.

    discord.py decodes every presence (activities, statuses) before checking
    whether it holds that member. We hold members for a handful of servers
    only, so nearly all of that decoding is thrown away. Doing the same check
    first gives the same result for every listener."""

    def __init__(self, bot):
        self.bot = bot
        state = bot._connection
        self._original = original = state.parsers["PRESENCE_UPDATE"]

        def parser(data):
            if not state.raw_presence_flag:
                guild = state._get_guild(int(data["guild_id"]))
                if guild is None or int(data["user"]["id"]) not in guild._members:
                    return
            original(data)

        state.parsers["PRESENCE_UPDATE"] = parser

    def cog_unload(self):
        self.bot._connection.parsers["PRESENCE_UPDATE"] = self._original


async def setup(bot):
    await bot.add_cog(PresenceFilter(bot))
