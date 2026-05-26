"""
src/fallback
------------
Smart Wikidata fallback layer for the heritage document recommendation system.

Exports
-------
FallbackGate
    Main entry point. Routes queries between local results and Wikidata
    based on per-result quality scoring.

EntryQualityScorer
    Scores individual local result dicts and emits a QualityVerdict.

WikidataClient
    Cache-backed client for Wikidata search and entity APIs.

HeritageResult
    Unified result dataclass (local or wikidata).

QualityVerdict
    Dataclass returned by EntryQualityScorer.score().

WikidataEntity
    Dataclass returned by WikidataClient.search() / get_entity().
"""

from src.fallback.entry_quality import EntryQualityScorer, QualityVerdict
from src.fallback.fallback_gate import FallbackGate
from src.fallback.result_normalizer import HeritageResult
from src.fallback.wikidata_client import WikidataClient, WikidataEntity

__all__ = [
    "FallbackGate",
    "EntryQualityScorer",
    "WikidataClient",
    "HeritageResult",
    "QualityVerdict",
    "WikidataEntity",
]
