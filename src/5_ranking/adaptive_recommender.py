"""
Adaptive Recommender Integration

Integrates learned weights and query-type-specific ranking into the
heritage document recommender system.
"""

import os
import sys
import pickle
from typing import List, Dict, Tuple
import numpy as np

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from query_classifier import QueryTypeClassifier
from learned_ranker import LearnedRanker, RankingWeights
from ensemble_ranker import EnsembleRanker, AdaptiveEnsemble, RankedDocument


class AdaptiveRecommender:
    """
    Adaptive heritage document recommender with learned weights

    Features:
    - Query type classification
    - Query-specific weight adaptation
    - Ensemble ranking methods
    - Fallback to fixed weights
    - Confidence-based weighting
    """

    def __init__(self,
                 classifier_path: str = 'models/ranker/query_classifier.pkl',
                 ranker_path: str = 'models/ranker/lambdamart_model.pkl',
                 use_ensemble: bool = True,
                 ensemble_method: str = 'rrf'):
        """
        Initialize adaptive recommender

        Args:
            classifier_path: Path to trained query classifier
            ranker_path: Path to trained LTR model
            use_ensemble: Whether to use ensemble ranking
            ensemble_method: Ensemble method ('rrf', 'cascade', 'borda', 'combmnz', 'adaptive')
        """
        self.ranker = None
        self.use_ensemble = use_ensemble
        self.ensemble_method = ensemble_method

        # Always initialise the classifier so predict() is always callable.
        # load() sets is_trained=True; without it predict() falls back to rule-based.
        self.classifier = QueryTypeClassifier()
        if os.path.exists(classifier_path):
            self.classifier.load(classifier_path)
            print(f"Loaded query classifier from: {classifier_path}")
        else:
            print(f"Warning: Query classifier not found at {classifier_path}")
            print("Using rule-based classification")

        if os.path.exists(ranker_path):
            # Infer model type from filename
            if 'lambdamart' in ranker_path:
                model_type = 'lambdamart'
            elif 'ranknet' in ranker_path:
                model_type = 'ranknet'
            elif 'listnet' in ranker_path:
                model_type = 'listnet'
            else:
                model_type = 'lambdamart'

            self.ranker = LearnedRanker(model_type=model_type)
            self.ranker.load(ranker_path)
            print(f"Loaded LTR model from: {ranker_path}")
        else:
            print(f"Warning: LTR model not found at {ranker_path}")
            print("Using default fixed weights")

        # Initialize ensemble ranker
        if use_ensemble:
            if ensemble_method == 'adaptive':
                self.ensemble = AdaptiveEnsemble()
            else:
                self.ensemble = EnsembleRanker(fusion_method=ensemble_method)

    def get_adaptive_weights(self,
                           query_text: str,
                           query_entities: List[str],
                           fallback_weights: Dict[str, float] = None) -> Tuple[RankingWeights, str]:
        """
        Get adaptive weights for a query

        Args:
            query_text: Query text
            query_entities: Extracted entities
            fallback_weights: Default weights if models unavailable

        Returns:
            (RankingWeights, query_type)
        """
        # Default fallback
        if fallback_weights is None:
            fallback_weights = {
                'simrank': 0.4,
                'horn_index': 0.3,
                'embedding': 0.3
            }

        # Classify query type (falls back to rule-based if not trained)
        query_type_id, query_type, confidence = self.classifier.predict(query_text, query_entities)

        # Get learned weights
        if self.ranker and self.ranker.is_trained:
            weights = self.ranker.get_weights_for_query_type(query_type)

            # If confidence is low, blend with fallback
            if weights.confidence < 0.5:
                alpha = weights.confidence  # Interpolation factor
                weights.simrank_weight = alpha * weights.simrank_weight + (1 - alpha) * fallback_weights['simrank']
                weights.horn_index_weight = alpha * weights.horn_index_weight + (1 - alpha) * fallback_weights['horn_index']
                weights.embedding_weight = alpha * weights.embedding_weight + (1 - alpha) * fallback_weights['embedding']
                weights.normalize()
        else:
            # Use fallback weights
            weights = RankingWeights(
                query_type=query_type,
                simrank_weight=fallback_weights['simrank'],
                horn_index_weight=fallback_weights['horn_index'],
                embedding_weight=fallback_weights['embedding'],
                confidence=0.5
            )

        return weights, query_type

    def rank_documents(self,
                      documents: List[Dict],
                      query_text: str,
                      query_entities: List[str],
                      query_complexity: float = 0.5) -> List[Dict]:
        """
        Rank documents using adaptive weights and ensemble methods

        Args:
            documents: List of documents with component scores
                      Each document should have:
                      - doc_id
                      - simrank_score
                      - horn_score
                      - embedding_score
                      - (optional) ltr_score
            query_text: Query text
            query_entities: Extracted entities
            query_complexity: Query complexity score [0, 1]

        Returns:
            Ranked list of documents with final_score
        """
        # Get adaptive weights
        weights, query_type = self.get_adaptive_weights(query_text, query_entities)

        print(f"\nQuery type: {query_type}")
        print(f"Adaptive weights: SimRank={weights.simrank_weight:.3f}, "
              f"Horn={weights.horn_index_weight:.3f}, "
              f"Embedding={weights.embedding_weight:.3f} "
              f"(confidence: {weights.confidence:.3f})")

        if self.use_ensemble:
            # Use ensemble ranking
            ranked_docs = self._ensemble_ranking(
                documents, weights, query_complexity, len(query_entities)
            )
        else:
            # Use weighted sum
            ranked_docs = self._weighted_ranking(documents, weights)

        return ranked_docs

    def _weighted_ranking(self, documents: List[Dict], weights: RankingWeights) -> List[Dict]:
        """Simple weighted sum ranking"""
        for doc in documents:
            doc['final_score'] = (
                weights.simrank_weight * doc.get('simrank_score', 0.0) +
                weights.horn_index_weight * doc.get('horn_score', 0.0) +
                weights.embedding_weight * doc.get('embedding_score', 0.0)
            )

        # Sort by final score
        ranked_docs = sorted(documents, key=lambda d: d['final_score'], reverse=True)

        # Add rank position
        for rank, doc in enumerate(ranked_docs):
            doc['rank'] = rank + 1

        return ranked_docs

    def _ensemble_ranking(self,
                         documents: List[Dict],
                         weights: RankingWeights,
                         query_complexity: float,
                         num_entities: int) -> List[Dict]:
        """Ensemble ranking with fusion methods"""
        # Convert to RankedDocument objects
        ranked_docs_objs = [
            RankedDocument(
                doc_id=doc['doc_id'],
                simrank_score=doc.get('simrank_score', 0.0),
                horn_score=doc.get('horn_score', 0.0),
                embedding_score=doc.get('embedding_score', 0.0),
                ltr_score=doc.get('ltr_score', 0.0)
            )
            for doc in documents
        ]

        # Apply ensemble ranking
        if self.ensemble_method == 'adaptive':
            ranked_objs, selected_method = self.ensemble.rank(
                ranked_docs_objs, query_complexity, num_entities
            )
            print(f"Ensemble method: {selected_method}")
        else:
            ranked_objs = self.ensemble.rank(ranked_docs_objs)
            print(f"Ensemble method: {self.ensemble_method}")

        # Convert back to dict format
        ranked_docs = []
        for rank, doc_obj in enumerate(ranked_objs):
            # Find original document
            orig_doc = next(d for d in documents if d['doc_id'] == doc_obj.doc_id)

            # Add ranking info
            orig_doc['final_score'] = doc_obj.final_score
            orig_doc['rank'] = rank + 1

            ranked_docs.append(orig_doc)

        return ranked_docs

    def explain_ranking(self, document: Dict, weights: RankingWeights) -> str:
        """
        Generate explanation for document ranking

        Args:
            document: Document with component scores
            weights: Weights used for ranking

        Returns:
            Explanation string
        """
        simrank = document.get('simrank_score', 0.0)
        horn = document.get('horn_score', 0.0)
        embedding = document.get('embedding_score', 0.0)
        final = document.get('final_score', 0.0)

        explanation = f"Ranking for: {document.get('title', document['doc_id'])}\n"
        explanation += f"  Final score: {final:.4f}\n\n"
        explanation += "  Component contributions:\n"
        explanation += f"    SimRank:   {simrank:.4f} × {weights.simrank_weight:.3f} = {simrank * weights.simrank_weight:.4f}\n"
        explanation += f"    Horn:      {horn:.4f} × {weights.horn_index_weight:.3f} = {horn * weights.horn_index_weight:.4f}\n"
        explanation += f"    Embedding: {embedding:.4f} × {weights.embedding_weight:.3f} = {embedding * weights.embedding_weight:.4f}\n"

        # Identify strongest component
        contributions = [
            ('graph structure (SimRank)', simrank * weights.simrank_weight),
            ('entity importance (Horn)', horn * weights.horn_index_weight),
            ('semantic similarity (embedding)', embedding * weights.embedding_weight)
        ]
        strongest = max(contributions, key=lambda x: x[1])

        explanation += f"\n  Primary ranking factor: {strongest[0]} ({strongest[1]:.4f})"

        return explanation


def demo_adaptive_ranking():
    """Demonstrate adaptive ranking with sample queries"""
    print("\n" + "="*80)
    print("ADAPTIVE RANKING DEMONSTRATION")
    print("="*80)

    # Initialize adaptive recommender
    recommender = AdaptiveRecommender(
        use_ensemble=True,
        ensemble_method='adaptive'
    )

    # Sample queries
    test_queries = [
        {
            'text': 'taj mahal',
            'entities': ['taj mahal'],
            'complexity': 0.2
        },
        {
            'text': 'mughal architecture',
            'entities': ['mughal architecture'],
            'complexity': 0.4
        },
        {
            'text': 'what are the main features of indo-islamic architecture',
            'entities': ['indo-islamic architecture'],
            'complexity': 0.9
        },
        {
            'text': 'ancient buddhist monuments in eastern india',
            'entities': ['buddhist monuments', 'eastern india'],
            'complexity': 0.7
        }
    ]

    # Sample documents
    sample_docs = [
        {
            'doc_id': 'doc_001',
            'title': 'Taj Mahal: A Mughal Masterpiece',
            'simrank_score': 0.85,
            'horn_score': 0.92,
            'embedding_score': 0.78
        },
        {
            'doc_id': 'doc_002',
            'title': 'Indo-Islamic Architecture in India',
            'simrank_score': 0.72,
            'horn_score': 0.68,
            'embedding_score': 0.88
        },
        {
            'doc_id': 'doc_003',
            'title': 'Buddhist Heritage Sites',
            'simrank_score': 0.65,
            'horn_score': 0.75,
            'embedding_score': 0.82
        }
    ]

    # Test each query
    for query in test_queries:
        print("\n" + "-"*80)
        print(f"Query: '{query['text']}'")

        ranked_docs = recommender.rank_documents(
            documents=sample_docs.copy(),
            query_text=query['text'],
            query_entities=query['entities'],
            query_complexity=query['complexity']
        )

        print("\nTop ranked documents:")
        for doc in ranked_docs[:3]:
            print(f"  {doc['rank']}. {doc['title']} (score: {doc['final_score']:.4f})")


if __name__ == '__main__':
    demo_adaptive_ranking()
