import json
import os
import re
import time
from typing import Dict, List

from dotenv import load_dotenv
from pyke import Continent, Pyke, Region

load_dotenv()
RIOT_API_KEY = os.getenv("RIOT_API_KEY")
api = Pyke(api_key=RIOT_API_KEY)

# 段位排序权重
TIER_WEIGHT = {
    'CHALLENGER': 9,
    'GRANDMASTER': 8,
    'MASTER': 7,
    'DIAMOND': 6,
    'EMERALD': 5,
    'PLATINUM': 4,
    'GOLD': 3,
    'SILVER': 2,
    'BRONZE': 1,
    'IRON': 0
}

RANK_WEIGHT = {
    'I': 4,
    'II': 3,
    'III': 2,
    'IV': 1
}

def parse_riot_id(line: str) -> tuple:
    """解析Riot ID，支持多种格式"""
    line = line.strip()
    if not line:
        return None, None

    # 尝试用#分割
    if '#' in line:
        parts = line.split('#')
        return parts[0].strip(), parts[1].strip()
    return None, None

def get_player_rank(game_name: str, tag_line: str, region_str: str = "me1") -> Dict:
    """获取玩家排位信息"""
    try:
        # 1. 优先使用 europe 路由获取 PUUID，因为 ME1 等服务器的 Riot ID 大都在 europe 路由
        account_url = f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{urllib.parse.quote(game_name)}/{urllib.parse.quote(tag_line)}"
        account_data = _fetch_json_sync(account_url, RIOT_API_KEY)
        
        # 如果 europe 找不到，尝试 asia
        if not account_data or "puuid" not in account_data:
            account_url = f"https://asia.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{urllib.parse.quote(game_name)}/{urllib.parse.quote(tag_line)}"
            account_data = _fetch_json_sync(account_url, RIOT_API_KEY)
            
        if not account_data or "puuid" not in account_data:
            return {
                'game_name': game_name,
                'tag_line': tag_line,
                'status': 'not_found'
            }
            
        puuid = account_data["puuid"]
        
        # 稍作延迟避免API限制
        time.sleep(0.5)

        # 2. 根据 PUUID 获取排位信息
        league_url = f"https://{region_str}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"
        league_entries = _fetch_json_sync(league_url, RIOT_API_KEY)

        if league_entries is None:
             return {
                'game_name': game_name,
                'tag_line': tag_line,
                'status': 'error',
                'error': '获取段位数据失败'
            }

        # 查找单双排信息
        solo_queue = None
        for entry in league_entries:
            if entry.get("queueType") == 'RANKED_SOLO_5x5':
                solo_queue = entry
                break

        if solo_queue:
            wins = solo_queue.get("wins", 0)
            losses = solo_queue.get("losses", 0)
            total_games = wins + losses
            win_rate = (wins / total_games * 100) if total_games > 0 else 0
            
            tier = solo_queue.get("tier", "UNRANKED")
            rank = solo_queue.get("rank", "I")
            lp = solo_queue.get("leaguePoints", 0)

            # 计算排序权重
            tier_score = TIER_WEIGHT.get(tier, 0) * 1000
            rank_score = RANK_WEIGHT.get(rank, 0) * 100
            total_score = tier_score + rank_score + lp

            return {
                'game_name': game_name,
                'tag_line': tag_line,
                'tier': tier,
                'rank': rank,
                'lp': lp,
                'wins': wins,
                'losses': losses,
                'win_rate': win_rate,
                'total_score': total_score,
                'status': 'success'
            }
        else:
            return {
                'game_name': game_name,
                'tag_line': tag_line,
                'status': 'unranked'
            }

    except Exception as e:
        error_msg = str(e)
        if '404' in error_msg or 'not found' in error_msg.lower() or 'Data not found' in error_msg:
            return {
                'game_name': game_name,
                'tag_line': tag_line,
                'status': 'not_found'
            }
        return {
            'game_name': game_name,
            'tag_line': tag_line,
            'status': 'error',
            'error': error_msg
        }

import urllib.request
import urllib.error
import urllib.parse
import asyncio

def _fetch_json_sync(url, api_key):
    headers = {"X-Riot-Token": api_key, "User-Agent": "Mozilla/5.0"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as res:
            return json.loads(res.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        if e.code == 429:
            retry_after = int(e.headers.get("Retry-After", 10))
            time.sleep(retry_after)
            return _fetch_json_sync(url, api_key)
        return None
    except Exception:
        return None

def get_player_history(server: str, game_name: str, tag_line: str) -> Dict:
    """获取玩家最近20场对局历史"""
    try:
        server = server.upper()
        # 1. 映射到平台和路由区域
        if server == "ME1":
            platform = "me1"
            routing = "europe"
        elif server == "EUW1":
            platform = "euw1"
            routing = "europe"
        elif server == "EUN1":
            platform = "eun1"
            routing = "europe"
        else:
            return {"status": "error", "error": "不支持的服务器"}

        # 2. 获取 PUUID (通过 account-v1)
        # account-v1 is available on americas, asia, europe, esports
        account_url = f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{urllib.parse.quote(game_name)}/{urllib.parse.quote(tag_line)}"
        account_data = _fetch_json_sync(account_url, RIOT_API_KEY)
        
        if not account_data or "puuid" not in account_data:
            return {"status": "not_found", "error": "未找到玩家"}
            
        puuid = account_data["puuid"]
        
        # 3. 获取最近 20 场对局 IDs (Match-V5)
        match_ids_url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count=20"
        match_ids = _fetch_json_sync(match_ids_url, RIOT_API_KEY)
        
        if not match_ids:
            return {"status": "success", "matches": []}
            
        # 4. 依次获取对局详细信息
        matches_info = []
        for match_id in match_ids:
            match_url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/{match_id}"
            match_data = _fetch_json_sync(match_url, RIOT_API_KEY)
            if not match_data:
                continue
                
            info = match_data.get("info", {})
            participants = info.get("participants", [])
            player_p = next((p for p in participants if p["puuid"] == puuid), None)
            
            if player_p:
                win = player_p.get("win", False)
                champ = player_p.get("championName", "Unknown")
                kills = player_p.get("kills", 0)
                deaths = player_p.get("deaths", 0)
                assists = player_p.get("assists", 0)
                
                # 判断游戏模式
                game_mode = info.get("gameMode", "CLASSIC")
                
                matches_info.append({
                    "match_id": match_id,
                    "win": win,
                    "champion": champ,
                    "kills": kills,
                    "deaths": deaths,
                    "assists": assists,
                    "mode": game_mode
                })
                
        return {"status": "success", "matches": matches_info}
        
    except Exception as e:
        return {"status": "error", "error": str(e)}

def save_data_to_json(players_data: List[Dict], filename: str = 'player_data.json'):
    """保存数据到JSON文件"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(players_data, f, ensure_ascii=False, indent=2)
    print(f"✓ 数据已保存到 {filename}")

def load_data_from_json(filename: str = 'player_data.json') -> List[Dict]:
    """从JSON文件加载数据"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return None

def generate_html(players_data: List[Dict]) -> str:
    """生成HTML排行榜"""

    # 分离成功和失败的数据
    ranked_players = [p for p in players_data if p['status'] == 'success']
    unranked_players = [p for p in players_data if p['status'] == 'unranked']
    error_players = [p for p in players_data if p['status'] in ['not_found', 'error']]

    # 按总分排序
    ranked_players.sort(key=lambda x: x['total_score'], reverse=True)

    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LOL排位排行榜</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        h1 {
            text-align: center;
            color: white;
            margin-bottom: 30px;
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .stats {
            background: white;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            text-align: center;
        }
        table {
            width: 100%;
            background: white;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        th {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: bold;
        }
        td {
            padding: 12px 15px;
            border-bottom: 1px solid #f0f0f0;
        }
        tr:hover {
            background-color: #f8f9fa;
        }
        .rank-badge {
            display: inline-block;
            padding: 5px 10px;
            border-radius: 5px;
            font-weight: bold;
            color: white;
        }
        .CHALLENGER { background: #f4c430; }
        .GRANDMASTER { background: #dc143c; }
        .MASTER { background: #9b59b6; }
        .DIAMOND { background: #3498db; }
        .EMERALD { background: #2ecc71; }
        .PLATINUM { background: #1abc9c; }
        .GOLD { background: #f39c12; }
        .SILVER { background: #95a5a6; }
        .BRONZE { background: #cd7f32; }
        .IRON { background: #636363; }
        .win-rate {
            font-weight: bold;
        }
        .high { color: #27ae60; }
        .medium { color: #f39c12; }
        .low { color: #e74c3c; }
        .section-title {
            color: white;
            font-size: 1.5em;
            margin: 20px 0 10px 0;
        }
        .error-section {
            background: white;
            border-radius: 10px;
            padding: 15px;
            margin-top: 20px;
        }
        .error-item {
            padding: 8px;
            border-bottom: 1px solid #f0f0f0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏆 LOL 排位排行榜 🏆</h1>

        <div class="stats">
            <strong>统计信息：</strong>
            已排位: """ + str(len(ranked_players)) + """ | 未排位: """ + str(len(unranked_players)) + """ | 查询失败: """ + str(len(error_players)) + """
        </div>
"""

    if ranked_players:
        html += """
        <h2 class="section-title">📊 排位玩家</h2>
        <table>
            <thead>
                <tr>
                    <th>排名</th>
                    <th>召唤师名称</th>
                    <th>段位</th>
                    <th>胜场</th>
                    <th>负场</th>
                    <th>总场次</th>
                    <th>胜率</th>
                </tr>
            </thead>
            <tbody>
"""

        for idx, player in enumerate(ranked_players, 1):
            win_rate_class = 'high' if player['win_rate'] >= 55 else ('medium' if player['win_rate'] >= 50 else 'low')
            total_games = player['wins'] + player['losses']

            html += f"""
                <tr>
                    <td><strong>#{idx}</strong></td>
                    <td>{player['game_name']}#{player['tag_line']}</td>
                    <td>
                        <span class="rank-badge {player['tier']}">
                            {player['tier']} {player['rank']}
                        </span>
                        <span style="color: #666;"> ({player['lp']} LP)</span>
                    </td>
                    <td style="color: #27ae60; font-weight: bold;">{player['wins']}</td>
                    <td style="color: #e74c3c; font-weight: bold;">{player['losses']}</td>
                    <td>{total_games}</td>
                    <td class="win-rate {win_rate_class}">{player['win_rate']:.1f}%</td>
                </tr>
"""

        html += """
            </tbody>
        </table>
"""

    if unranked_players:
        html += """
        <h2 class="section-title">❓ 未排位玩家</h2>
        <div class="error-section">
"""
        for player in unranked_players:
            html += f"""
            <div class="error-item">
                {player['game_name']}#{player['tag_line']} - 未进行排位赛
            </div>
"""
        html += "</div>"

    if error_players:
        html += """
        <h2 class="section-title">⚠️ 查询失败</h2>
        <div class="error-section">
"""
        for player in error_players:
            error_msg = player.get('error', '未找到该玩家')
            html += f"""
            <div class="error-item">
                {player['game_name']}#{player['tag_line']} - {error_msg}
            </div>
"""
        html += "</div>"

    html += """
    </div>
</body>
</html>
"""

    return html

def fetch_all_data():
    """抓取所有玩家数据"""
    print("开始读取玩家列表...")

    players_data = []
    try:
        with open('id_list.txt', 'r', encoding='utf-8') as f:
            lines = f.readlines()

        print(f"共找到 {len(lines)} 个玩家ID\n")

        for idx, line in enumerate(lines, 1):
            game_name, tag_line = parse_riot_id(line)

            if game_name and tag_line:
                print(f"[{idx}/{len(lines)}] 查询: {game_name}#{tag_line}")
                player_data = get_player_rank(game_name, tag_line)
                players_data.append(player_data)

                if player_data['status'] == 'success':
                    print(f"  ✓ {player_data['tier']} {player_data['rank']} - {player_data['lp']} LP")
                elif player_data['status'] == 'unranked':
                    print(f"  - 未排位")
                else:
                    print(f"  ✗ 查询失败")
            else:
                print(f"[{idx}/{len(lines)}] 跳过无效行: {line.strip()}")

        # 保存数据到JSON
        print("\n保存数据到本地...")
        save_data_to_json(players_data)

        return players_data

    except FileNotFoundError:
        print("错误: 找不到 id_list2.txt 文件")
        return None
    except Exception as e:
        print(f"错误: {e}")
        return None

def generate_html_from_data():
    """从本地数据生成HTML"""
    print("从本地加载数据...")
    players_data = load_data_from_json()

    if players_data is None:
        print("错误: 找不到 player_data.json 文件，请先运行数据抓取")
        return False

    print(f"加载了 {len(players_data)} 个玩家数据")
    print("生成HTML报告...")

    try:
        html_content = generate_html(players_data)

        # 保存HTML文件
        with open('lol_ranking.html', 'w', encoding='utf-8') as f:
            f.write(html_content)

        print("✓ 完成! 请打开 lol_ranking.html 查看结果")
        return True

    except Exception as e:
        print(f"生成HTML时出错: {e}")
        return False

def main():
    """主函数"""
    print("=" * 50)
    print("LOL 排位查询工具")
    print("=" * 50)
    print("\n请选择操作:")
    print("1. 抓取玩家数据（从API获取最新数据）")
    print("2. 生成HTML报告（使用本地缓存数据）")
    print("3. 抓取数据并生成HTML（完整流程）")
    print("\n")

    choice = input("请输入选项 (1/2/3): ").strip()

    if choice == '1':
        players_data = fetch_all_data()
        if players_data:
            print("\n数据抓取完成！")
            print("提示: 可以运行选项2来生成HTML报告")

    elif choice == '2':
        generate_html_from_data()

    elif choice == '3':
        players_data = fetch_all_data()
        if players_data:
            print("\n" + "=" * 50)
            generate_html_from_data()

    else:
        print("无效的选项！")

if __name__ == "__main__":
    main()
