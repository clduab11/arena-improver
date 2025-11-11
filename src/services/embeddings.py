"""Embeddings service for card similarity using Vultr GPU."""

import os
from typing import List, Dict, Optional
import numpy as np
from sentence_transformers import SentenceTransformer

from ..models.deck import Card


class EmbeddingsService:
    """Service for generating and comparing card embeddings."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize embeddings service.
        
        In production, this would connect to Vultr GPU for inference.
        For now, uses local sentence-transformers model.
        """
        self.model_name = model_name
        self.model = None
        self.vultr_api_key = os.getenv("VULTR_API_KEY")
        self._embeddings_cache = {}
    
    def _load_model(self):
        """Lazy load the embeddings model."""
        if self.model is None:
            self.model = SentenceTransformer(self.model_name)
    
    def generate_card_embedding(self, card: Card) -> np.ndarray:
        """Generate embedding vector for a card."""
        # Create card description for embedding
        card_text = self._card_to_text(card)
        
        # Check cache
        if card_text in self._embeddings_cache:
            return self._embeddings_cache[card_text]
        
        # Generate embedding
        self._load_model()
        embedding = self.model.encode(card_text, convert_to_numpy=True)
        
        # Cache result
        self._embeddings_cache[card_text] = embedding
        
        return embedding
    
    def find_similar_cards(
        self, card: Card, candidate_cards: List[Card], top_k: int = 5
    ) -> List[Dict]:
        """Find most similar cards based on embeddings."""
        # Generate embedding for target card
        target_embedding = self.generate_card_embedding(card)
        
        # Generate embeddings for candidates
        similarities = []
        for candidate in candidate_cards:
            if candidate.name == card.name:
                continue  # Skip same card
            
            candidate_embedding = self.generate_card_embedding(candidate)
            similarity = self._cosine_similarity(target_embedding, candidate_embedding)
            
            similarities.append({
                'card': candidate,
                'similarity': float(similarity)
            })
        
        # Sort by similarity and return top k
        similarities.sort(key=lambda x: x['similarity'], reverse=True)
        return similarities[:top_k]
    
    def find_replacement_cards(
        self, card: Card, format_cards: List[Card], top_k: int = 5
    ) -> List[Dict]:
        """
        Find potential replacement cards.
        
        Filters by similar CMC and card type before similarity search.
        """
        # Filter candidates
        candidates = [
            c for c in format_cards
            if c.card_type == card.card_type
            and abs(c.cmc - card.cmc) <= 1  # Similar mana cost
        ]
        
        if not candidates:
            # Fallback to just card type
            candidates = [
                c for c in format_cards
                if c.card_type == card.card_type
            ]
        
        # Find similar cards
        return self.find_similar_cards(card, candidates, top_k)
    
    def calculate_deck_similarity(
        self, deck1: List[Card], deck2: List[Card]
    ) -> float:
        """Calculate overall similarity between two decks."""
        # Generate deck embeddings (average of card embeddings)
        deck1_embeddings = [
            self.generate_card_embedding(card) for card in deck1
        ]
        deck2_embeddings = [
            self.generate_card_embedding(card) for card in deck2
        ]
        
        if not deck1_embeddings or not deck2_embeddings:
            return 0.0
        
        # Average embeddings
        deck1_avg = np.mean(deck1_embeddings, axis=0)
        deck2_avg = np.mean(deck2_embeddings, axis=0)
        
        # Calculate similarity
        similarity = self._cosine_similarity(deck1_avg, deck2_avg)
        
        return float(similarity)
    
    def _card_to_text(self, card: Card) -> str:
        """Convert card to text description for embedding."""
        colors = ' '.join(card.colors) if card.colors else 'Colorless'
        text = f"{card.name} {card.card_type} {colors} CMC {card.cmc} {card.mana_cost}"
        return text
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def get_embedding_stats(self) -> Dict:
        """Get statistics about embeddings cache."""
        return {
            'cached_embeddings': len(self._embeddings_cache),
            'model': self.model_name,
            'vultr_connected': bool(self.vultr_api_key)
        }
