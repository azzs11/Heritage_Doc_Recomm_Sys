"""
Feature Extractor for Learning to Rank

Extracts comprehensive features for each query-document pair to enable
ML-based ranking optimization.
"""

import os
import numpy as np
from typing import Dict, List, Tuple, Set
from dataclasses import dataclass
import pickle
import json


@dataclass
class QueryDocFeatures:
    """Feature vector for a query-document pair"""
    query_id: str
    doc_id: str

    # Component scores (3 features)
    simrank_score: float
    horn_index_score: float
    embedding_similarity: float

    # Normalized scores (3 features)
    simrank_normalized: float
    horn_index_normalized: float
    embedding_normalized: float

    # Query-document overlap (4 features)
    heritage_type_match: float  # Binary + weighted
    domain_overlap: float  # Jaccard similarity
    time_period_match: float
    region_match: float

    # Document features (4 features)
    cluster_id: int
    node_degree: float  # In knowledge graph
    doc_length: float  # Normalized
    doc_completeness: float  # Metadata completeness

    # Query features (4 features)
    num_entities: int
    query_length: int
    query_complexity: float  # Linguistic complexity score
    query_type_encoding: int  # 0-3 for 4 query types

    # Ground truth (if available)
    relevance_label: int = -1  # 0-3 scale, -1 = unlabeled

    def to_feature_vector(self) -> np.ndarray:
        """Convert to numpy array for ML models"""
        return np.array([
            # Component scores
            self.simrank_score,
            self.horn_index_score,
            self.embedding_similarity,
            # Normalized scores
            self.simrank_normalized,
            self.horn_index_normalized,
            self.embedding_normalized,
            # Overlap features
            self.heritage_type_match,
            self.domain_overlap,
            self.time_period_match,
            self.region_match,
            # Document features
            float(self.cluster_id),
            self.node_degree,
            self.doc_length,
            self.doc_completeness,
            # Query features
            float(self.num_entities),
            float(self.query_length),
            self.query_complexity,
            float(self.query_type_encoding)
        ])

    @staticmethod
    def feature_names() -> List[str]:
        """Get feature names for interpretability"""
        return [
            'simrank_score', 'horn_index_score', 'embedding_similarity',
            'simrank_normalized', 'horn_index_normalized', 'embedding_normalized',
            'heritage_type_match', 'domain_overlap', 'time_period_match', 'region_match',
            'cluster_id', 'node_degree', 'doc_length', 'doc_completeness',
            'num_entities', 'query_length', 'query_complexity', 'query_type_encoding'
        ]


class FeatureExtractor:
    """Extract ranking features from queries and documents"""

    def __init__(self,
                 kg_file: str,
                 document_metadata_file: str,
                 entity_importance_file: str = None):
        """
        Initialize feature extractor

        Args:
            kg_file: Path to knowledge graph pickle
            document_metadata_file: Path to document metadata JSON
            entity_importance_file: Path to entity importance scores
        """
        self.kg = self._load_kg(kg_file)
        self.doc_metadata = self._load_metadata(document_metadata_file)
        self.entity_importance = self._load_entity_importance(entity_importance_file) if entity_importance_file else {}

        # Heritage domain vocabulary
        self.heritage_types = {
            'monument', 'temple', 'fort', 'palace', 'stupa', 'mosque', 'church',
            'tomb', 'memorial', 'archaeological site', 'cave', 'stepwell'
        }

        self.time_periods = {
            'ancient', 'medieval', 'modern', 'prehistoric', 'vedic', 'mauryan',
            'gupta', 'mughal', 'colonial', 'post-independence'
        }

        self.regions = {
            'north india', 'south india', 'east india', 'west india', 'central india',
            'delhi', 'agra', 'jaipur', 'rajasthan', 'maharashtra', 'tamil nadu',
            'karnataka', 'kerala', 'bengal', 'odisha', 'madhya pradesh'
        }

    def _load_kg(self, kg_file: str):
        """Load knowledge graph"""
        try:
            with open(kg_file, 'rb') as f:
                return pickle.load(f)
        except FileNotFoundError:
            print(f"Warning: KG file not found: {kg_file}")
            return None

    def _load_metadata(self, metadata_file: str) -> Dict:
        """Load document metadata"""
        try:
            with open(metadata_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Warning: Metadata file not found: {metadata_file}")
            return {}

    def _load_entity_importance(self, importance_file: str) -> Dict:
        """Load entity importance scores"""
        try:
            with open(importance_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Warning: Entity importance file not found: {importance_file}")
            return {}

    def extract_features(self,
                        query_id: str,
                        query_text: str,
                        doc_id: str,
                        query_entities: List[str],
                        simrank_score: float,
                        horn_score: float,
                        embedding_score: float,
                        all_scores: Dict[str, List[float]] = None,
                        relevance_label: int = -1) -> QueryDocFeatures:
        """
        Extract all features for a query-document pair

        Args:
            query_id: Query identifier
            query_text: Query text
            doc_id: Document identifier
            query_entities: Extracted entities from query
            simrank_score: SimRank similarity score
            horn_score: Horn's Index weighted score
            embedding_score: Embedding similarity score
            all_scores: Dict of all scores for normalization
            relevance_label: Ground truth relevance (0-3)

        Returns:
            QueryDocFeatures object
        """
        # Normalize component scores (z-score normalization)
        simrank_norm = self._normalize_score(simrank_score, all_scores.get('simrank', [])) if all_scores else simrank_score
        horn_norm = self._normalize_score(horn_score, all_scores.get('horn', [])) if all_scores else horn_score
        embedding_norm = self._normalize_score(embedding_score, all_scores.get('embedding', [])) if all_scores else embedding_score

        # Query-document overlap features
        doc_metadata = self.doc_metadata.get(doc_id, {})
        heritage_match = self._compute_heritage_type_match(query_text, doc_metadata)
        domain_overlap = self._compute_domain_overlap(query_entities, doc_metadata)
        time_match = self._compute_time_period_match(query_text, doc_metadata)
        region_match = self._compute_region_match(query_text, doc_metadata)

        # Document features
        cluster_id = doc_metadata.get('cluster_id', 0)
        node_degree = self._get_node_degree(doc_id)
        doc_length = self._normalize_doc_length(doc_metadata.get('content_length', 0))
        doc_completeness = self._compute_completeness(doc_metadata)

        # Query features
        num_entities = len(query_entities)
        query_length = len(query_text.split())
        query_complexity = self._compute_query_complexity(query_text)
        query_type = self._classify_query_type(query_text, query_entities)

        return QueryDocFeatures(
            query_id=query_id,
            doc_id=doc_id,
            simrank_score=simrank_score,
            horn_index_score=horn_score,
            embedding_similarity=embedding_score,
            simrank_normalized=simrank_norm,
            horn_index_normalized=horn_norm,
            embedding_normalized=embedding_norm,
            heritage_type_match=heritage_match,
            domain_overlap=domain_overlap,
            time_period_match=time_match,
            region_match=region_match,
            cluster_id=cluster_id,
            node_degree=node_degree,
            doc_length=doc_length,
            doc_completeness=doc_completeness,
            num_entities=num_entities,
            query_length=query_length,
            query_complexity=query_complexity,
            query_type_encoding=query_type,
            relevance_label=relevance_label
        )

    def _normalize_score(self, score: float, all_scores: List[float]) -> float:
        """Z-score normalization"""
        if not all_scores or len(all_scores) < 2:
            return score
        mean = np.mean(all_scores)
        std = np.std(all_scores)
        if std == 0:
            return 0.0
        return (score - mean) / std

    def _compute_heritage_type_match(self, query_text: str, doc_metadata: Dict) -> float:
        """Binary + weighted heritage type matching"""
        query_lower = query_text.lower()
        doc_types = set(doc_metadata.get('heritage_types', []))

        # Binary match
        binary_match = 0.0
        for h_type in self.heritage_types:
            if h_type in query_lower and h_type in ' '.join(doc_types).lower():
                binary_match = 1.0
                break

        # Weighted by type importance (UNESCO > ASI > local)
        weighted_match = 0.0
        if 'unesco' in doc_metadata.get('tags', []):
            weighted_match += 0.5
        if 'asi' in doc_metadata.get('tags', []):
            weighted_match += 0.3

        return min(binary_match + weighted_match, 1.0)

    def _compute_domain_overlap(self, query_entities: List[str], doc_metadata: Dict) -> float:
        """Jaccard similarity between query entities and document entities"""
        query_set = set(e.lower() for e in query_entities)
        doc_entities = set(e.lower() for e in doc_metadata.get('entities', []))

        if not query_set or not doc_entities:
            return 0.0

        intersection = query_set.intersection(doc_entities)
        union = query_set.union(doc_entities)

        return len(intersection) / len(union) if union else 0.0

    def _compute_time_period_match(self, query_text: str, doc_metadata: Dict) -> float:
        """Match time periods between query and document"""
        query_lower = query_text.lower()
        doc_period = doc_metadata.get('time_period', '').lower()

        for period in self.time_periods:
            if period in query_lower and period in doc_period:
                return 1.0

        return 0.0

    def _compute_region_match(self, query_text: str, doc_metadata: Dict) -> float:
        """Match geographic regions"""
        query_lower = query_text.lower()
        doc_location = doc_metadata.get('location', '').lower()

        for region in self.regions:
            if region in query_lower and region in doc_location:
                return 1.0

        return 0.0

    def _get_node_degree(self, doc_id: str) -> float:
        """Get normalized node degree from KG"""
        if self.kg is None:
            return 0.0

        try:
            degree = self.kg.degree(doc_id)
            max_degree = max(dict(self.kg.degree()).values()) if self.kg.number_of_nodes() > 0 else 1
            return degree / max_degree if max_degree > 0 else 0.0
        except:
            return 0.0

    def _normalize_doc_length(self, length: int) -> float:
        """Normalize document length to [0, 1]"""
        # Assume typical heritage doc is 500-5000 words
        return min(length / 5000.0, 1.0)

    def _compute_completeness(self, doc_metadata: Dict) -> float:
        """Compute metadata completeness score"""
        required_fields = ['title', 'content', 'heritage_types', 'location', 'time_period']
        present = sum(1 for field in required_fields if doc_metadata.get(field))
        return present / len(required_fields)

    def _compute_query_complexity(self, query_text: str) -> float:
        """Compute linguistic complexity score"""
        words = query_text.split()

        # Length-based complexity
        length_score = min(len(words) / 20.0, 1.0)  # 20+ words = complex

        # Linguistic markers
        complex_markers = ['how', 'why', 'what', 'which', 'compare', 'difference', 'relationship']
        marker_score = sum(1 for marker in complex_markers if marker in query_text.lower()) / len(complex_markers)

        return (length_score + marker_score) / 2.0

    def _classify_query_type(self, query_text: str, query_entities: List[str]) -> int:
        """
        Classify query type for adaptive weighting

        Returns:
            0: simple_keyword (1-3 words, no entities)
            1: entity_focused (specific monument/person/org)
            2: concept_focused (architectural style, domain concepts)
            3: complex_nlp (natural language question)
        """
        words = query_text.split()
        query_lower = query_text.lower()

        # Complex NLP: questions, long queries
        if any(q in query_lower for q in ['how', 'why', 'what', 'which', 'where', 'when']) or len(words) > 10:
            return 3

        # Entity-focused: has entities, specific names
        if query_entities and len(query_entities) >= 1:
            # Check if entity is a specific monument/person
            entity_lower = query_entities[0].lower()
            if any(word in entity_lower for word in ['temple', 'fort', 'palace', 'tomb', 'emperor', 'king']):
                return 1

        # Concept-focused: architectural styles, domains
        concept_keywords = ['architecture', 'style', 'dynasty', 'empire', 'period', 'art', 'culture']
        if any(kw in query_lower for kw in concept_keywords):
            return 2

        # Simple keyword: default
        return 0


def _get_relevance_label_from_gt(query_data: dict, doc_id: str) -> int:
    """
    Extract relevance label from a GT query, handling both v1 and v2.0 formats.

    v1 format:  query_data['annotations'] = [{'doc_id': 'doc_12', 'relevance': 3}, ...]
    v2.0 format: query_data['relevance_judgments'] = {'12': [{'relevance_level': 3, ...}], ...}

    Args:
        query_data: Single query dict from ground truth
        doc_id: Document node ID in the form "doc_N"

    Returns:
        Relevance label (0-3) or -1 if not annotated
    """
    # v2.0 format: relevance_judgments keyed by numeric string
    if 'relevance_judgments' in query_data:
        # doc_id is "doc_12" → key is "12"
        numeric_key = doc_id.replace('doc_', '') if doc_id.startswith('doc_') else doc_id
        judgments = query_data['relevance_judgments'].get(numeric_key, [])
        if judgments:
            # Average across annotators, round to int
            levels = [j['relevance_level'] for j in judgments if 'relevance_level' in j]
            if levels:
                return round(sum(levels) / len(levels))
        return -1

    # v1 format: annotations list
    for annotation in query_data.get('annotations', []):
        ann_doc = annotation.get('doc_id', '')
        # Support "doc_12", "12", or 12 as doc identifier
        if str(ann_doc) == doc_id or str(ann_doc) == doc_id.replace('doc_', ''):
            return annotation.get('relevance', -1)

    return -1


def create_training_dataset(ground_truth_file: str,
                           recommender_results_file: str,
                           feature_extractor: FeatureExtractor,
                           output_file: str):
    """
    Create training dataset from ground truth and recommender results.
    Supports both v1 (annotations list) and v2.0 (relevance_judgments dict) GT formats.

    Args:
        ground_truth_file: Ground truth annotations with relevance labels
        recommender_results_file: Recommender output with scores
        feature_extractor: FeatureExtractor instance
        output_file: Output file for training data
    """
    with open(ground_truth_file, 'r') as f:
        ground_truth = json.load(f)

    with open(recommender_results_file, 'r') as f:
        recommender_results = json.load(f)

    training_samples = []

    for query_data in ground_truth['queries']:
        query_id = query_data['query_id']
        query_text = query_data['query_text']

        # Build entity list from structured GT fields (v2.0) or explicit entities (v1)
        query_entities = query_data.get('entities', [])
        for field in ('heritage_types', 'domains'):
            query_entities = query_entities + query_data.get(field, [])

        # Get recommender results for this query
        results = recommender_results.get(query_id, {})
        if not results:
            print(f"Warning: no recommender results for query '{query_id}', skipping")
            continue

        doc_results = results.get('documents', [])

        # Pre-compute score lists for normalization
        all_scores = {
            'simrank': [d['simrank_score'] for d in doc_results],
            'horn': [d['horn_score'] for d in doc_results],
            'embedding': [d['embedding_score'] for d in doc_results],
        }

        for doc_result in doc_results:
            doc_id = doc_result['doc_id']

            relevance = _get_relevance_label_from_gt(query_data, doc_id)

            # Skip if no label
            if relevance == -1:
                continue

            # Extract features
            features = feature_extractor.extract_features(
                query_id=query_id,
                query_text=query_text,
                doc_id=doc_id,
                query_entities=query_entities,
                simrank_score=doc_result.get('simrank_score', 0.0),
                horn_score=doc_result.get('horn_score', 0.0),
                embedding_score=doc_result.get('embedding_score', 0.0),
                all_scores=all_scores,
                relevance_label=relevance
            )

            training_samples.append(features)

    # Save training data
    os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else '.', exist_ok=True)
    with open(output_file, 'wb') as f:
        pickle.dump(training_samples, f)

    print(f"Created training dataset: {len(training_samples)} samples")
    print(f"Saved to: {output_file}")

    return training_samples


if __name__ == '__main__':
    # Example usage
    extractor = FeatureExtractor(
        kg_file='data/knowledge_graph/heritage_kg.gpickle',
        document_metadata_file='data/processed/document_metadata.json',
        entity_importance_file='data/entity_importance/computed_scores.json'
    )

    # Test feature extraction
    features = extractor.extract_features(
        query_id='q1',
        query_text='Ancient Buddhist monuments in eastern India',
        doc_id='doc_123',
        query_entities=['Buddhist monuments', 'eastern India'],
        simrank_score=0.75,
        horn_score=0.85,
        embedding_score=0.65,
        relevance_label=3
    )

    print("Feature vector shape:", features.to_feature_vector().shape)
    print("Feature names:", QueryDocFeatures.feature_names())
    print("Query type:", features.query_type_encoding)
