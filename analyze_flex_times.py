import os
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
MATCH_COUNT = 20

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
    api_key = get_api_key()
    if not api_key:
        print("未找到 RIOT_API_KEY。")
        return

    print(f"1. 正在获取 {REGION} {QUEUE} 排行榜 (王者/宗师/大师)...")
    entries = []
    
    url_challenger = f"https://{REGION}.api.riotgames.com/lol/league/v4/challengerleagues/by-queue/{QUEUE}"
    data_c = fetch_json(url_challenger, api_key)
    if data_c and "entries" in data_c:
        entries.extend(data_c["entries"])
        
    if len(entries) < 30:
        url_gm = f"https://{REGION}.api.riotgames.com/lol/league/v4/grandmasterleagues/by-queue/{QUEUE}"
        data_gm = fetch_json(url_gm, api_key)
        if data_gm and "entries" in data_gm:
            entries.extend(data_gm["entries"])
            
    if len(entries) < 30:
        url_m = f"https://{REGION}.api.riotgames.com/lol/league/v4/masterleagues/by-queue/{QUEUE}"
        data_m = fetch_json(url_m, api_key)
        if data_m and "entries" in data_m:
            entries.extend(data_m["entries"])

    if not entries:
        print("未能获取到排行榜数据。")
        return
    
    entries.sort(key=lambda x: x["leaguePoints"], reverse=True)
    top_30 = entries[:30]
    
    print(f"成功获取前30名玩家。正在分析他们的近期对局...")
    print("注意：受限于 Riot 开发密钥的频率限制（每 2 分钟 100 次请求），抓取对局数据可能需要几分钟，请耐心等待。")
    
    # Store global play hours
    global_play_hours = Counter()
    global_total_matches = 0
    
    # Store detailed report
    report_lines = []
    report_lines.append(f"========== ME Flex Top 30 玩家游戏时间统计 (UAE时间) ==========")
    report_lines.append(f"统计生成时间: {datetime.now(UAE_TZ).strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("=" * 65)

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
            # Maybe no matches played recently
            match_ids = []
            
        print(f"[{idx}/30] 正在处理玩家: {riot_id} (LP: {league_points}) - 获取了 {len(match_ids)} 场对局")
        
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
                
        # Append player specific report
        report_lines.append(f"\n[{idx}/30] 玩家: {riot_id} | 段位分数: {league_points} LP")
        report_lines.append(f"最近对局数: {player_matches} 场")
        if player_matches > 0:
            report_lines.append("活跃时间分布:")
            # Sort by hour or by count? Let's sort by hour
            for hour in sorted(player_play_hours.keys()):
                count = player_play_hours[hour]
                pct = (count / player_matches) * 100
                bar = "█" * int(pct / 5) # Scale bar
                report_lines.append(f"  {hour:02d}:00 - {hour+1:02d}:00 | {count:2d} 场 | {pct:5.1f}% {bar}")
        else:
            report_lines.append("暂无近期对局数据。")
        report_lines.append("-" * 40)
        
        # Save incrementally so user can read partial results if it crashes
        with open("flex_play_times_report.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(report_lines))

    # Finally add global summary
    report_lines.append("\n" + "=" * 65)
    report_lines.append(f"========== 总体统计汇总 (前30名总和) ==========")
    report_lines.append(f"共计分析对局数: {global_total_matches} 场")
    if global_total_matches > 0:
        for hour in range(24):
            count = global_play_hours.get(hour, 0)
            pct = (count / global_total_matches) * 100
            bar = "█" * int(pct / 2)
            report_lines.append(f"  {hour:02d}:00 - {hour+1:02d}:00 | {count:4d} 场 | {pct:5.1f}% {bar}")
    report_lines.append("=" * 65)
    
    report_content = "\n".join(report_lines)
    with open("flex_play_times_report.txt", "w", encoding="utf-8") as f:
        f.write(report_content)
        
    print(f"\n✅ 所有数据处理完毕！详细报告已保存到: flex_play_times_report.txt")

if __name__ == "__main__":
    main()
