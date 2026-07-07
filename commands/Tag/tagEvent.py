import discord, asyncio, datetime, time, aiohttp
from discord.ext import commands, tasks
from firebase_admin import db
import os

try:
    from .tagEnabledGuilds import enabledGuilds
except:
    enabledGuilds = []
last_modified = os.path.getmtime("./commands/Tag/tagEnabledGuilds.py") if os.path.exists("./commands/Tag/tagEnabledGuilds.py") else 0

def check_reload():
    global enabledGuilds, last_modified
    current_modified = os.path.getmtime("./commands/Tag/tagEnabledGuilds.py")
    if current_modified > last_modified:
        with open("./commands/Tag/tagEnabledGuilds.py", "r") as f:
            for line in f:
                if line.startswith("enabledGuilds ="):
                    enabledGuilds = eval(line.split("=")[1].strip())
                    last_modified = current_modified
                    print("Reloaded tagEnabledGuilds.py")
                    break

def word(n):
    return str(n) + ("th" if 4 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th"))

def script(string, user, guild):
    replacements = {
        "{mention}": user.mention,
        "{server}": guild.name,
        "{user}": user.name,
        "{tag}": user.primary_guild.tag if user.primary_guild else "No Tag"
    }
    for k, v in replacements.items():
        string = string.replace(k, v)
    return string

class TagRoleHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tag_check.start()

    def cog_unload(self):
        self.tag_check.cancel()

    @tasks.loop(minutes=1)
    async def tag_check(self):
        try:
            check_reload()
        except Exception as e:
            print(f"Error reloading guilds: {e}")
        
        try:
            ref = db.reference("/Tag Roles")
            all_configs = ref.get()
        except Exception as e:
            print(f"Error fetching tag roles: {e}")
            return

        if not all_configs:
            return

        for guild_id in enabledGuilds:
            try:
                guild = self.bot.get_guild(guild_id)
                if not guild: 
                    continue

                # Force chunk to ensure cache is up to date
                # try:
                #     if not guild.chunked:
                #         await asyncio.wait_for(guild.chunk(), timeout=20.0)
                #         print(f"Chunking guild {guild.name} ({guild.id}) with {guild.member_count} members")
                # except asyncio.TimeoutError:
                #     print(f"Timed out chunking guild {guild.name}")
                # except Exception as e:
                #     print(f"Error chunking guild {guild.name}: {e}")
                
                config = None
                for _, val in all_configs.items():
                    if val.get('Server ID') == guild_id:
                        config = val
                        break
                if not config: continue
                
                # Validate config
                if 'Role ID' not in config or 'Log Channel ID' not in config or 'Tag Server ID' not in config:
                    # print(f"Incomplete config for guild {guild.name}")
                    continue

                role = guild.get_role(config['Role ID'])
                log_channel = guild.get_channel(config['Log Channel ID'])
                tag_server_id = config['Tag Server ID']
                
                if not role or not log_channel:
                    # print(f"Missing role/channel in {guild.name}")
                    continue
                
                # Check bot permissions
                if not guild.me.guild_permissions.manage_roles:
                    # print(f"Missing manage_roles permission in {guild.name}")
                    continue
                
                if role >= guild.me.top_role:
                    if log_channel:
                        embed = discord.Embed(
                            description=f"⚠️ Cannot manage tag role {role.mention} because it is higher than or equal to the bot's top role. Make sure the bot's role is higher in your server settings.",
                            colour=0xFFFF00
                        )
                        try:
                            await log_channel.send(embed=embed)
                        except: pass
                    # print(f"Role {role.name} is higher than bot's top role in {guild.name}")
                    continue

                # Check all members
                checked_count = 0
                tag_match_count = 0
                
                start_time = time.time()
                # print(f"Checking guild {guild.name} ({guild.id}) with {guild.member_count} members for tag role synchronization")
                async for member in guild.fetch_members(limit=None):
                    checked_count += 1
                    
                    try:
                        # Ensure IDs are compared as integers
                        m_tag_id = member.primary_guild.id if member.primary_guild else None
                        t_server_id = int(tag_server_id) if tag_server_id else None
                        
                        has_tag = m_tag_id == t_server_id and member.primary_guild.tag is not None
                        has_role = role in member.roles
                        
                        if has_tag:
                            tag_match_count += 1
                        
                        # Should have role but doesn't
                        if has_tag and not has_role:
                            await member.add_roles(role)
                            embed = discord.Embed(
                                description=f"✅ {member.mention} was given the tag role",
                                colour=0x00FF00
                            )
                            try:
                                await log_channel.send(embed=embed)
                            except: pass
                            await self.send_thank_you(member, guild)
                        
                        # Shouldn't have role but does
                        elif not has_tag and has_role:
                            await member.remove_roles(role)
                            embed = discord.Embed(
                                description=f"❌ {member.mention} had tag role removed",
                                colour=0xFF0000
                            )
                            try:
                                await log_channel.send(embed=embed)
                            except: pass
                    except discord.Forbidden:
                        print(f"Forbidden: Could not modify role for {member} in {guild.name}")
                        pass
                    except Exception as e:
                        print(f"Error processing {member}: {e}")
                
                # print(f"Guild {guild.name}: Checked {checked_count} members. Found {tag_match_count} with matching tag. (Time taken: {time.time() - start_time:.2f}s)")
            except Exception as e:
                print(f"Error processing guild {guild_id}: {e}")
            
        # print("Finished tag role check!")

    @tag_check.error
    async def tag_check_error(self, error):
        print(f"Tag check loop crashed: {error}")

    async def send_thank_you(self, member, guild):
        """Send thank you message if configured and cooldown passed"""
        # Check thank you config
        ref = db.reference("/Tag Thanks")
        thanks_config = None
        
        # Optimize: Query by Server ID instead of fetching all
        try:
            snapshot = ref.order_by_child('Server ID').equal_to(guild.id).get()
            if snapshot:
                # snapshot is a dict {key: val}, take the first one
                thanks_config = list(snapshot.values())[0]
        except Exception as e:
            print(f"Error fetching Tag Thanks config: {e}")
            
        if not thanks_config: return
        
        # Check cooldown
        ref = db.reference("/Tag Thanks Cooldown")
        last_thanked = 0
        
        # Query by User instead of fetching all
        try:
            # We query by User, then filter by Guild in memory (since we can only query 1 field)
            # Assuming User ID is more selective than Guild ID
            snapshot = ref.order_by_child('User').equal_to(member.id).get()
            if snapshot:
                for key, val in snapshot.items():
                    if val['Guild'] == guild.id:
                        last_thanked = val['Timestamp']
                        if time.time() - last_thanked < 86400:  # 24 hours
                            return
                        else:
                            ref.child(key).delete()
        except Exception as e:
            print(f"Error checking cooldown: {e}")
        
        # Record new thank
        ref.push().set({
            "User": member.id,
            "Guild": guild.id,
            "Timestamp": time.time()
        })
        
        # Get message content
        msg_ref = db.reference("/Tag Thanks Message")
        msg_config = None
        
        # Query by Server ID
        try:
            snapshot = msg_ref.order_by_child('Server ID').equal_to(guild.id).get()
            if snapshot:
                msg_config = list(snapshot.values())[0]
        except Exception as e:
            print(f"Error fetching Tag Thanks Message: {e}")
        
        # Prepare message
        content = script(msg_config.get("Message Content", ""), member, guild) if msg_config else ""
        embed = None
        
        if msg_config and any(msg_config.get(k) for k in ["Title", "Description", "Image Link"]):
            color_str = msg_config.get("Color", "")
            color = discord.Color(int(color_str[1:], 16)) if color_str.startswith("#") else discord.Color.blurple()
            
            embed = discord.Embed(
                title=script(msg_config.get("Title", ""), member, guild),
                description=script(msg_config.get("Description", ""), member, guild),
                color=color
            )
            if msg_config.get("Image Link"):
                embed.set_image(url=msg_config["Image Link"])
        
        # Send message
        try:
            if thanks_config['DM']:
                await member.send(content, embed=embed)
            else:
                channel = guild.get_channel(thanks_config['Channel ID'])
                if channel:
                    await channel.send(content, embed=embed)
        except Exception as e:
            print(f"Failed to send thank you: {e}")

    @tag_check.before_loop
    async def before_tag_check(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(TagRoleHandler(bot))