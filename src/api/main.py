import os
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from src.data.loader import FrameworkLoader
from src.scoring.engine import ScoringEngine
from src.data.models import FrameworkSchema, ComputedScores

app = FastAPI(
    title="TrueArch Intelligence API",
    description="API for accessing TrueArch framework scores and telemetry data.",
    version="1.0.0"
)

# Global state for the prototype
loader = None
engine = None
frameworks_db: Dict[str, FrameworkSchema] = {}

class FrameworkResponse(BaseModel):
    id: str
    name: str
    category: str
    subcategory: str | None
    genome_dimension: str
    overall_score: float
    confidence: float
    score_band: str
    url: str
    docs_url: str

class FrameworkDetailResponse(BaseModel):
    framework: FrameworkSchema
    scores: ComputedScores

@app.on_event("startup")
async def startup_event():
    global loader, engine, frameworks_db
    
    # Path resolution for local vs containerized
    base_dir = "." if os.path.exists("data/frameworks") else "../.."
    data_dir = os.path.join(base_dir, "data/frameworks")
    
    loader = FrameworkLoader(data_dir=data_dir)
    engine = ScoringEngine()
    
    try:
        frameworks_db = loader.load_all()
        # Pre-compute scores to cache them in the models
        for fw_id, fw in frameworks_db.items():
            fw.computed_scores = engine.compute_scores(fw)
        print(f"Loaded and scored {len(frameworks_db)} frameworks successfully.")
    except Exception as e:
        print(f"Failed to load frameworks on startup: {e}")

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "frameworks_loaded": len(frameworks_db)
    }

@app.get("/api/v1/frameworks", response_model=List[FrameworkResponse])
async def list_frameworks(
    category: str = Query(None, description="Filter by category (e.g. 'orchestration', 'vector-db')"),
    genome_dimension: str = Query(None, description="Filter by genome dimension (e.g. 'D8_orchestrator')")
):
    results = []
    for fw in frameworks_db.values():
        if category and fw.category != category:
            continue
        if genome_dimension and fw.genome_dimension.key != genome_dimension:
            continue
            
        results.append(FrameworkResponse(
            id=fw.id,
            name=fw.name,
            category=fw.category,
            subcategory=fw.subcategory,
            genome_dimension=fw.genome_dimension.value,
            overall_score=fw.computed_scores.overall,
            confidence=fw.computed_scores.confidence,
            score_band=fw.computed_scores.score_band,
            url=fw.url,
            docs_url=fw.docs_url
        ))
        
    # Sort by overall score descending
    results.sort(key=lambda x: x.overall_score, reverse=True)
    return results

@app.get("/api/v1/frameworks/{framework_id}", response_model=FrameworkDetailResponse)
async def get_framework(framework_id: str):
    if framework_id not in frameworks_db:
        raise HTTPException(status_code=404, detail="Framework not found")
        
    fw = frameworks_db[framework_id]
    return FrameworkDetailResponse(
        framework=fw,
        scores=fw.computed_scores
    )

@app.get("/api/v1/recommendations", response_model=List[FrameworkResponse])
async def get_recommendations(
    category: str = Query(..., description="The category to get recommendations for")
):
    """Get the top recommended frameworks for a specific category, sorted by TrueArch score."""
    candidates = [fw for fw in frameworks_db.values() if fw.category == category]
    
    if not candidates:
        raise HTTPException(status_code=404, detail=f"No frameworks found for category: {category}")
        
    # Filter out anything with poor score band (optional, but good for recommendations)
    recommended = [fw for fw in candidates if fw.computed_scores.overall >= 60]
    
    if not recommended:
        # Fallback to the best available if all are < 60
        recommended = candidates
        
    results = [
        FrameworkResponse(
            id=fw.id,
            name=fw.name,
            category=fw.category,
            subcategory=fw.subcategory,
            genome_dimension=fw.genome_dimension.value,
            overall_score=fw.computed_scores.overall,
            confidence=fw.computed_scores.confidence,
            score_band=fw.computed_scores.score_band,
            url=fw.url,
            docs_url=fw.docs_url
        ) for fw in recommended
    ]
    
    results.sort(key=lambda x: x.overall_score, reverse=True)
    return results
