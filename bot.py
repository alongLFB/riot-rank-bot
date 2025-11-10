import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from datetime import time as dtime

import aiofiles
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

# Use functions from lol_rank_tracker.py
from lol_rank_tracker import generate_html, get_player_rank, parse_riot_id

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID = os.getenv("DISCORD_GUILD_ID")  # optional
REPORT_CHANNEL_ID = os.getenv("REPORT_CHANNEL_ID")
# Match lol_rank_tracker which reads id_list.txt by default
ID_LIST_FILE = os.getenv("ID_LIST_FILE", "id_list.txt")

# 定义 UAE 时区 (UTC+4)
UAE_TZ = timezone(timedelta(hours=4))

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# 全局缓存的玩家列表（用于自动补全）
_id_list = []  # elements like "Faker#KR1"
_id_list_mtime = None


async def load_id_list():
    global _id_list, _id_list_mtime
    try:
        stat = os.stat(ID_LIST_FILE)
        mtime = stat.st_mtime
    except FileNotFoundError:
        logging.warning(f"ID list file not found: {ID_LIST_FILE}")
        _id_list = []
        _id_list_mtime = None
        return
    except Exception as e:
        logging.error(f"Failed to stat {ID_LIST_FILE}: {e}")
        _id_list = []
        _id_list_mtime = None
        return

    if _id_list_mtime == mtime:
        return

    try:
        async with aiofiles.open(ID_LIST_FILE, "r", encoding="utf-8") as f:
            lines = await f.readlines()
        cleaned = [ln.strip() for ln in lines if ln.strip() and '#' in ln and not ln.strip().startswith('#')]
        _id_list = cleaned
        _id_list_mtime = mtime
        logging.info(f"Loaded {len(_id_list)} IDs from {ID_LIST_FILE} (mtime: {mtime})")
        if _id_list:
            logging.info(f"Sample IDs: {_id_list[:3]}")
        else:
            logging.warning(f"No valid IDs found in {ID_LIST_FILE}")
    except Exception as e:
        logging.error(f"Failed to read {ID_LIST_FILE}: {e}")


# 简单的模糊匹配自动补全（按前缀）
async def autocomplete_ids(interaction: discord.Interaction, current: str):
    await load_id_list()
    if not current:
        suggestions = _id_list[:25]
    else:
        cur = current.lower()
        filtered = [s for s in _id_list if s.lower().startswith(cur)]
        suggestions = filtered[:25]
    # 返回 app_commands.Choice 列表
    return [app_commands.Choice(name=s, value=s) for s in suggestions]


@bot.event
async def on_ready():
    logging.info(f"Bot logged in as {bot.user} (id: {bot.user.id})")
    # sync commands: 若指定 GUILD_ID，则只在该服务器同步，便于测试更快
    try:
        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            await tree.sync(guild=guild)
            logging.info("Slash commands synced to guild.")
        else:
            await tree.sync()
            logging.info("Global slash commands synced.")
    except Exception as e:
        logging.exception(f"Slash sync failed: {e}")

    # load id list initially
    await load_id_list()

    # 启动每日刷新任务
    if not daily_refresh_task.is_running():
        daily_refresh_task.start()


# /rank 斜杠命令（使用自动补全）
@tree.command(name="rank", description="查询召唤师段位（示例：Faker#KR1）")
@app_commands.describe(game_id="召唤师（Name#Tag）")
@app_commands.autocomplete(game_id=autocomplete_ids)
async def rank_command(interaction: discord.Interaction, game_id: str):
    await interaction.response.defer()
    if '#' not in game_id:
        await interaction.followup.send("格式错误！正确格式示例：`Faker#KR1`")
        return

    name, tag = parse_riot_id(game_id)

    try:
        data = await asyncio.to_thread(get_player_rank, name, tag)
    except Exception as e:
        logging.exception("查询异常")
        await interaction.followup.send(f"查询失败：{e}")
        return

    status = data.get("status") if isinstance(data, dict) else None
    if status in (None, "not_found"):
        await interaction.followup.send(f"未找到玩家：**{game_id}**")
        return
    if status == "error":
        await interaction.followup.send(f"查询出错：{data.get('error','未知错误')}")
        return

    display_name = f"{data.get('game_name') or name}#{data.get('tag_line') or tag}"
    embed = discord.Embed(title=display_name, timestamp=datetime.now(UAE_TZ))

    if status == "unranked":
        embed.add_field(name="段位", value="未定级", inline=True)
        embed.add_field(name="LP", value=str(data.get("lp", 0)), inline=True)
    else:
        embed.add_field(name="段位", value=f"{data.get('tier','-')} {data.get('rank','')}", inline=True)
        embed.add_field(name="LP", value=str(data.get('lp', 0)), inline=True)

    wins = data.get('wins', 0)
    losses = data.get('losses', 0)
    total = wins + losses
    winrate = f"{(wins/total*100):.1f}%" if total > 0 else "N/A"
    embed.add_field(name="胜/负", value=f"{wins}W / {losses}L", inline=True)
    embed.add_field(name="胜率", value=winrate, inline=True)
    embed.add_field(name="状态", value="-", inline=False)

    embed.set_footer(text="由 RankBot 提供 | 数据来自 Riot API")
    await interaction.followup.send(embed=embed)


def _next_run_seconds(hour=3, minute=0):
    """计算距离下一次运行的秒数（UAE时区）"""
    now_uae = datetime.now(UAE_TZ)
    target_today = datetime.combine(now_uae.date(), dtime(hour=hour, minute=minute))
    target_today = target_today.replace(tzinfo=UAE_TZ)

    if now_uae >= target_today:
        target_today = target_today + timedelta(days=1)

    delta = target_today - now_uae
    return delta.total_seconds()


@tasks.loop(count=None)
async def daily_refresh_task():
    wait_seconds = _next_run_seconds(hour=3, minute=0)
    logging.info(f"Daily refresh will run in {wait_seconds/3600:.2f} hours (03:00 UAE time).")
    await asyncio.sleep(wait_seconds)

    while True:
        logging.info("Starting daily rank refresh...")
        await load_id_list()
        players = []

        async def worker(entry):
            name, tag = parse_riot_id(entry)
            try:
                data = await asyncio.to_thread(get_player_rank, name, tag)
                if data:
                    players.append(data)
            except Exception:
                logging.exception(f"Failed to fetch {entry}")

        chunk_size = 50
        for i in range(0, len(_id_list), chunk_size):
            batch = _id_list[i:i+chunk_size]
            tasks_ = [asyncio.create_task(worker(e)) for e in batch]
            await asyncio.gather(*tasks_)
            await asyncio.sleep(1)

        players.sort(key=lambda x: x.get("total_score", 0), reverse=True)

        html = generate_html(players)
        output_file = "rank_list_daily.html"
        async with aiofiles.open(output_file, "w", encoding="utf-8") as f:
            await f.write(html)
        logging.info(f"Daily HTML saved to {output_file} (players: {len(players)})")

        if REPORT_CHANNEL_ID:
            try:
                channel = bot.get_channel(int(REPORT_CHANNEL_ID)) or await bot.fetch_channel(int(REPORT_CHANNEL_ID))
                if channel:
                    embed = discord.Embed(
                        title="每日段位排行榜已更新",
                        description=f"共查询 {len(players)} 位玩家",
                        timestamp=datetime.now(UAE_TZ)
                    )
                    embed.set_footer(text="RankBot 自动更新（03:00 UAE）")
                    file = discord.File(output_file, filename=output_file)
                    await channel.send(embed=embed, file=file)
                    logging.info("Uploaded daily HTML to channel.")
            except Exception:
                logging.exception("Failed to send daily report to channel.")

        logging.info("Daily refresh finished. Sleeping 24 hours until next run.")
        await asyncio.sleep(24 * 3600)


if __name__ == "__main__":
    bot.run(DISCORD_BOT_TOKEN)
