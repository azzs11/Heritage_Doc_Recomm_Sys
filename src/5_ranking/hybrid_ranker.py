"""
Hybrid Ranker

Combines SimRank (graph structure), Horn's Index (entity importance),
and embedding similarity into a single weighted score.

Supports:
- Fixed weights (default α·SR + β·HORN + (1-α-β)·EMB)
- Query-type-adaptive weights (loaded from learned_weights.json)
- Score normalization before combination
"""

import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# Default weights as specified in the architecture diagram (Stage 5)
DEFAULT_SIMRANK_WEIGHT: float = 0.4
DEFAULT_HORN_WEIGHT: float = 0.3
DEFAULT_EMBEDDING_WEIGHT: float = 0.3


class HybridRanker:
    """
    α·SimRank + β·Horn + (1-α-β)·Embedding hybrid scorer.

    Weights can be fixed or loaded per-query-type from learned_weights.json.
    """

    def __init__(
        self,
        simrank_weight: float = DEFAULT_SIMRANK_WEIGHT,
        horn_weight: float = DEFAULT_HORN_WEIGHT,
        embedding_weight: float = DEFAULT_EMBEDDING_WEIGHT,
        learned_weights_path: Optional[str] = None,
        normalize: bool = True,
    ):
        """
        Args:
            simrank_weight: Default weight for SimRank component.
            horn_weight: Default weight for Horn's Index component.
            embedding_weight: Default weight for embedding similarity.
            learned_weights_path: Optional path to learned_weights.json.
                                  When provided the per-query-type weights
                                  override the defaults at score time.
            normalize: Min-max normalise each component before combining.
        """
        self._validate_weights(simrank_weight, horn_weight, embedding_weight)
        self.simrank_weight = simrank_weight
        self.horn_weight = horn_weight
        self.embedding_weight = embedding_weight
        self.normalize = normalize

        # Per-query-type weight tables {model -> {query_type -> {field -> float}}}
        self._learned_weights: Dict = {}
        if learned_weights_path and Path(learned_weights_path).exists():
            with open(learned_weights_path) as f:
                self._learned_weights = json.load(f)

    # ── Public API ────────────────────────────────────────────────────────────

    def score(
        self,
        simrank_scores: List[float],
        horn_scores: List[float],
        embedding_scores: List[float],
        query_type: Optional[str] = None,
        model: str = "lambdamart",
    ) -> List[float]:
        """
        Compute hybrid scores for a list of documents.

        Args:
            simrank_scores: SimRank similarity for each candidate.
            horn_scores: Horn's Index score for each candidate.
            embedding_scores: Embedding cosine similarity for each candidate.
            query_type: Classifier output (e.g. 'concept_focused').
                        When provided and learned weights exist the adaptive
                        weights are used instead of the defaults.
            model: Which LTR model's weights to read ('lambdamart', etc.).

        Returns:
            List of hybrid scores, one per document, in the same order.
        """
        sr = np.array(simrank_scores, dtype=float)
        hn = np.array(horn_scores, dtype=float)
        em = np.array(embedding_scores, dtype=float)

        if self.normalize:
            sr = self._minmax(sr)
            hn = self._minmax(hn)
            em = self._minmax(em)

        sw, hw, ew = self._get_weights(query_type, model)
        return (sw * sr + hw * hn + ew * em).tolist()

    def score_single(
        self,
        simrank: float,
        horn: float,
        embedding: float,
        query_type: Optional[str] = None,
        model: str = "lambdamart",
    ) -> float:
        """Score a single document (no normalisation applied)."""
        sw, hw, ew = self._get_weights(query_type, model)
        return sw * simrank + hw * horn + ew * embedding

    def rank(
        self,
        documents: List[Dict],
        query_type: Optional[str] = None,
        model: str = "lambdamart",
    ) -> List[Dict]:
        """
        Rank a list of document dicts in-place and return them sorted.

        Each dict must contain 'simrank_score', 'horn_score', 'embedding_score'.
        A 'hybrid_score' key is added/updated on each dict.

        Args:
            documents: List of dicts with component scores.
            query_type: Optional query type for adaptive weights.
            model: LTR model name for weight lookup.

        Returns:
            Documents sorted by hybrid_score descending.
        """
        if not documents:
            return documents

        sr = [d.get("simrank_score", 0.0) for d in documents]
        hn = [d.get("horn_score", 0.0) for d in documents]
        em = [d.get("embedding_score", 0.0) for d in documents]

        scores = self.score(sr, hn, em, query_type=query_type, model=model)

        for doc, s in zip(documents, scores):
            doc["hybrid_score"] = round(float(s), 6)

        documents.sort(key=lambda d: d["hybrid_score"], reverse=True)
        return documents

    def get_weights(
        self, query_type: Optional[str] = None, model: str = "lambdamart"
    ) -> Tuple[float, float, float]:
        """Return (simrank_w, horn_w, embedding_w) for the given query type."""
        return self._get_weights(query_type, model)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _get_weights(
        self, query_type: Optional[str], model: str
    ) -> Tuple[float, float, float]:
        """Resolve weights: learned > defaults."""
        if query_type and self._learned_weights:
            model_table = (
                self._learned_weights.get(model)
                or next(iter(self._learned_weights.values()), None)
            )
            if model_table and query_type in model_table:
                w = model_table[query_type]
                sw = float(w.get("simrank_weight", self.simrank_weight))
                hw = float(w.get("horn_index_weight", self.horn_weight))
                ew = float(w.get("embedding_weight", self.embedding_weight))
                # Re-normalise in case weights don't sum to 1
                total = sw + hw + ew
                if total > 0:
                    sw, hw, ew = sw / total, hw / total, ew / total
                return sw, hw, ew
        return self.simrank_weight, self.horn_weight, self.embedding_weight

    @staticmethod
    def _minmax(arr: np.ndarray) -> np.ndarray:
        lo, hi = arr.min(), arr.max()
        if hi - lo < 1e-9:
            return np.zeros_like(arr)
        return (arr - lo) / (hi - lo)

    @staticmethod
    def _validate_weights(sw: float, hw: float, ew: float):
        total = sw + hw + ew
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"Weights must sum to 1.0, got {sw}+{hw}+{ew}={total:.6f}"
            )
        if any(w < 0 for w in (sw, hw, ew)):
            raise ValueError("All weights must be non-negative.")


# ── Convenience factory ───────────────────────────────────────────────────────

def load_hybrid_ranker(
    learned_weights_path: str = "models/ranker/learned_weights.json",
    normalize: bool = True,
) -> HybridRanker:
    """
    Create a HybridRanker with learned weights if available,
    falling back to architecture defaults (0.4 / 0.3 / 0.3).
    """
    return HybridRanker(
        simrank_weight=DEFAULT_SIMRANK_WEIGHT,
        horn_weight=DEFAULT_HORN_WEIGHT,
        embedding_weight=DEFAULT_EMBEDDING_WEIGHT,
        learned_weights_path=learned_weights_path,
        normalize=normalize,
    )


if __name__ == "__main__":
    ranker = load_hybrid_ranker()

    docs = [
        {"doc_id": "doc_1", "simrank_score": 0.9, "horn_score": 0.8, "embedding_score": 0.7},
        {"doc_id": "doc_2", "simrank_score": 0.3, "horn_score": 0.95, "embedding_score": 0.6},
        {"doc_id": "doc_3", "simrank_score": 0.6, "horn_score": 0.5, "embedding_score": 0.9},
    ]

    print("Fixed weights (default):")
    ranked = ranker.rank([d.copy() for d in docs])
    for d in ranked:
        print(f"  {d['doc_id']}: {d['hybrid_score']:.4f}")

    print("\nAdaptive weights (concept_focused):")
    ranked = ranker.rank([d.copy() for d in docs], query_type="concept_focused")
    for d in ranked:
        print(f"  {d['doc_id']}: {d['hybrid_score']:.4f}")
