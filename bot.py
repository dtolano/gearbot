import os
import re
import aiohttp
import aiosqlite
import discord
from discord.ext import tasks, commands

# ===== ENVIRONMENT VARIABLES =====
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("POST_CHANNEL_ID"))

# ===== COMPANY SOURCES =====
GREENHOUSE_BOARDS = [
    "raytheon",
    "honeywell",
    "lockheedmartin",
]

LEVER_ACCOUNTS = [
    "spacex",
    "tesla",
]

# ===== FILTER KEYWORDS =====
KEYWORDS = [
    "intern", "internship", "co-op", "coop",
    "mechanical", "engineering", "aerospace",
    "robotics", "mechatronics", "manufacturing"
]

DB = "posted.db"

def matches(text):
    text = text.lower()
    return any(k in text for k in KEYWORDS)

def make_key(job):
    return re.sub(r"\s+", "", f"{job['source']}{job['id']}").lower()

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ===== DATABASE =====
async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY)"
        )
        await db.commit()

async def seen(job_id):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            "SELECT 1 FROM jobs WHERE id=?", (job_id,)
        )
        return await cur.fetchone() is not None

async def mark(job_id):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT OR IGNORE INTO jobs VALUES(?)", (job_id,)
        )
        await db.commit()

# ===== FETCHERS =====
async def fetch_greenhouse(session, company):
    url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs"
    async with session.get(url) as r:
        data = await r.json()

    return [{
        "source": f"Greenhouse:{company}",
        "id": j["id"],
        "title": j["title"],
        "location": j["location"]["name"],
        "url": j["absolute_url"]
    } for j in data.get("jobs", [])]

async def fetch_lever(session, company):
    url = f"https://api.lever.co/v0/postings/{company}?mode=json"
    async with session.get(url) as r:
        data = await r.json()

    return [{
        "source": f"Lever:{company}",
        "id": j["id"],
        "title": j["text"],
        "location": j["categories"].get("location", "Unknown"),
        "url": j["hostedUrl"]
    } for j in data]

# ===== MAIN SCAN LOOP =====
@tasks.loop(hours=6)
async def scan_jobs():
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        return

    async with aiohttp.ClientSession() as session:
        jobs = []

        for c in GREENHOUSE_BOARDS:
            try:
                jobs += await fetch_greenhouse(session, c)
            except Exception as e:
                print("Greenhouse error:", c, e)

        for c in LEVER_ACCOUNTS:
            try:
                jobs += await fetch_lever(session, c)
            except Exception as e:
                print("Lever error:", c, e)

    for job in jobs:
        if not matches(job["title"]):
            continue

        key = make_key(job)
        if await seen(key):
            continue

        embed = discord.Embed(
            title=job["title"],
            description=f"📍 {job['location']}\n🔗 {job['source']}",
            url=job["url"],
            color=0x1f8b4c
        )

        await channel.send(embed=embed)
        await mark(key)

# ===== EVENTS =====
@bot.event
async def on_ready():
    await init_db()
    scan_jobs.start()
    print(f"Bot online as {bot.user}")

bot.run(TOKEN)
