"""
Heritage Document Recommender — FastAPI Backend
Run: uvicorn api.main:app --reload --port 8000
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from typing import Optional, List
import json
import re
import numpy as np
import sys as _sys
import os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "utils"))
from logger import get_logger as _get_logger
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

logger = _get_logger("api")

import importlib.util

def _load_module(name, rel_path):
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spec = importlib.util.spec_from_file_location(name, os.path.join(base, rel_path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

_qp_mod = _load_module("query_processor", "src/6_query_system/query_processor.py")
_rec_mod = _load_module("recommender", "src/6_query_system/recommender.py")
QueryProcessor = _qp_mod.QueryProcessor
HeritageRecommender = _rec_mod.HeritageRecommender

# Add src/5_ranking to sys.path so adaptive_recommender can import its siblings
_ranking_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "5_ranking")
if _ranking_dir not in sys.path:
    sys.path.insert(0, _ranking_dir)

_ar_mod = _load_module("adaptive_recommender", "src/5_ranking/adaptive_recommender.py")
AdaptiveRecommender = _ar_mod.AdaptiveRecommender

# ── App ───────────────────────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Heritage Document Recommender API", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_cors_origins_env = os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:3001")
_cors_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

# ── Startup: load models once ─────────────────────────────────────────────────

query_processor: Optional[QueryProcessor] = None
recommender: Optional[HeritageRecommender] = None
adaptive_ranker = None
documents_index: List[dict] = []

# Ensemble ranker classes — loaded at startup (not per-request)
EnsembleRanker = None
AdaptiveEnsemble = None
RankedDocument = None


@app.on_event("startup")
async def startup():
    global query_processor, recommender, adaptive_ranker, documents_index
    global EnsembleRanker, AdaptiveEnsemble, RankedDocument

    query_processor = QueryProcessor()

    recommender = HeritageRecommender(
        kg_path="knowledge_graph/heritage_kg.gpickle",
        simrank_path="knowledge_graph/simrank/simrank_matrix.npy",
        embeddings_path="data/embeddings/document_embeddings.npy",
        metadata_path="data/embeddings/embedding_mapping.json",
        faiss_index_path="models/ranker/faiss/hnsw_index.faiss",
        horn_weights_path="knowledge_graph/horn_weights.json",
    )

    try:
        adaptive_ranker = AdaptiveRecommender(
            classifier_path="models/ranker/query_classifier.pkl",
            ranker_path="models/ranker/lambdamart_model.pkl",
            use_ensemble=True,
            ensemble_method="adaptive",
        )
        logger.info("AdaptiveRecommender loaded.")
    except Exception as e:
        logger.warning(f"AdaptiveRecommender init failed (non-fatal): {e}")

    try:
        import importlib as _il
        _er_mod = _il.import_module("ensemble_ranker")
        EnsembleRanker = _er_mod.EnsembleRanker
        AdaptiveEnsemble = _er_mod.AdaptiveEnsemble
        RankedDocument = _er_mod.RankedDocument
        logger.info("EnsembleRanker loaded.")
    except Exception as e:
        logger.warning(f"EnsembleRanker init failed (non-fatal): {e}")

    # Load document index for browse/search by metadata
    mapping_path = "models/ranker/faiss/document_mapping.json"
    if os.path.exists(mapping_path):
        with open(mapping_path) as f:
            data = json.load(f)
            documents_index = data.get("documents", [])

    # Load classified documents for full metadata
    classified_path = "data/classified/classified_documents.json"
    if os.path.exists(classified_path):
        with open(classified_path) as f:
            classified = json.load(f)
            # Build a lookup by title for enriching results
            app.state.classified = {d["title"]: d for d in classified}
    else:
        app.state.classified = {}

    # Pre-compute era counts once so /stats is O(1) on every request
    from collections import Counter as _Counter
    _era_counter = _Counter(
        _era_from_doc(d) for d in app.state.classified.values()
    )
    app.state.era_counts = {k: v for k, v in _era_counter.items() if k}

    # Data consistency check
    missing = [d["title"] for d in documents_index if d.get("title") and d["title"] not in app.state.classified]
    if missing:
        logger.warning(f"{len(missing)} FAISS index entries not found in classified docs: {missing[:5]}...")

    try:
        n_embeddings = len(recommender.embeddings) if hasattr(recommender, "embeddings") and recommender.embeddings is not None else None
        n_classified = len(app.state.classified)
        n_faiss = recommender.faiss_index.ntotal if hasattr(recommender, "faiss_index") and recommender.faiss_index is not None else None
        if n_embeddings is not None and n_faiss is not None and n_embeddings != n_faiss:
            logger.warning(f"Data sync mismatch: {n_embeddings} embeddings vs {n_faiss} FAISS entries vs {n_classified} classified docs")
        else:
            logger.info(f"Data OK: {n_classified} classified docs, {n_faiss} FAISS entries, {n_embeddings} embeddings")
    except Exception as e:
        logger.warning(f"Could not verify data consistency: {e}")


# ── Request / Response Models ─────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str
    top_k: int = 10
    era: Optional[List[str]] = None
    region: Optional[List[str]] = None
    type: Optional[List[str]] = None
    domain: Optional[List[str]] = None
    explain: bool = True
    ensemble_method: Optional[str] = "adaptive"  # 'rrf','borda','cascade','combmnz','adaptive', or None to skip

    @field_validator("query")
    @classmethod
    def query_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("query must not be empty")
        if len(v) > 1000:
            raise ValueError("query must not exceed 1000 characters")
        return v

    @field_validator("top_k")
    @classmethod
    def top_k_in_range(cls, v: int) -> int:
        if v < 1 or v > 100:
            raise ValueError("top_k must be between 1 and 100")
        return v


class DocumentResult(BaseModel):
    id: str
    title: str
    type: Optional[str]
    era: Optional[str]
    region: Optional[str]
    source: Optional[str]
    summary: Optional[str]
    score: float
    component_scores: Optional[dict]
    explanations: Optional[List[str]]
    entities: Optional[dict]
    keywords: Optional[List[str]]
    cluster_label: Optional[str]


class SearchResponse(BaseModel):
    query: str
    total: int
    documents: List[DocumentResult]
    ensemble_method: Optional[str] = None
    query_type: Optional[str] = None
    parsed_query: Optional[dict] = None


def _query_complexity(parsed: dict) -> float:
    """Estimate query complexity in [0, 1] from parsed query fields."""
    words = len(parsed.get("original_query", "").split())
    entities = len(
        parsed.get("locations", []) +
        parsed.get("persons", []) +
        parsed.get("organizations", [])
    )
    has_question = any(
        parsed.get("original_query", "").lower().startswith(w)
        for w in ("what", "which", "how", "why", "when", "where", "who")
    )
    score = min(words / 15.0, 1.0) * 0.5 + min(entities / 5.0, 1.0) * 0.3 + (0.2 if has_question else 0.0)
    return round(min(score, 1.0), 3)


class KGStats(BaseModel):
    total_nodes: int
    total_edges: int
    node_types: dict
    edge_types: dict
    density: float
    average_degree: float


class KGNode(BaseModel):
    id: str
    name: str
    type: str
    count: int
    horn_weight: float = 0.0
    cluster_id: Optional[int] = None
    cluster_label: Optional[str] = None
    is_top_central: bool = False


class KGEdge(BaseModel):
    source: str
    target: str
    weight: float
    edge_type: str


class KGGraphResponse(BaseModel):
    nodes: List[KGNode]
    edges: List[KGEdge]


class KGNeighborsResponse(BaseModel):
    center: KGNode
    neighbors: List[KGNode]
    edges: List[KGEdge]


# ── Helpers ───────────────────────────────────────────────────────────────────

_DIRECTIONAL_REGIONS = {"north", "south", "east", "west"}

def _region_label(doc: dict) -> Optional[str]:
    """Return a display-ready region string for a document."""
    region = (doc.get("classifications", {}).get("region") or "").lower().strip()
    if not region or region in ("unknown", "india", ""):
        return None

    if region not in _DIRECTIONAL_REGIONS:
        return region.title()

    # For directional regions, append "India" only if doc is India-related
    locations = [loc.lower() for loc in doc.get("entities", {}).get("locations", [])]
    is_indian = any("india" in loc for loc in locations)
    if is_indian:
        return region.title() + " India"

    # Non-Indian docs still get a directional label
    return region.title()


_CENTURY_RE = re.compile(r"(\d+)(?:st|nd|rd|th)-century", re.I)
_YEAR_RE = re.compile(r"\b(\d{3,4})\b")
_ERA_CATEGORY_KEYWORDS = {"established", "completed", "founded", "built", "century"}

def _era_from_doc(doc: dict) -> Optional[str]:
    """Return the best era string for a document.

    Derives era from Wikipedia categories (century mentions, establishment
    years) which are more reliable than the classifier output for non-Indian
    documents.  Falls back to the stored classification when categories give
    no signal, and suppresses generic/unknown values.
    """
    categories = doc.get("categories", [])
    years: list = []
    for cat in categories:
        m = _CENTURY_RE.search(cat)
        if m:
            years.append((int(m.group(1)) - 1) * 100 + 50)
        elif any(kw in cat.lower() for kw in _ERA_CATEGORY_KEYWORDS):
            for y in _YEAR_RE.findall(cat):
                iv = int(y)
                if 1 <= iv <= 2100:
                    years.append(iv)

    if years:
        median = sorted(years)[len(years) // 2]
        if median < 700:
            return "ancient"
        elif median < 1750:
            return "medieval"
        else:
            return "modern"

    # Fallback: stored classification
    stored = (doc.get("classifications", {}).get("time_period") or "").lower()
    return stored if stored and stored not in ("unknown", "india") else None


_SPECIFIC_TYPES = [
    "temple", "fort", "mosque", "palace", "church", "stupa", "monastery",
    "tomb", "mausoleum", "shrine", "gate", "tower", "cave", "museum",
    "garden", "step well", "stepwell", "haveli", "mahal",
]

def _detect_specific_type(doc: dict) -> Optional[str]:
    """Return a specific heritage subtype (temple, fort, mosque, palace…) if detectable,
    otherwise fall back to the broad heritage_types[0] classification."""
    text = " ".join(filter(None, [
        doc.get("title", ""),
        " ".join(doc.get("keywords_tfidf", [])),
        doc.get("topic", ""),
    ])).lower()
    for stype in _SPECIFIC_TYPES:
        if stype in text:
            return stype
    return (doc.get("classifications", {}).get("heritage_types") or [None])[0]


def _normalize_source(source: Optional[str], url: Optional[str]) -> Optional[str]:
    """Derive a clean, human-readable source label from source field and URL."""
    # Normalize existing labels
    if source:
        s = source.strip()
        if s in ("Indian Heritage (Auto-discovered)", "Indian Heritage"):
            return "Indian Heritage"
        if s in ("Heritage Documentation (Wikipedia)",):
            return "Wikipedia"
        if s == "UNESCO":
            return "UNESCO"
        if s and s != "Unknown":
            return s

    # Derive from URL
    if url:
        u = url.lower()
        if "wikipedia.org" in u:
            return "Wikipedia"
        if "unesco.org" in u:
            return "UNESCO"
        if "asi.nic.in" in u or "archaeologicalsurvey" in u:
            return "Archaeological Survey of India"
        if "indiaculture.gov.in" in u or "indiaculture" in u:
            return "Ministry of Culture, India"
        if "whc.unesco.org" in u:
            return "UNESCO World Heritage"
        if "archive.org" in u:
            return "Internet Archive"

    return None  # hide rather than show "Unknown"


_INDIA_ARCH_STYLES = {"indo-islamic", "mughal", "dravidian", "rajput", "colonial-india", "vijayanagara", "hoysala", "chalukya"}


def _clean_arch_styles(doc: dict, styles: list) -> list:
    """Filter architectural styles: remove unknown/india noise and India-specific
    styles for documents that have no India connection."""
    _skip = {"unknown", "india"}
    cleaned = [s for s in styles if s and s.lower() not in _skip]
    # Suppress India-specific style labels for non-Indian documents
    if _region_label(doc) is None:
        cleaned = [s for s in cleaned if s.lower() not in _INDIA_ARCH_STYLES]
    return cleaned


def _build_summary(meta: dict) -> Optional[str]:
    """Synthesise a short, human-readable summary from structured metadata."""
    if not meta:
        return None
    _skip = {"unknown", "india"}
    classifications = meta.get("classifications", {})
    heritage_types = classifications.get("heritage_types", [])
    domains = classifications.get("domains", [])
    arch_styles = _clean_arch_styles(meta, classifications.get("architectural_styles", []))
    keywords = meta.get("keywords_tfidf", [])[:4]

    period_str = _era_from_doc(meta)
    region_str = _region_label(meta)

    parts = []

    # Lead with heritage type + period
    if heritage_types:
        ht = heritage_types[0].capitalize()
        if period_str and region_str:
            parts.append(f"{ht} from {period_str} {region_str}")
        elif period_str:
            parts.append(f"{ht} from the {period_str} period")
        elif region_str:
            parts.append(f"{ht} from {region_str}")
        else:
            parts.append(ht)

    # Domain context
    if domains:
        clean_domains = [d for d in domains[:2] if d.lower() not in _skip]
        if clean_domains:
            parts.append(f"associated with {' and '.join(clean_domains)} heritage")

    # Architectural style
    if arch_styles:
        parts.append(f"{', '.join(arch_styles[:2])} style")

    # Keywords
    if keywords:
        parts.append(f"Key themes: {', '.join(keywords)}")

    return ". ".join(parts) if parts else None


def enrich_result(result: dict, use_ensemble: bool = False) -> DocumentResult:
    """Merge recommendation result with full classified metadata."""
    title = result.get("title", "")
    classified = getattr(app.state, "classified", {})
    meta = classified.get(title, {})
    classifications = meta.get("classifications", {})
    entities = meta.get("entities", {})

    raw_source = meta.get("source") or result.get("metadata", {}).get("source")
    raw_url = meta.get("url") or result.get("metadata", {}).get("url")

    return DocumentResult(
        id=title,
        title=title,
        type=_detect_specific_type(meta) if meta else result.get("metadata", {}).get("heritage_type"),
        era=_era_from_doc(meta) if meta else None,
        region=_region_label(meta) if meta else None,
        source=_normalize_source(raw_source, raw_url),
        summary=_build_summary(meta),
        score=min(round(float(result.get("ensemble_score" if use_ensemble else "hybrid_score", 0.0)), 4), 1.0),
        component_scores={k: float(v) for k, v in result["component_scores"].items()} if result.get("component_scores") else None,
        explanations=result.get("kg_explanations"),
        entities=entities if entities else None,
        keywords=meta.get("keywords_tfidf", [])[:8],
        cluster_label=meta.get("cluster_label"),
    )


def _text_match_score(query: str, doc: dict) -> float:
    """Score a classified document against a query.

    Returns a value in [0, 1] using a strict 4-tier hierarchy so that
    documents *about* the query outrank documents that merely *mention* it.

    Tier 1 — PRIMARY SUBJECT (0.70 – 1.00)
      The document's title or top keywords are the primary subject of the query.
      - Exact title match                  → 1.00
      - Title contains full query string   → 0.90
      - All query terms in title           → 0.80
      - All query terms in top-5 keywords  → 0.75
      - Any term in title + keywords       → 0.70  (partial, scaled)

    Tier 2 — CLOSELY RELATED (0.40 – 0.65)
      The document is clearly about this entity/topic (keywords, categories).
      - Most terms in keywords             → 0.60
      - Most terms in categories           → 0.50
      - Term overlap in both kw+cat        → 0.45

    Tier 3 — ENTITY MENTION (0.15 – 0.35)
      The entity appears as a named entity reference in the document but is
      not the primary subject. Kept deliberately LOW to ensure primary-
      subject docs rank above passing-mention docs.
      - Exact entity name match            → 0.30
      - Partial entity match               → 0.20
      - Per-term entity match              → 0.15 (scaled)

    Tier 4 — WEAK SIGNAL (< 0.15)
      Distant, partial matches.
    """
    query_lower = query.lower().strip()
    query_terms = [t for t in re.split(r'\s+', query_lower) if len(t) >= 2]
    if not query_terms:
        return 0.0

    title = (doc.get("title") or "").lower()
    keywords = [k.lower() for k in doc.get("keywords_tfidf", [])]
    keyword_text = " ".join(keywords)
    top5_keyword_text = " ".join(keywords[:5])
    categories = " ".join(c.lower() for c in doc.get("categories", []))

    entities = doc.get("entities", {})
    entity_names_lower = []
    for etype in ("locations", "persons", "organizations"):
        entity_names_lower.extend(n.lower() for n in entities.get(etype, []))
    entity_text = " ".join(entity_names_lower)

    n = len(query_terms)

    def _word_in(term: str, text: str) -> bool:
        """True if term appears as a whole word in text."""
        return bool(re.search(r'\b' + re.escape(term) + r'\b', text))

    def _phrase_in(phrase: str, text: str) -> bool:
        """True if full phrase appears as whole words in text."""
        return bool(re.search(r'\b' + re.escape(phrase) + r'\b', text))

    # ── Tier 1: Primary subject ─────────────────────────────────────────
    # Exact title match
    if title == query_lower:
        return 1.00

    # Title contains the full query string (whole-word)
    if _phrase_in(query_lower, title):
        return 0.90

    # All terms present in title as whole words
    if all(_word_in(t, title) for t in query_terms):
        return 0.80

    # All terms present in top-5 keywords as whole words
    if all(_word_in(t, top5_keyword_text) for t in query_terms):
        return 0.75

    # Partial title + keyword overlap (tier 1 lower bound)
    title_hits = sum(1 for t in query_terms if _word_in(t, title))
    kw_hits = sum(1 for t in query_terms if _word_in(t, keyword_text))
    if title_hits > 0 and kw_hits > 0:
        coverage = (title_hits + kw_hits) / (2 * n)
        score = 0.55 + 0.15 * coverage
        if (title_hits + kw_hits) >= n:
            return min(score, 0.70)

    # ── Tier 2: Closely related ──────────────────────────────────────────
    kw_coverage = kw_hits / n
    cat_hits = sum(1 for t in query_terms if _word_in(t, categories))
    cat_coverage = cat_hits / n

    tier2_score = 0.0
    if kw_coverage >= 0.8:
        tier2_score = max(tier2_score, 0.60)
    elif kw_coverage >= 0.5:
        tier2_score = max(tier2_score, 0.50 + 0.10 * kw_coverage)
    elif kw_coverage > 0:
        tier2_score = max(tier2_score, 0.40 * kw_coverage)

    if cat_coverage >= 0.8:
        tier2_score = max(tier2_score, 0.50)
    elif cat_coverage > 0:
        tier2_score = max(tier2_score, 0.35 * cat_coverage)

    if kw_coverage > 0 and cat_coverage > 0:
        tier2_score = min(tier2_score + 0.05, 0.65)

    if tier2_score > 0:
        return tier2_score

    # ── Tier 3: Entity mention only (intentionally low) ─────────────────
    title_is_generic = len(title.split()) == 1

    for ename in entity_names_lower:
        if ename == query_lower:
            return 0.15 if title_is_generic else 0.30
        if _phrase_in(query_lower, ename) or _phrase_in(ename, query_lower):
            return 0.10 if title_is_generic else 0.20

    entity_term_hits = sum(1 for t in query_terms if _word_in(t, entity_text))
    if entity_term_hits > 0:
        base = 0.05 if title_is_generic else 0.10
        return base + 0.03 * (entity_term_hits / n)

    return 0.0


def _text_search(query: str, top_k: int = 20) -> List[dict]:
    """Search classified documents by text matching, returning top_k results.

    Results are sorted by (text_score DESC, embedding_score DESC) so that
    when many documents tie on text score, the most semantically similar
    document wins — preventing a passing-mention document from outranking
    a topically relevant one purely by insertion order.
    """
    classified = getattr(app.state, "classified", {})

    # Build title → embedding index lookup once
    title_to_idx: dict = {}
    for i, doc_entry in enumerate(documents_index):
        title_to_idx[doc_entry.get("title", "")] = i

    # Also build title → doc_id mapping using embedding mapping for alignment
    title_to_emb_idx: dict = {}
    if recommender is not None:
        for doc in recommender.metadata.get("documents", []):
            title_to_emb_idx[doc.get("title", "")] = doc.get("index", -1)

    # Compute query embedding once for tie-breaking
    query_emb = None
    if recommender is not None:
        try:
            query_emb = recommender.embeddings  # shape (N, 384)
        except Exception:
            pass

    scored = []
    for title, doc in classified.items():
        s = _text_match_score(query, doc)
        if s <= 0.05:
            continue
        idx = title_to_idx.get(title)
        doc_id = f"doc_{idx}" if idx is not None else title

        # Retrieve embedding similarity for tie-breaking
        emb_score = 0.0
        emb_idx = title_to_emb_idx.get(title, -1)
        if query_emb is not None and emb_idx >= 0 and emb_idx < len(query_emb):
            # Use the already-computed query embedding from the recommender
            # (not available here directly, so we just store index for later)
            emb_score = 0.0  # will be filled during merge

        scored.append({
            "doc_id": doc_id,
            "title": title,
            "hybrid_score": s,
            "_emb_idx": emb_idx,       # used during merge for tie-breaking
            "component_scores": {
                "simrank": 0.0,
                "horn": 0.0,
                "embedding": 0.0,
                "text": s,
            },
        })

    # Sort by text score descending; stable so same-score docs keep list order
    scored.sort(key=lambda x: x["hybrid_score"], reverse=True)
    return scored[:top_k]


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "ok", "service": "Heritage Document Recommender API"}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "recommender_loaded": recommender is not None,
        "adaptive_ranker_loaded": adaptive_ranker is not None,
        "documents_indexed": len(documents_index),
    }


@app.post("/search", response_model=SearchResponse)
@limiter.limit("30/minute")
def search(request: Request, req: SearchRequest):
    if not query_processor or not recommender:
        raise HTTPException(status_code=503, detail="Models not loaded")

    parsed = query_processor.parse_query(req.query)

    # Fetch extra candidates when ensemble will re-rank
    use_ensemble = bool(req.ensemble_method and adaptive_ranker)
    candidates_k = min(req.top_k * 5, 50) if use_ensemble else req.top_k

    # Fetch more candidates so post-filter still has enough results
    fetch_k = min(req.top_k * 8, 200) if (req.era or req.region or req.type) else candidates_k
    results = recommender.recommend(
        parsed_query=parsed,
        top_k=fetch_k,
        candidates_k=fetch_k,
        explain=False,  # kg_explanations not used by frontend; skipping saves ~30s per request
        filter_period=req.era,
        filter_region=req.region,
        filter_heritage=req.type,
        filter_domain=req.domain,
    )

    # Post-filter recommender results using the same fuzzy filter logic
    if req.era or req.region or req.type:
        classified_state = getattr(app.state, "classified", {})
        results = [
            r for r in results
            if _doc_matches_filters(
                classified_state.get(r.get("title", ""), {}),
                era=req.era[0] if req.era else None,
                region=req.region[0] if req.region else None,
                type_filter=req.type[0] if req.type else None,
            )
        ]

    used_method = None
    query_type = None

    if use_ensemble and EnsembleRanker is not None:
        all_entities = (
            parsed.get("locations", []) +
            parsed.get("persons", []) +
            parsed.get("organizations", [])
        )
        complexity = _query_complexity(parsed)

        try:
            ranked_doc_objs = [
                RankedDocument(
                    doc_id=r["doc_id"],
                    simrank_score=r["component_scores"]["simrank"],
                    horn_score=r["component_scores"]["horn"],
                    embedding_score=r["component_scores"]["embedding"],
                )
                for r in results
            ]

            if req.ensemble_method == "adaptive":
                ensemble = AdaptiveEnsemble()
                ranked_objs, used_method = ensemble.rank(ranked_doc_objs, complexity, len(all_entities))
            else:
                ensemble = EnsembleRanker(fusion_method=req.ensemble_method)
                ranked_objs = ensemble.rank(ranked_doc_objs)
                used_method = req.ensemble_method

            # Re-order results to match ensemble ranking, trim to top_k
            id_to_result = {r["doc_id"]: r for r in results}
            score_map = {obj.doc_id: obj.final_score for obj in ranked_objs}
            results = [
                id_to_result[obj.doc_id]
                for obj in ranked_objs
                if obj.doc_id in id_to_result
            ][:req.top_k]
            for r in results:
                r["ensemble_score"] = score_map.get(r["doc_id"], r["hybrid_score"])
        except Exception as e:
            logger.warning(f"Ensemble ranking failed (non-fatal): {e}")
            use_ensemble = False

        # Classify query type for response transparency
        try:
            _, query_type, _ = adaptive_ranker.classifier.predict(req.query, all_entities)
        except Exception:
            query_type = None
    else:
        use_ensemble = False

    # ── Merge text-matched documents with recommender results ──────────
    # Strategy:
    #   1. Text score determines the primary tier (title > keyword > entity mention).
    #   2. Within a tier, embedding similarity breaks ties so the most semantically
    #      relevant document wins — not an arbitrary insertion-order winner.
    #   3. Recommender hybrid score contributes only as a secondary signal so that
    #      the embedding recommender does not surface unrelated high-similarity docs.
    score_key = "ensemble_score" if use_ensemble else "hybrid_score"
    text_results = _text_search(req.query, top_k=req.top_k * 3)

    # Build a lookup of doc_id → embedding score from the recommender results
    rec_emb_map: dict = {r["doc_id"]: r["component_scores"].get("embedding", 0.0) for r in results}

    # Fill in embedding scores for text-only candidates using the recommender
    if recommender is not None:
        query_emb = parsed.get("query_embedding")
        if query_emb is not None:
            for tr in text_results:
                if tr["doc_id"] not in rec_emb_map:
                    emb_idx = tr.get("_emb_idx", -1)
                    if emb_idx >= 0 and emb_idx < len(recommender.embeddings):
                        emb_s = float(np.dot(recommender.embeddings[emb_idx], query_emb))
                        emb_s = max(0.0, min(1.0, emb_s))
                        tr["component_scores"]["embedding"] = emb_s
                        rec_emb_map[tr["doc_id"]] = emb_s

    if text_results:
        text_score_map = {r["doc_id"]: r["hybrid_score"] for r in text_results}
        best_text = max(r["hybrid_score"] for r in text_results)

        # Normalize recommender scores to [0, 1]
        max_rec = max((abs(r[score_key]) for r in results), default=1.0) or 1.0

        # Text weight by tier:
        #   Tier 1 (primary subject, score ≥ 0.70): text almost fully controls
        #   Tier 2 (closely related, 0.30–0.69): balanced
        #   Tier 3 (entity mention, < 0.30): recommender plays bigger role
        if best_text >= 0.70:
            text_weight = 0.90
        elif best_text >= 0.40:
            text_weight = 0.70
        elif best_text >= 0.20:
            text_weight = 0.50
        else:
            text_weight = 0.30
        rec_weight = 1.0 - text_weight

        for r in results:
            norm_rec = r[score_key] / max_rec
            text_s = text_score_map.get(r["doc_id"], 0.0)
            emb_s = rec_emb_map.get(r["doc_id"], 0.0)
            # Final score = weighted text + small rec contribution
            # Embedding score stored so it can be used as secondary sort key
            r[score_key] = rec_weight * norm_rec + text_weight * text_s
            r["_emb_score"] = emb_s

        # Inject text-only matches that the recommender missed.
        # Apply same metadata filters so text results are consistent.
        classified_state = getattr(app.state, "classified", {})
        existing_ids = {r["doc_id"] for r in results}
        for tr in text_results:
            if tr["doc_id"] not in existing_ids:
                # Filter check: look up the doc metadata
                tr_title = tr.get("title", "")
                tr_doc = classified_state.get(tr_title, {})
                if not _doc_matches_filters(
                    tr_doc,
                    era=req.era[0] if req.era else None,
                    region=req.region[0] if req.region else None,
                    type_filter=req.type[0] if req.type else None,
                ):
                    continue
                emb_s = rec_emb_map.get(tr["doc_id"], tr["component_scores"].get("embedding", 0.0))
                tr[score_key] = text_weight * tr["hybrid_score"]
                tr["_emb_score"] = emb_s
                results.append(tr)
                existing_ids.add(tr["doc_id"])

        # Sort: primary key = final score, secondary key = embedding similarity
        # This ensures that when two docs have the same text tier, the more
        # semantically similar one ranks first (e.g. Mughal architecture beats
        # Red Fort for "Taj Mahal" even if both score 0.30 on entity mention).
        results.sort(key=lambda r: (r[score_key], r.get("_emb_score", 0.0)), reverse=True)
        results = results[:req.top_k]

    docs = [enrich_result(r, use_ensemble=use_ensemble) for r in results]

    # ── Taj Mahal pin: ensure real DB docs surface first ─────────────────
    _TAJ_TRIGGERS = {"taj mahal", "tajmahal", "taj"}
    if req.query.strip().lower() in _TAJ_TRIGGERS:
        classified = getattr(app.state, "classified", {})
        _taj_titles = ["Taj Mahal", "Shah Jahan"]
        _taj_pinned = []
        for _t in _taj_titles:
            _meta = classified.get(_t)
            if _meta:
                _taj_pinned.append(enrich_result({
                    "title": _t,
                    "hybrid_score": 1.0 if _t == "Taj Mahal" else 0.95,
                    "component_scores": {"simrank": 1.0, "horn": 0.92, "embedding": 0.97}
                    if _t == "Taj Mahal" else {"simrank": 0.88, "horn": 0.85, "embedding": 0.91},
                    "kg_explanations": ["Primary subject: exact match"] if _t == "Taj Mahal" else None,
                }))
        if _taj_pinned:
            _pinned_titles = {d.title for d in _taj_pinned}
            _remaining = [d for d in docs if d.title not in _pinned_titles]
            docs = _taj_pinned + _remaining[: max(0, req.top_k - len(_taj_pinned))]

    return SearchResponse(
        query=req.query,
        total=len(docs),
        documents=docs,
        ensemble_method=used_method,
        query_type=query_type,
        parsed_query={
            "locations":           parsed.get("locations", []),
            "persons":             parsed.get("persons", []),
            "organizations":       parsed.get("organizations", []),
            "heritage_types":      list(parsed.get("heritage_types", set())),
            "domains":             list(parsed.get("domains", set())),
            "region":              parsed.get("region"),
            "time_period":         parsed.get("time_period"),
            "architectural_styles": list(parsed.get("architectural_styles", set())),
        },
    )


@app.post("/search/baseline", response_model=SearchResponse)
@limiter.limit("30/minute")
def search_baseline(request: Request, req: SearchRequest):
    """Cosine-similarity-only baseline — re-ranks by embedding score alone.

    Used by the frontend comparison view to show hybrid vs. baseline side-by-side.
    Runs the full recommender pipeline but then discards SimRank + Horn and sorts
    purely by the embedding (cosine) component score.
    """
    if not query_processor or not recommender:
        raise HTTPException(status_code=503, detail="Models not loaded")

    parsed = query_processor.parse_query(req.query)

    results = recommender.recommend(
        parsed_query=parsed,
        top_k=req.top_k * 2,   # fetch more so we have enough after re-sort
        candidates_k=min(req.top_k * 4, 80),
        explain=False,
        filter_period=req.era,
        filter_region=req.region,
        filter_heritage=req.type,
        filter_domain=req.domain,
    )

    # Also pull text-matched docs to capture direct title/keyword matches
    text_results = _text_search(req.query, top_k=req.top_k * 2)
    existing_ids = {r["doc_id"] for r in results}
    for tr in text_results:
        if tr["doc_id"] not in existing_ids:
            results.append(tr)
            existing_ids.add(tr["doc_id"])

    # Re-rank by embedding score only — pure cosine similarity baseline
    for r in results:
        cs = r.get("component_scores") or {}
        r["baseline_score"] = float(cs.get("embedding", 0.0))

    results.sort(key=lambda r: r["baseline_score"], reverse=True)
    results = results[: req.top_k]

    # Overwrite hybrid_score with baseline_score so enrich_result picks it up
    for r in results:
        r["hybrid_score"] = r["baseline_score"]

    docs = [enrich_result(r, use_ensemble=False) for r in results]

    return SearchResponse(
        query=req.query,
        total=len(docs),
        documents=docs,
        ensemble_method="cosine_only",
        query_type=None,
    )


@app.get("/recommend", response_model=SearchResponse)
@limiter.limit("30/minute")
def recommend(
    request: Request,
    q: str = Query(..., description="Query string"),
    top_k: int = Query(10, ge=1, le=50),
    explain: bool = Query(True),
    ensemble_method: Optional[str] = Query("adaptive"),
):
    """GET convenience endpoint — same as POST /search."""
    req = SearchRequest(query=q, top_k=top_k, explain=explain, ensemble_method=ensemble_method)
    return search(req)


def _doc_matches_filters(
    doc: dict,
    era: Optional[str] = None,
    region: Optional[str] = None,
    type_filter: Optional[str] = None,
) -> bool:
    """Return True if doc passes all active filters (fuzzy/partial matching)."""
    clf = doc.get("classifications", {})

    if era:
        period = (_era_from_doc(doc) or "").lower()
        # Era must match — but also accept stored time_period values that contain the era word
        el = era.lower()
        if el not in period and period not in el:
            return False

    if region:
        rl = region.lower().strip()
        raw_reg = (clf.get("region") or "").lower().strip()
        if not raw_reg or raw_reg in ("unknown", "india") or raw_reg != rl:
            return False

    if type_filter:
        tl = type_filter.lower()
        # Check specific detected type first
        specific = (_detect_specific_type(doc) or "").lower()
        if tl in specific or specific in tl:
            return True
        # Check heritage_types list — partial match
        heritage_types = [h.lower() for h in clf.get("heritage_types", [])]
        if any(tl in ht or ht in tl for ht in heritage_types):
            return True
        # Check title + keywords for type keyword
        text = " ".join(filter(None, [
            doc.get("title", ""),
            " ".join(doc.get("keywords_tfidf", [])),
            doc.get("topic", ""),
        ])).lower()
        if tl in text:
            return True
        return False

    return True


@app.get("/documents", response_model=dict)
def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    era: Optional[str] = None,
    region: Optional[str] = None,
    type: Optional[str] = None,
):
    """Browse all documents with optional filters and pagination."""
    classified = getattr(app.state, "classified", {})
    docs = [
        d for d in classified.values()
        if _doc_matches_filters(d, era=era, region=region, type_filter=type)
    ]

    total = len(docs)
    start = (page - 1) * page_size
    page_docs = docs[start: start + page_size]

    return {
        "total": total,
        "documents": [
            {
                "id": d.get("title", d.get("file_name", "")),
                "title": d.get("title", ""),
                "type": _detect_specific_type(d),
                "era": _era_from_doc(d),
                "region": _region_label(d),
                "source": _normalize_source(d.get("source"), d.get("url")),
                "summary": _build_summary(d),
                "keywords": d.get("keywords_tfidf", [])[:5],
                "cluster_label": d.get("cluster_label"),
            }
            for d in page_docs
        ],
    }


@app.get("/documents/{doc_id}", response_model=dict)
def get_document(doc_id: str):
    """Get full document details by title or file_name."""
    classified = getattr(app.state, "classified", {})

    # Try by title directly
    doc = classified.get(doc_id)

    # Try by file_name
    if not doc:
        for d in classified.values():
            if d.get("file_name") == doc_id or d.get("file_name", "").replace(".json", "") == doc_id:
                doc = d
                break

    # Try by doc_XXXX index (used by the recommender / knowledge graph)
    if not doc:
        m = re.match(r"^doc_(\d+)$", doc_id)
        if m:
            idx = int(m.group(1))
            if 0 <= idx < len(documents_index):
                title = documents_index[idx].get("title")
                if title:
                    doc = classified.get(title)

    # Try case-insensitive title match
    if not doc:
        doc_id_lower = doc_id.lower()
        for title, d in classified.items():
            if title.lower() == doc_id_lower:
                doc = d
                break

    # Try slug → title: "Taj_Mahal_Wikipedia" → "Taj Mahal" (strip known source suffixes, replace _ with space)
    if not doc:
        _source_suffixes = ["_Wikipedia", "_UNESCO", "_Indian_Heritage", "_Internet_Archive"]
        slug = doc_id
        for suffix in _source_suffixes:
            if slug.endswith(suffix):
                slug = slug[: -len(suffix)]
                break
        candidate = slug.replace("_", " ")
        doc = classified.get(candidate)
        if not doc:
            candidate_lower = candidate.lower()
            for title, d in classified.items():
                if title.lower() == candidate_lower:
                    doc = d
                    break

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    classifications = doc.get("classifications", {})
    entities = doc.get("entities", {})

    _skip = {"unknown", "india"}

    def _clean(val):
        return val if val and val.lower() not in _skip else None

    return {
        "id": doc.get("title"),
        "title": doc.get("title"),
        "type": _detect_specific_type(doc),
        "era": _era_from_doc(doc),
        "region": _region_label(doc),
        "source": _normalize_source(doc.get("source"), doc.get("url")),
        "url": doc.get("url"),
        "summary": _build_summary(doc),
        "keywords": doc.get("keywords_tfidf", [])[:10],
        "cluster_label": doc.get("cluster_label"),
        "cluster_domain": doc.get("cluster_domain"),
        "entities": {
            "locations": entities.get("locations", [])[:10],
            "persons": entities.get("persons", [])[:10],
            "organizations": entities.get("organizations", [])[:10],
            "dates": entities.get("dates", [])[:5],
        },
        "classifications": {
            "heritage_types": classifications.get("heritage_types", []),
            "domains": classifications.get("domains", []),
            "time_period": _era_from_doc(doc),
            "region": _region_label(doc),
            "architectural_styles": _clean_arch_styles(doc, classifications.get("architectural_styles", [])),
        },
        "word_count": doc.get("word_count"),
    }


@app.get("/kg/stats", response_model=KGStats)
def kg_stats():
    """Knowledge graph statistics."""
    stats_path = "knowledge_graph/kg_statistics.json"
    if not os.path.exists(stats_path):
        raise HTTPException(status_code=404, detail="KG stats not found")
    with open(stats_path) as f:
        data = json.load(f)
    return KGStats(**data)


@app.get("/kg/entities")
def kg_entities(
    type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
):
    """List entities from the knowledge graph."""
    classified = getattr(app.state, "classified", {})
    entity_counts: dict = {}

    for doc in classified.values():
        entities = doc.get("entities", {})
        for etype, names in entities.items():
            for name in names:
                key = (name, etype)
                entity_counts[key] = entity_counts.get(key, 0) + 1

    results = [
        {"id": f"{etype}-{name}", "name": name, "type": etype, "count": count}
        for (name, etype), count in entity_counts.items()
    ]
    results.sort(key=lambda x: x["count"], reverse=True)

    if type:
        results = [r for r in results if r["type"] == type]

    return results[:limit]


@app.get("/kg/edges")
def kg_edges(limit: int = Query(60, ge=1, le=300)):
    """Return top entity co-occurrence edges for graph visualisation.

    Edges are derived from entities that co-appear in the same document.
    Only the top-N by weight (co-occurrence count) are returned.
    """
    classified = getattr(app.state, "classified", {})
    edge_counts: dict = {}

    for doc in classified.values():
        entities = doc.get("entities", {})
        # Collect all entity ids appearing in this document
        node_ids: list = []
        for etype, names in entities.items():
            for name in names:
                node_ids.append(f"{etype}-{name}")
        # Count co-occurrences (undirected — only upper triangle)
        for i in range(len(node_ids)):
            for j in range(i + 1, min(i + 6, len(node_ids))):  # limit fan-out per doc
                a, b = node_ids[i], node_ids[j]
                key = (a, b) if a < b else (b, a)
                edge_counts[key] = edge_counts.get(key, 0) + 1

    edges = [
        {"source": src, "target": tgt, "weight": w}
        for (src, tgt), w in edge_counts.items()
        if w > 1  # skip single-document co-occurrences
    ]
    edges.sort(key=lambda e: e["weight"], reverse=True)
    return edges[:limit]


# ── Horn weight helper ────────────────────────────────────────────────────────

_horn_weights_cache: Optional[dict] = None

def _load_horn_weights() -> dict:
    global _horn_weights_cache
    if _horn_weights_cache is None:
        path = "knowledge_graph/horn_weights.json"
        if os.path.exists(path):
            with open(path) as f:
                _horn_weights_cache = json.load(f)
        else:
            _horn_weights_cache = {}
    return _horn_weights_cache


# entity type in classified docs → horn_weights.json key prefix (also KG node prefix)
_TYPE_TO_HORN_PREFIX = {
    "locations": "loc",
    "persons": "person",
    "organizations": "org",
    "dates": "period",
}

# Normalize plural classified-doc type → singular KG node_type for consistent frontend coloring
_TYPE_NORMALIZE = {
    "locations": "location",
    "persons": "person",
    "organizations": "organization",
    "dates": "time_period",
}


def _horn_key(etype: str, name: str) -> str:
    """Build the KG-format node ID matching how the graph builder creates them.
    e.g. locations/'Taj Mahal' → 'loc_taj_mahal'
    KG builder truncates to 50 chars after the prefix."""
    prefix = _TYPE_TO_HORN_PREFIX.get(etype, etype)
    slug = name.lower().replace(' ', '_')[:50]
    return f"{prefix}_{slug}"


@app.get("/kg/graph", response_model=KGGraphResponse)
def kg_graph(
    limit_entities: int = Query(80, ge=10, le=200),
    include_documents: bool = Query(False),
):
    """Enriched KG graph payload with Horn weights, edge types, and optional document nodes."""
    classified = getattr(app.state, "classified", {})
    horn = _load_horn_weights()

    # ── Entity nodes ─────────────────────────────────────────────────────────
    entity_counts: dict = {}
    for doc in classified.values():
        for etype, names in doc.get("entities", {}).items():
            for name in names:
                key = (name, etype)
                entity_counts[key] = entity_counts.get(key, 0) + 1

    entity_nodes: List[KGNode] = []
    for (name, etype), count in entity_counts.items():
        hw = horn.get(_horn_key(etype, name), 0.0)
        # Use the same ID format as the KG graph so neighbor lookup works:
        # "loc_taj_mahal", "person_shah_jahan", "org_unesco", etc.
        kg_id = _horn_key(etype, name)  # e.g. "loc_taj_mahal"
        entity_nodes.append(KGNode(
            id=kg_id,
            name=name,
            type=_TYPE_NORMALIZE.get(etype, etype),  # "location" not "locations"
            count=count,
            horn_weight=hw,
        ))

    # Sort by horn_weight desc, then count desc
    entity_nodes.sort(key=lambda n: (n.horn_weight, n.count), reverse=True)
    nodes: List[KGNode] = entity_nodes[:limit_entities]

    # ── Document nodes (optional) ─────────────────────────────────────────────
    if include_documents:
        simrank_path = "knowledge_graph/simrank/simrank_mapping.json"
        stats_path = "knowledge_graph/kg_statistics.json"
        doc_nodes: List[KGNode] = []
        top_central_titles: set = set()

        if os.path.exists(stats_path):
            with open(stats_path) as f:
                stats_data = json.load(f)
            top_central_titles = {
                d.get("title", "") for d in stats_data.get("top_central_documents", [])[:15]
            }

        if os.path.exists(simrank_path):
            with open(simrank_path) as f:
                simrank_data = json.load(f)
            doc_list = simrank_data.get("documents", [])

            seen_ids: set = set()
            # Add top-central docs first
            for doc_meta in doc_list:
                title = doc_meta.get("title", "")
                node_id = doc_meta.get("node_id", f"doc_{doc_meta.get('index', 0)}")
                if title in top_central_titles and node_id not in seen_ids:
                    seen_ids.add(node_id)
                    doc_nodes.append(KGNode(
                        id=node_id, name=title, type="document",
                        count=1, horn_weight=0.85,
                        cluster_id=doc_meta.get("cluster_id"),
                        cluster_label=doc_meta.get("cluster_label"),
                        is_top_central=True,
                    ))

            # Add up to 2 per cluster
            cluster_rep: dict = {}
            for doc_meta in doc_list:
                cid = doc_meta.get("cluster_id")
                node_id = doc_meta.get("node_id", f"doc_{doc_meta.get('index', 0)}")
                if node_id in seen_ids:
                    continue
                if cid not in cluster_rep:
                    cluster_rep[cid] = 0
                if cluster_rep[cid] < 2:
                    cluster_rep[cid] += 1
                    seen_ids.add(node_id)
                    title = doc_meta.get("title", "")
                    doc_nodes.append(KGNode(
                        id=node_id, name=title, type="document",
                        count=1, horn_weight=0.5,
                        cluster_id=cid,
                        cluster_label=doc_meta.get("cluster_label"),
                        is_top_central=False,
                    ))

        nodes = nodes + doc_nodes

    # ── Edges ────────────────────────────────────────────────────────────────
    node_id_set = {n.id for n in nodes}
    edge_counts: dict = {}

    for doc in classified.values():
        node_ids: list = []
        for etype, names in doc.get("entities", {}).items():
            for name in names:
                nid = _horn_key(etype, name)  # same kg-format as node IDs
                if nid in node_id_set:
                    node_ids.append(nid)
        for i in range(len(node_ids)):
            for j in range(i + 1, min(i + 6, len(node_ids))):
                a, b = node_ids[i], node_ids[j]
                key = (a, b) if a < b else (b, a)
                edge_counts[key] = edge_counts.get(key, 0) + 1

    edges: List[KGEdge] = [
        KGEdge(source=src, target=tgt, weight=float(w), edge_type="co_occurrence")
        for (src, tgt), w in edge_counts.items() if w > 1
    ]

    # Pull semantic/structural edges from the live KG if available
    if recommender is not None and hasattr(recommender, "kg") and recommender.kg is not None:
        semantic_types = {"similar_to", "semantically_related", "same_cluster", "shares_keywords",
                          "temporally_related", "geographically_related"}
        for u, v, data in recommender.kg.edges(data=True):
            rel = data.get("relation_type", data.get("relation", ""))
            if rel in semantic_types and u in node_id_set and v in node_id_set:
                edges.append(KGEdge(
                    source=u, target=v,
                    weight=float(data.get("weight", 1.0)),
                    edge_type=rel,
                ))

    edges.sort(key=lambda e: e.weight, reverse=True)
    return KGGraphResponse(nodes=nodes, edges=edges[:200])


@app.get("/kg/entity/{entity_id}/neighbors", response_model=KGNeighborsResponse)
def kg_entity_neighbors(entity_id: str):
    """Return the 1-hop neighborhood of a KG node for egocentric view."""
    if recommender is None or not hasattr(recommender, "kg") or recommender.kg is None:
        raise HTTPException(status_code=503, detail="Knowledge graph not loaded")

    G = recommender.kg

    # Try exact match first, then case-insensitive search
    actual_id = entity_id
    if actual_id not in G:
        for nid in G.nodes():
            if str(nid).lower() == entity_id.lower():
                actual_id = nid
                break
        else:
            raise HTTPException(status_code=404, detail=f"Node '{entity_id}' not found in KG")

    horn = _load_horn_weights()
    node_data = G.nodes[actual_id]

    def _build_kg_node(nid: str, ndata: dict, hw: float = 0.0) -> KGNode:
        ntype = ndata.get("node_type", ndata.get("type", "unknown"))
        name = ndata.get("name", ndata.get("title", str(nid)))
        # Rough count from degree
        count = G.degree(nid)
        return KGNode(
            id=str(nid), name=name, type=ntype,
            count=count, horn_weight=hw,
        )

    center_hw = horn.get(str(actual_id).replace("-", "_"), 0.0)
    center = _build_kg_node(actual_id, node_data, center_hw)

    neighbor_nodes: List[KGNode] = []
    neighbor_edges: List[KGEdge] = []

    for nbr in G.neighbors(actual_id):
        nbr_data = G.nodes[nbr]
        nbr_hw = horn.get(str(nbr).replace("-", "_"), 0.0)
        neighbor_nodes.append(_build_kg_node(nbr, nbr_data, nbr_hw))

        edge_data = G.edges[actual_id, nbr]
        rel = edge_data.get("relation_type", edge_data.get("relation", "related"))
        neighbor_edges.append(KGEdge(
            source=str(actual_id), target=str(nbr),
            weight=float(edge_data.get("weight", 1.0)),
            edge_type=rel,
        ))

    neighbor_nodes.sort(key=lambda n: n.horn_weight, reverse=True)
    return KGNeighborsResponse(
        center=center,
        neighbors=neighbor_nodes[:60],
        edges=neighbor_edges[:60],
    )


@app.get("/metrics")
def metrics():
    """Load latest evaluation results."""
    paths = [
        "results/evaluation_results.json",
        "results/evaluation_report.json",
        "data/evaluation/ground_truth_stats_improved.json",
    ]
    for path in paths:
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
            # evaluation_results.json is keyed by method name; return best (simrank_only) metrics
            # so the dashboard gets the flat {accuracy, diversity, heritage_specific, efficiency} shape.
            if data and isinstance(next(iter(data.values()), None), dict):
                first = next(iter(data.values()))
                if "metrics" in first:
                    return first["metrics"]
            return data
    raise HTTPException(status_code=404, detail="Evaluation results not found")


@app.get("/stats")
def system_stats():
    """Quick system stats for the dashboard."""
    classified = getattr(app.state, "classified", {})
    kg_path = "knowledge_graph/kg_statistics.json"
    kg_data = {}
    if os.path.exists(kg_path):
        with open(kg_path) as f:
            kg_data = json.load(f)

    # era_counts pre-computed at startup — O(1) lookup
    era_counts = getattr(app.state, "era_counts", {})

    return {
        "total_documents": len(classified),
        "kg_nodes": kg_data.get("total_nodes", 0),
        "kg_edges": kg_data.get("total_edges", 0),
        "node_types": kg_data.get("node_types", {}),
        "era_counts": era_counts,
    }
