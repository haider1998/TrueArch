import os
from contextlib import asynccontextmanager
from typing import List, Dict, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from src.data.loader import FrameworkLoader
from src.scoring.engine import ScoringEngine
from src.data.models import FrameworkSchema, ComputedScores

# ── Global state ─────────────────────────────────────────────────────────────

_loader: Optional[FrameworkLoader] = None
_engine: Optional[ScoringEngine] = None
frameworks_db: Dict[str, FrameworkSchema] = {}


# ── Lifespan (replaces deprecated @app.on_event("startup")) ──────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load and score all frameworks on startup, clean up on shutdown."""
    global _loader, _engine, frameworks_db

    base_dir = "." if os.path.exists("data/frameworks") else "../.."
    data_dir = os.path.join(base_dir, "data/frameworks")

    _loader = FrameworkLoader(data_dir=data_dir)
    _engine = ScoringEngine()

    try:
        frameworks_db = _loader.load_all()
        for fw in frameworks_db.values():
            fw.computed_scores = _engine.compute_scores(fw)
        print(f"TrueArch: loaded and scored {len(frameworks_db)} frameworks.")
    except Exception as e:
        print(f"TrueArch: startup error — {e}")

    yield  # application runs here

    frameworks_db.clear()
    print("TrueArch: shutdown complete.")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="TrueArch Intelligence API",
    description=(
        "AI-native framework scoring engine. "
        "Every recommendation is explainable, auditable, and time-bounded."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ── Response models ───────────────────────────────────────────────────────────

class FrameworkResponse(BaseModel):
    id: str
    name: str
    category: str
    subcategory: Optional[str] = None
    genome_dimension: str
    overall_score: float
    confidence: float
    score_band: str
    url: str
    docs_url: str


class FrameworkDetailResponse(BaseModel):
    framework: FrameworkSchema
    scores: ComputedScores


# ── Helper ────────────────────────────────────────────────────────────────────

def _to_response(fw: FrameworkSchema) -> FrameworkResponse:
    """Convert a FrameworkSchema into the lightweight list response.
    Guards against unscored frameworks (scores could be None if startup failed).
    """
    scores = fw.computed_scores
    return FrameworkResponse(
        id=fw.id,
        name=fw.name,
        category=fw.category,
        subcategory=fw.subcategory,
        genome_dimension=fw.genome_dimension.value,
        overall_score=scores.overall if scores.overall is not None else 0.0,
        confidence=scores.confidence if scores.confidence is not None else 0.0,
        score_band=scores.score_band if scores.score_band is not None else "Poor",
        url=fw.url,
        docs_url=fw.docs_url,
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["system"])
async def health_check():
    return {
        "status": "ok",
        "frameworks_loaded": len(frameworks_db),
    }


@app.get("/api/v1/frameworks", response_model=List[FrameworkResponse], tags=["frameworks"])
async def list_frameworks(
    category: Optional[str] = Query(None, description="Filter by category (e.g. 'orchestration', 'vector-db')"),
    genome_dimension: Optional[str] = Query(None, description="Filter by genome dimension key (e.g. 'D8_orchestrator')"),
):
    """List all frameworks, optionally filtered by category or genome dimension."""
    results = []
    for fw in frameworks_db.values():
        if category and fw.category != category:
            continue
        if genome_dimension and fw.genome_dimension.key != genome_dimension:
            continue
        results.append(_to_response(fw))

    results.sort(key=lambda x: x.overall_score, reverse=True)
    return results


@app.get("/api/v1/frameworks/{framework_id}", response_model=FrameworkDetailResponse, tags=["frameworks"])
async def get_framework(framework_id: str):
    """Get full details and dimension breakdown for a specific framework."""
    if framework_id not in frameworks_db:
        raise HTTPException(
            status_code=404,
            detail=f"Framework '{framework_id}' not found. "
                   f"Known IDs: {sorted(frameworks_db.keys())}",
        )
    fw = frameworks_db[framework_id]
    return FrameworkDetailResponse(framework=fw, scores=fw.computed_scores)


@app.get("/api/v1/recommendations", response_model=List[FrameworkResponse], tags=["recommendations"])
async def get_recommendations(
    category: str = Query(..., description="The category to get recommendations for"),
):
    """Return the top frameworks for a category, sorted by TrueArch overall score.
    Frameworks scoring below 60 (Fair and below) are excluded unless they are
    the only options in the category.
    """
    candidates = [fw for fw in frameworks_db.values() if fw.category == category]

    if not candidates:
        raise HTTPException(
            status_code=404,
            detail=f"No frameworks found for category '{category}'.",
        )

    # Prefer Good+ (≥60); fall back to all candidates if nothing qualifies
    recommended = [fw for fw in candidates if (fw.computed_scores.overall or 0) >= 60]
    if not recommended:
        recommended = candidates

    results = [_to_response(fw) for fw in recommended]
    results.sort(key=lambda x: x.overall_score, reverse=True)
    return results
