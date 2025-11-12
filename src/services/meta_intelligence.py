"""MetaIntelligence service for real-time MTG Arena meta analysis.

This service leverages MCP servers (Tavily, Exa) to fetch current meta data,
tournament results, and professional deck strategies from various sources.
"""

import os
import json
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, asdict
import asyncio

from ..models.deck import Deck

logger = logging.getLogger(__name__)


@dataclass
class MetaArchetype:
    """Represents a current meta archetype."""
    name: str
    format: str
    meta_share: float  # percentage
    win_rate: float  # percentage
    key_cards: List[str]
    strategy_type: str  # aggro, control, midrange, combo
    strengths: List[str]
    weaknesses: List[str]
    source: str
    last_updated: str


@dataclass
class TournamentResult:
    """Represents recent tournament data."""
    event_name: str
    date: str
    format: str
    winning_deck: str
    archetype: str
    decklist_url: Optional[str] = None
    pilot_name: Optional[str] = None


@dataclass
class MetaSnapshot:
    """Complete meta snapshot for a format."""
    format: str
    archetypes: List[MetaArchetype]
    tournament_results: List[TournamentResult]
    ban_list_updates: List[Dict[str, str]]
    meta_trends: Dict[str, Any]
    timestamp: str


class MetaIntelligenceService:
    """Service for fetching and analyzing real-time MTG Arena meta data.

    This service uses MCP tools (via cld-omnisearch) to query:
    - MTGGoldfish for meta shares and decklists
    - AetherHub for Arena-specific meta data
    - Tournament results and professional play data
    - Ban list updates and format changes
    """

    def __init__(self):
        self.cache: Dict[str, MetaSnapshot] = {}
        try:
            self.cache_duration = int(os.getenv("META_UPDATE_FREQUENCY", "24")) * 3600
        except ValueError as e:
            env_val = os.getenv('META_UPDATE_FREQUENCY', "24")
            raise ValueError(
                f"Invalid META_UPDATE_FREQUENCY: '{env_val}' is not a valid integer."
            ) from e
        self.meta_sources = os.getenv(
            "META_SOURCES",
            "https://www.mtggoldfish.com/metagame/standard,https://aetherhub.com/Metagame/Standard-BO3"
        ).split(",")

    async def get_current_meta(self, format: str = "Standard") -> MetaSnapshot:
        """Get current meta snapshot for a format.

        Uses MCP tools to fetch fresh data from meta websites.
        Results are cached to avoid excessive API calls.
        """
        # Check cache
        cache_key = f"meta_{format.lower()}"
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            cache_time = datetime.fromisoformat(cached.timestamp)
            if cache_time.tzinfo is None:
                cache_time = cache_time.replace(tzinfo=timezone.utc)
                logger.debug("Cache timestamp was naive, converted to UTC")
            elif cache_time.tzinfo != timezone.utc:
                cache_time = cache_time.astimezone(timezone.utc)
                logger.debug("Cache timestamp converted from %s to UTC", cache_time.tzinfo.tzname(cache_time))
            if (datetime.now(timezone.utc) - cache_time).total_seconds() < self.cache_duration:
                return cached

        # Fetch fresh data using MCPs
        archetypes = await self._fetch_archetypes(format)
        tournaments = await self._fetch_tournament_results(format)
        ban_updates = await self._fetch_ban_list_updates(format)
        trends = await self._analyze_meta_trends(archetypes)

        snapshot = MetaSnapshot(
            format=format,
            archetypes=archetypes,
            tournament_results=tournaments,
            ban_list_updates=ban_updates,
            meta_trends=trends,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

        # Update cache
        self.cache[cache_key] = snapshot
        return snapshot

    async def _fetch_archetypes(self, format: str) -> List[MetaArchetype]:
        """Fetch current meta archetypes using MCP search tools.

        This method should be called through MCP's Tavily or Exa tools.
        For now, returns enhanced example data.
        """
        # TODO: When MCP tools are available, use them like:
        # result = await mcp_tool("tavily_search", {
        #     "query": f"MTG Arena {format} meta archetypes decklists 2024",
        #     "search_depth": "advanced"
        # })

        # Enhanced example archetypes based on current Standard meta
        return [
            MetaArchetype(
                name="Dimir Midrange",
                format=format,
                meta_share=12.5,
                win_rate=54.2,
                key_cards=[
                    "Sheoldred, the Apocalypse",
                    "Preacher of the Schism",
                    "Cut Down",
                    "Go for the Throat",
                    "Deep-Cavern Bat"
                ],
                strategy_type="midrange",
                strengths=[
                    "Strong removal suite",
                    "Powerful card advantage engines",
                    "Good against creature-based strategies"
                ],
                weaknesses=[
                    "Vulnerable to aggressive starts",
                    "Limited answers to resolved planeswalkers",
                    "Can struggle against control"
                ],
                source="mtggoldfish.com",
                last_updated=datetime.now(timezone.utc).isoformat()
            ),
            MetaArchetype(
                name="Boros Convoke",
                format=format,
                meta_share=15.8,
                win_rate=52.7,
                key_cards=[
                    "Gleeful Demolition",
                    "Imodane's Recruiter",
                    "Venerable Warsinger",
                    "Knight-Errant of Eos",
                    "Urabrask's Forge"
                ],
                strategy_type="aggro",
                strengths=[
                    "Explosive starts with convoke",
                    "Resilient to sweepers",
                    "Good mana efficiency"
                ],
                weaknesses=[
                    "Struggles without early creatures",
                    "Weak to targeted removal + sweepers combo",
                    "Limited reach in late game"
                ],
                source="aetherhub.com",
                last_updated=datetime.now(timezone.utc).isoformat()
            ),
            MetaArchetype(
                name="Domain Ramp",
                format=format,
                meta_share=10.3,
                win_rate=51.8,
                key_cards=[
                    "Leyline Binding",
                    "Atraxa, Grand Unifier",
                    "Sunfall",
                    "Up the Beanstalk",
                    "Topiary Stomper"
                ],
                strategy_type="control",
                strengths=[
                    "Powerful late game threats",
                    "Efficient removal with Leyline Binding",
                    "Card advantage from Up the Beanstalk"
                ],
                weaknesses=[
                    "Mulligan-dependent mana base",
                    "Vulnerable to fast aggro",
                    "Weak to mana denial"
                ],
                source="mtggoldfish.com",
                last_updated=datetime.now(timezone.utc).isoformat()
            ),
            MetaArchetype(
                name="Mono-Red Aggro",
                format=format,
                meta_share=14.2,
                win_rate=53.5,
                key_cards=[
                    "Monastery Swiftspear",
                    "Emberheart Challenger",
                    "Kumano Faces Kakkazan",
                    "Monstrous Rage",
                    "Phoenix Chick"
                ],
                strategy_type="aggro",
                strengths=[
                    "Consistent fast clock",
                    "Punishes slow starts",
                    "Good against greedy mana bases"
                ],
                weaknesses=[
                    "Runs out of cards quickly",
                    "Vulnerable to lifegain",
                    "Struggles against early blockers"
                ],
                source="mtggoldfish.com",
                last_updated=datetime.now(timezone.utc).isoformat()
            ),
            MetaArchetype(
                name="Esper Legends",
                format=format,
                meta_share=8.7,
                win_rate=50.9,
                key_cards=[
                    "Raffine, Scheming Seer",
                    "Dennick, Pious Apprentice",
                    "Thalia, Guardian of Thraben",
                    "The Wandering Emperor",
                    "Flowering of the White Tree"
                ],
                strategy_type="midrange",
                strengths=[
                    "Versatile threats",
                    "Good interaction suite",
                    "Strong tribal synergies"
                ],
                weaknesses=[
                    "Vulnerable to sweepers",
                    "Mana base constraints",
                    "Can be outvalued by dedicated control"
                ],
                source="aetherhub.com",
                last_updated=datetime.now(timezone.utc).isoformat()
            ),
            MetaArchetype(
                name="Azorius Control",
                format=format,
                meta_share=9.4,
                win_rate=52.1,
                key_cards=[
                    "The Wandering Emperor",
                    "Temporary Lockdown",
                    "Make Disappear",
                    "Haughty Djinn",
                    "Memory Deluge"
                ],
                strategy_type="control",
                strengths=[
                    "Strong late game",
                    "Efficient answers",
                    "Card selection"
                ],
                weaknesses=[
                    "Weak to resolved threats",
                    "Vulnerable to aggro",
                    "Struggles with recursive threats"
                ],
                source="mtggoldfish.com",
                last_updated=datetime.now(timezone.utc).isoformat()
            )
        ]

    async def _fetch_tournament_results(self, format: str) -> List[TournamentResult]:
        """Fetch recent tournament results using MCP search.

        TODO: Integrate with MCP tools when available.
        """
        # Example tournament data
        return [
            TournamentResult(
                event_name="Pro Tour Thunder Junction",
                date=(datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
                format=format,
                winning_deck="Boros Convoke",
                archetype="aggro",
                pilot_name="Example Pro Player"
            ),
            TournamentResult(
                event_name="Arena Championship 6",
                date=(datetime.now(timezone.utc) - timedelta(days=12)).isoformat(),
                format=format,
                winning_deck="Dimir Midrange",
                archetype="midrange"
            )
        ]

    async def _fetch_ban_list_updates(self, format: str) -> List[Dict[str, str]]:
        """Fetch recent ban list updates using MCP search.

        TODO: Integrate with MCP tools when available.
        """
        # Example ban list data
        return [
            {
                "date": "2024-03-04",
                "action": "banned",
                "card": "Fable of the Mirror-Breaker",
                "format": "Standard"
            }
        ]

    async def _analyze_meta_trends(
        self, archetypes: List[MetaArchetype]
    ) -> Dict[str, Any]:
        """Analyze meta trends from archetype data."""
        # Guard against empty archetypes
        if not archetypes:
            return {
                "total_archetypes": 0,
                "covered_meta_share": 0.0,
                "strategy_distribution": {},
                "dominant_strategy": None,
                "dominant_strategy_share": 0.0,
                "avg_winrates_by_strategy": {},
                "meta_health": self._assess_meta_health([])
            }

        total_share = sum(arch.meta_share for arch in archetypes)

        # Calculate strategy type distribution
        strategy_distribution = {}
        for arch in archetypes:
            strategy_distribution[arch.strategy_type] = \
                strategy_distribution.get(arch.strategy_type, 0) + arch.meta_share

        # Guard against empty strategy distribution
        if not strategy_distribution:
            return {
                "total_archetypes": len(archetypes),
                "covered_meta_share": round(total_share, 2),
                "strategy_distribution": {},
                "dominant_strategy": None,
                "dominant_strategy_share": 0.0,
                "avg_winrates_by_strategy": {},
                "meta_health": self._assess_meta_health(archetypes)
            }

        # Identify dominant strategy
        dominant_strategy = max(strategy_distribution.items(), key=lambda x: x[1], default=(None, 0.0))

        # Calculate average win rates by strategy
        strategy_winrates = {}
        strategy_counts = {}
        for arch in archetypes:
            if arch.strategy_type not in strategy_winrates:
                strategy_winrates[arch.strategy_type] = 0
                strategy_counts[arch.strategy_type] = 0
            strategy_winrates[arch.strategy_type] += arch.win_rate
            strategy_counts[arch.strategy_type] += 1

        avg_strategy_winrates = {
            strat: strategy_winrates[strat] / strategy_counts[strat]
            for strat in strategy_winrates
            if strategy_counts[strat] > 0
        }

        return {
            "total_archetypes": len(archetypes),
            "covered_meta_share": round(total_share, 2),
            "strategy_distribution": {
                k: round(v, 2) for k, v in strategy_distribution.items()
            },
            "dominant_strategy": dominant_strategy[0] or "N/A",
            "dominant_strategy_share": round(dominant_strategy[1], 2),
            "avg_winrates_by_strategy": {
                k: round(v, 2) for k, v in avg_strategy_winrates.items()
            },
            "meta_health": self._assess_meta_health(archetypes)
        }

    def _assess_meta_health(self, archetypes: List[MetaArchetype]) -> str:
        """Assess overall meta health based on diversity."""
        if not archetypes:
            return "unknown"

        # Check if any archetype is too dominant
        max_share = max(arch.meta_share for arch in archetypes)
        if max_share > 25:
            return "unhealthy_dominant"

        # Check for diversity
        if len(archetypes) >= 6 and max_share < 20:
            return "healthy_diverse"

        return "moderate"

    async def get_archetype_matchup_data(
        self, deck_archetype: str, format: str = "Standard"
    ) -> Dict[str, float]:
        """Get matchup win rates for a specific archetype against the meta."""
        meta = await self.get_current_meta(format)

        # TODO: When MCP tools are available, fetch actual matchup data
        # For now, use heuristics based on strategy types
        matchups = {}

        for arch in meta.archetypes:
            # Simplified matchup estimation
            estimated_winrate = self._estimate_matchup(deck_archetype, arch)
            matchups[arch.name] = estimated_winrate

        return matchups

    def _estimate_matchup(
        self, player_archetype: str, opponent: MetaArchetype
    ) -> float:
        """Estimate matchup win rate based on strategy types.

        This is a simplified heuristic. Real implementation should use
        MCP tools to fetch actual matchup data.
        """
        # Strategy type matchup matrix (aggro vs control, etc.)
        matchup_matrix = {
            "aggro": {"aggro": 50, "midrange": 45, "control": 55, "combo": 50},
            "midrange": {"aggro": 55, "midrange": 50, "control": 45, "combo": 52},
            "control": {"aggro": 45, "midrange": 55, "control": 50, "combo": 48},
            "combo": {"aggro": 50, "midrange": 48, "control": 52, "combo": 50}
        }

        # Explicit mapping from archetype name to strategy type for known archetypes
        # Updated for November 2025 MTG Arena Standard meta
        strategy_map = {
            # Current Tier 1 Archetypes (November 2025)
            "Mono-Red Aggro": "aggro",
            "Izzet Cauldron": "combo",
            "Dimir Midrange": "midrange",
            "Simic Aggro": "aggro",
            "Simic Omniscience": "combo",
            "Jeskai Artifacts": "midrange",
            "Jeskai Control": "control",
            "4 Color Control": "control",
            "4C Control": "control",
            "Sultai Reanimator": "combo",
            "Grixis Reanimator": "combo",
            "Gruul Aggro": "aggro",
            "Mono-Green Landfall": "aggro",
            "Mono-Black Demons": "midrange",
            "Azorius Control": "control",
            "Orzhov Lifegain": "midrange",
            "Temur Battlecrier": "aggro",
            # Legacy/Common Archetypes
            "Boros Convoke": "aggro",
            "Domain Ramp": "control",
            "Esper Legends": "midrange",
        }
        
        # Check explicit map first
        if player_archetype in strategy_map:
            player_type = strategy_map[player_archetype]
        else:
            # Fallback: detect strategy type from archetype name using keyword matching
            # Priority order: control > combo > aggro > midrange (most to least specific)
            archetype_lower = player_archetype.lower()
            if "control" in archetype_lower:
                player_type = "control"
            elif "combo" in archetype_lower:
                player_type = "combo"
            elif "aggro" in archetype_lower or "aggressive" in archetype_lower:
                player_type = "aggro"
            elif "midrange" in archetype_lower or "mid-range" in archetype_lower:
                player_type = "midrange"
            elif "tempo" in archetype_lower:
                # Tempo decks are typically aggro-control hybrids, lean aggro
                player_type = "aggro"
            elif "ramp" in archetype_lower:
                # Ramp decks typically lean control
                player_type = "control"
            else:
                # Default to midrange for unknown archetypes
                player_type = "midrange"

        return matchup_matrix.get(player_type, {}).get(opponent.strategy_type, 50.0)

    async def search_card_synergies(
        self, card_name: str, format: str = "Standard"
    ) -> List[Dict[str, Any]]:
        """Search for cards that synergize with a given card.

        Uses MCP semantic search to find related cards and strategies.
        """
        # TODO: Integrate with Exa MCP for semantic search
        # result = await mcp_tool("exa_search", {
        #     "query": f"{card_name} MTG Arena synergies combos",
        #     "type": "neural",
        #     "num_results": 10
        # })

        return [
            {
                "synergy_card": "Example Synergy",
                "reason": "Works well together",
                "strength": 75
            }
        ]

    async def get_sideboard_suggestions(
        self, deck: Deck, target_archetype: str
    ) -> List[Dict[str, Any]]:
        """Get sideboard suggestions for a specific matchup.

        Uses MCP tools to find current sideboard tech.
        """
        # TODO: Use MCP search to find current sideboard strategies
        return [
            {
                "card": "Example Sideboard Card",
                "reason": "Good against target archetype",
                "quantity": 2
            }
        ]

    def _get_fallback_archetypes(self, format: str) -> List[MetaArchetype]:
        """Provide fallback archetypes when meta data fetching fails."""
        logger.info("Using fallback archetypes for %s", format)
        return [
            MetaArchetype(
                name="Generic Aggro",
                format=format,
                meta_share=20.0,
                win_rate=50.0,
                key_cards=["Aggressive Creature", "Burn Spell"],
                strategy_type="aggro",
                strengths=["Fast clock", "Punishes slow decks"],
                weaknesses=["Runs out of resources", "Vulnerable to sweepers"],
                source="fallback",
                last_updated=datetime.now(timezone.utc).isoformat()
            ),
            MetaArchetype(
                name="Generic Midrange",
                format=format,
                meta_share=30.0,
                win_rate=50.0,
                key_cards=["Value Creature", "Removal Spell"],
                strategy_type="midrange",
                strengths=["Flexible gameplay", "Good threats"],
                weaknesses=["Can be too slow or too fast"],
                source="fallback",
                last_updated=datetime.now(timezone.utc).isoformat()
            ),
            MetaArchetype(
                name="Generic Control",
                format=format,
                meta_share=25.0,
                win_rate=50.0,
                key_cards=["Counterspell", "Board Wipe"],
                strategy_type="control",
                strengths=["Strong late game", "Answers to threats"],
                weaknesses=["Vulnerable to aggro", "Resource-intensive"],
                source="fallback",
                last_updated=datetime.now(timezone.utc).isoformat()
            )
        ]

    def to_dict(self, meta: MetaSnapshot) -> dict:
        """Convert MetaSnapshot to dictionary."""
        return {
            "format": meta.format,
            "archetypes": [asdict(arch) for arch in meta.archetypes],
            "tournament_results": [asdict(tr) for tr in meta.tournament_results],
            "ban_list_updates": meta.ban_list_updates,
            "meta_trends": meta.meta_trends,
            "timestamp": meta.timestamp
        }
