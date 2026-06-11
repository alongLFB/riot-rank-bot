import os
import asyncio
import aiohttp
import logging
from collections import Counter
from dotenv import load_dotenv

load_dotenv()
RIOT_API_KEY = os.getenv("RIOT_API_KEY")

if not RIOT_API_KEY:
    raise ValueError("RIOT_API_KEY not found in .env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Riot API Headers
HEADERS = {
    "X-Riot-Token": RIOT_API_KEY
}

# Configuration
EUW_BASE = "https://euw1.api.riotgames.com"
EUROPE_BASE = "https://europe.api.riotgames.com"
NUM_PLAYERS_TO_ANALYZE = 200
MATCHES_PER_PLAYER = 5
CONCURRENCY_LIMIT = 5

sem = asyncio.Semaphore(CONCURRENCY_LIMIT)

async def fetch_json(session: aiohttp.ClientSession, url: str):
    async with sem:
        while True:
            async with session.get(url, headers=HEADERS) as resp:
                if resp.status == 200:
                    return await resp.json()
                elif resp.status == 429:
                    retry_after = int(resp.headers.get("Retry-After", 10))
                    logging.warning(f"Rate limited (429). Sleeping for {retry_after} seconds...")
                    await asyncio.sleep(retry_after)
                elif resp.status in (500, 502, 503, 504):
                    logging.warning(f"Server error {resp.status}. Sleeping for 5 seconds...")
                    await asyncio.sleep(5)
                else:
                    text = await resp.text()
                    logging.error(f"Error {resp.status} on {url}: {text}")
                    return None

async def get_matches(session, puuid, count=5):
    # queue 420 is Ranked Solo 5v5
    url = f"{EUROPE_BASE}/lol/match/v5/matches/by-puuid/{puuid}/ids?queue=420&start=0&count={count}"
    data = await fetch_json(session, url)
    return data if data else []

async def get_match_position(session, match_id, puuid):
    url = f"{EUROPE_BASE}/lol/match/v5/matches/{match_id}"
    data = await fetch_json(session, url)
    if not data or "info" not in data:
        return "UNKNOWN"
        
    for participant in data["info"]["participants"]:
        if participant.get("puuid") == puuid:
            pos = participant.get("teamPosition", "UNKNOWN")
            return pos if pos else "UNKNOWN"
            
    return "UNKNOWN"

async def analyze_player(session, entry, rank_num):
    puuid = entry.get("puuid")
    summoner_name = entry.get("summonerName", puuid[:8])
    league_points = entry.get("leaguePoints")
    
    if not puuid:
        logging.error(f"#{rank_num} No PUUID found for entry")
        return None
        
    match_ids = await get_matches(session, puuid, count=MATCHES_PER_PLAYER)
    
    positions = []
    for match_id in match_ids:
        pos = await get_match_position(session, match_id, puuid)
        if pos and pos != "UNKNOWN":
            positions.append(pos)
            
    if not positions:
        logging.warning(f"#{rank_num} No positions found for {summoner_name}")
        return "UNKNOWN"
        
    # Find most common position
    main_pos = Counter(positions).most_common(1)[0][0]
    logging.info(f"#{rank_num} LP: {league_points} | Main Role: {main_pos} (based on {positions})")
    return main_pos

async def main():
    logging.info("Starting EUW Top 200 Position Analysis...")
    
    async with aiohttp.ClientSession() as session:
        # 1. Fetch Challenger Leaderboard
        league_url = f"{EUW_BASE}/lol/league/v4/challengerleagues/by-queue/RANKED_SOLO_5x5"
        league_data = await fetch_json(session, league_url)
        
        if not league_data or "entries" not in league_data:
            logging.error("Failed to fetch challenger leaderboard.")
            return
            
        entries = league_data["entries"]
        # Sort by LP descending
        entries.sort(key=lambda x: x.get("leaguePoints", 0), reverse=True)
        
        # Take Top N
        top_entries = entries[:NUM_PLAYERS_TO_ANALYZE]
        logging.info(f"Found {len(top_entries)} players to analyze.")
        
        # We will process them sequentially or with limited concurrency to be nice to the rate limit
        role_counts = Counter()
        
        for idx, entry in enumerate(top_entries, 1):
            main_role = await analyze_player(session, entry, idx)
            if main_role:
                role_counts[main_role] += 1
                
        # Generate Report
        report = f"## EUW Top {NUM_PLAYERS_TO_ANALYZE} Solo/Duo Role Distribution\n\n"
        report += "| Position | Count | Percentage |\n"
        report += "|---|---|---|\n"
        
        total = sum(role_counts.values())
        
        # Standardizing names
        pos_display = {
            "TOP": "Top (上单)",
            "JUNGLE": "Jungle (打野)",
            "MIDDLE": "Mid (中单)",
            "BOTTOM": "ADC (下路)",
            "UTILITY": "Support (辅助)",
            "UNKNOWN": "Unknown (未知)"
        }
        
        for role, count in role_counts.most_common():
            display_name = pos_display.get(role, role)
            percent = (count / total * 100) if total > 0 else 0
            report += f"| {display_name} | {count} | {percent:.1f}% |\n"
            
        logging.info("Analysis Complete!")
        print("\n\n" + report)
        
        with open("euw_position_report.md", "w", encoding="utf-8") as f:
            f.write(report)

if __name__ == "__main__":
    asyncio.run(main())
