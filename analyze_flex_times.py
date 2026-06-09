import os
import sys
import argparse
import urllib.request
import urllib.error
import json
import time
from collections import Counter
from datetime import datetime, timezone, timedelta

# Constants
REGION = "me1"
ROUTING = "europe" # Match-V5 requires regional routing (americas, asia, europe, esports)
ACCOUNT_ROUTING = "europe"
QUEUE = "RANKED_FLEX_SR"
# UAE Timezone (UTC+4)
UAE_TZ = timezone(timedelta(hours=4))
# Number of recent matches to fetch per player
MATCH_COUNT = 50

def get_api_key():
    if os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                if line.startswith("RIOT_API_KEY="):
                    return line.strip().split("=", 1)[1].strip('"\'')
    return None

def fetch_json(url, api_key):
    headers = {
        "X-Riot-Token": api_key,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 403:
            print("HTTP 403 Forbidden: API密钥无效或已过期！请在.env中更新 RIOT_API_KEY。")
            exit(1)
        elif e.code == 429:
            retry_after = e.headers.get("Retry-After")
            wait_time = int(retry_after) if retry_after else 10
            print(f"  [API限流] 等待 {wait_time} 秒...")
            time.sleep(wait_time)
            return fetch_json(url, api_key)
        else:
            print(f"HTTP Error {e.code} for {url}")
            return None
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def get_riot_id(puuid, api_key):
    url = f"https://{ACCOUNT_ROUTING}.api.riotgames.com/riot/account/v1/accounts/by-puuid/{puuid}"
    data = fetch_json(url, api_key)
    if data:
        game_name = data.get("gameName", "Unknown")
        tag_line = data.get("tagLine", "")
        return f"{game_name}#{tag_line}"
    return "UnknownPlayer"

def main():
    parser = argparse.ArgumentParser(description="Analyze ME Flex Play Times")
    parser.add_argument("--top", type=int, default=30, help="Number of top players to analyze")
    args = parser.parse_args()
    target_top = args.top

    api_key = get_api_key()
    if not api_key:
        print("未找到 RIOT_API_KEY。")
        return

    print(f"1. 正在获取 {REGION} {QUEUE} 排行榜 (目标前 {target_top} 名)...")
    entries = []
    
    url_challenger = f"https://{REGION}.api.riotgames.com/lol/league/v4/challengerleagues/by-queue/{QUEUE}"
    data_c = fetch_json(url_challenger, api_key)
    if data_c and "entries" in data_c:
        entries.extend(data_c["entries"])
        
    if len(entries) < target_top:
        url_gm = f"https://{REGION}.api.riotgames.com/lol/league/v4/grandmasterleagues/by-queue/{QUEUE}"
        data_gm = fetch_json(url_gm, api_key)
        if data_gm and "entries" in data_gm:
            entries.extend(data_gm["entries"])
            
    if len(entries) < target_top:
        url_m = f"https://{REGION}.api.riotgames.com/lol/league/v4/masterleagues/by-queue/{QUEUE}"
        data_m = fetch_json(url_m, api_key)
        if data_m and "entries" in data_m:
            entries.extend(data_m["entries"])

    # If apex tiers still don't have enough players, query Diamond/Emerald via league-exp API
    fallback_tiers = [
        ("DIAMOND", "I"), ("DIAMOND", "II"), ("DIAMOND", "III"), ("DIAMOND", "IV"),
        ("EMERALD", "I"), ("EMERALD", "II"), ("EMERALD", "III"), ("EMERALD", "IV")
    ]
    
    for tier, div in fallback_tiers:
        if len(entries) >= target_top:
            break
        print(f"   Apex 段位人数不足，继续获取 {tier} {div}...")
        url_exp = f"https://{REGION}.api.riotgames.com/lol/league-exp/v4/entries/{QUEUE}/{tier}/{div}?page=1"
        data_exp = fetch_json(url_exp, api_key)
        if data_exp:
            data_exp.sort(key=lambda x: x.get("leaguePoints", 0), reverse=True)
            entries.extend(data_exp)

    if not entries:
        print("未能获取到排行榜数据。")
        return
    
    top_30 = entries[:target_top]
    
    print(f"成功获取前{len(top_30)}名玩家。正在分析他们的近期对局...")
    print("注意：受限于 Riot 开发密钥的频率限制（每 2 分钟 100 次请求），抓取对局数据可能需要几分钟，请耐心等待。")
    
    # Store global play hours
    global_play_hours = Counter()
    global_total_matches = 0
    
    # Store structured data for HTML report
    report_data = {
        "generated_at": datetime.now(UAE_TZ).strftime('%Y-%m-%d %H:%M:%S'),
        "global_total_matches": 0,
        "global_play_hours": {},
        "players": []
    }
    
    # Store detailed report (TXT version)
    report_lines = []
    report_lines.append(f"========== ME Flex Top 30 玩家游戏时间统计 (UAE时间) ==========")
    report_lines.append(f"统计生成时间: {report_data['generated_at']}")
    report_lines.append("=" * 65)

    from html_generator import generate_report_html

    for idx, player in enumerate(top_30, 1):
        puuid = player.get("puuid")
        league_points = player.get("leaguePoints", 0)
        
        if not puuid:
            print(f"[{idx}/30] 跳过: 无法获取 puuid")
            continue
            
        riot_id = get_riot_id(puuid, api_key)
        
        url_matches = f"https://{ROUTING}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count={MATCH_COUNT}"
        match_ids = fetch_json(url_matches, api_key)
        if not match_ids:
            match_ids = []
            
        print(f"[{idx}/{len(top_30)}] 正在处理玩家: {riot_id} (LP: {league_points}) - 获取了 {len(match_ids)} 场对局")
        
        player_play_hours = Counter()
        player_matches = 0
        
        for match_id in match_ids:
            url_match = f"https://{ROUTING}.api.riotgames.com/lol/match/v5/matches/{match_id}"
            match_data = fetch_json(url_match, api_key)
            if match_data:
                game_creation = match_data["info"]["gameCreation"]
                dt = datetime.fromtimestamp(game_creation / 1000.0, tz=UAE_TZ)
                player_play_hours[dt.hour] += 1
                player_matches += 1
                
                # add to global
                global_play_hours[dt.hour] += 1
                global_total_matches += 1
                
        # Update JSON data
        player_data = {
            "idx": idx,
            "total_top": len(top_30),
            "riot_id": riot_id,
            "league_points": league_points,
            "total_matches": player_matches,
            "play_hours": dict(player_play_hours)
        }
        report_data["players"].append(player_data)
        report_data["global_total_matches"] = global_total_matches
        report_data["global_play_hours"] = dict(global_play_hours)
        
        # Save HTML incrementally
        generate_report_html(report_data)
                
        # Append player specific report (TXT version)
        report_lines.append(f"\n[{idx}/{len(top_30)}] 玩家: {riot_id} | 段位分数: {league_points} LP")
        report_lines.append(f"最近对局数: {player_matches} 场")
        if player_matches > 0:
            report_lines.append("活跃时间分布:")
            for hour in sorted(player_play_hours.keys()):
                count = player_play_hours[hour]
                pct = (count / player_matches) * 100
                bar = "█" * int(pct / 5)
                report_lines.append(f"  {hour:02d}:00 - {hour+1:02d}:00 | {count:2d} 场 | {pct:5.1f}% {bar}")
        else:
            report_lines.append("暂无近期对局数据。")
        report_lines.append("-" * 40)
        
        with open("flex_play_times_report.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(report_lines))

    # Finally add global summary (TXT version)
    report_lines.append("\n" + "=" * 65)
    report_lines.append(f"========== 总体统计汇总 (前{len(top_30)}名总和) ==========")
    report_lines.append(f"共计分析对局数: {global_total_matches} 场")
    if global_total_matches > 0:
        for hour in range(24):
            count = global_play_hours.get(hour, 0)
            pct = (count / global_total_matches) * 100
            bar = "█" * int(pct / 2)
            report_lines.append(f"  {hour:02d}:00 - {hour+1:02d}:00 | {count:4d} 场 | {pct:5.1f}% {bar}")
    report_lines.append("=" * 65)
    
    with open("flex_play_times_report.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
        
    print(f"\n✅ 所有数据处理完毕！")
    print(f"📊 文本报告: flex_play_times_report.txt")
    print(f"🌐 网页报告: flex_play_times_report.html")

if __name__ == "__main__":
    main()
