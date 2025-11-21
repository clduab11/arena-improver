"""Scryfall API integration for card data and Arena availability."""

import asyncio
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
import httpx
from functools import lru_cache

logger = logging.getLogger(__name__)


class ScryfallService:
    """Service for interacting with Scryfall API.
    
    Uses connection pooling for efficient API access.
    Can be used as async context manager for proper resource lifecycle.
    """

    BASE_URL = "https://api.scryfall.com"
    RATE_LIMIT_DELAY = 0.1  # 100ms between requests (Scryfall rate limit)
    CACHE_DURATION = timedelta(hours=24)

    def __init__(self):
        """Initialize Scryfall service with connection pooling support."""
        self._last_request_time = datetime.now()
        self._cache: Dict[str, tuple[datetime, Any]] = {}
        self._client: Optional[httpx.AsyncClient] = None

    async def _rate_limit(self):
        """Enforce Scryfall rate limit (100ms between requests)."""
        now = datetime.now()
        time_since_last = (now - self._last_request_time).total_seconds()

        if time_since_last < self.RATE_LIMIT_DELAY:
            await asyncio.sleep(self.RATE_LIMIT_DELAY - time_since_last)

        self._last_request_time = datetime.now()

    def _get_cached(self, key: str) -> Optional[Any]:
        """Get cached data if not expired."""
        if key in self._cache:
            timestamp, data = self._cache[key]
            if datetime.now() - timestamp < self.CACHE_DURATION:
                return data
            else:
                del self._cache[key]
        return None

    def _set_cached(self, key: str, data: Any):
        """Set cached data with timestamp."""
        self._cache[key] = (datetime.now(), data)

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Create HTTP client with connection pooling if not exists.
        
        Returns:
            httpx.AsyncClient: Client with connection pooling enabled
        """
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=10.0,
                limits=httpx.Limits(
                    max_keepalive_connections=5,
                    max_connections=10
                )
            )
        return self._client

    async def __aenter__(self):
        """Async context manager entry - ensures client is created."""
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - closes client properly."""
        if self._client:
            await self._client.aclose()
            self._client = None
        return False

    async def close(self):
        """Explicitly close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get_card_by_name(
        self,
        card_name: str,
        set_code: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get card data from Scryfall by name.

        Args:
            card_name: Name of the card
            set_code: Optional set code for specific printing

        Returns:
            Card data dict or None if not found
        """
        cache_key = f"card:{card_name}:{set_code or 'latest'}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        await self._rate_limit()

        try:
            await self._ensure_client()
            client = self._client
            params = {"fuzzy": card_name}
            if set_code:
                params["set"] = set_code

            response = await client.get(
                f"{self.BASE_URL}/cards/named",
                params=params,
                timeout=10.0
            )

            if response.status_code == 200:
                data = response.json()
                self._set_cached(cache_key, data)
                return data
            elif response.status_code == 404:
                logger.warning(f"Card not found on Scryfall: {card_name}")
                return None
            else:
                logger.error(f"Scryfall API error {response.status_code}: {response.text}")
                return None

        except httpx.TimeoutException:
            logger.error(f"Timeout fetching card: {card_name}")
            return None
        except Exception as e:
            logger.error(f"Error fetching card from Scryfall: {e}")
            return None

    async def is_arena_only(self, card_name: str, set_code: Optional[str] = None) -> bool:
        """
        Check if a card is Arena-only (not available in paper).

        Args:
            card_name: Name of the card
            set_code: Optional set code

        Returns:
            True if card is Arena-only, False otherwise
        """
        card_data = await self.get_card_by_name(card_name, set_code)

        if not card_data:
            # If we can't find the card, assume it might be Arena-only
            logger.warning(f"Could not determine Arena status for: {card_name}")
            return True

        # Check if card is digital-only
        games = card_data.get("games", [])

        # Card is Arena-only if it's available in Arena but not in Paper
        is_in_arena = "arena" in games
        is_in_paper = "paper" in games

        return is_in_arena and not is_in_paper

    async def get_card_prices(
        self,
        card_name: str,
        set_code: Optional[str] = None
    ) -> Dict[str, Optional[float]]:
        """
        Get card prices from Scryfall.

        Args:
            card_name: Name of the card
            set_code: Optional set code

        Returns:
            Dict with price information (usd, usd_foil, eur, tix)
        """
        card_data = await self.get_card_by_name(card_name, set_code)

        if not card_data:
            return {
                "usd": None,
                "usd_foil": None,
                "eur": None,
                "tix": None
            }

        prices = card_data.get("prices", {})

        return {
            "usd": float(prices.get("usd")) if prices.get("usd") else None,
            "usd_foil": float(prices.get("usd_foil")) if prices.get("usd_foil") else None,
            "eur": float(prices.get("eur")) if prices.get("eur") else None,
            "tix": float(prices.get("tix")) if prices.get("tix") else None,
        }

    async def get_purchase_uris(
        self,
        card_name: str,
        set_code: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Get purchase URIs for card vendors.

        Args:
            card_name: Name of the card
            set_code: Optional set code

        Returns:
            Dict with vendor URIs (tcgplayer, cardmarket, cardhoarder)
        """
        card_data = await self.get_card_by_name(card_name, set_code)

        if not card_data:
            return {}

        purchase_uris = card_data.get("purchase_uris", {})

        return {
            "tcgplayer": purchase_uris.get("tcgplayer"),
            "cardmarket": purchase_uris.get("cardmarket"),
            "cardhoarder": purchase_uris.get("cardhoarder"),
        }

    async def get_card_legality(
        self,
        card_name: str,
        set_code: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Get card legality information.

        Args:
            card_name: Name of the card
            set_code: Optional set code

        Returns:
            Dict with format legalities (standard, historic, pioneer, etc.)
        """
        card_data = await self.get_card_by_name(card_name, set_code)

        if not card_data:
            return {}

        return card_data.get("legalities", {})

    async def search_cards(
        self,
        query: str,
        unique: str = "cards",
        order: str = "name"
    ) -> List[Dict[str, Any]]:
        """
        Search for cards using Scryfall syntax.

        Args:
            query: Scryfall search query
            unique: Unique mode (cards, art, prints)
            order: Sort order

        Returns:
            List of card data dicts
        """
        cache_key = f"search:{query}:{unique}:{order}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        await self._rate_limit()

        try:
            await self._ensure_client()
            client = self._client
            response = await client.get(
                f"{self.BASE_URL}/cards/search",
                params={
                    "q": query,
                    "unique": unique,
                    "order": order
                },
                timeout=10.0
            )

            if response.status_code == 200:
                data = response.json()
                cards = data.get("data", [])
                self._set_cached(cache_key, cards)
                return cards
            else:
                logger.error(f"Scryfall search error {response.status_code}: {response.text}")
                return []

        except Exception as e:
            logger.error(f"Error searching Scryfall: {e}")
            return []

    async def get_card_image_uri(
        self,
        card_name: str,
        set_code: Optional[str] = None,
        image_type: str = "normal"
    ) -> Optional[str]:
        """
        Get card image URI.

        Args:
            card_name: Name of the card
            set_code: Optional set code
            image_type: Image type (small, normal, large, art_crop, border_crop)

        Returns:
            Image URI or None
        """
        card_data = await self.get_card_by_name(card_name, set_code)

        if not card_data:
            return None

        image_uris = card_data.get("image_uris", {})
        return image_uris.get(image_type)

    async def batch_check_arena_availability(
        self,
        card_names: List[str]
    ) -> Dict[str, bool]:
        """
        Check Arena availability for multiple cards.

        Args:
            card_names: List of card names

        Returns:
            Dict mapping card name to is_in_paper (True if available in paper)
        """
        results = {}

        for card_name in card_names:
            is_arena_only = await self.is_arena_only(card_name)
            results[card_name] = not is_arena_only  # Return True if available in paper

        return results
