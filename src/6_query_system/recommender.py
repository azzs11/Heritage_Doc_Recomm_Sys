"""
Hybrid Recommender for Heritage Document System

Combines three scoring components:
1. SimRank (0.4 weight): Structural graph similarity
2. Horn's Index (0.3 weight): Entity importance weights
3. Embedding Similarity (0.3 weight): Semantic similarity via FAISS

Provides explainable recommendations with KG path reasoning.
"""

import numpy as np
import pickle
import json
import faiss
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Set, Optional
import networkx as nx
import sys
import os

# Configure logging
logger = logging.getLogger(__name__)


class HeritageRecommender:
    """Hybrid recommender combining SimRank, Horn's Index, and embeddings."""

    def __init__(
        self,
        kg_path: str = 'knowledge_graph/heritage_kg.gpickle',
        simrank_path: str = 'knowledge_graph/simrank/simrank_matrix.npy',
        embeddings_path: str = 'data/embeddings/document_embeddings.npy',
        metadata_path: str = 'data/embeddings/embedding_mapping.json',
        faiss_index_path: str = 'models/ranker/faiss/hnsw_index.faiss',
        horn_weights_path: str = 'knowledge_graph/horn_weights.json',
        ltr_weights_path: str = 'models/ranker/learned_weights.json',
        query_classifier_path: str = 'models/ranker/query_classifier.pkl',
        simrank_weight: float = 0.4,
        horn_weight: float = 0.3,
        embedding_weight: float = 0.3,
        horn_fallback_value: float = 0.5
    ):
        """
        Initialize hybrid recommender.

        Args:
            kg_path: Path to knowledge graph pickle file
            simrank_path: Path to SimRank matrix
            embeddings_path: Path to document embeddings
            metadata_path: Path to embedding metadata
            faiss_index_path: Path to FAISS index
            horn_weights_path: Path to Horn's Index weights
            ltr_weights_path: Path to LTR learned weights JSON (optional)
            query_classifier_path: Path to trained query classifier pickle (optional)
            simrank_weight: Weight for SimRank score (default 0.4)
            horn_weight: Weight for Horn's Index score (default 0.3)
            embedding_weight: Weight for embedding similarity (default 0.3)
            horn_fallback_value: Fallback value when Horn weights unavailable (default 0.5)
        """
        print("Loading knowledge graph...")
        with open(kg_path, 'rb') as f:
            self.G = pickle.load(f)

        print("Loading SimRank matrix...")
        self.simrank_matrix = np.load(simrank_path)

        print("Loading embeddings...")
        self.embeddings = np.load(embeddings_path)

        print("Loading metadata...")
        with open(metadata_path, 'r', encoding='utf-8') as f:
            self.metadata = json.load(f)

        print("Loading FAISS index...")
        self.faiss_index = faiss.read_index(faiss_index_path)

        # Load Horn's weights if available
        self.horn_weights = {}
        if Path(horn_weights_path).exists():
            print("Loading Horn's Index weights...")
            with open(horn_weights_path, 'r', encoding='utf-8') as f:
                self.horn_weights = json.load(f)
        else:
            print("Warning: Horn's weights not found. Using uniform weights.")

        # Load LTR learned weights if available
        self.ltr_weights: Dict = {}
        if Path(ltr_weights_path).exists():
            print("Loading LTR learned weights...")
            with open(ltr_weights_path, 'r', encoding='utf-8') as f:
                self.ltr_weights = json.load(f)
        else:
            print("LTR learned weights not found. Using default weights.")

        # Add ranking module to path so pkl classes can be unpickled
        ranking_dir = str(Path(query_classifier_path).parent.parent.parent / 'src' / '5_ranking')
        if ranking_dir not in sys.path:
            sys.path.insert(0, ranking_dir)

        # Load query classifier if available
        self.query_classifier = None
        if Path(query_classifier_path).exists():
            print("Loading query classifier...")
            with open(query_classifier_path, 'rb') as f:
                self.query_classifier = pickle.load(f)
            print("Query classifier loaded.")
        else:
            print("Query classifier not found. Query-type adaptive ranking disabled.")

        # Load LTR model for per-document scoring (prefer lambdamart, fall back to others)
        self._ltr_model = None
        self._ltr_model_type = None
        for model_name in ('lambdamart_model.pkl', 'ranknet_model.pkl', 'listnet_model.pkl'):
            candidate = Path(ltr_weights_path).parent / model_name
            if candidate.exists():
                try:
                    with open(candidate, 'rb') as f:
                        model_data = pickle.load(f)
                    self._ltr_model = model_data.get('model')
                    self._ltr_model_type = model_data.get('model_type', 'lambdamart')
                    # For neural models, load state into wrapper
                    if self._ltr_model_type in ('ranknet', 'listnet') and 'model_state' in model_data:
                        import torch
                        if self._ltr_model_type == 'ranknet':
                            from learned_ranker import RankNet
                            net = RankNet(18)
                        else:
                            from learned_ranker import ListNet
                            net = ListNet(18)
                        net.load_state_dict(model_data['model_state'])
                        net.eval()
                        self._ltr_model = net
                    print(f"LTR model loaded: {model_name} ({self._ltr_model_type})")
                    break
                except Exception as e:
                    logger.warning("Could not load LTR model %s: %s", model_name, e)
        if self._ltr_model is None:
            print("No LTR model loaded. ltr_score will be 0.0.")

        # Scoring weights (defaults, overridden per-query by LTR if available)
        self.simrank_weight = simrank_weight
        self.horn_weight = horn_weight
        self.embedding_weight = embedding_weight
        self.horn_fallback_value = horn_fallback_value
        self._horn_fallback_logged = False  # Log warning only once

        # Create document index mapping
        self.doc_nodes = [n for n, d in self.G.nodes(data=True) if d.get('node_type') == 'document']
        self.doc_id_to_idx = {doc_id: idx for idx, doc_id in enumerate(self.doc_nodes)}
        self.idx_to_doc_id = {idx: doc_id for doc_id, idx in self.doc_id_to_idx.items()}

        # Precompute per-document entity sets for fast Horn score calculation
        _entity_types = {'location', 'person', 'organization', 'heritage_type', 'domain', 'time_period', 'region'}
        self._doc_entity_sets: dict = {
            doc_id: {
                nb for nb in self.G.neighbors(doc_id)
                if self.G.nodes[nb].get('node_type') in _entity_types
            }
            for doc_id in self.doc_nodes
        }

        print(f"Recommender initialized with {len(self.doc_nodes)} documents!")
        print(f"Weights: SimRank={simrank_weight}, Horn={horn_weight}, Embedding={embedding_weight}")

    def compute_simrank_score(self, query_doc_idx: int, candidate_doc_idx: int) -> float:
        """
        Compute SimRank similarity between two documents.

        Args:
            query_doc_idx: Index of query document
            candidate_doc_idx: Index of candidate document

        Returns:
            SimRank similarity score [0, 1]
        """
        if query_doc_idx >= len(self.simrank_matrix) or candidate_doc_idx >= len(self.simrank_matrix):
            return 0.0
        return self.simrank_matrix[query_doc_idx, candidate_doc_idx]

    def compute_horn_score(self, doc_id: str, parsed_query: Dict) -> float:
        """
        Compute Horn's Index score based on entity importance.

        Two-pass scoring:
        1. KG-based: overlap between query entities (as KG IDs) and the document's
           KG neighbours — weighted by precomputed Horn weights.
        2. Fallback text-entity matching: if the KG pass returns 0 (entity not in
           graph), check whether query location/person/org names appear literally
           in the document node's metadata.  This handles queries like "Taj Mahal"
           whose entity isn't a first-class KG node.

        Returns:
            Horn's Index score [0, 1]
        """
        if not self.horn_weights:
            if not self._horn_fallback_logged:
                logger.warning(f"Horn weights not available. Using fallback value: {self.horn_fallback_value}")
                self._horn_fallback_logged = True
            return self.horn_fallback_value

        # Use precomputed entity sets (avoids per-call graph traversal)
        doc_entities = self._doc_entity_sets.get(doc_id, set())

        # Convert query entities to KG entity IDs (with prefixes)
        query_entities = set()

        for heritage_type in parsed_query.get('heritage_types', []):
            query_entities.add(f"type_{heritage_type}")
        for domain in parsed_query.get('domains', []):
            query_entities.add(f"domain_{domain}")
        if parsed_query.get('time_period'):
            query_entities.add(f"period_{parsed_query['time_period']}")
        if parsed_query.get('region'):
            query_entities.add(f"region_{parsed_query['region']}")
        for location in parsed_query.get('locations', []):
            query_entities.add(f"loc_{location.lower().replace(' ', '_')}")
        for person in parsed_query.get('persons', []):
            query_entities.add(f"person_{person.lower().replace(' ', '_')}")
        for org in parsed_query.get('organizations', []):
            query_entities.add(f"org_{org.lower().replace(' ', '_')}")

        # ── Pass 1: KG graph overlap ────────────────────────────────────
        kg_score = 0.0
        if query_entities and doc_entities:
            matching_entities = doc_entities.intersection(query_entities)
            if matching_entities:
                total_weight = sum(self.horn_weights.get(entity, 0.5) for entity in matching_entities)
                kg_score = total_weight / len(matching_entities)

        if kg_score > 0.0:
            return kg_score

        # ── Pass 2: text-entity fallback ────────────────────────────────
        # For entities not represented in the KG (e.g. "Taj Mahal"), check
        # whether any query entity name appears in the document node's title
        # or its KG-neighbour labels.
        query_names = (
            [n.lower() for n in parsed_query.get('locations', [])] +
            [n.lower() for n in parsed_query.get('persons', [])] +
            [n.lower() for n in parsed_query.get('organizations', [])]
        )
        if not query_names:
            return 0.0

        # Build searchable text from the document's KG neighbourhood
        doc_data = self.G.nodes.get(doc_id, {})
        doc_title = (doc_data.get('title') or '').lower()

        # Collect labels of all neighbour nodes (entities in the KG connected to this doc)
        neighbour_labels = set()
        for nb in self.G.neighbors(doc_id):
            nb_data = self.G.nodes.get(nb, {})
            label = (nb_data.get('name') or nb_data.get('title') or nb).lower()
            neighbour_labels.add(label)

        matches = 0
        for name in query_names:
            # Check title
            if name in doc_title:
                matches += 1
                continue
            # Check neighbour labels (partial match — "taj mahal" in "the taj mahal")
            for label in neighbour_labels:
                if name in label or label in name:
                    matches += 1
                    break

        if matches == 0:
            return 0.0

        return min(1.0, 0.4 * (matches / len(query_names)))

    def compute_embedding_similarity(self, query_embedding: np.ndarray, doc_idx: int) -> float:
        """
        Compute cosine similarity between query and document embeddings.

        Args:
            query_embedding: Query embedding vector (384-dim)
            doc_idx: Document index in embeddings matrix

        Returns:
            Cosine similarity score [0, 1]
        """
        if doc_idx >= len(self.embeddings):
            return 0.0

        doc_embedding = self.embeddings[doc_idx]

        # Cosine similarity (both are L2-normalized)
        similarity = np.dot(query_embedding, doc_embedding)

        # Ensure [0, 1] range
        return max(0.0, min(1.0, similarity))

    def get_kg_path_explanation(self, source_doc_id: str, target_doc_id: str, max_paths: int = 3) -> List[List[str]]:
        """
        Find shortest paths between documents in KG for explanation.

        Args:
            source_doc_id: Source document node ID
            target_doc_id: Target document node ID
            max_paths: Maximum number of paths to return

        Returns:
            List of paths (each path is a list of node IDs)
        """
        try:
            path = nx.shortest_path(self.G, source=source_doc_id, target=target_doc_id)
            return [path]
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

    def format_path_explanation(self, path: List[str]) -> str:
        """
        Format a KG path into human-readable explanation.

        Args:
            path: List of node IDs in path

        Returns:
            Formatted path string
        """
        formatted_parts = []
        for node_id in path:
            node_data = self.G.nodes[node_id]
            node_type = node_data.get('node_type', 'unknown')

            if node_type == 'document':
                formatted_parts.append(f"[{node_data.get('title', node_id)}]")
            else:
                formatted_parts.append(f"({node_type}: {node_id})")

        return " � ".join(formatted_parts)

    def recommend(
        self,
        parsed_query: Dict,
        top_k: int = 10,
        candidates_k: Optional[int] = None,
        explain: bool = True,
        filter_period: Optional[List[str]] = None,
        filter_region: Optional[List[str]] = None,
        filter_heritage: Optional[List[str]] = None,
        filter_domain: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Generate top-K recommendations using hybrid scoring.

        Args:
            parsed_query: Parsed query from QueryProcessor
            top_k: Number of recommendations to return
            explain: Whether to include KG path explanations
            filter_period: Optional list of time periods to filter by (e.g., ['ancient', 'medieval'])
            filter_region: Optional list of regions to filter by (e.g., ['north', 'south'])
            filter_heritage: Optional list of heritage types to filter by (e.g., ['temple', 'fort'])
            filter_domain: Optional list of domains to filter by (e.g., ['religious', 'military'])

        Returns:
            List of recommendation dictionaries with scores and explanations
        """
        query_embedding = parsed_query['query_embedding']
        scores = []

        # Determine per-query weights via LTR (if classifier + weights available)
        simrank_w, horn_w, emb_w = self.simrank_weight, self.horn_weight, self.embedding_weight
        if self.query_classifier is not None:
            query_text = parsed_query.get('original_query', '')
            all_entities = (
                parsed_query.get('locations', []) +
                parsed_query.get('persons', []) +
                parsed_query.get('organizations', [])
            )
            try:
                _type_id, query_type_name, _conf = self.query_classifier.predict(query_text, all_entities)
                # Pick best available model's weights; prefer lambdamart, else first available
                model_weights = (
                    self.ltr_weights.get('lambdamart') or
                    next(iter(self.ltr_weights.values()), None)
                ) if self.ltr_weights else None
                if model_weights and query_type_name in model_weights:
                    w = model_weights[query_type_name]
                    simrank_w = w.get('simrank_weight', simrank_w)
                    horn_w = w.get('horn_index_weight', horn_w)
                    emb_w = w.get('embedding_weight', emb_w)
                    logger.debug(
                        "LTR weights for '%s': simrank=%.3f horn=%.3f emb=%.3f",
                        query_type_name, simrank_w, horn_w, emb_w,
                    )
            except Exception as e:
                logger.warning("Query classifier failed, using defaults: %s", e)

        # Select query document: single most embedding-similar document.
        # FAISS returns an index into the embeddings array; we must map that
        # back to the doc_nodes index used by the SimRank matrix.
        faiss_idx = self._get_top_k_similar_by_embedding(query_embedding, k=1)[0]

        # Map FAISS embedding index → document node id → doc_nodes index.
        # embedding_mapping.json maps doc_id → faiss_idx, so we build the
        # reverse lookup once from self.metadata.
        if not hasattr(self, '_faiss_to_docnode_idx'):
            # embedding_mapping.json has a 'documents' list; each entry has
            # 'index' (the FAISS position) which corresponds to KG node doc_{index}
            self._faiss_to_docnode_idx: dict = {}
            for doc in self.metadata.get('documents', []):
                faiss_i = doc['index']
                doc_id = f"doc_{faiss_i}"
                if doc_id in self.doc_id_to_idx:
                    self._faiss_to_docnode_idx[faiss_i] = self.doc_id_to_idx[doc_id]

        query_doc_idx = self._faiss_to_docnode_idx.get(faiss_idx, 0)

        # Compute hybrid scores for all documents — vectorized for speed
        n_docs = len(self.doc_nodes)

        # Embedding similarity: batch dot product against all doc embeddings
        valid_emb = min(n_docs, len(self.embeddings))
        emb_scores = np.zeros(n_docs, dtype=float)
        emb_scores[:valid_emb] = self.embeddings[:valid_emb].dot(query_embedding)

        # SimRank scores: single row lookup
        if query_doc_idx < len(self.simrank_matrix):
            simrank_row = self.simrank_matrix[query_doc_idx]
            valid_sr = min(n_docs, len(simrank_row))
            simrank_scores = np.zeros(n_docs, dtype=float)
            simrank_scores[:valid_sr] = simrank_row[:valid_sr]
        else:
            simrank_scores = np.zeros(n_docs, dtype=float)

        # Horn scores: computed per-doc (requires KG graph traversal)
        horn_scores = np.array([
            self.compute_horn_score(doc_id, parsed_query)
            for doc_id in self.doc_nodes
        ], dtype=float)

        hybrid_scores = simrank_w * simrank_scores + horn_w * horn_scores + emb_w * emb_scores

        scores = [
            {
                'doc_id': doc_id,
                'doc_idx': doc_idx,
                'hybrid_score': float(hybrid_scores[doc_idx]),
                'simrank_score': float(simrank_scores[doc_idx]),
                'horn_score': float(horn_scores[doc_idx]),
                'embedding_score': float(emb_scores[doc_idx]),
            }
            for doc_idx, doc_id in enumerate(self.doc_nodes)
        ]

        # Compute LTR scores in batch if a model is loaded
        if self._ltr_model is not None:
            try:
                # Build normalized component arrays for the full doc list
                all_sr = np.array([s['simrank_score'] for s in scores])
                all_hn = np.array([s['horn_score'] for s in scores])
                all_em = np.array([s['embedding_score'] for s in scores])

                def _minmax(arr):
                    lo, hi = arr.min(), arr.max()
                    return (arr - lo) / (hi - lo) if hi - lo > 1e-9 else np.zeros_like(arr)

                sr_norm = _minmax(all_sr)
                hn_norm = _minmax(all_hn)
                em_norm = _minmax(all_em)

                # Query-level features (constant across all docs for this query)
                all_entities = (
                    parsed_query.get('locations', []) +
                    parsed_query.get('persons', []) +
                    parsed_query.get('organizations', [])
                )
                num_entities = float(len(all_entities))
                query_text = parsed_query.get('original_query', '')
                query_len = float(len(query_text.split()))
                query_complexity = min(1.0, query_len / 20.0)
                query_type_enc = 0.0
                if self.query_classifier is not None:
                    try:
                        type_id, _, _ = self.query_classifier.predict(query_text, all_entities)
                        query_type_enc = float(type_id)
                    except Exception:
                        pass

                # Build feature matrix (18 features per doc, matching QueryDocFeatures.to_feature_vector)
                n_docs = len(scores)
                X = np.zeros((n_docs, 18), dtype=float)
                for i, (s, sr, hn, em, srn, hnn, emn) in enumerate(
                    zip(scores, all_sr, all_hn, all_em, sr_norm, hn_norm, em_norm)
                ):
                    doc_id = s['doc_id']
                    doc_data = self.G.nodes.get(doc_id, {})

                    # Overlap features
                    doc_ht = set(doc_data.get('heritage_types', []) or [])
                    q_ht = set(parsed_query.get('heritage_types', []))
                    ht_match = 1.0 if doc_ht & q_ht else 0.0

                    doc_dom = set(doc_data.get('domains', []) or [])
                    q_dom = set(parsed_query.get('domains', []))
                    dom_union = doc_dom | q_dom
                    dom_overlap = len(doc_dom & q_dom) / len(dom_union) if dom_union else 0.0

                    tp_match = 1.0 if (
                        parsed_query.get('time_period') and
                        doc_data.get('time_period') == parsed_query['time_period']
                    ) else 0.0
                    reg_match = 1.0 if (
                        parsed_query.get('region') and
                        doc_data.get('region') == parsed_query['region']
                    ) else 0.0

                    # Document graph features
                    node_degree = float(self.G.degree(doc_id)) if doc_id in self.G else 0.0

                    X[i] = [
                        sr, hn, em,        # raw component scores
                        srn, hnn, emn,     # normalized
                        ht_match, dom_overlap, tp_match, reg_match,  # overlap
                        0.0,               # cluster_id (not available at query time)
                        node_degree, 1.0, 1.0,  # node_degree, doc_length, doc_completeness
                        num_entities, query_len, query_complexity, query_type_enc,
                    ]

                # Predict
                if self._ltr_model_type == 'lambdamart':
                    ltr_scores = self._ltr_model.predict(X)
                else:
                    import torch
                    with torch.no_grad():
                        ltr_scores = self._ltr_model(torch.FloatTensor(X)).numpy()
                    if ltr_scores.ndim > 1:
                        ltr_scores = ltr_scores.squeeze(-1)

                # Normalise LTR scores to [0, 1] and inject
                ltr_min, ltr_max = ltr_scores.min(), ltr_scores.max()
                if ltr_max - ltr_min > 1e-9:
                    ltr_scores = (ltr_scores - ltr_min) / (ltr_max - ltr_min)
                else:
                    ltr_scores = np.zeros(n_docs)

                for s, ltr_s in zip(scores, ltr_scores):
                    s['ltr_score'] = float(ltr_s)

            except Exception as e:
                logger.warning("LTR scoring failed, ltr_score=0.0: %s", e)
                for s in scores:
                    s.setdefault('ltr_score', 0.0)
        else:
            for s in scores:
                s['ltr_score'] = 0.0

        # Sort by hybrid score
        scores = sorted(scores, key=lambda x: x['hybrid_score'], reverse=True)

        # Apply filters if provided (filter AFTER scoring, BEFORE selecting top-K)
        if any([filter_period, filter_region, filter_heritage, filter_domain]):
            scores = self._apply_filters(
                scores,
                filter_period,
                filter_region,
                filter_heritage,
                filter_domain
            )

        # Get top-K recommendations (or more candidates for ensemble re-ranking)
        fetch_k = candidates_k if candidates_k and candidates_k > top_k else top_k
        recommendations = []
        for rank, score_dict in enumerate(scores[:fetch_k], 1):
            doc_id = score_dict['doc_id']
            doc_data = self.G.nodes[doc_id]

            # Extract metadata (handle both arrays and single values)
            heritage_types = doc_data.get('heritage_types', [])
            domains = doc_data.get('domains', [])

            # Convert to display strings (join arrays with comma)
            heritage_display = ', '.join(heritage_types) if heritage_types else None
            domain_display = ', '.join(domains) if domains else None

            rec = {
                'rank': rank,
                'doc_id': doc_id,
                'title': doc_data.get('title', 'Unknown'),
                'hybrid_score': score_dict['hybrid_score'],
                'component_scores': {
                    'simrank': score_dict['simrank_score'],
                    'horn': score_dict['horn_score'],
                    'embedding': score_dict['embedding_score'],
                    'ltr': score_dict.get('ltr_score', 0.0),
                },
                'metadata': {
                    'heritage_type': heritage_display,
                    'domain': domain_display,
                    'time_period': doc_data.get('time_period'),
                    'region': doc_data.get('region')
                }
            }

            # Add KG path explanations
            if explain:
                # Find paths to top similar documents
                top_similar_docs = [scores[i]['doc_id'] for i in range(min(3, len(scores)))
                                  if scores[i]['doc_id'] != doc_id]

                explanations = []
                for similar_doc_id in top_similar_docs:
                    try:
                        paths = self.get_kg_path_explanation(similar_doc_id, doc_id, max_paths=1)
                        if paths:
                            path_str = self.format_path_explanation(paths[0])
                            explanations.append(path_str)
                    except Exception as e:
                        logger.warning(
                            "KG traversal failed for %s -> %s: %s",
                            similar_doc_id, doc_id, e,
                        )

                rec['kg_explanations'] = explanations

            recommendations.append(rec)

        return recommendations

    def _apply_filters(
        self,
        scores: List[Dict],
        filter_period: Optional[List[str]],
        filter_region: Optional[List[str]],
        filter_heritage: Optional[List[str]],
        filter_domain: Optional[List[str]]
    ) -> List[Dict]:
        """
        Filter scored documents based on metadata.

        All comparisons are case-insensitive (values normalised to lowercase).
        Empty / None filter lists are treated as "no filter".

        Args:
            scores: List of score dictionaries with doc_id
            filter_period: Time periods to filter by (empty list = no filter)
            filter_region: Regions to filter by (empty list = no filter)
            filter_heritage: Heritage types to filter by (empty list = no filter)
            filter_domain: Domains to filter by (empty list = no filter)

        Returns:
            Filtered list of score dictionaries
        """
        # Normalise filter values to lowercase sets for O(1) lookup
        norm_period  = {v.lower() for v in filter_period}  if filter_period  else set()
        norm_region  = {v.lower() for v in filter_region}  if filter_region  else set()
        norm_heritage = {v.lower() for v in filter_heritage} if filter_heritage else set()
        norm_domain  = {v.lower() for v in filter_domain}  if filter_domain  else set()

        filtered = []
        for score_dict in scores:
            doc_id = score_dict['doc_id']
            doc_data = self.G.nodes[doc_id]

            # Time period — single string value in graph node
            if norm_period:
                period = (doc_data.get('time_period') or '').lower()
                if period not in norm_period:
                    continue

            # Region — single string value in graph node
            if norm_region:
                region = (doc_data.get('region') or '').lower()
                if region not in norm_region:
                    continue

            # Heritage types — list in graph node; pass if ANY value matches
            if norm_heritage:
                heritage_types = doc_data.get('heritage_types', [])
                if isinstance(heritage_types, str):
                    heritage_types = [heritage_types]
                doc_ht = {h.lower() for h in heritage_types}
                if not doc_ht.intersection(norm_heritage):
                    continue

            # Domains — list in graph node; pass if ANY value matches
            if norm_domain:
                domains = doc_data.get('domains', [])
                if isinstance(domains, str):
                    domains = [domains]
                doc_dom = {d.lower() for d in domains}
                if not doc_dom.intersection(norm_domain):
                    continue

            filtered.append(score_dict)

        return filtered

    def _get_top_k_similar_by_embedding(self, query_embedding: np.ndarray, k: int = 5) -> List[int]:
        """
        Get top-K most similar documents by embedding similarity.

        Args:
            query_embedding: Query embedding vector
            k: Number of similar docs to retrieve

        Returns:
            List of document indices
        """
        # FAISS search
        query_embedding = query_embedding.reshape(1, -1).astype('float32')
        distances, indices = self.faiss_index.search(query_embedding, k)
        return indices[0].tolist()

    def format_recommendation(self, rec: Dict) -> str:
        """
        Format a recommendation for display.

        Args:
            rec: Recommendation dictionary

        Returns:
            Formatted string
        """
        lines = [
            f"#{rec['rank']} {rec['title']}",
            f"  Score: {rec['hybrid_score']:.4f} (SimRank: {rec['component_scores']['simrank']:.3f}, "
            f"Horn: {rec['component_scores']['horn']:.3f}, Embedding: {rec['component_scores']['embedding']:.3f})",
        ]

        # Metadata
        meta = rec['metadata']
        meta_parts = []
        if meta.get('heritage_type'):
            meta_parts.append(f"Type: {meta['heritage_type']}")
        if meta.get('domain'):
            meta_parts.append(f"Domain: {meta['domain']}")
        if meta.get('time_period'):
            meta_parts.append(f"Period: {meta['time_period']}")
        if meta.get('region'):
            meta_parts.append(f"Region: {meta['region']}")

        if meta_parts:
            lines.append(f"  {' | '.join(meta_parts)}")

        # KG explanations
        if rec.get('kg_explanations'):
            lines.append("  Why recommended:")
            for explanation in rec['kg_explanations'][:2]:  # Show top 2 paths
                lines.append(f"    • {explanation}")

        return '\n'.join(lines)


def main():
    """Test recommender with sample parsed queries."""
    from query_processor import QueryProcessor

    # Initialize
    processor = QueryProcessor()
    recommender = HeritageRecommender()

    # Test queries
    test_queries = [
        "Mughal temples in North India",
        "Ancient forts in Rajasthan",
        "Buddhist stupas and monasteries"
    ]

    print("\n" + "=" * 80)
    print("HERITAGE RECOMMENDER TEST")
    print("=" * 80)

    for query_text in test_queries:
        print(f"\nQuery: {query_text}")
        print("-" * 80)

        # Parse query
        parsed_query = processor.parse_query(query_text)

        # Get recommendations
        recommendations = recommender.recommend(parsed_query, top_k=5, explain=True)

        # Display results
        for rec in recommendations:
            print(recommender.format_recommendation(rec))
            print()


if __name__ == '__main__':
    main()
