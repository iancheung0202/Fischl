import traceback

import asyncpg
import discord
from discord import app_commands
from discord.ext import commands

OWNER = 692254240290242601
SYNTAX_HELP = (
    "Common mistakes:\n"
    "- Missing semicolon at end: `SELECT * FROM table;`\n"
    "- Misspelled table/column name\n"
    "- Missing quotes around string values: `'value'`\n"
    "- Missing commas between columns\n"
    "- Wrong quote type (use double quotes for identifiers, single for strings)"
)
KINDS = ("SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP")
# The first word found in an error's text decides which hint is shown with it.
HINTS = {
    "permission": (
        "💡 Permission Issue",
        "The database user might not have permission for this operation.",
    ),
    "connection": (
        "💡 Connection Issue",
        "The database connection may be lost. Try again in a moment.",
    ),
    "type": (
        "💡 Type Mismatch",
        "The data type doesn't match the column type.\n"
        "Examples:\n"
        "• `BIGINT` expects integers: `123` (not `'123'`)\n"
        "• `VARCHAR` expects strings: `'text'` (with quotes)",
    ),
}
INTEGRITY_CAUSES = (
    "• Foreign key constraint violation\n"
    "• Unique constraint violation\n"
    "• NOT NULL constraint violation"
)


def shown(query, limit):
    """Gives the query as a code block, cut off after `limit` characters."""
    return f"```sql\n{query[:limit]}{'...' if len(query) > limit else ''}\n```"


def table(rows, columns):
    """Lists as many rows as fit in one embed field, and says how many are left."""
    text = ""
    for number, row in enumerate(rows, 1):
        line = "  ".join(str(row[column])[:30] for column in columns)
        longer = f"{text}{number}. {line}\n"
        left = len(rows) - number
        rest = f"\n... and {left} more rows" if left > 0 else ""
        if len(f"```\n{longer}{rest}\n```") > 1024:
            if number > 1:
                text += f"\n... and {len(rows) - number + 1} more rows"
            break
        text = longer
    return f"```\n{text}\n```" if text else "*(no data)*"


def result_embed(rows, query):
    """Builds the embed showing what a SELECT found."""
    if not rows:
        return discord.Embed(
            title="Query Result (Empty)",
            description="```\n(no results)\n```",
            color=discord.Color.orange(),
        )
    embed = discord.Embed(
        title=f"Query Result ({len(rows)} row{'s' if len(rows) != 1 else ''})",
        color=discord.Color.green(),
    )
    columns = list(rows[0].keys())
    embed.add_field(
        name="Columns", value=f"```\n{', '.join(columns)}\n```", inline=False
    )
    embed.add_field(name="Data", value=table(rows, columns), inline=False)
    embed.add_field(name="Query", value=shown(query, 200), inline=False)
    embed.set_footer(text=f"Total rows: {len(rows)}")
    return embed


def syntax_embed(error, query):
    """Builds the embed for a query Postgres could not parse."""
    embed = discord.Embed(title="❌ SQL Syntax Error", color=discord.Color.red())
    embed.add_field(name="Error", value=f"```\n{str(error)[:300]}\n```", inline=False)
    embed.add_field(name="💡 SQL Syntax Help", value=SYNTAX_HELP, inline=False)
    embed.add_field(name="Query Attempted", value=shown(query, 200), inline=False)
    return embed


def integrity_embed(kind, text):
    """Builds the embed for a change that broke a constraint."""
    embed = discord.Embed(
        title=f"🚫 {kind} Failed: Integrity Constraint",
        description=f"```\n{text[:500]}\n```",
        color=discord.Color.red(),
    )
    embed.add_field(name="💡 Common Causes", value=INTEGRITY_CAUSES, inline=False)
    return embed


def error_embed(error, query):
    """Builds the embed for any other error, with a hint and a short traceback."""
    text = str(error)
    embed = discord.Embed(title=f"❌ {type(error).__name__}", color=discord.Color.red())
    embed.add_field(name="Error Details", value=f"```\n{text[:400]}\n```", inline=False)
    for word, (name, hint) in HINTS.items():
        if word in text.lower():
            embed.add_field(name=name, value=hint, inline=False)
            break
    embed.add_field(name="Query Attempted", value=shown(query, 200), inline=False)
    trace = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    if len(trace) < 500:
        embed.add_field(
            name="Traceback", value=f"```python\n{trace}\n```", inline=False
        )
    return embed


def failure_embed(error, query, kind=None):
    """Picks the embed for a failed query; only changes to rows pass a `kind`."""
    text = str(error).lower()
    if isinstance(error, asyncpg.PostgresError):
        if "syntax error" in text:
            return syntax_embed(error, query)
        if kind and any(w in text for w in ("integrity", "unique", "foreign key")):
            return integrity_embed(kind, str(error))
    return error_embed(error, query)


async def select(interaction, pool, query):
    """Runs a SELECT and shows its rows."""
    async with pool.acquire() as connection:
        try:
            rows = await connection.fetch(query)
        except Exception as e:
            embed = failure_embed(e, query)
            return await interaction.followup.send(embed=embed, ephemeral=True)
    await interaction.followup.send(embed=result_embed(rows, query), ephemeral=True)


async def modify(interaction, pool, query, kind):
    """Runs an INSERT, UPDATE or DELETE and says how many rows it changed."""
    async with pool.acquire() as connection:
        try:
            result = await connection.execute(query)
        except Exception as e:
            embed = failure_embed(e, query, kind)
            return await interaction.followup.send(embed=embed, ephemeral=True)
    words = result.split() if result else []
    embed = discord.Embed(
        title=f"✅ {kind} Successful",
        description=f"**Rows affected:** `{words[-1] if words else 'unknown'}`",
        color=discord.Color.green(),
    )
    embed.add_field(name="Query", value=shown(query, 300), inline=False)
    await interaction.followup.send(embed=embed, ephemeral=True)


class ConfirmView(discord.ui.View):
    """The Execute and Cancel buttons shown before the schema is changed."""

    def __init__(self, owner, pool, query, kind):
        super().__init__(timeout=30)
        self.owner = owner
        self.pool = pool
        self.query = query
        self.kind = kind

    async def refused(self, interaction):
        """Turns away anyone but the member who ran the command."""
        if interaction.user.id == self.owner:
            return False
        await interaction.response.send_message(
            "❌ You didn't initiate this command!", ephemeral=True
        )
        return True

    @discord.ui.button(label="⚠️  Execute", style=discord.ButtonStyle.danger)
    async def execute(self, interaction, button):
        """Runs the query and reports how it went."""
        if await self.refused(interaction):
            return
        try:
            async with self.pool.acquire() as connection:
                await connection.execute(self.query)
            embed = discord.Embed(
                title=f"✅ {self.kind} Executed",
                description="Schema modification completed successfully.",
                color=discord.Color.green(),
            )
            embed.add_field(name="Query", value=shown(self.query, 300), inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            embed = error_embed(e, self.query)
            await interaction.followup.send(embed=embed, ephemeral=True)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction, button):
        """Drops the query."""
        if await self.refused(interaction):
            return
        await interaction.response.send_message("❌ Command cancelled.", ephemeral=True)
        self.stop()


def several(query):
    """Says whether more than one statement was given; a semicolon inside text counts too."""
    return ";" in query.strip().rstrip("; \n\t")


async def confirm(interaction, pool, query, kind):
    """Shows a CREATE, ALTER, DROP or several statements and waits for a yes before running."""
    warning = (
        "This will modify the database schema. Make sure you know what you're doing!"
    )
    if several(query):
        warning = "This holds more than one statement, and every one of them will run. Make sure you know what you're doing!"
    embed = discord.Embed(
        title=f"⚠️  {kind} Command - Proceed with Caution",
        description="Schema modification commands can significantly impact the database.",
        color=discord.Color.orange(),
    )
    embed.add_field(name="⚠️  Warning", value=warning, inline=False)
    embed.add_field(name="Query Preview", value=shown(query, 300), inline=False)
    view = ConfirmView(interaction.user.id, pool, query, kind)
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)


async def execute(interaction, query):
    """Sends the query to the handler for its first word."""
    pool = interaction.client.pool
    kind = query.split()[0].upper()
    if kind not in KINDS:
        await interaction.followup.send(
            f"❓ Unknown command: `{kind}`\n\n"
            f"Supported: SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, DROP",
            ephemeral=True,
        )
    elif kind in ("CREATE", "ALTER", "DROP") or several(query):
        await confirm(interaction, pool, query, kind)
    elif kind == "SELECT":
        await select(interaction, pool, query)
    else:
        await modify(interaction, pool, query, kind)


class DatabaseCog(commands.Cog):
    """The owner's command for running SQL against the bot's database."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="database", description="Execute raw SQL queries")
    @app_commands.describe(
        query="minigame_inventory/mora/progression/chests/rewards/cosmetics/elite/settings/guild_settings"
    )
    async def database_query(
        self, interaction: discord.Interaction, query: str
    ) -> None:
        """Runs one SQL statement for the owner and shows the outcome."""
        if interaction.user.id != OWNER:
            await interaction.response.send_message(
                "❌ Only the bot owner can use this command!", ephemeral=True
            )
            return
        await interaction.response.defer(thinking=True, ephemeral=True)
        query = query.strip()
        if not query:
            await interaction.followup.send("❌ Query cannot be empty!", ephemeral=True)
            return

        print(f"[psql] {interaction.user} ({interaction.user.id}) executed: {query}")
        try:
            await execute(interaction, query)
        except Exception as e:
            embed = error_embed(e, query)
            await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(DatabaseCog(bot))
