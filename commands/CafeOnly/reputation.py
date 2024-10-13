import discord, firebase_admin, random, datetime, asyncio, time, re, requests
import pandas as pd
from discord import app_commands
from discord.ext import commands
from firebase_admin import db
from discord.ui import Button, View

class ReputationMsg(commands.Cog): 
  def __init__(self, bot):
    self.client = bot

  @commands.Cog.listener() 
  async def on_message(self, message):
        
    if message.author == self.client.user or message.author.bot == True: 
      return

    if message.content.lower().startswith("-rep") and message.guild.id == 717029019270381578:
      try:
        id = int(message.content.split(" ")[1].replace("<@", "").replace(">", ""))
        username = message.guild.get_member(id).name
      except Exception as e:
        id = message.author.id
        username = message.author.name
      ref = db.reference("/Reps")
      reps = ref.get()
      ogrep = 0
      for key, val in reps.items():
        if val['User ID'] == id:
          ogrep = val['Points']
          break
      
      await message.channel.send(f"**{username}**: **{ogrep}** rep")
    
    if message.content.lower().startswith("-toprep") and message.guild.id == 717029019270381578:
      try:
        num = int(message.content.split(" ")[1])
        if num > 50:
          num = 50
        elif num <= 0:
          num = 10
      except Exception as e:
        num = 10
      list = []
      ref = db.reference("/Reps")
      reps = ref.get()
      for key, val in reps.items():
        list.append({"user_id": val['User ID'], "points": val['Points']})
      df_cafe = pd.DataFrame(list)
      df_sorted = df_cafe.sort_values(by='points', ascending=False)
      new = []
      for idx in df_sorted.index:
        record = df_sorted.loc[idx]
        if message.guild.get_member(record['user_id']) != None:
          new.append(record)
      new_df_sorted = pd.DataFrame(new)
      top_10 = new_df_sorted.head(num)
      desc = ""
      count = 1
      for idx in top_10.index:
        record = top_10.loc[idx]
        user = message.guild.get_member(record['user_id'])
        pts = record['points']
        desc = f"{desc}{count}. **{user.name}** `({user.id})` - **{pts}**\n"
        count += 1
      await message.channel.send(embed=discord.Embed(title=f"Reputation Leaderboard - Top {num}", description=desc, color=0xEB7660))
    
    if message.content.lower().startswith("-giverep") and message.guild.id == 717029019270381578:
      id = int(message.content.split(" ")[1].replace("<@", "").replace(">", ""))
      username = message.guild.get_member(id).name
      rep = int(message.content.split(" ")[2])
      if rep > 10:
        await message.reply("You can't give more than 10 reps at once.")
        raise Exception()
      elif id == message.author.id:
        await message.reply("You can't give yourself reps!")
        raise Exception()
      elif rep <= 0:
        await message.reply("You must give at least 1 rep.")
        raise Exception()
        
      ref = db.reference("/Reps")
      reps = ref.get()
      ogrep = 0
      for key, val in reps.items():
        if val['User ID'] == id:
          ogrep = val['Points']
          db.reference('/Reps').child(key).delete()
          break
      data = {
        "Data": {
          "User ID": int(id),
          "Points": ogrep + rep,
        }
      }
      for key, value in data.items():
        ref.push().set(value)
      
      await message.channel.send(f"Gave `{rep}` Rep to **{username}** (current - `{ogrep + rep}`)")

    if message.content == "!syncreputationpoints" and message.author.id == 692254240290242601:
      list = []
      for x in range(10):
        offset = x * 100
        response = requests.get(f'https://yagpdb.xyz/api/749418356926578748/reputation/leaderboard?limit=100&offset={offset}')
        print(offset)
        list = list + response.json()
      df = pd.DataFrame(list)

      cleaned_df = df[(df["user_id"].astype(str) != df["username"].astype(str)) & (df["points"] > 0) & (df["bot"] == False)]
      cleaned_df = cleaned_df[['user_id', 'points']]

      cafe_list = []
      for x in range(7):
        offset = x * 100
        response = requests.get(f'https://yagpdb.xyz/api/717029019270381578/reputation/leaderboard?limit=100&offset={offset}')
        print(offset)
        cafe_list = cafe_list + response.json()
      df_cafe = pd.DataFrame(cafe_list)
    
      cleaned_df_cafe = df_cafe[(df_cafe["user_id"].astype(str) != df_cafe["username"].astype(str)) & (df_cafe["points"] > 0) & (df_cafe["bot"] == False)]
      cleaned_df_cafe = cleaned_df_cafe[['user_id', 'points']]

      merged_df = pd.merge(cleaned_df, cleaned_df_cafe, on='user_id', how='outer')
      merged_df[['user_id', 'points_x', 'points_y']]
      merged_df.fillna(0, inplace=True)
      merged_df['total_points'] = merged_df['points_x'] + merged_df['points_y']
      merged_df

      df_formatted = merged_df.applymap(lambda x: '{:.0f}'.format(x) if isinstance(x, (int, float)) else x)
        
      ref = db.reference("/Reps")
      for idx in df_formatted.index:
        record = df_formatted.loc[idx]
        data = {
          "Data": {
            "User ID": int(record['user_id']),
            "Points": int(record['total_points']),
          }
        }
        for key, value in data.items():
          ref.push().set(value)
        print(idx)


async def setup(bot): 
  await bot.add_cog(ReputationMsg(bot))