"""Database models using SQLAlchemy."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class DeckModel(Base):
    """SQLAlchemy model for decks."""
    
    __tablename__ = "decks"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    format = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    cards = relationship("CardModel", back_populates="deck", cascade="all, delete-orphan")
    performances = relationship("PerformanceModel", back_populates="deck", cascade="all, delete-orphan")


class CardModel(Base):
    """SQLAlchemy model for cards in a deck."""
    
    __tablename__ = "cards"
    
    id = Column(Integer, primary_key=True, index=True)
    deck_id = Column(Integer, ForeignKey("decks.id"))
    name = Column(String, index=True)
    quantity = Column(Integer)
    card_type = Column(String)
    mana_cost = Column(String)
    cmc = Column(Float)
    colors = Column(JSON)  # Store as JSON array
    rarity = Column(String, nullable=True)
    set_code = Column(String, nullable=True)
    is_sideboard = Column(Integer, default=0)  # 0 for mainboard, 1 for sideboard
    
    # Relationships
    deck = relationship("DeckModel", back_populates="cards")


class PerformanceModel(Base):
    """SQLAlchemy model for deck performance history."""
    
    __tablename__ = "performances"
    
    id = Column(Integer, primary_key=True, index=True)
    deck_id = Column(Integer, ForeignKey("decks.id"))
    match_date = Column(DateTime, default=datetime.utcnow)
    opponent_archetype = Column(String)
    result = Column(String)  # win, loss, draw
    games_won = Column(Integer)
    games_lost = Column(Integer)
    notes = Column(Text, nullable=True)
    
    # Relationships
    deck = relationship("DeckModel", back_populates="performances")
