import discord
from discord.ext import commands

TOKEN = "PMTQ1OTA2NDA1Mzc0MDczMjU0MQ.Grhc2d.VZRIW0IbS1OOzfURCk6bkzM0QWuPYsKcxMb17o"

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.command()
async def ping(ctx):
    await ctx.send("pong")

bot.run(TOKEN)
