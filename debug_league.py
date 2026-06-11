import asyncio
import aiohttp
import os
from dotenv import load_dotenv

load_dotenv()
RIOT_API_KEY = os.getenv("RIOT_API_KEY")

async def test():
    url = "https://euw1.api.riotgames.com/lol/league/v4/challengerleagues/by-queue/RANKED_SOLO_5x5"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers={"X-Riot-Token": RIOT_API_KEY}) as resp:
            data = await resp.json()
            print(data["entries"][0])

if __name__ == "__main__":
    asyncio.run(test())
