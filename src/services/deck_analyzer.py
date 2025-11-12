"""Core deck analysis service."""

from typing import List, Dict, Optional
import statistics
import logging

from ..models.deck import (
    Deck, Card, DeckAnalysis, ManaCurve, CardSynergy,
    MetaMatchup
)
from .meta_intelligence import MetaIntelligenceService

logger = logging.getLogger(__name__)


class DeckAnalyzer:
    """Analyzes MTG Arena decks for optimization opportunities."""

    def __init__(self, meta_service: Optional[MetaIntelligenceService] = None):
        self._meta_service = meta_service
        self.meta_archetypes = []  # Will be loaded dynamically
    
    @property
    def meta_service(self) -> MetaIntelligenceService:
        """Lazy initialization of MetaIntelligenceService."""
        if self._meta_service is None:
            self._meta_service = MetaIntelligenceService()
        return self._meta_service
    
    async def analyze_deck(self, deck: Deck) -> DeckAnalysis:
        """Perform comprehensive deck analysis."""
        mana_curve = self._analyze_mana_curve(deck)
        color_dist = self._analyze_color_distribution(deck)
        card_types = self._analyze_card_types(deck)
        synergies = self._find_synergies(deck)
        matchups = await self._analyze_meta_matchups(deck)
        strengths, weaknesses = self._identify_strengths_weaknesses(
            deck, mana_curve, color_dist, card_types
        )
        overall_score = self._calculate_overall_score(
            mana_curve, color_dist, card_types, synergies
        )

        return DeckAnalysis(
            deck_name=deck.name,
            mana_curve=mana_curve,
            color_distribution=color_dist,
            card_types=card_types,
            synergies=synergies,
            meta_matchups=matchups,
            strengths=strengths,
            weaknesses=weaknesses,
            overall_score=overall_score
        )
    
    def _analyze_mana_curve(self, deck: Deck) -> ManaCurve:
        """Analyze the mana curve of the deck."""
        distribution = {}
        cmc_values = []
        
        for card in deck.mainboard:
            if card.card_type.lower() != 'land':
                cmc = int(card.cmc)
                # Cap at 7+ for curve analysis
                cmc_key = min(cmc, 7)
                distribution[cmc_key] = distribution.get(cmc_key, 0) + card.quantity
                cmc_values.extend([card.cmc] * card.quantity)
        
        avg_cmc = statistics.mean(cmc_values) if cmc_values else 0.0
        median_cmc = statistics.median(cmc_values) if cmc_values else 0.0
        
        # Calculate curve score (ideal curve has most cards at 2-3 CMC)
        curve_score = self._score_mana_curve(distribution)
        
        return ManaCurve(
            distribution=distribution,
            average_cmc=round(avg_cmc, 2),
            median_cmc=median_cmc,
            curve_score=curve_score
        )
    
    def _score_mana_curve(self, distribution: Dict[int, int]) -> float:
        """Score the mana curve (0-100)."""
        # Ideal distribution weights
        ideal = {0: 0, 1: 8, 2: 12, 3: 10, 4: 6, 5: 3, 6: 2, 7: 1}
        total_nonland = sum(distribution.values())
        
        if total_nonland == 0:
            return 0.0
        
        score = 100.0
        for cmc, ideal_count in ideal.items():
            actual_count = distribution.get(cmc, 0)
            actual_pct = (actual_count / total_nonland) * 100
            ideal_pct = (ideal_count / sum(ideal.values())) * 100
            
            # Penalize deviation from ideal
            deviation = abs(actual_pct - ideal_pct)
            score -= deviation * 0.5
        
        return max(0.0, min(100.0, score))
    
    def _analyze_color_distribution(self, deck: Deck) -> Dict[str, int]:
        """Analyze color distribution in the deck."""
        color_count = {'W': 0, 'U': 0, 'B': 0, 'R': 0, 'G': 0, 'C': 0}
        
        for card in deck.mainboard:
            if card.card_type.lower() != 'land':
                for color in card.colors:
                    if color in color_count:
                        color_count[color] += card.quantity
        
        # Remove colors with 0 count
        return {k: v for k, v in color_count.items() if v > 0}
    
    def _analyze_card_types(self, deck: Deck) -> Dict[str, int]:
        """Analyze distribution of card types."""
        type_count = {}
        
        for card in deck.mainboard:
            card_type = card.card_type
            type_count[card_type] = type_count.get(card_type, 0) + card.quantity
        
        return type_count
    
    def _find_synergies(self, deck: Deck) -> List[CardSynergy]:
        """Identify card synergies in the deck."""
        synergies = []
        
        # Simplified synergy detection
        cards = deck.mainboard
        card_names = [card.name for card in cards]
        
        # Example synergy rules (would be more sophisticated in production)
        for i, card1 in enumerate(cards):
            for card2 in cards[i+1:]:
                synergy = self._check_synergy(card1, card2)
                if synergy:
                    synergies.append(synergy)
        
        return synergies[:10]  # Limit to top 10
    
    def _check_synergy(self, card1: Card, card2: Card) -> CardSynergy:
        """Check if two cards have synergy."""
        # Simplified - would use ML or rules engine in production
        
        # Example: creatures and equipment
        if 'creature' in card1.card_type.lower() and 'equipment' in card2.card_type.lower():
            return CardSynergy(
                card1=card1.name,
                card2=card2.name,
                synergy_type="support",
                strength=60.0,
                explanation="Equipment enhances creature effectiveness"
            )
        
        return None
    
    async def _analyze_meta_matchups(self, deck: Deck) -> List[MetaMatchup]:
        """Analyze matchups against meta archetypes using real-time meta data.
        
        Returns:
            List[MetaMatchup]: List of matchups. Returns cached matchups if live fetch 
            fails and cache is available, or empty list if no cache exists.
            
        Note:
            Attempts to use cached meta data as fallback when live fetch fails.
            Returns empty list only when both live fetch and cache fallback fail.
            Check logs for error details.
        """
        matchups = []

        # Fetch current meta data
        try:
            meta_snapshot = await self.meta_service.get_current_meta(deck.format)

            for archetype in meta_snapshot.archetypes:
                win_rate = self._estimate_matchup_winrate_enhanced(deck, archetype)
                favorable = win_rate >= 50.0

                matchup = MetaMatchup(
                    archetype=archetype.name,
                    win_rate=win_rate,
                    favorable=favorable,
                    key_cards=archetype.key_cards[:5],  # Top 5 key cards
                    sideboard_suggestions=[]
                )
                matchups.append(matchup)
        except Exception as e:
            logger.warning("Could not fetch meta data: %s", e, exc_info=True)
            # Check if we have cached data we can use
            cache_key = f"meta_{deck.format.lower()}"
            if hasattr(self.meta_service, 'cache') and cache_key in self.meta_service.cache:
                logger.info("Using cached meta data as fallback")
                cached = self.meta_service.cache[cache_key]
                for archetype in cached.archetypes:
                    win_rate = self._estimate_matchup_winrate_enhanced(deck, archetype)
                    favorable = win_rate >= 50.0

                    matchup = MetaMatchup(
                        archetype=archetype.name,
                        win_rate=win_rate,
                        favorable=favorable,
                        key_cards=archetype.key_cards[:5],
                        sideboard_suggestions=[]
                    )
                    matchups.append(matchup)
            else:
                logger.error("No cached meta data available for fallback")

        return matchups
    
    def _estimate_matchup_winrate_enhanced(self, deck: Deck, archetype) -> float:
        """Estimate win rate against an archetype using enhanced heuristics.

        Args:
            deck: The player's deck
            archetype: MetaArchetype object from meta_intelligence
        """
        # Simplified - would use historical data and ML in production
        base_rate = 50.0

        # Identify deck strategy type based on mana curve and card types
        non_land_cards = sum(card.quantity for card in deck.mainboard
                            if card.card_type.lower() != 'land')
        avg_cmc = sum(card.cmc * card.quantity for card in deck.mainboard
                     if card.card_type.lower() != 'land') / max(1, non_land_cards)

        deck_strategy = self._identify_deck_strategy(deck, avg_cmc)

        # Strategy-based matchup matrix
        matchup_adjustments = {
            'aggro': {
                'aggro': 0,
                'midrange': -5,
                'control': +10,
                'combo': 0
            },
            'midrange': {
                'aggro': +5,
                'midrange': 0,
                'control': -5,
                'combo': +5
            },
            'control': {
                'aggro': -10,
                'midrange': +5,
                'control': 0,
                'combo': -5
            }
        }

        adjustment = matchup_adjustments.get(deck_strategy, {}).get(
            archetype.strategy_type, 0
        )
        base_rate += adjustment

        # Adjust based on specific cards
        if archetype.strategy_type == 'aggro':
            # More removal and lifegain helps against aggro
            removal_count = sum(
                card.quantity for card in deck.mainboard
                if any(word in card.name.lower()
                      for word in ['destroy', 'removal', 'wrath', 'exile', 'kill'])
            )
            base_rate += min(removal_count * 1.5, 10)

        return min(100.0, max(0.0, base_rate))

    def _identify_deck_strategy(self, deck: Deck, avg_cmc: float) -> str:
        """Identify deck strategy type based on composition."""
        creature_count = sum(
            card.quantity for card in deck.mainboard
            if 'creature' in card.card_type.lower()
        )
        total_nonland = sum(
            card.quantity for card in deck.mainboard
            if card.card_type.lower() != 'land'
        )

        if total_nonland == 0:
            return 'midrange'

        creature_ratio = creature_count / total_nonland

        # Aggro: low CMC, high creature density
        if avg_cmc < 2.5 and creature_ratio > 0.6:
            return 'aggro'

        # Control: high CMC, low creature density
        if avg_cmc > 3.5 and creature_ratio < 0.3:
            return 'control'

        # Default to midrange
        return 'midrange'
    
    def _identify_strengths_weaknesses(
        self, deck: Deck, mana_curve: ManaCurve, 
        color_dist: Dict[str, int], card_types: Dict[str, int]
    ) -> tuple[List[str], List[str]]:
        """Identify deck strengths and weaknesses."""
        strengths = []
        weaknesses = []
        
        # Mana curve analysis
        if mana_curve.curve_score >= 70:
            strengths.append("Well-balanced mana curve")
        elif mana_curve.curve_score < 50:
            weaknesses.append("Mana curve needs improvement")
        
        if mana_curve.average_cmc < 2.5:
            strengths.append("Fast, aggressive curve")
        elif mana_curve.average_cmc > 4.0:
            strengths.append("Late-game oriented strategy")
        
        # Color distribution
        num_colors = len(color_dist)
        if num_colors == 1:
            strengths.append("Mono-colored for consistent mana")
        elif num_colors >= 3:
            weaknesses.append("Multi-color may have mana consistency issues")
        
        # Card type balance
        creature_count = card_types.get('Creature', 0)
        total_nonland = sum(card_types.get(t, 0) for t in card_types if t != 'Land')
        
        if total_nonland > 0:
            creature_ratio = creature_count / total_nonland
            if 0.3 <= creature_ratio <= 0.5:
                strengths.append("Good creature-to-spell ratio")
            elif creature_ratio < 0.2:
                weaknesses.append("May lack creature presence")
            elif creature_ratio > 0.7:
                weaknesses.append("Heavy creature focus may be vulnerable")
        
        return strengths, weaknesses
    
    def _calculate_overall_score(
        self, mana_curve: ManaCurve, color_dist: Dict[str, int],
        card_types: Dict[str, int], synergies: List[CardSynergy]
    ) -> float:
        """Calculate overall deck score (0-100)."""
        # Weighted scoring
        curve_weight = 0.35
        color_weight = 0.15
        balance_weight = 0.25
        synergy_weight = 0.25
        
        # Mana curve score
        curve_score = mana_curve.curve_score
        
        # Color consistency score
        num_colors = len(color_dist)
        color_score = 100 - (num_colors - 1) * 15  # Penalize each additional color
        color_score = max(0, min(100, color_score))
        
        # Card type balance score
        total_nonland = sum(card_types.get(t, 0) for t in card_types if t != 'Land')
        creature_count = card_types.get('Creature', 0)
        if total_nonland > 0:
            creature_ratio = creature_count / total_nonland
            # Ideal ratio around 0.4
            balance_score = 100 - abs(creature_ratio - 0.4) * 100
        else:
            balance_score = 0
        
        # Synergy score
        avg_synergy = (
            statistics.mean([s.strength for s in synergies]) 
            if synergies else 50
        )
        
        # Calculate weighted total
        overall = (
            curve_score * curve_weight +
            color_score * color_weight +
            balance_score * balance_weight +
            avg_synergy * synergy_weight
        )
        
        return round(overall, 2)
    
    def _estimate_matchup_winrate(self, deck: Deck, archetype: Dict) -> float:
        """Legacy method for backward compatibility."""
        # This is kept for compatibility but shouldn't be used
        # Use _estimate_matchup_winrate_enhanced instead
        return 50.0
