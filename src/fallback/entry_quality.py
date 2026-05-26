"""
entry_quality.py
----------------
Scores individual local retrieval results for quality, flagging 'bad' entries
that should trigger a Wikidata fallback.

Independently testable:
    from src.fallback.entry_quality import EntryQualityScorer
    scorer = EntryQualityScorer()
    verdict = scorer.score(result_dict, cluster_size=12)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class QualityVerdict:
    """Verdict returned by EntryQualityScorer.score()."""
    is_bad: bool
    reason: str          # Human-readable explanation of what triggered the flag
    confidence: float    # 0.0–1.0; reflects how many triggers fired


# ---------------------------------------------------------------------------
# Noise title patterns
# ---------------------------------------------------------------------------

# Prefixes that indicate list/index/overview pages rather than specific entities
_NOISE_PREFIXES: tuple[str, ...] = (
    "list of",
    "lists of",
    "history of",
    "overview of",
    "index of",
    "outline of",
    "timeline of",
    "categories of",
)

# Regex to detect " in India" without a comma (region-grouped pages like
# "Buddhist temples in India" but NOT "Temples in Agra, India")
_IN_INDIA_NO_COMMA = re.compile(r"\bin india\b(?![^,]*,)", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

HYBRID_SCORE_MIN: float = 0.45       # Below this → weak retrieval match
EMBEDDING_SCORE_MIN: float = 0.35    # Below this → weak semantic signal
TITLE_MAX_WORDS: int = 12            # Titles longer than this are overly generic
CLUSTER_MAX: int = 45                # Overrepresented cluster upper bound
CLUSTER_MIN: int = 20                # Underrepresented cluster lower bound

# Confidence levels based on number of triggers fired
_CONFIDENCE_BY_TRIGGER_COUNT: Dict[int, float] = {
    1: 0.60,
    2: 0.80,
}
_CONFIDENCE_3_PLUS: float = 0.95


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------

class EntryQualityScorer:
    """
    Scores a single local retrieval result dict and decides whether it is
    a 'bad' entry that should be replaced or supplemented by a Wikidata result.

    Bad-entry triggers (ANY ONE is sufficient to set is_bad=True):
      1. Title matches known noise patterns (list pages, region pages, long titles)
      2. hybrid_score < 0.45
      3. cluster_size > 45 (overrepresented) or cluster_size < 20 (underrepresented)
      4. component_scores['embedding'] < 0.35

    Confidence is proportional to how many triggers fired:
      1 trigger  → 0.60
      2 triggers → 0.80
      3+         → 0.95
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score(self, result: Dict, cluster_size: int) -> QualityVerdict:
        """
        Evaluate a single result dict from recommender.recommend().

        Parameters
        ----------
        result : Dict
            A single element from the list returned by recommend().
            Expected keys: 'title', 'hybrid_score', 'component_scores'.
        cluster_size : int
            The number of documents in the cluster this result belongs to.

        Returns
        -------
        QualityVerdict
            Dataclass with is_bad, reason, confidence.
        """
        triggers: list[str] = []

        title: str = result.get("title", "")
        hybrid_score: float = float(result.get("hybrid_score", 0.0))
        component_scores: Dict = result.get("component_scores", {})
        embedding_score: float = float(component_scores.get("embedding", 0.0))

        # Trigger 1 — noisy title
        title_issue = self._check_title(title)
        if title_issue:
            triggers.append(f"Title issue: {title_issue}")

        # Trigger 2 — weak hybrid score
        if hybrid_score < HYBRID_SCORE_MIN:
            triggers.append(
                f"hybrid_score {hybrid_score:.3f} < threshold {HYBRID_SCORE_MIN}"
            )

        # Trigger 3 — imbalanced cluster
        if cluster_size > CLUSTER_MAX:
            triggers.append(
                f"cluster_size {cluster_size} > {CLUSTER_MAX} (overrepresented)"
            )
        elif cluster_size < CLUSTER_MIN:
            triggers.append(
                f"cluster_size {cluster_size} < {CLUSTER_MIN} (underrepresented)"
            )

        # Trigger 4 — weak embedding score
        if embedding_score < EMBEDDING_SCORE_MIN:
            triggers.append(
                f"embedding score {embedding_score:.3f} < threshold {EMBEDDING_SCORE_MIN}"
            )

        is_bad = len(triggers) > 0
        reason = "; ".join(triggers) if triggers else "All quality checks passed"
        confidence = self._compute_confidence(len(triggers))

        return QualityVerdict(is_bad=is_bad, reason=reason, confidence=confidence)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_title(title: str) -> str:
        """
        Return a non-empty string describing the title issue, or '' if clean.
        """
        title_lower = title.strip().lower()

        # Check noise prefixes
        for prefix in _NOISE_PREFIXES:
            if title_lower.startswith(prefix):
                return f"starts with noise prefix '{prefix}'"

        # Check " in India" without comma
        if _IN_INDIA_NO_COMMA.search(title_lower):
            return "region-grouped pattern '... in India' with no comma"

        # Check title word count
        word_count = len(title.split())
        if word_count > TITLE_MAX_WORDS:
            return f"title has {word_count} words (> {TITLE_MAX_WORDS}, likely generic)"

        return ""

    @staticmethod
    def _compute_confidence(trigger_count: int) -> float:
        """Map trigger count to a confidence value."""
        if trigger_count == 0:
            return 0.0
        if trigger_count >= 3:
            return _CONFIDENCE_3_PLUS
        return _CONFIDENCE_BY_TRIGGER_COUNT.get(trigger_count, 0.60)
