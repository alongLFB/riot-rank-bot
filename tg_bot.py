import os
import asyncio
import logging
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from lol_rank_tracker import get_player_rank, parse_riot_id, get_ranked_kings_mmr

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN in .env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(bot)

SERVERS = [
    ("中东服 (ME1)", "ME1"),
    ("欧服西区 (EUW1)", "EUW1"),
    ("欧服东北 (EUN1)", "EUN1")
]

def create_server_keyboard(command: str, game_id: str) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(row_width=3)
    buttons = []
    for server_name, server_val in SERVERS:
        # Callback data format: cmd|server|game_id (limited to 64 bytes)
        cb_data = f"{command}|{server_val}|{game_id}"
        # Make sure cb_data length <= 64!
        if len(cb_data.encode('utf-8')) > 64:
            # truncate game_id if too long, though usually riot ids are < 20 chars
            cb_data = f"{command}|{server_val}|{game_id[:30]}"
            
        buttons.append(InlineKeyboardButton(text=server_name, callback_data=cb_data))
    keyboard.add(*buttons)
    return keyboard

@dp.message_handler(commands=['start', 'help'])
async def send_welcome(message: types.Message):
    await message.reply(
        "欢迎使用 LOL 排位查询 Bot！\n\n"
        "可用命令：\n"
        "`/profile Name#Tag` - 查询召唤师段位与隐分卡片\n"
        "`/history Name#Tag` - 查询最近 20 场对局\n\n"
        "示例：`/profile Faker#KR1`",
        parse_mode="Markdown"
    )

@dp.message_handler(commands=['profile', 'rank'])
async def handle_profile_cmd(message: types.Message):
    args = message.get_args()
    if not args:
        await message.reply("请提供 Riot ID！\n格式：`/profile Name#Tag`", parse_mode="Markdown")
        return
        
    game_id = args.strip()
    if '#' not in game_id:
        await message.reply("格式错误！正确格式示例：`Faker#KR1`", parse_mode="Markdown")
        return

    keyboard = create_server_keyboard("prof", game_id)
    await message.reply(f"请选择 **{game_id}** 所在的服务器：", reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('prof|'))
async def process_profile_callback(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    
    parts = callback_query.data.split('|')
    if len(parts) != 3:
        return
        
    _, server_val, game_id = parts
    name, tag = parse_riot_id(game_id)
    
    # Edit message to show loading
    msg = callback_query.message
    await bot.edit_message_text(f"正在查询 **{game_id}** ({server_val})，请稍候...", chat_id=msg.chat.id, message_id=msg.message_id, parse_mode="Markdown")
    
    try:
        data = await asyncio.to_thread(get_player_rank, name, tag, server_val.lower())
    except Exception as e:
        logging.exception("查询异常")
        await bot.edit_message_text(f"查询失败：{e}", chat_id=msg.chat.id, message_id=msg.message_id)
        return

    status = data.get("status") if isinstance(data, dict) else None
    if status in (None, "not_found"):
        await bot.edit_message_text(f"未找到玩家：**{game_id}**", chat_id=msg.chat.id, message_id=msg.message_id, parse_mode="Markdown")
        return
    if status == "error":
        await bot.edit_message_text(f"查询出错：{data.get('error','未知错误')}", chat_id=msg.chat.id, message_id=msg.message_id)
        return

    display_name = f"{data.get('game_name') or name}#{data.get('tag_line') or tag}"
    
    # Build text response
    wins = data.get('wins', 0)
    losses = data.get('losses', 0)
    total = wins + losses
    winrate = f"{(wins/total*100):.1f}%" if total > 0 else "N/A"
    
    if status == "unranked":
        rank_text = "未定级"
        lp_text = str(data.get("lp", 0))
    else:
        rank_text = f"{data.get('tier','-')} {data.get('rank','')}"
        lp_text = str(data.get('lp', 0))

    score = str(data.get('total_score', 0))
    
    text_lines = [
        f"👑 **{display_name}**",
        "",
        f"**段位**：{rank_text}  |  **LP**：{lp_text}",
        f"**系统分**：{score}",
        f"**胜负**：{wins}W / {losses}L  |  **胜率**：{winrate}"
    ]
    
    # Fetch RankedKings Data & Image
    rk_data = await get_ranked_kings_mmr(server_val, game_id)
    
    current_tier = data.get('tier', 'UNRANKED')
    current_rank_num = data.get('rank', '')
    current_rank_str = f"{current_tier} {current_rank_num}".strip()
    
    if rk_data and rk_data.get("status") == "SUCCESS":
        your_mmr = rk_data.get("mmr", data.get("total_score", 0))
        corresponding_rank = rk_data.get("rank", "Estimated Rank")
        
        health_data = rk_data.get("health", {})
        actual_data = health_data.get("actual", {})
        
        rank_mmr = actual_data.get("mmr", "-")
        health_title = health_data.get("title")
    else:
        # Fallback
        your_mmr = data.get("total_score", 0)
        corresponding_rank = "Estimated (No API)"
        rank_mmr = your_mmr
        health_title = "RankedKings API 暂无该玩家数据，已为您显示理论评估值。"

    text_lines.append("")
    text_lines.append(f"**你的隐分 (Your MMR)**: {your_mmr} ({corresponding_rank})")
    text_lines.append(f"**该段位平均隐分**: {rank_mmr} ({current_rank_str})")
    if health_title:
        text_lines.append(f"**账号状态诊断**: {health_title}")

    await bot.edit_message_text("\n".join(text_lines), chat_id=msg.chat.id, message_id=msg.message_id, parse_mode="Markdown")

from datetime import datetime

@dp.message_handler(commands=['history'])
async def handle_history_cmd(message: types.Message):
    args = message.get_args()
    if not args:
        await message.reply("请提供 Riot ID！\n格式：`/history Name#Tag`", parse_mode="Markdown")
        return
        
    game_id = args.strip()
    if '#' not in game_id:
        await message.reply("格式错误！正确格式示例：`Faker#KR1`", parse_mode="Markdown")
        return

    keyboard = create_server_keyboard("hist", game_id)
    await message.reply(f"请选择 **{game_id}** 所在的服务器以查询历史战绩：", reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('hist|'))
async def process_history_callback(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    
    parts = callback_query.data.split('|')
    if len(parts) != 3:
        return
        
    _, server_val, game_id = parts
    name, tag = parse_riot_id(game_id)
    
    msg = callback_query.message
    await bot.edit_message_text(f"正在从 {server_val} 拉取 **{game_id}** 的战绩，请稍候...", chat_id=msg.chat.id, message_id=msg.message_id, parse_mode="Markdown")
    
    from lol_rank_tracker import get_player_history
    try:
        data = await asyncio.to_thread(get_player_history, server_val, name, tag)
    except Exception as e:
        logging.exception("战绩查询异常")
        await bot.edit_message_text(f"查询失败：{e}", chat_id=msg.chat.id, message_id=msg.message_id)
        return

    if data.get("status") == "not_found":
        await bot.edit_message_text(f"未找到玩家：**{game_id}** (在服务器 {server_val})", chat_id=msg.chat.id, message_id=msg.message_id, parse_mode="Markdown")
        return
    elif data.get("status") == "error":
        await bot.edit_message_text(f"查询出错：{data.get('error', '未知错误')}", chat_id=msg.chat.id, message_id=msg.message_id)
        return
        
    matches = data.get("matches", [])
    if not matches:
        await bot.edit_message_text(f"⚠️ 玩家 **{game_id}** 近期没有对局记录。", chat_id=msg.chat.id, message_id=msg.message_id, parse_mode="Markdown")
        return

    wins_count = sum(1 for m in matches if m['win'])
    total_count = len(matches)
    win_rate = (wins_count / total_count) * 100
    
    header = f"📜 **{game_id} 的近期战绩 ({server_val})**\n"
    header += f"最近 {total_count} 场胜率: {win_rate:.1f}% ({wins_count}胜 / {total_count - wins_count}负)\n\n"
    
    history_lines = []
    for i, m in enumerate(matches, 1):
        status_emoji = "🟢胜" if m['win'] else "🔴负"
        kda = f"{m['kills']}/{m['deaths']}/{m['assists']}"
        champ = m['champion']
        pos = m.get('position', '未知')
        
        creation_ms = m.get('creation', 0)
        try:
            dt = datetime.fromtimestamp(creation_ms / 1000.0)
            date_str = dt.strftime("%m-%d %H:%M")
        except Exception:
            date_str = "未知时间"
            
        duration = m.get('duration', 0)
        if duration > 10000:
            duration = duration // 1000
        mins = duration // 60
        secs = duration % 60
        dur_str = f"{mins}:{secs:02d}"
        
        dmg = m.get('damage', 0)
        dmg_str = f"{dmg/1000:.1f}k" if dmg >= 1000 else str(dmg)
        cs = m.get('cs', 0)
        mode = m.get('mode', '未知')
        
        line = f"`{i:02d}.` `[{date_str} {mode}]` {status_emoji} | **{champ}**({pos}) | ⚔️ `{kda}` | ⏱️ `{dur_str}` | 🗡️ {dmg_str} | 👾 {cs}刀"
        history_lines.append(line)
        
    body = "\n".join(history_lines)
    footer = "\n\n_注意: Riot API 暂不支持单局 LP(胜点) 变动查询_"
    
    full_text = header + body + footer
    
    await bot.edit_message_text(full_text, chat_id=msg.chat.id, message_id=msg.message_id, parse_mode="Markdown")

if __name__ == '__main__':
    logging.info("Starting Telegram Bot...")
    executor.start_polling(dp, skip_updates=True)
