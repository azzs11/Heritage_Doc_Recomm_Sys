"""
fallback_gate.py
----------------
Routing logic that decides whether to serve local results, blend local with
Wikidata, or fall back entirely to Wikidata based on per-result quality scores.

Independently testable:
    from src.fallback.fallback_gate import FallbackGate
    gate = FallbackGate(scorer, wikidata_client, cluster_size_map)
    results = gate.route("Ajanta Caves rock-cut monastery", local_results)
    print(gate.explain(results))
"""

from __future__ import annotations

import logging
from typing import Dict, List, Tuple

from src.fallback.entry_quality import EntryQualityScorer, QualityVerdict
from src.fallback.result_normalizer import (
    HeritageResult,
    normalize_batch,
    normalize_local,
    normalize_wikidata,
)
from src.fallback.wikidata_client import WikidataClient

logger = logging.getLogger(__name__)

# Number of top results to inspect for quality assessment
_QUALITY_CHECK_TOP_N = 3

# Default cluster size assumed when cluster_id is missing or unmapped
_DEFAULT_CLUSTER_SIZE = 30


class FallbackGate:
    """
    Routes a query to local results, a mixed blend, or a full Wikidata fallback
    depending on how many of the top-N local results are low quality.

    Routing rules:
      0 of top-3 bad → return all local results as-is
      1 of top-3 bad → mixed mode: replace the bad result(s) with Wikidata hits
      2–3 of top-3 bad → full fallback: return Wikidata results for the query

    Parameters
    ----------
    quality_scorer : EntryQualityScorer
        Scores individual result dicts.
    wikidata_client : WikidataClient
        Fetches Wikidata entities.
    cluster_size_map : Dict[str, int]
        Maps cluster_id (as str) → document count in that cluster.
        Build this once at startup from your classified documents metadata.
    """

    def __init__(
        self,
        quality_scorer: EntryQualityScorer,
        wikidata_client: WikidataClient,
        cluster_size_map: Dict[str, int],
    ) -> None:
        self._scorer = quality_scorer
        self._wiki = wikidata_client
        self._cluster_size_map = cluster_size_map

        # Populated by route() so explain() can summarise the last decision
        self._last_routing_info: Dict = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def route(
        self,
        query_text: str,
        local_results: List[Dict],
        top_k: int = 10,
    ) -> List[HeritageResult]:
        """
        Decide which results to return for query_text.

        Parameters
        ----------
        query_text : str
            The original user query string (used to call Wikidata if needed).
        local_results : List[Dict]
            Raw output from recommender.recommend(). May be empty.
        top_k : int
            Maximum number of results to return.

        Returns
        -------
        List[HeritageResult]
            Always HeritageResult objects, never raw dicts.
        """
        # --- Edge case: no local results at all ---
        if not local_results:
            logger.info("No local results; falling back to Wikidata for '%s'", query_text)
            self._last_routing_info = {
                "mode": "full_fallback",
                "bad_count": 0,
                "total_checked": 0,
                "trigger": "empty local results",
                "local_count": 0,
                "wikidata_count": 0,
            }
            wiki_results = self._fetch_wikidata(query_text, reason="No local results found")
            self._last_routing_info["wikidata_count"] = len(wiki_results)
            return self._rerank(wiki_results)[:top_k]

        # --- Score the top-N local results ---
        top_n = local_results[:_QUALITY_CHECK_TOP_N]
        scored: List[Tuple[Dict, QualityVerdict]] = [
            (r, self._scorer.score(r, self._get_cluster_size(r)))
            for r in top_n
        ]
        bad_indices = [i for i, (_, v) in enumerate(scored) if v.is_bad]
        bad_count = len(bad_indices)

        logger.debug(
            "Quality check: %d/%d top results flagged bad for query '%s'",
            bad_count, _QUALITY_CHECK_TOP_N, query_text,
        )

        # --- Route ---
        if bad_count == 0:
            # All good — return local as-is
            self._last_routing_info = {
                "mode": "local_only",
                "bad_count": 0,
                "total_checked": len(top_n),
                "local_count": len(local_results[:top_k]),
                "wikidata_count": 0,
            }
            return normalize_batch(local_results[:top_k])

        elif bad_count == 1:
            # Mixed mode — replace the single bad result with a Wikidata hit
            return self._mixed_mode(
                query_text, local_results, bad_indices, scored, top_k
            )

        else:
            # Full fallback — 2 or 3 of the top-3 are bad
            self._last_routing_info = {
                "mode": "full_fallback",
                "bad_count": bad_count,
                "total_checked": len(top_n),
                "trigger": "; ".join(
                    scored[i][1].reason for i in bad_indices
                ),
                "local_count": 0,
                "wikidata_count": 0,
            }
            reason = (
                f"{bad_count}/{_QUALITY_CHECK_TOP_N} top results were low quality. "
                + "; ".join(scored[i][1].reason for i in bad_indices)
            )
            wiki_results = self._fetch_wikidata(query_text, reason=reason)
            self._last_routing_info["wikidata_count"] = len(wiki_results)
            return self._rerank(wiki_results)[:top_k]

    def explain(self, results: List[HeritageResult]) -> str:
        """
        Return a human-readable summary of the routing decision made during
        the most recent call to route().

        Parameters
        ----------
        results : List[HeritageResult]
            The list returned by the last route() call (used for counts).

        Returns
        -------
        str
            One or two sentences describing what happened and why.
        """
        info = self._last_routing_info
        if not info:
            return "No routing decision has been made yet."

        mode = info.get("mode", "unknown")
        local_count = sum(1 for r in results if r.source == "local")
        wiki_count = sum(1 for r in results if r.source == "wikidata")

        if mode == "local_only":
            return (
                f"All top-{_QUALITY_CHECK_TOP_N} results passed quality checks. "
                f"Returned {local_count} local result(s)."
            )
        elif mode == "mixed":
            trigger = info.get("trigger", "quality issues")
            return (
                f"1/{_QUALITY_CHECK_TOP_N} top result was low quality ({trigger}). "
                f"Mixed mode: returned {local_count} local + {wiki_count} Wikidata result(s)."
            )
        elif mode == "full_fallback":
            trigger = info.get("trigger", "quality issues")
            bad = info.get("bad_count", "?")
            return (
                f"{bad}/{_QUALITY_CHECK_TOP_N} top results were low quality ({trigger}). "
                f"Fell back to Wikidata. Returned {local_count} local + {wiki_count} Wikidata result(s)."
            )
        return f"Unknown routing mode '{mode}'."

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _mixed_mode(
        self,
        query_text: str,
        local_results: List[Dict],
        bad_indices: List[int],
        scored: List[Tuple[Dict, QualityVerdict]],
        top_k: int,
    ) -> List[HeritageResult]:
        """Replace the single bad local result with a Wikidata hit."""
        bad_idx = bad_indices[0]
        bad_result, bad_verdict = scored[bad_idx]
        bad_title = bad_result.get("title", query_text)

        reason = (
            f"Local result '{bad_title}' was low quality: {bad_verdict.reason}"
        )

        # When the bad title is a noise page (e.g. "List of World Heritage Sites in India"),
        # strip the noise prefix so Wikidata gets a meaningful search term.
        search_title = self._strip_noise_prefix(bad_title)

        # Try progressively broader/shorter searches until we get results.
        # 1. Noise-stripped title (most targeted)
        # 2. Full query text
        # 3. Keyword-reduced query (drop stopwords)
        # 4. Leading 2-word bigram of keywords (Wikidata works better with short phrases)
        # 5. Same bigram, unfiltered (last resort)
        wiki_entities = self._wiki.search(search_title, limit=3)
        if not wiki_entities:
            wiki_entities = self._wiki.search(query_text, limit=3)
        if not wiki_entities:
            short_query = self._shorten_query(query_text)
            if short_query != query_text:
                wiki_entities = self._wiki.search(short_query, limit=3)
        if not wiki_entities:
            bigram = self._leading_bigram(query_text)
            if bigram:
                wiki_entities = self._wiki.search(bigram, limit=3)
        if not wiki_entities:
            bigram = self._leading_bigram(query_text) or self._shorten_query(query_text)
            wiki_entities = self._wiki.search(bigram, limit=3, strict_filter=False)

        # Build the final merged list
        output: List[HeritageResult] = []
        for i, r in enumerate(local_results[:top_k]):
            if i == bad_idx and wiki_entities:
                # Swap in the top Wikidata hit
                output.append(normalize_wikidata(wiki_entities[0], rank=i + 1, reason=reason))
            else:
                output.append(normalize_local(r))

        # Append any remaining Wikidata results (beyond the 1 swap) at the end
        # but only if we still have room
        for j, entity in enumerate(wiki_entities[1:], start=1):
            if len(output) >= top_k:
                break
            output.append(
                normalize_wikidata(entity, rank=len(output) + 1, reason=reason)
            )

        merged = self._rerank(output)[:top_k]

        self._last_routing_info = {
            "mode": "mixed",
            "bad_count": 1,
            "total_checked": _QUALITY_CHECK_TOP_N,
            "trigger": bad_verdict.reason,
            "local_count": sum(1 for r in merged if r.source == "local"),
            "wikidata_count": sum(1 for r in merged if r.source == "wikidata"),
        }
        return merged

    @staticmethod
    def _leading_bigram(query_text: str) -> str:
        """
        Return the first two meaningful (non-stopword) words from the query,
        which Wikidata search handles better than long multi-word phrases.
        E.g. "ancient cave temples India" → "cave temples"
        """
        _STOPWORDS = {
            "a", "an", "the", "of", "in", "on", "at", "to", "and", "or",
            "for", "with", "by", "from", "about", "is", "are", "was", "were",
            "ancient", "old", "historic", "historical", "famous", "notable",
            "traditional", "important", "significant", "major", "great",
            "its", "their", "some", "any", "all", "this", "that",
        }
        words = [w for w in query_text.split() if w.lower() not in _STOPWORDS]
        return " ".join(words[:2]) if len(words) >= 2 else " ".join(words)

    @staticmethod
    def _shorten_query(query_text: str) -> str:
        """
        Drop common stopwords and adjectives from a query to produce a shorter,
        more Wikidata-friendly search term.
        E.g. "ancient cave temples India" → "cave temples India"
        """
        _STOPWORDS = {
            "a", "an", "the", "of", "in", "on", "at", "to", "and", "or",
            "for", "with", "by", "from", "about", "is", "are", "was", "were",
            "ancient", "old", "historic", "historical", "famous", "notable",
            "traditional", "important", "significant", "major", "great",
            "its", "their", "some", "any", "all", "this", "that",
        }
        words = query_text.split()
        meaningful = [w for w in words if w.lower() not in _STOPWORDS]
        return " ".join(meaningful) if meaningful else query_text

    @staticmethod
    def _strip_noise_prefix(title: str) -> str:
        """
        Remove leading noise phrases (List of, History of, etc.) from a title
        so the remainder can be used as a cleaner Wikidata search term.
        E.g. "List of World Heritage Sites in India" → "World Heritage Sites in India"
        """
        import re as _re
        _NOISE = _re.compile(
            r"^(list of|lists of|history of|overview of|index of|"
            r"outline of|timeline of|categories of)\s+",
            _re.IGNORECASE,
        )
        return _NOISE.sub("", title).strip()

    def _fetch_wikidata(self, query_text: str, reason: str) -> List[HeritageResult]:
        """Search Wikidata and return normalised HeritageResult list."""
        entities = self._wiki.search(query_text, limit=10)
        return [
            normalize_wikidata(entity, rank=i + 1, reason=reason)
            for i, entity in enumerate(entities)
        ]

    def _get_cluster_size(self, result: Dict) -> int:
        """
        Look up cluster size from cluster_size_map.
        Falls back to _DEFAULT_CLUSTER_SIZE if cluster_id is missing or unmapped.
        """
        # cluster_id may live directly on the result or inside metadata
        cluster_id = result.get("cluster_id") or result.get("metadata", {}).get("cluster_id")
        if cluster_id is None:
            return _DEFAULT_CLUSTER_SIZE
        return self._cluster_size_map.get(str(cluster_id), _DEFAULT_CLUSTER_SIZE)

    @staticmethod
    def _rerank(results: List[HeritageResult]) -> List[HeritageResult]:
        """
        Sort results by score descending and reassign sequential ranks (1-indexed).
        """
        sorted_results = sorted(results, key=lambda r: r.score, reverse=True)
        for i, r in enumerate(sorted_results):
            r.rank = i + 1
        return sorted_results
