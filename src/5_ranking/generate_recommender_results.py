"""
Generate recommender_results.json by running the recommender on ground truth queries.

Output format expected by create_training_dataset in feature_extractor.py:
{
  "query_id": {
    "documents": [
      {
        "doc_id": "doc_12",
        "simrank_score": 0.5,
        "horn_score": 0.3,
        "embedding_score": 0.7
      },
      ...
    ]
  },
  ...
}
"""

import sys
import os
import json

# Run from project root
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '6_query_system'))

from query_processor import QueryProcessor
from recommender import HeritageRecommender


def load_ground_truth_queries(gt_file: str):
    """Load queries from ground_truth_v2.0_dev.json"""
    with open(gt_file, 'r') as f:
        data = json.load(f)
    return data['queries']


def build_parsed_query(query_data: dict, processor: QueryProcessor) -> dict:
    """
    Build a parsed_query dict from GT query data.
    Reuses query_processor for the embedding; fields already annotated in GT.
    """
    query_text = query_data['query_text']

    # Get embedding from processor
    parsed = processor.parse_query(query_text)

    # Override with GT-provided structured fields (more precise than NLP extraction)
    parsed['heritage_types'] = query_data.get('heritage_types', parsed.get('heritage_types', []))
    parsed['domains'] = query_data.get('domains', parsed.get('domains', []))

    time_period = query_data.get('time_period')
    if time_period:
        parsed['time_period'] = time_period

    region = query_data.get('region')
    if region:
        parsed['region'] = region

    return parsed


def run_recommender_on_queries(gt_file: str, output_file: str, top_k: int = 50):
    """
    Run recommender on all GT queries and save results.

    Args:
        gt_file: Path to ground_truth_v2.0_dev.json
        output_file: Output path for recommender_results.json
        top_k: Number of results per query (should cover all annotated docs)
    """
    print("Loading query processor...")
    processor = QueryProcessor()

    print("Loading recommender...")
    recommender = HeritageRecommender(
        kg_path='knowledge_graph/heritage_kg.gpickle',
        simrank_path='knowledge_graph/simrank/simrank_matrix.npy',
        embeddings_path='data/embeddings/document_embeddings.npy',
        metadata_path='data/embeddings/embedding_mapping.json',
        faiss_index_path='models/ranker/faiss/hnsw_index.faiss',
        horn_weights_path='knowledge_graph/horn_weights.json',
    )

    print(f"\nLoading ground truth queries from: {gt_file}")
    queries = load_ground_truth_queries(gt_file)
    print(f"Found {len(queries)} queries")

    results = {}

    for i, query_data in enumerate(queries):
        query_id = query_data['query_id']
        query_text = query_data['query_text']
        print(f"\n[{i+1}/{len(queries)}] Query: {query_id} — '{query_text}'")

        parsed = build_parsed_query(query_data, processor)

        # Get recommendations (no explain to keep it fast)
        recs = recommender.recommend(parsed, top_k=top_k, explain=False)

        documents = []
        for rec in recs:
            documents.append({
                'doc_id': rec['doc_id'],
                'simrank_score': float(rec['component_scores']['simrank']),
                'horn_score': float(rec['component_scores']['horn']),
                'embedding_score': float(rec['component_scores']['embedding']),
            })

        results[query_id] = {'documents': documents}
        print(f"  → {len(documents)} results")

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nSaved recommender results to: {output_file}")
    return results


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--gt', default='data/evaluation/ground_truth_v2.0_dev.json')
    parser.add_argument('--out', default='data/evaluation/recommender_results.json')
    parser.add_argument('--top_k', type=int, default=100,
                        help='Results per query — use >=100 to cover all annotated docs')
    args = parser.parse_args()

    run_recommender_on_queries(args.gt, args.out, top_k=args.top_k)
