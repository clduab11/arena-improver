"""SmartMemory service for historical performance tracking."""

from typing import List, Dict, Optional
from datetime import datetime, timedelta
from collections import defaultdict

from .smart_sql import SmartSQLService


class SmartMemoryService:
    """Service for tracking and analyzing historical deck performance."""
    
    def __init__(self, sql_service: SmartSQLService):
        self.sql_service = sql_service
    
    async def get_deck_statistics(self, deck_id: int) -> Dict:
        """Get comprehensive statistics for a deck."""
        performances = await self.sql_service.get_deck_performance(deck_id)
        
        if not performances:
            return {
                'total_matches': 0,
                'win_rate': 0.0,
                'games_won': 0,
                'games_lost': 0,
                'matchup_stats': {},
                'recent_form': []
            }
        
        total_matches = len(performances)
        wins = sum(1 for p in performances if p['result'] == 'win')
        win_rate = (wins / total_matches * 100) if total_matches > 0 else 0.0
        
        games_won = sum(p['games_won'] for p in performances)
        games_lost = sum(p['games_lost'] for p in performances)
        
        # Matchup statistics
        matchup_stats = self._calculate_matchup_stats(performances)
        
        # Recent form (last 10 matches)
        recent_form = self._calculate_recent_form(performances[:10])
        
        return {
            'total_matches': total_matches,
            'win_rate': round(win_rate, 2),
            'games_won': games_won,
            'games_lost': games_lost,
            'matchup_stats': matchup_stats,
            'recent_form': recent_form
        }
    
    async def get_performance_trends(
        self, deck_id: int, days: int = 30
    ) -> Dict:
        """Analyze performance trends over time."""
        performances = await self.sql_service.get_deck_performance(deck_id)
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Filter to specified time period
        recent_performances = [
            p for p in performances
            if datetime.fromisoformat(p['match_date']) >= cutoff_date
        ]
        
        if not recent_performances:
            return {'trend': 'no_data', 'direction': 'stable'}
        
        # Calculate win rate by week
        weekly_stats = self._calculate_weekly_stats(recent_performances)
        
        # Determine trend
        trend = self._determine_trend(weekly_stats)
        
        return {
            'trend': trend,
            'weekly_stats': weekly_stats,
            'sample_size': len(recent_performances)
        }
    
    async def compare_decks(
        self, deck_id1: int, deck_id2: int
    ) -> Dict:
        """Compare performance between two decks."""
        stats1 = await self.get_deck_statistics(deck_id1)
        stats2 = await self.get_deck_statistics(deck_id2)
        
        return {
            'deck1': {
                'id': deck_id1,
                'win_rate': stats1['win_rate'],
                'total_matches': stats1['total_matches']
            },
            'deck2': {
                'id': deck_id2,
                'win_rate': stats2['win_rate'],
                'total_matches': stats2['total_matches']
            },
            'win_rate_diff': stats1['win_rate'] - stats2['win_rate'],
            'better_deck': deck_id1 if stats1['win_rate'] > stats2['win_rate'] else deck_id2
        }
    
    async def get_learning_insights(self, deck_id: int) -> List[str]:
        """Generate insights from historical performance."""
        stats = await self.get_deck_statistics(deck_id)
        insights = []
        
        # Overall performance
        if stats['total_matches'] > 0:
            if stats['win_rate'] >= 60:
                insights.append(
                    f"Strong performance with {stats['win_rate']}% win rate"
                )
            elif stats['win_rate'] < 45:
                insights.append(
                    f"Struggling with {stats['win_rate']}% win rate - consider optimization"
                )
        
        # Matchup analysis
        if stats['matchup_stats']:
            best_matchup = max(
                stats['matchup_stats'].items(),
                key=lambda x: x[1]['win_rate']
            )
            worst_matchup = min(
                stats['matchup_stats'].items(),
                key=lambda x: x[1]['win_rate']
            )
            
            insights.append(
                f"Best matchup: {best_matchup[0]} ({best_matchup[1]['win_rate']}%)"
            )
            insights.append(
                f"Worst matchup: {worst_matchup[0]} ({worst_matchup[1]['win_rate']}%)"
            )
        
        # Sample size warnings
        if stats['total_matches'] < 20:
            insights.append(
                "Limited data - play more matches for accurate statistics"
            )
        
        return insights
    
    def _calculate_matchup_stats(self, performances: List[Dict]) -> Dict:
        """Calculate statistics by opponent archetype."""
        matchup_data = defaultdict(lambda: {'wins': 0, 'total': 0})
        
        for perf in performances:
            archetype = perf['opponent_archetype']
            matchup_data[archetype]['total'] += 1
            if perf['result'] == 'win':
                matchup_data[archetype]['wins'] += 1
        
        # Calculate win rates
        matchup_stats = {}
        for archetype, data in matchup_data.items():
            win_rate = (data['wins'] / data['total'] * 100) if data['total'] > 0 else 0
            matchup_stats[archetype] = {
                'win_rate': round(win_rate, 2),
                'matches_played': data['total'],
                'wins': data['wins']
            }
        
        return matchup_stats
    
    def _calculate_recent_form(self, recent_performances: List[Dict]) -> List[str]:
        """Calculate recent form (W/L pattern)."""
        return [
            'W' if p['result'] == 'win' else 'L'
            for p in recent_performances
        ]
    
    def _calculate_weekly_stats(self, performances: List[Dict]) -> List[Dict]:
        """Calculate win rate by week."""
        weekly_data = defaultdict(lambda: {'wins': 0, 'total': 0})
        
        for perf in performances:
            match_date = datetime.fromisoformat(perf['match_date'])
            week_start = match_date - timedelta(days=match_date.weekday())
            week_key = week_start.strftime('%Y-%m-%d')
            
            weekly_data[week_key]['total'] += 1
            if perf['result'] == 'win':
                weekly_data[week_key]['wins'] += 1
        
        # Convert to list and calculate win rates
        weekly_stats = []
        for week, data in sorted(weekly_data.items()):
            win_rate = (data['wins'] / data['total'] * 100) if data['total'] > 0 else 0
            weekly_stats.append({
                'week': week,
                'win_rate': round(win_rate, 2),
                'matches': data['total']
            })
        
        return weekly_stats
    
    def _determine_trend(self, weekly_stats: List[Dict]) -> str:
        """Determine performance trend."""
        if len(weekly_stats) < 2:
            return 'stable'
        
        # Compare recent weeks to earlier weeks
        recent = weekly_stats[-2:]
        earlier = weekly_stats[:-2] if len(weekly_stats) > 2 else weekly_stats[:1]
        
        recent_avg = sum(w['win_rate'] for w in recent) / len(recent)
        earlier_avg = sum(w['win_rate'] for w in earlier) / len(earlier)
        
        diff = recent_avg - earlier_avg
        
        if diff > 10:
            return 'improving'
        elif diff < -10:
            return 'declining'
        else:
            return 'stable'
