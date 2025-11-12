"""SmartSQL service for deck storage and retrieval."""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, and_
from datetime import datetime

from ..models.database import Base, DeckModel, CardModel, PerformanceModel
from ..models.deck import Deck, Card


class SmartSQLService:
    """Service for intelligent deck storage and querying."""
    
    def __init__(self, database_url: str = "sqlite+aiosqlite:///./data/arena_improver.db"):
        self.database_url = database_url
        self.engine = create_async_engine(database_url, echo=False)
        self.SessionLocal = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
    
    async def init_db(self):
        """Initialize database tables."""
        # Ensure the directory exists for SQLite database
        if self.database_url.startswith("sqlite"):
            import os
            from pathlib import Path
            
            # Extract the file path from the database URL
            # Format: sqlite+aiosqlite:///./data/arena_improver.db
            db_path = self.database_url.split("///", 1)[-1]
            db_dir = os.path.dirname(db_path)
            
            if db_dir and db_dir not in [".", ""]:
                Path(db_dir).mkdir(parents=True, exist_ok=True)
        
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def store_deck(self, deck: Deck) -> int:
        """Store a deck in the database."""
        async with self.SessionLocal() as session:
            # Create deck model
            deck_model = DeckModel(
                name=deck.name,
                format=deck.format
            )
            session.add(deck_model)
            await session.flush()  # Get the deck ID
            
            # Add mainboard cards
            for card in deck.mainboard:
                card_model = CardModel(
                    deck_id=deck_model.id,
                    name=card.name,
                    quantity=card.quantity,
                    card_type=card.card_type,
                    mana_cost=card.mana_cost,
                    cmc=card.cmc,
                    colors=card.colors,
                    rarity=card.rarity,
                    set_code=card.set_code,
                    is_sideboard=0
                )
                session.add(card_model)
            
            # Add sideboard cards
            for card in deck.sideboard:
                card_model = CardModel(
                    deck_id=deck_model.id,
                    name=card.name,
                    quantity=card.quantity,
                    card_type=card.card_type,
                    mana_cost=card.mana_cost,
                    cmc=card.cmc,
                    colors=card.colors,
                    rarity=card.rarity,
                    set_code=card.set_code,
                    is_sideboard=1
                )
                session.add(card_model)
            
            await session.commit()
            return deck_model.id
    
    async def get_deck(self, deck_id: int) -> Optional[Deck]:
        """Retrieve a deck from the database."""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(DeckModel).where(DeckModel.id == deck_id)
            )
            deck_model = result.scalar_one_or_none()
            
            if not deck_model:
                return None
            
            # Load cards
            card_result = await session.execute(
                select(CardModel).where(CardModel.deck_id == deck_id)
            )
            cards = card_result.scalars().all()
            
            mainboard = []
            sideboard = []
            
            for card_model in cards:
                card = Card(
                    name=card_model.name,
                    quantity=card_model.quantity,
                    card_type=card_model.card_type,
                    mana_cost=card_model.mana_cost,
                    cmc=card_model.cmc,
                    colors=card_model.colors or [],
                    rarity=card_model.rarity,
                    set_code=card_model.set_code
                )
                
                if card_model.is_sideboard:
                    sideboard.append(card)
                else:
                    mainboard.append(card)
            
            return Deck(
                name=deck_model.name,
                format=deck_model.format,
                mainboard=mainboard,
                sideboard=sideboard
            )
    
    async def list_decks(self, format: Optional[str] = None) -> List[dict]:
        """List all decks with optional format filter."""
        async with self.SessionLocal() as session:
            query = select(DeckModel)
            if format:
                query = query.where(DeckModel.format == format)
            
            result = await session.execute(query)
            decks = result.scalars().all()
            
            return [
                {
                    'id': deck.id,
                    'name': deck.name,
                    'format': deck.format,
                    'created_at': deck.created_at.isoformat(),
                    'updated_at': deck.updated_at.isoformat()
                }
                for deck in decks
            ]
    
    async def record_performance(
        self, deck_id: int, opponent_archetype: str, 
        result: str, games_won: int, games_lost: int, notes: str = ""
    ):
        """Record a match performance."""
        async with self.SessionLocal() as session:
            performance = PerformanceModel(
                deck_id=deck_id,
                opponent_archetype=opponent_archetype,
                result=result,
                games_won=games_won,
                games_lost=games_lost,
                notes=notes
            )
            session.add(performance)
            await session.commit()
    
    async def get_deck_performance(self, deck_id: int) -> List[dict]:
        """Get performance history for a deck."""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(PerformanceModel)
                .where(PerformanceModel.deck_id == deck_id)
                .order_by(PerformanceModel.match_date.desc())
            )
            performances = result.scalars().all()
            
            return [
                {
                    'match_date': perf.match_date.isoformat(),
                    'opponent_archetype': perf.opponent_archetype,
                    'result': perf.result,
                    'games_won': perf.games_won,
                    'games_lost': perf.games_lost,
                    'notes': perf.notes
                }
                for perf in performances
            ]
    
    async def close(self):
        """Close the database engine and cleanup resources."""
        await self.engine.dispose()
