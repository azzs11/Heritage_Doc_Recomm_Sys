"""
result_normalizer.py
--------------------
Converts heterogeneous result shapes (local recommender dicts and Wikidata
entities) into a single unified HeritageResult dataclass.

Independently testable:
    from src.fallback.result_normalizer import normalize_local, normalize_wikidata
    hr = normalize_local(result_dict)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.fallback.wikidata_client import WikidataEntity


# ---------------------------------------------------------------------------
# Unified result dataclass
# ---------------------------------------------------------------------------

@dataclass
class HeritageResult:
    """
    Normalised representation of a single retrieval result, regardless of
    whether it originated from the local recommender or Wikidata.

    Attributes
    ----------
    name : str
        Human-readable title / label of the heritage entity.
    source : str
        "local" for results from the local recommender, "wikidata" for fallbacks.
    entity_id : str
        doc_id for local results; Wikidata QID (e.g. "Q1290") for wikidata results.
    score : float
        Relevance score. hybrid_score for local; 1/rank for wikidata (rank-decay).
    rank : int
        Position in the final merged result list (1-indexed).
    reason : Optional[str]
        Why a fallback was triggered. Only set for wikidata results.
    metadata : Dict
        Passthrough of the original metadata dict for local results;
        {"instance_of": [...], "description": "..."} for wikidata results.
    """
    name: str
    source: str
    entity_id: str
    score: float
    rank: int
    reason: Optional[str] = None
    metadata: Dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Normalisation functions
# ---------------------------------------------------------------------------

def normalize_local(result: Dict) -> HeritageResult:
    """
    Map a single raw dict from recommender.recommend() to HeritageResult.

    Parameters
    ----------
    result : Dict
        A single element from List[Dict] returned by recommend().
        Expected keys: 'doc_id', 'title', 'hybrid_score', 'rank', 'metadata'.

    Returns
    -------
    HeritageResult with source="local".
    """
    return HeritageResult(
        name=result.get("title", ""),
        source="local",
        entity_id=result.get("doc_id", ""),
        score=float(result.get("hybrid_score", 0.0)),
        rank=int(result.get("rank", 0)),
        reason=None,
        metadata=dict(result.get("metadata", {})),
    )


def normalize_wikidata(
    entity: WikidataEntity,
    rank: int,
    reason: str,
) -> HeritageResult:
    """
    Map a WikidataEntity to HeritageResult using rank-decay scoring.

    Score = 1.0 / rank, so rank-1 → 1.0, rank-2 → 0.5, rank-3 → 0.33 …

    Parameters
    ----------
    entity : WikidataEntity
        Entity returned by WikidataClient.search() or get_entity().
    rank : int
        1-indexed position of this entity in the Wikidata search results.
    reason : str
        Human-readable explanation of why the fallback was triggered.

    Returns
    -------
    HeritageResult with source="wikidata".
    """
    score = 1.0 / max(rank, 1)  # Guard against rank=0
    return HeritageResult(
        name=entity.name,
        source="wikidata",
        entity_id=entity.qid,
        score=score,
        rank=rank,
        reason=reason,
        metadata={
            "instance_of": entity.instance_of,
            "description": entity.description,
        },
    )


def normalize_batch(
    results: List[Dict],
    source: str = "local",
) -> List[HeritageResult]:
    """
    Convenience wrapper: normalise an entire list of raw local result dicts.

    Parameters
    ----------
    results : List[Dict]
        Full list returned by recommend().
    source : str
        Always "local" when called from the fallback gate; exposed as a
        parameter for future extensibility.

    Returns
    -------
    List[HeritageResult] preserving original order and ranks.
    """
    if source != "local":
        raise ValueError(
            f"normalize_batch only supports source='local', got '{source}'. "
            "Use normalize_wikidata() directly for Wikidata entities."
        )
    return [normalize_local(r) for r in results]
