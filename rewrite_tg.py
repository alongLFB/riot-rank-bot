import re

with open("tg_bot.py", "r", encoding="utf-8") as f:
    content = f.read()

# Refactor Profile
profile_logic_pattern = r"""@dp\.callback_query_handler\(lambda c: c\.data and c\.data\.startswith\('prof\|'\)\)
async def process_profile_callback\(callback_query: types\.CallbackQuery\):
    await bot\.answer_callback_query\(callback_query\.id\)
    
    parts = callback_query\.data\.split\('\|'\)
    if len\(parts\) != 3:
        return
        
    _, server_val, game_id = parts
    msg = callback_query\.message
    await bot\.edit_message_text\(f"正在查询 \*\*\{game_id\}\*\* \(\{server_val\}\)，请稍候\.\.\.", chat_id=msg\.chat\.id, message_id=msg\.message_id, parse_mode="Markdown"\)(.*?)    await bot\.edit_message_text\("\\n"\.join\(text_lines\), chat_id=msg\.chat\.id, message_id=msg\.message_id, parse_mode="Markdown"\)"""

profile_logic_match = re.search(profile_logic_pattern, content, re.DOTALL)
if not profile_logic_match:
    print("Could not find profile logic")
    exit(1)

profile_core = profile_logic_match.group(1)

new_execute_profile = f"""
async def execute_profile(chat_id: int, message_id: int, server_val: str, game_id: str):
    name, tag = parse_riot_id(game_id){profile_core}    await bot.edit_message_text("\\n".join(text_lines), chat_id=chat_id, message_id=message_id, parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('prof|'))
async def process_profile_callback(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    parts = callback_query.data.split('|')
    if len(parts) != 3: return
    _, server_val, game_id = parts
    msg = callback_query.message
    await bot.edit_message_text(f"正在查询 **{{game_id}}** ({{server_val}})，请稍候...", chat_id=msg.chat.id, message_id=msg.message_id, parse_mode="Markdown")
    await execute_profile(msg.chat.id, msg.message_id, server_val, game_id)
"""
# Replace `chat_id=msg.chat.id` with `chat_id=chat_id` in the core logic if it exists
new_execute_profile = new_execute_profile.replace("chat_id=msg.chat.id", "chat_id=chat_id").replace("message_id=msg.message_id", "message_id=message_id")

content = content.replace(profile_logic_match.group(0), new_execute_profile)

# Update handle_profile_cmd
old_handle_profile = """@dp.message_handler(commands=['profile', 'rank'])
async def handle_profile_cmd(message: types.Message):
    args = message.get_args()
    if not args:
        await message.reply("请提供 Riot ID！\\n格式：`/profile Name#Tag`", parse_mode="Markdown")
        return
        
    game_id = args.strip()
    if '#' not in game_id:
        await message.reply("格式错误！正确格式示例：`Faker#KR1`", parse_mode="Markdown")
        return

    keyboard = create_server_keyboard("prof", game_id)
    await message.reply(f"请选择 **{game_id}** 所在的服务器：", reply_markup=keyboard, parse_mode="Markdown")"""

new_handle_profile = """@dp.message_handler(commands=['profile', 'rank'])
async def handle_profile_cmd(message: types.Message):
    args = message.get_args().strip()
    if not args:
        await message.reply("请提供 Riot ID！\\n格式：`/profile [服务器] Name#Tag`\\n示例：`/profile EUW1 Faker#KR1`", parse_mode="Markdown")
        return
        
    parts = args.split()
    if len(parts) >= 2:
        server_val = parts[0].upper()
        game_id = parts[1]
        valid_servers = [s[1] for s in SERVERS]
        if server_val in valid_servers:
            msg = await message.reply(f"正在查询 **{game_id}** ({server_val})，请稍候...", parse_mode="Markdown")
            await execute_profile(msg.chat.id, msg.message_id, server_val, game_id)
            return

    game_id = parts[0]
    if '#' not in game_id:
        await message.reply("格式错误！正确格式示例：`/profile EUW1 Faker#KR1` 或 `/profile Faker#KR1`", parse_mode="Markdown")
        return

    keyboard = create_server_keyboard("prof", game_id)
    await message.reply(f"请选择 **{game_id}** 所在的服务器：", reply_markup=keyboard, parse_mode="Markdown")"""

content = content.replace(old_handle_profile, new_handle_profile)

# Refactor History
history_logic_pattern = r"""@dp\.callback_query_handler\(lambda c: c\.data and c\.data\.startswith\('hist\|'\)\)
async def process_history_callback\(callback_query: types\.CallbackQuery\):
    await bot\.answer_callback_query\(callback_query\.id\)
    
    parts = callback_query\.data\.split\('\|'\)
    if len\(parts\) != 3:
        return
        
    _, server_val, game_id = parts
    name, tag = parse_riot_id\(game_id\)
    
    msg = callback_query\.message
    await bot\.edit_message_text\(f"正在从 \{server_val\} 拉取 \*\*\{game_id\}\*\* 的战绩，请稍候\.\.\.", chat_id=msg\.chat\.id, message_id=msg\.message_id, parse_mode="Markdown"\)(.*?)    await bot\.edit_message_text\(full_text, chat_id=msg\.chat\.id, message_id=msg\.message_id, parse_mode="Markdown"\)"""

history_logic_match = re.search(history_logic_pattern, content, re.DOTALL)
if not history_logic_match:
    print("Could not find history logic")
    exit(1)

history_core = history_logic_match.group(1)

new_execute_history = f"""
async def execute_history(chat_id: int, message_id: int, server_val: str, game_id: str):
    name, tag = parse_riot_id(game_id){history_core}    await bot.edit_message_text(full_text, chat_id=chat_id, message_id=message_id, parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('hist|'))
async def process_history_callback(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    parts = callback_query.data.split('|')
    if len(parts) != 3: return
    _, server_val, game_id = parts
    msg = callback_query.message
    await bot.edit_message_text(f"正在从 {{server_val}} 拉取 **{{game_id}}** 的战绩，请稍候...", chat_id=msg.chat.id, message_id=msg.message_id, parse_mode="Markdown")
    await execute_history(msg.chat.id, msg.message_id, server_val, game_id)
"""
new_execute_history = new_execute_history.replace("chat_id=msg.chat.id", "chat_id=chat_id").replace("message_id=msg.message_id", "message_id=message_id")

content = content.replace(history_logic_match.group(0), new_execute_history)

# Update handle_history_cmd
old_handle_history = """@dp.message_handler(commands=['history'])
async def handle_history_cmd(message: types.Message):
    args = message.get_args()
    if not args:
        await message.reply("请提供 Riot ID！\\n格式：`/history Name#Tag`", parse_mode="Markdown")
        return
        
    game_id = args.strip()
    if '#' not in game_id:
        await message.reply("格式错误！正确格式示例：`Faker#KR1`", parse_mode="Markdown")
        return

    keyboard = create_server_keyboard("hist", game_id)
    await message.reply(f"请选择 **{game_id}** 所在的服务器以查询历史战绩：", reply_markup=keyboard, parse_mode="Markdown")"""

new_handle_history = """@dp.message_handler(commands=['history'])
async def handle_history_cmd(message: types.Message):
    args = message.get_args().strip()
    if not args:
        await message.reply("请提供 Riot ID！\\n格式：`/history [服务器] Name#Tag`\\n示例：`/history EUW1 Faker#KR1`", parse_mode="Markdown")
        return
        
    parts = args.split()
    if len(parts) >= 2:
        server_val = parts[0].upper()
        game_id = parts[1]
        valid_servers = [s[1] for s in SERVERS]
        if server_val in valid_servers:
            msg = await message.reply(f"正在从 {server_val} 拉取 **{game_id}** 的战绩，请稍候...", parse_mode="Markdown")
            await execute_history(msg.chat.id, msg.message_id, server_val, game_id)
            return

    game_id = parts[0]
    if '#' not in game_id:
        await message.reply("格式错误！正确格式示例：`/history EUW1 Faker#KR1` 或 `/history Faker#KR1`", parse_mode="Markdown")
        return

    keyboard = create_server_keyboard("hist", game_id)
    await message.reply(f"请选择 **{game_id}** 所在的服务器以查询历史战绩：", reply_markup=keyboard, parse_mode="Markdown")"""

content = content.replace(old_handle_history, new_handle_history)

# Also update welcome message examples
content = content.replace("示例：`/profile Faker#KR1`", "示例：`/profile EUW1 Faker#KR1` 或 `/profile Faker#KR1`")

with open("tg_bot.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Refactor complete")
