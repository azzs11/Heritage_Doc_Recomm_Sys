"""
wikidata_client.py
------------------
Thin, cache-backed client for Wikidata's public search and entity APIs.
No authentication required. No heavy dependencies (stdlib + requests only).

Independently testable:
    from src.fallback.wikidata_client import WikidataClient
    client = WikidataClient()
    results = client.search("Ajanta Caves")
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Heritage-domain description keywords used to filter Wikidata results
# ---------------------------------------------------------------------------
_HERITAGE_KEYWORDS: tuple[str, ...] = (
    "heritage",
    "monument",
    "temple",
    "site",
    "ruins",
    "fort",
    "cave",
    "palace",
    "mosque",
    "church",
    "archaeological",
    "UNESCO",
    "historic",
)

# Wikidata API endpoints
_SEARCH_API = "https://www.wikidata.org/w/api.php"
_ENTITY_API = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"

# HTTP timeout (seconds)
_TIMEOUT = 10

# Wikidata requires a descriptive User-Agent; plain requests UA returns 403
_HEADERS = {
    "User-Agent": "HeritageDocRecommender/1.0 (cultural heritage research tool; python-requests)"
}


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class WikidataEntity:
    """A single Wikidata entity relevant to cultural heritage."""
    name: str
    qid: str                        # e.g. "Q1290"
    description: str
    instance_of: List[str] = field(default_factory=list)  # P31 labels


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class WikidataClient:
    """
    Searches Wikidata for cultural heritage entities and fetches entity details.

    Results are cached as flat JSON files so repeated queries are instant and
    offline-safe. Cache never expires (heritage data is largely immutable).

    Parameters
    ----------
    cache_dir : str
        Directory for cached responses. Defaults to ~/.cache/heritage_fallback/.
        Created automatically if it does not exist.
    """

    def __init__(self, cache_dir: str = "~/.cache/heritage_fallback/") -> None:
        self._cache_dir = Path(cache_dir).expanduser()
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(
        self, query: str, limit: int = 5, strict_filter: bool = True
    ) -> List[WikidataEntity]:
        """
        Search Wikidata for entities matching query, filtered to heritage domain.

        Parameters
        ----------
        query : str
            Free-text search string (e.g. "Ajanta Caves").
        limit : int
            Max results to request from Wikidata (before heritage filtering).
        strict_filter : bool
            When True (default) only entities whose description OR name contains
            a heritage keyword are returned. Set False to return all hits (used
            as a last-resort fallback when strict filtering yields nothing).

        Returns
        -------
        List[WikidataEntity]
            Heritage-relevant entities. Empty list on any network error.
        """
        cache_key = self._search_cache_key(query, limit, strict_filter)
        cached = self._load_cache(cache_key)
        if cached is not None:
            return [WikidataEntity(**item) for item in cached]

        params = {
            "action": "wbsearchentities",
            "search": query,
            "language": "en",
            "type": "item",
            "limit": limit,
            "format": "json",
        }

        try:
            response = requests.get(_SEARCH_API, params=params, headers=_HEADERS, timeout=_TIMEOUT)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            logger.warning("Wikidata search failed for '%s': %s", query, exc)
            return []

        entities: List[WikidataEntity] = []
        for hit in data.get("search", []):
            description = hit.get("description", "")
            label = hit.get("label", "")
            # Accept if either the description OR the label contains a heritage keyword,
            # or if strict_filter is disabled (last-resort fallback path)
            if strict_filter and (
                not self._is_heritage_relevant(description)
                and not self._is_heritage_relevant(label)
            ):
                continue
            entities.append(
                WikidataEntity(
                    name=hit.get("label", ""),
                    qid=hit.get("id", ""),
                    description=description,
                    instance_of=[],  # Not available from search endpoint; use get_entity
                )
            )

        # Cache the serialised result (list of dicts)
        self._save_cache(cache_key, [vars(e) for e in entities])
        return entities

    def get_entity(self, qid: str) -> Optional[WikidataEntity]:
        """
        Fetch full entity details for a Wikidata QID.

        Extracts English label, description, and P31 (instance of) values.

        Parameters
        ----------
        qid : str
            Wikidata item ID, e.g. "Q1290".

        Returns
        -------
        WikidataEntity or None on any failure.
        """
        cache_key = self._entity_cache_key(qid)
        cached = self._load_cache(cache_key)
        if cached is not None:
            return WikidataEntity(**cached)

        url = _ENTITY_API.format(qid=qid)
        try:
            response = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            logger.warning("Wikidata entity fetch failed for '%s': %s", qid, exc)
            return None

        entity_data = data.get("entities", {}).get(qid)
        if not entity_data:
            logger.warning("QID '%s' not found in Wikidata response", qid)
            return None

        name = self._extract_en_value(
            entity_data.get("labels", {}), default=""
        )
        description = self._extract_en_value(
            entity_data.get("descriptions", {}), default=""
        )
        instance_of = self._extract_p31_labels(entity_data)

        entity = WikidataEntity(
            name=name, qid=qid,
            description=description, instance_of=instance_of
        )
        self._save_cache(cache_key, vars(entity))
        return entity

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def _search_cache_key(self, query: str, limit: int, strict_filter: bool = True) -> str:
        raw = f"search:{query}:{limit}:strict={strict_filter}"
        return f"search_{hashlib.md5(raw.encode()).hexdigest()}.json"

    def _entity_cache_key(self, qid: str) -> str:
        return f"entity_{qid}.json"

    def _cache_path(self, filename: str) -> Path:
        return self._cache_dir / filename

    def _load_cache(self, filename: str):
        path = self._cache_path(filename)
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Cache read failed for %s: %s", filename, exc)
        return None

    def _save_cache(self, filename: str, data) -> None:
        path = self._cache_path(filename)
        try:
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        except OSError as exc:
            logger.warning("Cache write failed for %s: %s", filename, exc)

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_heritage_relevant(description: str) -> bool:
        """Return True if description contains any heritage keyword."""
        desc_lower = description.lower()
        return any(kw.lower() in desc_lower for kw in _HERITAGE_KEYWORDS)

    @staticmethod
    def _extract_en_value(field_dict: dict, default: str = "") -> str:
        """Extract the English value from a Wikidata labels/descriptions dict."""
        en = field_dict.get("en", {})
        return en.get("value", default) if isinstance(en, dict) else default

    @staticmethod
    def _extract_p31_labels(entity_data: dict) -> List[str]:
        """
        Extract P31 (instance of) claim labels from an entity data dict.
        Returns a list of English label strings.
        """
        claims = entity_data.get("claims", {})
        p31_claims = claims.get("P31", [])
        labels: List[str] = []
        for claim in p31_claims:
            try:
                value = (
                    claim["mainsnak"]["datavalue"]["value"]["id"]
                )
                # value is a QID like "Q839954"; we just store it as-is
                # since resolving each nested QID would require more API calls.
                labels.append(value)
            except (KeyError, TypeError):
                continue
        return labels
