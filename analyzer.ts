import { FunTag, MatchSummary } from '../types';

export class AnalyzerService {
  /**
   * Extremely simplified MMR estimation.
   * Real MMR estimation looks at the average tier/division of all 10 players in a match.
   * For MVP, we'll base it roughly on the player's LP and Win Rate.
   */
  static estimateMMR(tier: string, rank: string, lp: number, winRate: number): number {
    const tierValues: { [key: string]: number } = {
      'IRON': 400, 'BRONZE': 800, 'SILVER': 1200, 'GOLD': 1600,
      'PLATINUM': 2000, 'EMERALD': 2400, 'DIAMOND': 2800, 'MASTER': 3200,
      'GRANDMASTER': 3600, 'CHALLENGER': 4000
    };
    
    const rankValues: { [key: string]: number } = {
      'IV': 0, 'III': 100, 'II': 200, 'I': 300
    };

    let baseMmr = (tierValues[tier] || 1200) + (rankValues[rank] || 0) + lp;
    
    // Adjust based on winrate (if > 50%, slightly higher MMR than visual rank)
    const winRateModifier = (winRate - 50) * 5; 
    
    return Math.round(baseMmr + winRateModifier);
  }

  /**
   * Generates "Fun Tags" (League of Graphs style) based on match history
   */
  static generateFunTags(matches: MatchSummary[]): FunTag[] {
    const tags: FunTag[] = [];
    if (!matches || matches.length === 0) return tags;

    let totalKills = 0;
    let totalDeaths = 0;
    let totalAssists = 0;
    let flawlessGames = 0;
    let pacifistGames = 0;

    matches.forEach(m => {
      totalKills += m.kills;
      totalDeaths += m.deaths;
      totalAssists += m.assists;
      if (m.deaths === 0) flawlessGames++;
      if (m.kills === 0 && m.assists > 10) pacifistGames++;
    });

    const avgKills = totalKills / matches.length;
    const avgDeaths = totalDeaths / matches.length;

    if (flawlessGames >= 2) {
      tags.push({
        id: 'unkillable', title: 'Unkillable Demon King',
        description: 'Zero deaths in multiple recent games.',
        type: 'positive', color: 'var(--accent-blue)'
      });
    }

    if (avgDeaths > 8) {
      tags.push({
        id: 'feeder', title: 'Tactical Feeder',
        description: 'Averaging high deaths recently. Or maybe just creating space?',
        type: 'negative', color: 'var(--accent-red)'
      });
    }

    if (avgKills > 12) {
      tags.push({
        id: 'carry', title: '1v9 Machine',
        description: 'Hard carrying with massive kill counts.',
        type: 'positive', color: 'var(--accent-gold)'
      });
    }

    if (pacifistGames > 0) {
      tags.push({
        id: 'pacifist', title: 'Pacifist',
        description: 'Winning without blood on your hands.',
        type: 'neutral', color: 'var(--text-secondary)'
      });
    }

    return tags;
  }

  /**
   * Parses raw match data from Riot into our simplified MatchSummary
   */
  static parseMatchData(rawMatch: any, puuid: string): MatchSummary | null {
    try {
      const participant = rawMatch.info.participants.find((p: any) => p.puuid === puuid);
      if (!participant) return null;

      const kda = participant.deaths === 0 
        ? 'Perfect' 
        : ((participant.kills + participant.assists) / participant.deaths).toFixed(2);

      return {
        matchId: rawMatch.metadata.matchId,
        championId: participant.championId,
        win: participant.win,
        kills: participant.kills,
        deaths: participant.deaths,
        assists: participant.assists,
        kda: kda,
        gameDuration: rawMatch.info.gameDuration,
        gameCreation: rawMatch.info.gameCreation
      };
    } catch (e) {
      console.error('Error parsing match data', e);
      return null;
    }
  }

  /**
   * Fetches the MMR from RankedKings API.
   * Since their API queues the request and returns "Accepted" initially,
   * we poll up to 3 times with a delay if we see "Accepted".
   */
  static async getRankedKingsMMR(region: string, riotId: string): Promise<any | null> {
    // Map Riot platform ID (euw1, na1) to RankedKings region format (EUW, NA)
    const regionMap: { [key: string]: string } = {
      'euw1': 'EUW',
      'na1': 'NA',
      'kr': 'KR',
      'eun1': 'EUNE',
      'tr1': 'TR',
      'ru': 'RU',
      'jp1': 'JP'
    };
    const rkRegion = regionMap[region.toLowerCase()] || region.toUpperCase().replace(/[0-9]/g, '');

    const encodedId = encodeURIComponent(riotId);
    const url = `https://api.rankedkings.com/lol-mmr/v2/check/${rkRegion}/${encodedId}/RANKED_SOLO/false`;
    
    for (let i = 0; i < 3; i++) {
      try {
        const response = await fetch(url, {
          headers: {
            'accept': 'application/json, text/plain, */*',
            'origin': 'https://rankedkings.com',
            'referer': 'https://rankedkings.com/',
            'user-agent': 'Mozilla/5.0'
          }
        });

        const text = await response.text();
        
        if (text === 'Accepted') {
          // Wait 2 seconds and retry
          await new Promise(resolve => setTimeout(resolve, 2000));
          continue;
        }

        const data = JSON.parse(text);
        if (data.status === 'SUCCESS') {
          return data;
        }
        return null;
      } catch (error) {
        console.error('Error fetching RankedKings MMR:', error);
        return null;
      }
    }
    return null;
  }
}
