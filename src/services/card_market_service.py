"""Card market pricing and vendor integration service."""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from .scryfall_service import ScryfallService

logger = logging.getLogger(__name__)


@dataclass
class VendorPrice:
    """Vendor pricing information for a card."""
    vendor_name: str
    price_usd: Optional[float]
    price_eur: Optional[float]
    currency: str
    purchase_url: Optional[str]
    in_stock: bool = True
    last_updated: datetime = None

    def __post_init__(self):
        if self.last_updated is None:
            self.last_updated = datetime.now()


@dataclass
class CardMarketInfo:
    """Complete market information for a card."""
    card_name: str
    set_code: Optional[str]
    is_arena_only: bool
    available_in_paper: bool
    vendors: List[VendorPrice]
    best_price_usd: Optional[float]
    best_vendor: Optional[str]
    scryfall_id: Optional[str] = None
    image_uri: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "card_name": self.card_name,
            "set_code": self.set_code,
            "is_arena_only": self.is_arena_only,
            "available_in_paper": self.available_in_paper,
            "vendors": [
                {
                    "vendor_name": v.vendor_name,
                    "price_usd": v.price_usd,
                    "price_eur": v.price_eur,
                    "currency": v.currency,
                    "purchase_url": v.purchase_url,
                    "in_stock": v.in_stock,
                    "last_updated": v.last_updated.isoformat()
                }
                for v in self.vendors
            ],
            "best_price_usd": self.best_price_usd,
            "best_vendor": self.best_vendor,
            "scryfall_id": self.scryfall_id,
            "image_uri": self.image_uri
        }


class CardMarketService:
    """Service for fetching card pricing and vendor information.
    
    Uses async context manager for proper lifecycle management of dependencies.
    """

    def __init__(self, scryfall_service: Optional[ScryfallService] = None):
        """
        Initialize card market service.

        Args:
            scryfall_service: Optional ScryfallService instance (deferred creation)
        """
        self.scryfall = scryfall_service

    async def __aenter__(self):
        """Async context manager entry - ensures Scryfall service is initialized."""
        if not self.scryfall:
            self.scryfall = ScryfallService()
        # Only enter context if not already entered
        if not getattr(self.scryfall, "_entered", False):
            await self.scryfall.__aenter__()
            setattr(self.scryfall, "_entered", True)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - properly closes Scryfall service."""
        if self.scryfall and getattr(self.scryfall, "_entered", False):
            await self.scryfall.__aexit__(exc_type, exc_val, exc_tb)
            setattr(self.scryfall, "_entered", False)
        return False

    async def close(self):
        """Explicitly close the Scryfall service."""
        if self.scryfall:
            await self.scryfall.close()

    async def get_card_market_info(
        self,
        card_name: str,
        set_code: Optional[str] = None,
        exclude_arena_only: bool = True
    ) -> Optional[CardMarketInfo]:
        """
        Get complete market information for a card.

        Args:
            card_name: Name of the card
            set_code: Optional set code
            exclude_arena_only: If True, return None for Arena-only cards

        Returns:
            CardMarketInfo or None if Arena-only and excluded
        """
        # Check if card is Arena-only
        is_arena_only = await self.scryfall.is_arena_only(card_name, set_code)

        if exclude_arena_only and is_arena_only:
            logger.info(f"Excluding Arena-only card: {card_name}")
            return None

        # Get card data from Scryfall
        card_data = await self.scryfall.get_card_by_name(card_name, set_code)

        if not card_data:
            logger.warning(f"Could not fetch card data for: {card_name}")
            return None

        # Get prices
        prices = await self.scryfall.get_card_prices(card_name, set_code)

        # Get purchase URIs
        purchase_uris = await self.scryfall.get_purchase_uris(card_name, set_code)

        # Get image URI
        image_uri = await self.scryfall.get_card_image_uri(card_name, set_code, "normal")

        # Build vendor list
        vendors = []

        # TCGPlayer
        if purchase_uris.get("tcgplayer"):
            vendors.append(VendorPrice(
                vendor_name="TCGPlayer",
                price_usd=prices.get("usd"),
                price_eur=None,
                currency="USD",
                purchase_url=purchase_uris["tcgplayer"],
                in_stock=prices.get("usd") is not None
            ))

        # CardMarket (MKM)
        if purchase_uris.get("cardmarket"):
            vendors.append(VendorPrice(
                vendor_name="CardMarket",
                price_usd=None,
                price_eur=prices.get("eur"),
                currency="EUR",
                purchase_url=purchase_uris["cardmarket"],
                in_stock=prices.get("eur") is not None
            ))

        # Cardhoarder (MTGO)
        if purchase_uris.get("cardhoarder"):
            vendors.append(VendorPrice(
                vendor_name="Cardhoarder",
                price_usd=prices.get("tix"),
                price_eur=None,
                currency="TIX",
                purchase_url=purchase_uris["cardhoarder"],
                in_stock=prices.get("tix") is not None
            ))

        # Find best price in USD
        best_price_usd = None
        best_vendor = None

        usd_vendors = [v for v in vendors if v.price_usd is not None and v.currency == "USD"]
        if usd_vendors:
            best_vendor_obj = min(usd_vendors, key=lambda v: v.price_usd)
            best_price_usd = best_vendor_obj.price_usd
            best_vendor = best_vendor_obj.vendor_name

        return CardMarketInfo(
            card_name=card_name,
            set_code=set_code,
            is_arena_only=is_arena_only,
            available_in_paper=not is_arena_only,
            vendors=vendors,
            best_price_usd=best_price_usd,
            best_vendor=best_vendor,
            scryfall_id=card_data.get("id"),
            image_uri=image_uri
        )

    async def get_deck_market_info(
        self,
        cards: List[tuple[str, int, Optional[str]]],
        exclude_arena_only: bool = True
    ) -> Dict[str, Any]:
        """
        Get market information for an entire deck.

        Args:
            cards: List of (card_name, quantity, set_code) tuples
            exclude_arena_only: If True, exclude Arena-only cards

        Returns:
            Dict with deck market summary
        """
        card_market_info = []
        total_price_usd = 0.0
        arena_only_cards = []
        purchasable_cards = []

        for card_name, quantity, set_code in cards:
            market_info = await self.get_card_market_info(
                card_name,
                set_code,
                exclude_arena_only=False  # Get info for all to track Arena-only
            )

            if not market_info:
                continue

            if market_info.is_arena_only:
                arena_only_cards.append({
                    "card_name": card_name,
                    "quantity": quantity
                })
            else:
                card_price = market_info.best_price_usd or 0.0
                total_price_usd += card_price * quantity

                purchasable_cards.append({
                    "card_name": card_name,
                    "quantity": quantity,
                    "unit_price_usd": card_price,
                    "total_price_usd": card_price * quantity,
                    "best_vendor": market_info.best_vendor,
                    "vendors": [
                        {
                            "vendor_name": v.vendor_name,
                            "price_usd": v.price_usd,
                            "price_eur": v.price_eur,
                            "purchase_url": v.purchase_url,
                            "in_stock": v.in_stock
                        }
                        for v in market_info.vendors
                    ],
                    "image_uri": market_info.image_uri
                })

                card_market_info.append(market_info)

        return {
            "total_cards": len(cards),
            "purchasable_cards": len(purchasable_cards),
            "arena_only_cards": len(arena_only_cards),
            "total_price_usd": round(total_price_usd, 2),
            "cards": purchasable_cards,
            "arena_only": arena_only_cards,
            "summary": {
                "cheapest_vendor_breakdown": self._get_vendor_breakdown(purchasable_cards),
                "avg_card_price_usd": round(total_price_usd / len(purchasable_cards), 2) if purchasable_cards else 0.0
            }
        }

    def _get_vendor_breakdown(self, purchasable_cards: List[Dict]) -> Dict[str, float]:
        """
        Calculate total cost by vendor if buying all from one vendor.

        Args:
            purchasable_cards: List of card dicts with vendor info

        Returns:
            Dict mapping vendor name to total cost
        """
        vendor_totals: Dict[str, float] = {}

        for card in purchasable_cards:
            for vendor in card.get("vendors", []):
                vendor_name = vendor["vendor_name"]
                price = vendor.get("price_usd")

                if price and vendor.get("in_stock", True):
                    if vendor_name not in vendor_totals:
                        vendor_totals[vendor_name] = 0.0
                    vendor_totals[vendor_name] += price * card["quantity"]

        return {
            vendor: round(total, 2)
            for vendor, total in sorted(vendor_totals.items(), key=lambda x: x[1])
        }

    async def find_card_alternatives(
        self,
        card_name: str,
        max_price_usd: Optional[float] = None
    ) -> List[CardMarketInfo]:
        """
        Find alternative printings or similar cards within price range.

        Args:
            card_name: Name of the card
            max_price_usd: Maximum price in USD

        Returns:
            List of alternative card market info
        """
        # Search for all printings of the card
        search_query = f'!"{card_name}" game:paper'
        cards = await self.scryfall.search_cards(search_query, unique="prints")

        alternatives = []

        for card_data in cards[:10]:  # Limit to 10 printings
            card_name_variant = card_data.get("name")
            set_code = card_data.get("set")

            market_info = await self.get_card_market_info(
                card_name_variant,
                set_code,
                exclude_arena_only=True
            )

            if not market_info:
                continue

            # Filter by price if specified
            if max_price_usd and market_info.best_price_usd:
                if market_info.best_price_usd <= max_price_usd:
                    alternatives.append(market_info)
            else:
                alternatives.append(market_info)

        # Sort by price
        alternatives.sort(key=lambda x: x.best_price_usd or float('inf'))

        return alternatives

    async def get_budget_replacements(
        self,
        expensive_cards: List[tuple[str, int]],
        max_price_per_card: float = 5.0
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Find budget replacement options for expensive cards.

        Args:
            expensive_cards: List of (card_name, quantity) tuples
            max_price_per_card: Maximum price per card in USD

        Returns:
            Dict mapping card name to list of budget alternatives
        """
        replacements = {}

        for card_name, quantity in expensive_cards:
            alternatives = await self.find_card_alternatives(
                card_name,
                max_price_usd=max_price_per_card
            )

            if alternatives:
                replacements[card_name] = [
                    {
                        "card_name": alt.card_name,
                        "set_code": alt.set_code,
                        "price_usd": alt.best_price_usd,
                        "vendor": alt.best_vendor,
                        "savings_per_copy": (
                            (alternatives[0].best_price_usd or 0) - (alt.best_price_usd or 0)
                        ),
                        "image_uri": alt.image_uri
                    }
                    for alt in alternatives[:5]  # Top 5 alternatives
                ]

        return replacements
