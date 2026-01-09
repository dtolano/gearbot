import os
import asyncio
import datetime as dt
import discord
from discord.ext import commands, tasks
import aiohttp

TOKEN = os.getenv("DISCORD_TOKEN")
POST_CHANNEL_ID = os.getenv("POST_CHANNEL_ID")

if not TOKEN:
    raise RuntimeError("Missing DISCORD_TOKEN env var (set it in Fly secrets).")
if not POST_CHANNEL_ID:
    raise RuntimeError("Missing POST_CHANNEL_ID env var (set it in Fly secrets).")

POST_CHANNEL_ID = int(POST_CHANNEL_ID)

# Intents: message_content is required for prefix commands like !ping
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


def build_embed(title: str, url: str, source: str) -> discord.Embed:
    e = discord.Embed(
        title=title[:256],
        url=url,
        description=f"Source: **{source}**",
        timestamp=dt.datetime.now(dt.timezone.utc),
    )
    e.set_footer(text="Gear Labs Bot")
    return e


async def fetch_json(session: aiohttp.ClientSession, url: str):
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as r:
        r.raise_for_status()
        return await r.json()


async def scan_jobs_once(limit: int = 5):
    """
    Simple scan using GitHub Jobs-like sources:
    We'll use two reliable public sources that allow simple linking:
      - Simplify Jobs GitHub repo (internship list)
      - Pitt CSC Summer 2026 Internships repo (if available)
    We’ll just post repo search links + a few items from a JSON endpoint when possible.
    """

    results = []

    # 1) Simplify Jobs repo (link is stable)
    results.append((
        "Internships List (Simplify Jobs)",
        "https://github.com/SimplifyJobs/Summer2026-Internships",
        "GitHub"
    ))

    # 2) Pitt CSC repo (common internships repo)
    results.append((
        "Internships List (Pitt CSC)",
        "https://github.com/pittcsc/Summer2026-Internships",
        "GitHub"
    ))

    # 3) Optional: Remotive API (has JSON, but more general roles)
    # We'll search for "intern" and add a couple entries if returned
    try:
        async with aiohttp.ClientSession(headers={"User-Agent": "GearLabsBot/1.0"}) as session:
            data = await fetch_json(session, "https://remotive.com/api/remote-jobs?search=intern")
            jobs = data.get("jobs", [])[: max(0, limit - len(results))]
            for j in jobs:
                title = j.get("title", "Intern Role")
                url = j.get("url", "")
                company = j.get("company_name", "Remotive")
                if url:
                    results.append((f"{title} — {company}", url, "Remotive"))
    except Exception:
        # If API fails, we still have the GitHub lists, so ignore.
        pass

    return results[:limit]


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (id={bot.user.id})")
    if not auto_scan.is_running():
        auto_scan.start()


@bot.command()
async def ping(ctx: commands.Context):
    await ctx.send("pong ✅")


@bot.command()
async def scan(ctx: commands.Context):
    """Manually scan and post to the configured channel."""
    await ctx.send("Scanning internships… 🔎")
    channel = bot.get_channel(POST_CHANNEL_ID)
    if channel is None:
        await ctx.send("I can't access the post channel. Check POST_CHANNEL_ID and bot permissions.")
        return

    jobs = await scan_jobs_once(limit=6)
    if not jobs:
        await ctx.send("No results found right now.")
        return

    posted = 0
    for title, url, source in jobs:
        try:
            await channel.send(embed=build_embed(title, url, source))
            posted += 1
        except Exception as e:
            await ctx.send(f"Failed posting one item: {e}")
            break

    await ctx.send(f"Posted {posted} items to <#{POST_CHANNEL_ID}> ✅")


@tasks.loop(minutes=30)
async def auto_scan():
    """Auto scan every 30 minutes and post to the target channel."""
    channel = bot.get_channel(POST_CHANNEL_ID)
    if channel is None:
        print("auto_scan: channel not found (check POST_CHANNEL_ID / permissions).")
        return

    jobs = await scan_jobs_once(limit=3)
    for title, url, source in jobs:
        try:
            await channel.send(embed=build_embed(title, url, source))
            await asyncio.sleep(1)
        except Exception as e:
            print("auto_scan post error:", e)


@auto_scan.before_loop
async def before_auto_scan():
    await bot.wait_until_ready()


bot.run(TOKEN)
