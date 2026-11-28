import io
import os  # noqa: F401 - kept so evaluated code can use it
import textwrap
import traceback

import discord
from discord.ext import commands


class Eval(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name="eval")
    @commands.is_owner()
    async def eval_command(self, ctx, *, code: str):
        """Runs the owner's Python code and answers with what it printed or raised."""
        if code.startswith("```") and code.endswith("```"):
            code = "\n".join(code.split("\n")[1:-1])

        env = {
            "bot": self.bot,
            "ctx": ctx,
            "channel": ctx.channel,
            "author": ctx.author,
            "guild": ctx.guild,
            "message": ctx.message,
            "self": self,
        }
        env.update(globals())

        try:
            to_compile = f'async def func():\n{textwrap.indent(code, "  ")}'
            exec(to_compile, env)
            func = env["func"]
            ret = await func()
            if ret is not None:
                result = str(ret)
                if len(result) > 2000:
                    await ctx.send(
                        "Output too long, sending as file:",
                        file=discord.File(io.StringIO(result), "output.txt"),
                    )
                else:
                    await ctx.send(result)

        except Exception:
            error = f"```py\n{traceback.format_exc()}\n```"
            if len(error) > 2000:
                await ctx.send(
                    "Error too long, sending as file:",
                    file=discord.File(io.StringIO(error), "error.txt"),
                )
            else:
                await ctx.send(error)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Eval(bot))
