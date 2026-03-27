"""
Ensemble Ranking Methods

Implements sophisticated fusion methods for combining ranking signals:
- Re-ranking cascade
- Reciprocal Rank Fusion (RRF)
- Borda count
- CombMNZ
"""

import numpy as np
from typing import List, Dict, Tuple
from dataclasses import dataclass


@dataclass
class RankedDocument:
    """Document with multiple ranking scores"""
    doc_id: str
    simrank_score: float
    horn_score: float
    embedding_score: float
    ltr_score: float = 0.0
    final_score: float = 0.0
    rank_position: int = -1


class EnsembleRanker:
    """Ensemble methods for ranking fusion"""

    def __init__(self, fusion_method: str = 'rrf'):
        """
        Initialize ensemble ranker

        Args:
            fusion_method: 'cascade', 'rrf', 'borda', or 'combmnz'
        """
        self.fusion_method = fusion_method

    def rank(self, documents: List[RankedDocument]) -> List[RankedDocument]:
        """
        Rank documents using ensemble method

        Args:
            documents: List of RankedDocument objects

        Returns:
            Ranked list of documents
        """
        if self.fusion_method == 'cascade':
            return self._cascade_reranking(documents)
        elif self.fusion_method == 'rrf':
            return self._reciprocal_rank_fusion(documents)
        elif self.fusion_method == 'borda':
            return self._borda_count(documents)
        elif self.fusion_method == 'combmnz':
            return self._combmnz(documents)
        else:
            raise ValueError(f"Unknown fusion method: {self.fusion_method}")

    def _cascade_reranking(self, documents: List[RankedDocument]) -> List[RankedDocument]:
        """
        Re-ranking Cascade

        Stage 1: FAISS (embedding) retrieves top-100 candidates (already done)
        Stage 2: SimRank re-ranks top-100 using graph structure
        Stage 3: Horn's Index refines top-20 using entity importance
        Stage 4: LTR model final ranking of top-20

        Args:
            documents: Initial candidate documents (top-100 from FAISS)

        Returns:
            Final ranked documents
        """
        # Stage 2: SimRank re-ranking (top-100)
        docs_sorted_simrank = sorted(documents, key=lambda d: d.simrank_score, reverse=True)[:100]

        # Stage 3: Horn's Index refinement (top-20)
        docs_sorted_horn = sorted(docs_sorted_simrank, key=lambda d: d.horn_score, reverse=True)[:20]

        # Stage 4: LTR final ranking
        if docs_sorted_horn and docs_sorted_horn[0].ltr_score > 0:
            # Use LTR scores if available
            docs_final = sorted(docs_sorted_horn, key=lambda d: d.ltr_score, reverse=True)
        else:
            # Fallback to weighted combination
            for doc in docs_sorted_horn:
                doc.final_score = 0.4 * doc.simrank_score + 0.4 * doc.horn_score + 0.2 * doc.embedding_score
            docs_final = sorted(docs_sorted_horn, key=lambda d: d.final_score, reverse=True)

        # Assign rank positions
        for rank, doc in enumerate(docs_final):
            doc.rank_position = rank + 1

        return docs_final

    def _reciprocal_rank_fusion(self, documents: List[RankedDocument], k: int = 60) -> List[RankedDocument]:
        """
        Reciprocal Rank Fusion (RRF)

        Combines rankings by summing reciprocal ranks:
        RRF_score(d) = sum_i [ 1 / (k + rank_i(d)) ]

        Robust to score scale differences and effective for combining
        heterogeneous ranking systems.

        Args:
            documents: Documents with multiple scores
            k: Constant to prevent division by zero (default: 60)

        Returns:
            Fused ranking
        """
        # Get rankings from each component
        simrank_ranking = {doc.doc_id: rank for rank, doc in enumerate(
            sorted(documents, key=lambda d: d.simrank_score, reverse=True), 1)}

        horn_ranking = {doc.doc_id: rank for rank, doc in enumerate(
            sorted(documents, key=lambda d: d.horn_score, reverse=True), 1)}

        embedding_ranking = {doc.doc_id: rank for rank, doc in enumerate(
            sorted(documents, key=lambda d: d.embedding_score, reverse=True), 1)}

        # Build LTR ranking once if any document has a non-zero LTR score
        has_ltr = any(doc.ltr_score > 0 for doc in documents)
        ltr_ranking = {}
        if has_ltr:
            ltr_ranking = {doc.doc_id: rank for rank, doc in enumerate(
                sorted(documents, key=lambda d: d.ltr_score, reverse=True), 1)}

        # Compute RRF scores
        for doc in documents:
            rrf_score = 0.0
            rrf_score += 1.0 / (k + simrank_ranking.get(doc.doc_id, 1000))
            rrf_score += 1.0 / (k + horn_ranking.get(doc.doc_id, 1000))
            rrf_score += 1.0 / (k + embedding_ranking.get(doc.doc_id, 1000))
            if has_ltr:
                rrf_score += 1.0 / (k + ltr_ranking.get(doc.doc_id, 1000))
            doc.final_score = rrf_score

        # Sort by RRF score
        docs_sorted = sorted(documents, key=lambda d: d.final_score, reverse=True)

        # Assign rank positions
        for rank, doc in enumerate(docs_sorted):
            doc.rank_position = rank + 1

        return docs_sorted

    def _borda_count(self, documents: List[RankedDocument]) -> List[RankedDocument]:
        """
        Borda Count

        Each ranking assigns points: top document gets n points,
        second gets n-1, etc. Sum points across all rankings.

        Args:
            documents: Documents with multiple scores

        Returns:
            Borda fused ranking
        """
        n = len(documents)

        # Get rankings from each component
        simrank_ranking = {doc.doc_id: n - rank for rank, doc in enumerate(
            sorted(documents, key=lambda d: d.simrank_score, reverse=True))}

        horn_ranking = {doc.doc_id: n - rank for rank, doc in enumerate(
            sorted(documents, key=lambda d: d.horn_score, reverse=True))}

        embedding_ranking = {doc.doc_id: n - rank for rank, doc in enumerate(
            sorted(documents, key=lambda d: d.embedding_score, reverse=True))}

        # Build LTR Borda ranking once if any document has a non-zero LTR score
        has_ltr = any(doc.ltr_score > 0 for doc in documents)
        ltr_ranking = {}
        if has_ltr:
            ltr_ranking = {doc.doc_id: n - rank for rank, doc in enumerate(
                sorted(documents, key=lambda d: d.ltr_score, reverse=True))}

        # Sum Borda points
        for doc in documents:
            borda_score = 0.0
            borda_score += simrank_ranking.get(doc.doc_id, 0)
            borda_score += horn_ranking.get(doc.doc_id, 0)
            borda_score += embedding_ranking.get(doc.doc_id, 0)
            if has_ltr:
                borda_score += ltr_ranking.get(doc.doc_id, 0)
            doc.final_score = borda_score

        # Sort by Borda score
        docs_sorted = sorted(documents, key=lambda d: d.final_score, reverse=True)

        # Assign rank positions
        for rank, doc in enumerate(docs_sorted):
            doc.rank_position = rank + 1

        return docs_sorted

    def _combmnz(self, documents: List[RankedDocument]) -> List[RankedDocument]:
        """
        CombMNZ (Combination with Multiply Non-Zero)

        Score = (sum of normalized scores) * (number of systems that retrieved doc)

        Gives bonus to documents retrieved by multiple systems.

        Args:
            documents: Documents with multiple scores

        Returns:
            CombMNZ fused ranking
        """
        # Normalize scores to [0, 1]
        simrank_scores = [d.simrank_score for d in documents]
        horn_scores = [d.horn_score for d in documents]
        embedding_scores = [d.embedding_score for d in documents]
        ltr_scores = [d.ltr_score for d in documents]

        simrank_max = max(simrank_scores) if simrank_scores else 1.0
        horn_max = max(horn_scores) if horn_scores else 1.0
        embedding_max = max(embedding_scores) if embedding_scores else 1.0
        ltr_max = max(ltr_scores) if ltr_scores else 0.0
        has_ltr = ltr_max > 0

        for doc in documents:
            # Normalized scores
            norm_simrank = doc.simrank_score / simrank_max if simrank_max > 0 else 0
            norm_horn = doc.horn_score / horn_max if horn_max > 0 else 0
            norm_embedding = doc.embedding_score / embedding_max if embedding_max > 0 else 0
            norm_ltr = doc.ltr_score / ltr_max if has_ltr else 0.0

            # Sum of scores
            score_sum = norm_simrank + norm_horn + norm_embedding + norm_ltr

            # Count non-zero systems
            non_zero_count = sum([
                norm_simrank > 0.01,
                norm_horn > 0.01,
                norm_embedding > 0.01,
                norm_ltr > 0.01,
            ])

            # CombMNZ score
            doc.final_score = score_sum * non_zero_count

        # Sort by CombMNZ score
        docs_sorted = sorted(documents, key=lambda d: d.final_score, reverse=True)

        # Assign rank positions
        for rank, doc in enumerate(docs_sorted):
            doc.rank_position = rank + 1

        return docs_sorted


class AdaptiveEnsemble:
    """
    Adaptive ensemble that selects fusion method based on query characteristics
    """

    def __init__(self):
        """Initialize adaptive ensemble"""
        self.method_performance = {
            'cascade': 0.0,
            'rrf': 0.0,
            'borda': 0.0,
            'combmnz': 0.0
        }

    def rank(self,
             documents: List[RankedDocument],
             query_complexity: float = 0.5,
             num_entities: int = 1) -> Tuple[List[RankedDocument], str]:
        """
        Select best fusion method based on query characteristics

        Args:
            documents: Documents to rank
            query_complexity: Query complexity score [0, 1]
            num_entities: Number of extracted entities

        Returns:
            (ranked_documents, selected_method)
        """
        # Selection heuristics:
        # - Cascade: Complex queries with entities (benefits from multi-stage)
        # - RRF: General purpose, robust to score scales
        # - Borda: Simple queries (rank-based is stable)
        # - CombMNZ: Entity-focused queries (rewards consensus)

        if query_complexity > 0.7 and num_entities >= 2:
            method = 'cascade'
        elif num_entities >= 3:
            method = 'combmnz'
        elif query_complexity < 0.3:
            method = 'borda'
        else:
            method = 'rrf'

        # Rank using selected method
        ranker = EnsembleRanker(fusion_method=method)
        ranked_docs = ranker.rank(documents)

        return ranked_docs, method

    def update_performance(self, method: str, ndcg: float):
        """Update performance tracking for a method"""
        # Exponential moving average
        alpha = 0.1
        self.method_performance[method] = (
            alpha * ndcg + (1 - alpha) * self.method_performance[method]
        )


def compare_fusion_methods(documents: List[RankedDocument],
                          ground_truth_relevance: Dict[str, int]) -> Dict[str, float]:
    """
    Compare all fusion methods on a query

    Args:
        documents: Documents with multiple scores
        ground_truth_relevance: {doc_id: relevance_label}

    Returns:
        NDCG@10 scores for each method
    """
    from sklearn.metrics import ndcg_score

    methods = ['cascade', 'rrf', 'borda', 'combmnz']
    results = {}

    # Ground truth relevance array
    doc_ids_original = [d.doc_id for d in documents]
    y_true = np.array([ground_truth_relevance.get(doc_id, 0) for doc_id in doc_ids_original])

    for method in methods:
        ranker = EnsembleRanker(fusion_method=method)
        ranked_docs = ranker.rank(documents.copy())

        # Build score array aligned to original doc order
        ranked_order = {d.doc_id: rank for rank, d in enumerate(ranked_docs)}
        # y_pred: higher score = earlier rank = more relevant; invert rank
        n = len(doc_ids_original)
        y_pred = np.array([n - ranked_order.get(doc_id, n) for doc_id in doc_ids_original], dtype=float)

        # Compute NDCG@10
        if len(y_pred) > 0:
            ndcg = ndcg_score(y_true.reshape(1, -1), y_pred.reshape(1, -1), k=min(10, n))
            results[method] = ndcg
        else:
            results[method] = 0.0

    return results


if __name__ == '__main__':
    # Example usage
    print("Ensemble Ranking Methods")
    print("="*60)

    # Create sample documents
    sample_docs = [
        RankedDocument('doc1', simrank_score=0.9, horn_score=0.8, embedding_score=0.7),
        RankedDocument('doc2', simrank_score=0.7, horn_score=0.9, embedding_score=0.85),
        RankedDocument('doc3', simrank_score=0.85, horn_score=0.75, embedding_score=0.8),
        RankedDocument('doc4', simrank_score=0.6, horn_score=0.7, embedding_score=0.9),
        RankedDocument('doc5', simrank_score=0.5, horn_score=0.6, embedding_score=0.65),
    ]

    # Test each fusion method
    for method in ['cascade', 'rrf', 'borda', 'combmnz']:
        print(f"\n{method.upper()} Fusion:")
        ranker = EnsembleRanker(fusion_method=method)
        ranked = ranker.rank(sample_docs.copy())

        for doc in ranked[:3]:
            print(f"  Rank {doc.rank_position}: {doc.doc_id} (score: {doc.final_score:.4f})")
