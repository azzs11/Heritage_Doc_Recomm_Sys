"""
Heritage Document Recommender — FastAPI Backend
Run: uvicorn api.main:app --reload --port 8000
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import json
import numpy as np

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

app = FastAPI(title="Heritage Document Recommender API", version="1.0.0")

_cors_origins_env = os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
_cors_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
        print("AdaptiveRecommender loaded.")
    except Exception as e:
        print(f"AdaptiveRecommender init failed (non-fatal): {e}")

    try:
        import importlib as _il
        _er_mod = _il.import_module("ensemble_ranker")
        EnsembleRanker = _er_mod.EnsembleRanker
        AdaptiveEnsemble = _er_mod.AdaptiveEnsemble
        RankedDocument = _er_mod.RankedDocument
        print("EnsembleRanker loaded.")
    except Exception as e:
        print(f"EnsembleRanker init failed (non-fatal): {e}")

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


# ── Helpers ───────────────────────────────────────────────────────────────────

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


def _build_summary(meta: dict) -> Optional[str]:
    """Synthesise a short, human-readable summary from structured metadata."""
    if not meta:
        return None
    classifications = meta.get("classifications", {})
    heritage_types = classifications.get("heritage_types", [])
    domains = classifications.get("domains", [])
    time_period = classifications.get("time_period")
    region = classifications.get("region")
    arch_styles = classifications.get("architectural_styles", [])
    keywords = meta.get("keywords_tfidf", [])[:4]

    # Skip generic/unknown values
    skip = {"unknown", "india", ""}
    period_str = time_period if time_period and time_period.lower() not in skip else None
    region_str = region if region and region.lower() not in skip else None

    parts = []

    # Lead with heritage type + period
    if heritage_types:
        ht = heritage_types[0].capitalize()
        if period_str and region_str:
            parts.append(f"{ht} from {period_str} {region_str} India")
        elif period_str:
            parts.append(f"{ht} from the {period_str} period")
        elif region_str:
            parts.append(f"{ht} from {region_str} India")
        else:
            parts.append(ht)

    # Domain context
    if domains:
        clean_domains = [d for d in domains[:2] if d.lower() not in skip]
        if clean_domains:
            parts.append(f"associated with {' and '.join(clean_domains)} heritage")

    # Architectural style
    if arch_styles:
        clean_styles = [s for s in arch_styles[:2] if s.lower() not in skip]
        if clean_styles:
            parts.append(f"{', '.join(clean_styles)} style")

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

    # Suppress values that are clearly not useful as era/region
    _skip = {"unknown", "india"}
    era = classifications.get("time_period") or result.get("metadata", {}).get("time_period")
    era = era if era and era.lower() not in _skip else None
    region = classifications.get("region") or result.get("metadata", {}).get("region")
    region = region if region and region.lower() not in _skip else None

    return DocumentResult(
        id=result.get("doc_id", title),
        title=title,
        type=classifications.get("heritage_types", [None])[0] if classifications.get("heritage_types") else result.get("metadata", {}).get("heritage_type"),
        era=era,
        region=region,
        source=_normalize_source(raw_source, raw_url),
        summary=_build_summary(meta),
        score=round(float(result.get("ensemble_score" if use_ensemble else "hybrid_score", 0.0)), 4),
        component_scores={k: float(v) for k, v in result["component_scores"].items()} if result.get("component_scores") else None,
        explanations=result.get("kg_explanations"),
        entities=entities if entities else None,
        keywords=meta.get("keywords_tfidf", [])[:8],
        cluster_label=meta.get("cluster_label"),
    )


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
def search(req: SearchRequest):
    if not query_processor or not recommender:
        raise HTTPException(status_code=503, detail="Models not loaded")

    parsed = query_processor.parse_query(req.query)

    # Fetch extra candidates when ensemble will re-rank
    use_ensemble = bool(req.ensemble_method and adaptive_ranker)
    candidates_k = min(req.top_k * 5, 50) if use_ensemble else req.top_k

    results = recommender.recommend(
        parsed_query=parsed,
        top_k=req.top_k,
        candidates_k=candidates_k,
        explain=req.explain,
        filter_period=req.era,
        filter_region=req.region,
        filter_heritage=req.type,
        filter_domain=req.domain,
    )

    used_method = None
    query_type = None

    if use_ensemble:
        all_entities = (
            parsed.get("locations", []) +
            parsed.get("persons", []) +
            parsed.get("organizations", [])
        )
        complexity = _query_complexity(parsed)

        if EnsembleRanker is None:
            raise HTTPException(status_code=503, detail="EnsembleRanker not loaded")

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

        # Classify query type for response transparency
        try:
            _, query_type, _ = adaptive_ranker.classifier.predict(req.query, all_entities)
        except Exception:
            query_type = None

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

    docs = [enrich_result(r, use_ensemble=use_ensemble) for r in results]
    return SearchResponse(
        query=req.query,
        total=len(docs),
        documents=docs,
        ensemble_method=used_method,
        query_type=query_type,
    )


@app.get("/recommend", response_model=SearchResponse)
def recommend(
    q: str = Query(..., description="Query string"),
    top_k: int = Query(10, ge=1, le=50),
    explain: bool = Query(True),
    ensemble_method: Optional[str] = Query("adaptive"),
):
    """GET convenience endpoint — same as POST /search."""
    req = SearchRequest(query=q, top_k=top_k, explain=explain, ensemble_method=ensemble_method)
    return search(req)


@app.get("/documents", response_model=List[dict])
def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    era: Optional[str] = None,
    region: Optional[str] = None,
    type: Optional[str] = None,
):
    """Browse all documents with optional filters and pagination."""
    classified = getattr(app.state, "classified", {})
    docs = list(classified.values())

    # Filter
    if era:
        docs = [d for d in docs if d.get("classifications", {}).get("time_period") == era.lower()]
    if region:
        docs = [d for d in docs if d.get("classifications", {}).get("region") == region.lower()]
    if type:
        docs = [d for d in docs if type.lower() in d.get("classifications", {}).get("heritage_types", [])]

    total = len(docs)
    start = (page - 1) * page_size
    page_docs = docs[start: start + page_size]

    _skip = {"unknown", "india"}

    def _clean(val):
        return val if val and val.lower() not in _skip else None

    return [
        {
            "id": d.get("file_name", d.get("title", "")),
            "title": d.get("title", ""),
            "type": (d.get("classifications", {}).get("heritage_types") or [None])[0],
            "era": _clean(d.get("classifications", {}).get("time_period")),
            "region": _clean(d.get("classifications", {}).get("region")),
            "source": _normalize_source(d.get("source"), d.get("url")),
            "summary": _build_summary(d),
            "keywords": d.get("keywords_tfidf", [])[:5],
            "cluster_label": d.get("cluster_label"),
            "total": total,
        }
        for d in page_docs
    ]


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

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    classifications = doc.get("classifications", {})
    entities = doc.get("entities", {})

    _skip = {"unknown", "india"}

    def _clean(val):
        return val if val and val.lower() not in _skip else None

    return {
        "id": doc.get("file_name", doc.get("title")),
        "title": doc.get("title"),
        "type": (classifications.get("heritage_types") or [None])[0],
        "era": _clean(classifications.get("time_period")),
        "region": _clean(classifications.get("region")),
        "source": _normalize_source(doc.get("source"), doc.get("url")),
        "url": doc.get("url"),
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
            "time_period": classifications.get("time_period"),
            "region": classifications.get("region"),
            "architectural_styles": classifications.get("architectural_styles", []),
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

    return {
        "total_documents": len(classified),
        "kg_nodes": kg_data.get("total_nodes", 0),
        "kg_edges": kg_data.get("total_edges", 0),
        "node_types": kg_data.get("node_types", {}),
    }
