"""FastAPI routes for deck analysis."""

from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from ..models.deck import Deck, DeckAnalysis, OptimizedDeck, DeckSuggestion
from ..services.deck_analyzer import DeckAnalyzer
from ..services.smart_sql import SmartSQLService
from ..services.smart_inference import SmartInferenceService
from ..services.smart_memory import SmartMemoryService
from ..services.embeddings import EmbeddingsService
from ..utils.csv_parser import parse_arena_csv, parse_deck_string


router = APIRouter()

# Initialize services
sql_service = SmartSQLService()
analyzer = DeckAnalyzer()
inference_service = SmartInferenceService()
embeddings_service = EmbeddingsService()


class DeckUploadRequest(BaseModel):
    """Request model for deck upload via text."""
    deck_string: str
    format: str = "Standard"


class OptimizationResponse(BaseModel):
    """Response model for deck optimization."""
    analysis: DeckAnalysis
    suggestions: list[DeckSuggestion]
    predicted_win_rate: float
    confidence: float


class PerformanceRecordRequest(BaseModel):
    """Request model for recording match performance."""
    opponent_archetype: str
    result: str  # Must be 'win', 'loss', or 'draw'
    games_won: int
    games_lost: int
    notes: str = ""
    
    class Config:
        json_schema_extra = {
            "example": {
                "opponent_archetype": "Mono-Red Aggro",
                "result": "win",
                "games_won": 2,
                "games_lost": 1,
                "notes": "Good sideboard choices"
            }
        }


@router.post("/upload/csv", response_model=dict)
async def upload_deck_csv(file: UploadFile = File(...)):
    """
    Upload deck via CSV file.
    
    Expected CSV format:
        Quantity,Name,Set,Collector Number,Type,Mana Cost,CMC,Colors,Rarity
    """
    try:
        content = await file.read()
        csv_content = content.decode('utf-8')
        
        # Parse CSV
        deck = parse_arena_csv(csv_content)
        
        # Store in database
        deck_id = await sql_service.store_deck(deck)
        
        return {
            "status": "success",
            "deck_id": deck_id,
            "message": f"Deck '{deck.name}' uploaded successfully"
        }
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error parsing CSV: {str(e)}")


@router.post("/upload/text", response_model=dict)
async def upload_deck_text(request: DeckUploadRequest):
    """
    Upload deck via Arena text format.
    
    Format example:
        4 Lightning Bolt (M11) 146
        2 Counterspell (MH2) 267
    """
    try:
        # Parse deck string
        deck = parse_deck_string(request.deck_string)
        deck.format = request.format
        
        # Store in database
        deck_id = await sql_service.store_deck(deck)
        
        return {
            "status": "success",
            "deck_id": deck_id,
            "message": f"Deck uploaded successfully"
        }
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error parsing deck: {str(e)}")


@router.get("/deck/{deck_id}", response_model=Deck)
async def get_deck(deck_id: int):
    """Get a deck by ID."""
    deck = await sql_service.get_deck(deck_id)
    
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    
    return deck


@router.get("/decks", response_model=list)
async def list_decks(format: Optional[str] = None):
    """List all decks with optional format filter."""
    decks = await sql_service.list_decks(format=format)
    return decks


@router.post("/analyze/{deck_id}", response_model=DeckAnalysis)
async def analyze_deck(deck_id: int):
    """Analyze a deck for strengths, weaknesses, and opportunities."""
    # Get deck from database
    deck = await sql_service.get_deck(deck_id)
    
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    
    # Perform analysis
    analysis = await analyzer.analyze_deck(deck)
    
    return analysis


@router.post("/optimize/{deck_id}", response_model=OptimizationResponse)
async def optimize_deck(deck_id: int):
    """
    Optimize a deck with AI-powered suggestions.
    
    Returns analysis, suggestions, and predicted win rate.
    """
    # Get deck from database
    deck = await sql_service.get_deck(deck_id)
    
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    
    # Perform analysis
    analysis = await analyzer.analyze_deck(deck)
    
    # Generate suggestions
    suggestions = await inference_service.generate_suggestions(deck, analysis)
    
    # Predict win rate
    prediction = await inference_service.predict_win_rate(deck, suggestions)
    
    return OptimizationResponse(
        analysis=analysis,
        suggestions=suggestions,
        predicted_win_rate=prediction.get("predicted_win_rate", 50.0),
        confidence=prediction.get("confidence", 0.5)
    )


@router.get("/stats/{deck_id}", response_model=dict)
async def get_deck_stats(deck_id: int):
    """Get performance statistics for a deck."""
    memory_service = SmartMemoryService(sql_service)
    stats = await memory_service.get_deck_statistics(deck_id)
    insights = await memory_service.get_learning_insights(deck_id)
    
    return {
        **stats,
        "insights": insights
    }


@router.post("/performance/{deck_id}", response_model=dict)
async def record_performance(
    deck_id: int,
    performance: PerformanceRecordRequest
):
    """Record a match performance for a deck."""
    # Validate result value
    valid_results = {"win", "loss", "draw"}
    if performance.result not in valid_results:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid result value. Must be one of: {', '.join(valid_results)}"
        )
    
    # Verify deck exists
    deck = await sql_service.get_deck(deck_id)
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    
    # Record performance
    await sql_service.record_performance(
        deck_id=deck_id,
        opponent_archetype=performance.opponent_archetype,
        result=performance.result,
        games_won=performance.games_won,
        games_lost=performance.games_lost,
        notes=performance.notes
    )
    
    return {
        "status": "success",
        "message": "Performance recorded"
    }


@router.get("/similar/{deck_id}", response_model=dict)
async def find_similar_decks(deck_id: int, limit: int = 5):
    """Find similar decks using embeddings."""
    # Get target deck
    deck = await sql_service.get_deck(deck_id)
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    
    # Get all decks
    all_decks_info = await sql_service.list_decks()
    
    similarities = []
    for deck_info in all_decks_info:
        if deck_info['id'] == deck_id:
            continue
        
        other_deck = await sql_service.get_deck(deck_info['id'])
        if other_deck:
            similarity = embeddings_service.calculate_deck_similarity(
                deck.mainboard, other_deck.mainboard
            )
            similarities.append({
                'deck_id': deck_info['id'],
                'deck_name': deck_info['name'],
                'similarity': similarity
            })
    
    # Sort and limit
    similarities.sort(key=lambda x: x['similarity'], reverse=True)
    
    return {
        "similar_decks": similarities[:limit]
    }


@router.get("/health", response_model=dict)
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Arena Improver API"
    }
