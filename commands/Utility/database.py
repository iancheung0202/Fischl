import discord
import asyncpg
import traceback

from discord.ext import commands
from discord import app_commands
from typing import Optional

class DatabaseCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="database",
        description="Execute raw SQL queries"
    )
    @app_commands.describe(
        query="Raw SQL query to execute (e.g., SELECT * FROM minigame_inventory LIMIT 5;)"
    )
    async def database_query(
        self,
        interaction: discord.Interaction,
        query: str
    ) -> None:
        if interaction.user.id != 692254240290242601:
            await interaction.response.send_message(
                "❌ Only the bot owner can use this command!",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(thinking=True, ephemeral=True)
        
        query = query.strip()
        if not query:
            await interaction.followup.send(
                "❌ Query cannot be empty!",
                ephemeral=True
            )
            return
        
        print(f"[psql] {interaction.user} ({interaction.user.id}) executed: {query}")
        
        try:
            pool = interaction.client.pool
            query_upper = query.split()[0].upper()
            
            if query_upper == "SELECT":
                await self._execute_select(interaction, pool, query)
            elif query_upper in ("INSERT", "UPDATE", "DELETE"):
                await self._execute_modify(interaction, pool, query, query_upper)
            elif query_upper in ("CREATE", "ALTER", "DROP"):
                await self._execute_ddl(interaction, pool, query, query_upper)
            else:
                await interaction.followup.send(
                    f"❓ Unknown command: `{query_upper}`\n\n"
                    f"Supported: SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, DROP",
                    ephemeral=True
                )
        
        except Exception as e:
            await self._format_error(interaction, e, query)

    async def _execute_select(self, interaction, pool, query: str) -> None:
        """Execute SELECT query and display results."""
        async with pool.acquire() as conn:
            try:
                rows = await conn.fetch(query)
            except asyncpg.PostgresError as e:
                error_msg = str(e)
                if "syntax error" in error_msg.lower():
                    await self._format_syntax_error(interaction, e, query)
                else:
                    await self._format_error(interaction, e, query)
                return
            except Exception as e:
                await self._format_error(interaction, e, query)
                return
        
        if not rows:
            embed = discord.Embed(
                title="Query Result (Empty)",
                description="```\n(no results)\n```",
                color=discord.Color.orange()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"Query Result ({len(rows)} row{'s' if len(rows) != 1 else ''})",
            color=discord.Color.green()
        )
        
        columns = list(rows[0].keys())
        embed.add_field(
            name="Columns",
            value=f"```\n{', '.join(columns)}\n```",
            inline=False
        )
        
        result_text = ""
        MAX_FIELD_LENGTH = 1024
        rows_added = 0
        
        for idx, row in enumerate(rows, 1):
            row_text = "  ".join(str(row[col])[:30] for col in columns)
            new_line = f"{idx}. {row_text}\n"
            test_text = result_text + new_line
            remaining_count = len(rows) - idx
            remaining_msg = f"\n... and {remaining_count} more rows" if remaining_count > 0 else ""
            test_value = f"```\n{test_text}{remaining_msg}\n```"
            if len(test_value) > MAX_FIELD_LENGTH:
                if rows_added > 0:
                    remaining_count = len(rows) - rows_added
                    result_text += f"\n... and {remaining_count} more rows"
                break
            result_text = test_text
            rows_added += 1
        
        embed.add_field(
            name="Data",
            value=f"```\n{result_text}\n```" if result_text else "*(no data)*",
            inline=False
        )
        
        embed.add_field(
            name="Query",
            value=f"```sql\n{query[:200]}{'...' if len(query) > 200 else ''}\n```",
            inline=False
        )
        embed.set_footer(text=f"Total rows: {len(rows)}")
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def _execute_modify(self, interaction, pool, query: str, query_type: str) -> None:
        """Execute INSERT, UPDATE, or DELETE query."""
        async with pool.acquire() as conn:
            try:
                result = await conn.execute(query)
            except asyncpg.PostgresError as e:
                error_msg = str(e)
                if "syntax error" in error_msg.lower():
                    await self._format_syntax_error(interaction, e, query)
                    return
                elif "integrity" in error_msg.lower() or "unique" in error_msg.lower() or "foreign key" in error_msg.lower():
                    embed = discord.Embed(
                        title=f"🚫 {query_type} Failed: Integrity Constraint",
                        description=f"```\n{error_msg[:500]}\n```",
                        color=discord.Color.red()
                    )
                    embed.add_field(
                        name="💡 Common Causes",
                        value="• Foreign key constraint violation\n"
                              "• Unique constraint violation\n"
                              "• NOT NULL constraint violation",
                        inline=False
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return
                else:
                    await self._format_error(interaction, e, query)
                    return
            except Exception as e:
                await self._format_error(interaction, e, query)
                return
        
        affected = "unknown"
        if result:
            result_parts = result.split()
            if result_parts:
                affected = result_parts[-1]
        
        embed = discord.Embed(
            title=f"✅ {query_type} Successful",
            description=f"**Rows affected:** `{affected}`",
            color=discord.Color.green()
        )
        embed.add_field(
            name="Query",
            value=f"```sql\n{query[:300]}{'...' if len(query) > 300 else ''}\n```",
            inline=False
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def _execute_ddl(self, interaction, pool, query: str, query_type: str) -> None:
        """Execute CREATE, ALTER, or DROP query."""
        embed = discord.Embed(
            title=f"⚠️  {query_type} Command - Proceed with Caution",
            description=f"Schema modification commands can significantly impact the database.",
            color=discord.Color.orange()
        )
        
        embed.add_field(
            name="⚠️  Warning",
            value="This will modify the database schema. Make sure you know what you're doing!",
            inline=False
        )
        
        embed.add_field(
            name="Query Preview",
            value=f"```sql\n{query[:300]}{'...' if len(query) > 300 else ''}\n```",
            inline=False
        )
        
        class ConfirmView(discord.ui.View):
            def __init__(self, parent_cog, pool, query):
                super().__init__(timeout=30)
                self.parent_cog = parent_cog
                self.pool = pool
                self.query = query
                self.confirmed = False
            
            @discord.ui.button(label="⚠️  Execute", style=discord.ButtonStyle.danger)
            async def execute(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                if button_interaction.user.id != interaction.user.id:
                    await button_interaction.response.send_message(
                        "❌ You didn't initiate this command!",
                        ephemeral=True
                    )
                    return
                
                try:
                    async with self.pool.acquire() as conn:
                        await conn.execute(self.query)
                    
                    result_embed = discord.Embed(
                        title=f"✅ {query_type} Executed",
                        description=f"Schema modification completed successfully.",
                        color=discord.Color.green()
                    )
                    result_embed.add_field(
                        name="Query",
                        value=f"```sql\n{self.query[:300]}{'...' if len(self.query) > 300 else ''}\n```",
                        inline=False
                    )
                    await button_interaction.response.send_message(embed=result_embed, ephemeral=True)
                    self.confirmed = True
                
                except Exception as e:
                    await self.parent_cog._format_error(button_interaction, e, self.query)
                
                self.stop()
            
            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                if button_interaction.user.id != interaction.user.id:
                    await button_interaction.response.send_message(
                        "❌ You didn't initiate this command!",
                        ephemeral=True
                    )
                    return
                
                await button_interaction.response.send_message(
                    "❌ Command cancelled.",
                    ephemeral=True
                )
                self.stop()
        
        view = ConfirmView(self, pool, query)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    async def _format_syntax_error(self, interaction, error: Exception, query: str) -> None:
        """Format SQL syntax errors with helpful guidance."""
        embed = discord.Embed(
            title="❌ SQL Syntax Error",
            color=discord.Color.red()
        )
        
        error_msg = str(error)
        embed.add_field(
            name="Error",
            value=f"```\n{error_msg[:300]}\n```",
            inline=False
        )
        
        if "syntax error" in error_msg.lower():
            embed.add_field(
                name="💡 SQL Syntax Help",
                value="Common mistakes:\n"
                      "- Missing semicolon at end: `SELECT * FROM table;`\n"
                      "- Misspelled table/column name\n"
                      "- Missing quotes around string values: `'value'`\n"
                      "- Missing commas between columns\n"
                      "- Wrong quote type (use double quotes for identifiers, single for strings)",
                inline=False
            )
        elif "does not exist" in error_msg.lower():
            embed.add_field(
                name="💡 Table/Column Not Found",
                value="Try one of these:\n"
                      "- Check spelling: `\\dt` in psql to list tables\n"
                      "- List columns: `\\d table_name` in psql\n"
                      "- Use correct case (usually lowercase in PostgreSQL)",
                inline=False
            )
        
        embed.add_field(
            name="Query Attempted",
            value=f"```sql\n{query[:200]}{'...' if len(query) > 200 else ''}\n```",
            inline=False
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def _format_error(self, interaction, error: Exception, query: str) -> None:
        """Format generic errors with helpful context."""
        error_type = type(error).__name__
        error_msg = str(error)
        
        embed = discord.Embed(
            title=f"❌ {error_type}",
            color=discord.Color.red()
        )
        
        embed.add_field(
            name="Error Details",
            value=f"```\n{error_msg[:400]}\n```",
            inline=False
        )
        
        if "permission" in error_msg.lower():
            embed.add_field(
                name="💡 Permission Issue",
                value="The database user might not have permission for this operation.",
                inline=False
            )
        elif "connection" in error_msg.lower():
            embed.add_field(
                name="💡 Connection Issue",
                value="The database connection may be lost. Try again in a moment.",
                inline=False
            )
        elif "type" in error_msg.lower():
            embed.add_field(
                name="💡 Type Mismatch",
                value="The data type doesn't match the column type.\n"
                      "Examples:\n"
                      "• `BIGINT` expects integers: `123` (not `'123'`)\n"
                      "• `VARCHAR` expects strings: `'text'` (with quotes)",
                inline=False
            )
        
        embed.add_field(
            name="Query Attempted",
            value=f"```sql\n{query[:200]}{'...' if len(query) > 200 else ''}\n```",
            inline=False
        )
        
        tb_str = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        if len(tb_str) < 500:
            embed.add_field(
                name="Traceback",
                value=f"```python\n{tb_str}\n```",
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DatabaseCog(bot))
