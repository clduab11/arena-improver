"""SmartInference service for AI-powered deck recommendations."""

import os
from typing import List, Optional
import json

from openai import AsyncOpenAI

from ..models.deck import Deck, DeckAnalysis, DeckSuggestion, OptimizedDeck


class SmartInferenceService:
    """Service for AI-powered deck optimization using OpenAI."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.client = AsyncOpenAI(api_key=self.api_key) if self.api_key else None
    
    async def generate_suggestions(
        self, deck: Deck, analysis: DeckAnalysis
    ) -> List[DeckSuggestion]:
        """Generate deck improvement suggestions using AI."""
        if not self.client:
            # Return fallback suggestions if no API key
            return self._fallback_suggestions(deck, analysis)
        
        # Prepare context for AI
        context = self._prepare_context(deck, analysis)
        
        prompt = f"""You are an expert Magic: The Gathering deck builder. 
Analyze this deck and provide specific card suggestions to improve it.

{context}

Provide 5-10 concrete suggestions in the following JSON format:
[
  {{
    "type": "add|remove|replace",
    "card_name": "Card Name",
    "quantity": 1,
    "reason": "Brief explanation",
    "impact_score": 75,
    "replacement_for": "Card to replace (if type is replace)"
  }}
]

Focus on:
1. Improving mana curve
2. Adding synergies
3. Strengthening meta matchups
4. Fixing identified weaknesses
"""
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a Magic: The Gathering expert."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1500
            )
            
            # Parse response
            content = response.choices[0].message.content
            suggestions_data = self._extract_json(content)
            
            suggestions = [
                DeckSuggestion(**item) for item in suggestions_data
            ]
            
            return suggestions
        
        except Exception as e:
            print(f"Error generating suggestions: {e}")
            return self._fallback_suggestions(deck, analysis)
    
    async def predict_win_rate(
        self, deck: Deck, suggestions: List[DeckSuggestion]
    ) -> dict:
        """Predict win rate improvement with suggestions."""
        if not self.client:
            return {"predicted_win_rate": 55.0, "confidence": 0.6}
        
        # Prepare context
        deck_summary = self._deck_summary(deck)
        suggestions_summary = "\n".join([
            f"- {s.type.upper()}: {s.card_name} ({s.reason})"
            for s in suggestions[:5]
        ])
        
        prompt = f"""Based on this MTG Arena deck and proposed changes, predict the expected win rate.

Deck Summary:
{deck_summary}

Proposed Changes:
{suggestions_summary}

Provide your prediction as JSON:
{{
  "predicted_win_rate": 55.5,
  "confidence": 0.75,
  "reasoning": "Brief explanation"
}}
"""
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a Magic: The Gathering meta analyst."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=300
            )
            
            content = response.choices[0].message.content
            prediction = self._extract_json(content)
            
            return prediction
        
        except Exception as e:
            print(f"Error predicting win rate: {e}")
            return {"predicted_win_rate": 52.0, "confidence": 0.5}
    
    def _prepare_context(self, deck: Deck, analysis: DeckAnalysis) -> str:
        """Prepare context string for AI."""
        context = f"""
Deck Name: {deck.name}
Format: {deck.format}

Mana Curve:
- Average CMC: {analysis.mana_curve.average_cmc}
- Distribution: {analysis.mana_curve.distribution}
- Curve Score: {analysis.mana_curve.curve_score}/100

Colors: {', '.join(analysis.color_distribution.keys())}

Card Types:
{', '.join(f"{k}: {v}" for k, v in analysis.card_types.items())}

Strengths:
{chr(10).join(f"- {s}" for s in analysis.strengths)}

Weaknesses:
{chr(10).join(f"- {w}" for w in analysis.weaknesses)}

Overall Score: {analysis.overall_score}/100

Mainboard ({len(deck.mainboard)} unique cards):
{chr(10).join(f"- {card.quantity}x {card.name}" for card in deck.mainboard[:15])}
"""
        return context
    
    def _deck_summary(self, deck: Deck) -> str:
        """Create brief deck summary."""
        total_cards = sum(card.quantity for card in deck.mainboard)
        return f"{deck.name} ({deck.format}) - {total_cards} cards"
    
    def _extract_json(self, content: str) -> dict:
        """Extract JSON from AI response."""
        try:
            # Try to find JSON in the response
            start = content.find('[')
            end = content.rfind(']') + 1
            if start != -1 and end > start:
                json_str = content[start:end]
                return json.loads(json_str)
            
            # Try to parse entire content
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end > start:
                json_str = content[start:end]
                return json.loads(json_str)
            
            return {}
        except json.JSONDecodeError:
            return {}
    
    def _fallback_suggestions(
        self, deck: Deck, analysis: DeckAnalysis
    ) -> List[DeckSuggestion]:
        """Generate fallback suggestions without AI."""
        suggestions = []
        
        # Mana curve suggestions
        if analysis.mana_curve.average_cmc > 3.5:
            suggestions.append(DeckSuggestion(
                type="add",
                card_name="Efficient 2-drop creature",
                quantity=2,
                reason="Lower the average mana curve",
                impact_score=70
            ))
        
        # Color fixing
        num_colors = len(analysis.color_distribution)
        if num_colors >= 3:
            suggestions.append(DeckSuggestion(
                type="add",
                card_name="Dual lands or mana fixing",
                quantity=2,
                reason="Improve mana consistency",
                impact_score=80
            ))
        
        return suggestions
