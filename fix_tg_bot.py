import re

with open("tg_bot.py", "r", encoding="utf-8") as f:
    content = f.read()

# Fix execute_profile
pattern_profile = re.compile(
    r'async def execute_profile\(chat_id: int, message_id: int, server_val: str, game_id: str\):\n'
    r'    name, tag = parse_riot_id\(game_id\)\n\n'
    r'@dp\.callback_query_handler\(lambda c: c\.data and c\.data\.startswith\(\'prof\|\'\)\)\n'
    r'async def process_profile_callback\(callback_query: types\.CallbackQuery\):\n'
    r'.*?name, tag = parse_riot_id\(game_id\)\n'
    r'.*?# await bot\.edit_message_text.*?\n'
    r'    \n'
    r'    try:(.*?)(    await bot\.edit_message_text\("\\n"\.join\(text_lines\), chat_id=chat_id, message_id=message_id, parse_mode="Markdown"\)\n)',
    re.DOTALL
)

def repl_profile(m):
    inner = "    try:" + m.group(1) + m.group(2)
    # The inner block currently has 4-space indentation for its top-level statements inside the function
    # Wait, in process_profile_callback, it's indented by 4 spaces.
    # So if we put it inside execute_profile, it's ALREADY 4 spaces indented!
    # Perfect!
    
    return f"""async def execute_profile(chat_id: int, message_id: int, server_val: str, game_id: str):
    name, tag = parse_riot_id(game_id)
{inner}

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('prof|'))
async def process_profile_callback(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    
    parts = callback_query.data.split('|')
    if len(parts) != 3:
        return
        
    _, server_val, game_id = parts
    msg = callback_query.message
    await bot.edit_message_text(f"正在查询 **{{game_id}}** ({{server_val}})，请稍候...", chat_id=msg.chat.id, message_id=msg.message_id, parse_mode="Markdown")
    
    await execute_profile(msg.chat.id, msg.message_id, server_val, game_id)
"""

content = pattern_profile.sub(repl_profile, content)

# Fix execute_history
pattern_history = re.compile(
    r'async def execute_history\(chat_id: int, message_id: int, server_val: str, game_id: str\):\n'
    r'    name, tag = parse_riot_id\(game_id\)\n\n'
    r'@dp\.callback_query_handler\(lambda c: c\.data and c\.data\.startswith\(\'hist\|\'\)\)\n'
    r'async def process_history_callback\(callback_query: types\.CallbackQuery\):\n'
    r'.*?name, tag = parse_riot_id\(game_id\)\n'
    r'.*?# await bot\.edit_message_text.*?\n'
    r'    \n'
    r'    from lol_rank_tracker import get_player_history\n'
    r'    try:(.*?)(    await bot\.edit_message_text\(full_text, chat_id=chat_id, message_id=message_id, parse_mode="Markdown"\)\n)',
    re.DOTALL
)

def repl_history(m):
    inner = "    from lol_rank_tracker import get_player_history\n    try:" + m.group(1) + m.group(2)
    return f"""async def execute_history(chat_id: int, message_id: int, server_val: str, game_id: str):
    name, tag = parse_riot_id(game_id)
{inner}

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('hist|'))
async def process_history_callback(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    
    parts = callback_query.data.split('|')
    if len(parts) != 3:
        return
        
    _, server_val, game_id = parts
    msg = callback_query.message
    await bot.edit_message_text(f"正在从 {{server_val}} 拉取 **{{game_id}}** 的战绩，请稍候...", chat_id=msg.chat.id, message_id=msg.message_id, parse_mode="Markdown")
    
    await execute_history(msg.chat.id, msg.message_id, server_val, game_id)
"""

content = pattern_history.sub(repl_history, content)

with open("tg_bot.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Fixed tg_bot.py")
