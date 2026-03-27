"""
Training Script for Learning to Rank Models

Trains LTR models on ground truth data and compares performance.
"""

import sys
import os
import json
import pickle
import numpy as np
from typing import List, Dict

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from feature_extractor import FeatureExtractor, QueryDocFeatures, create_training_dataset
from query_classifier import QueryTypeClassifier, create_synthetic_training_data
from learned_ranker import LearnedRanker, RankingWeights
from ensemble_ranker import compare_fusion_methods, RankedDocument


def train_query_classifier(output_dir: str = 'models/ranker'):
    """Train and save query type classifier"""
    print("\n" + "="*80)
    print("TRAINING QUERY TYPE CLASSIFIER")
    print("="*80)

    # Create synthetic training data
    queries, entities, labels = create_synthetic_training_data()

    # Train classifier
    classifier = QueryTypeClassifier()
    classifier.train(queries, entities, labels)

    # Save model
    os.makedirs(output_dir, exist_ok=True)
    classifier.save(f'{output_dir}/query_classifier.pkl')

    return classifier


def train_ltr_models(training_features: List[QueryDocFeatures],
                     output_dir: str = 'models/ranker') -> Dict[str, LearnedRanker]:
    """
    Train all LTR models and compare

    Args:
        training_features: List of training samples
        output_dir: Directory to save models

    Returns:
        Dict of trained models
    """
    print("\n" + "="*80)
    print("TRAINING LTR MODELS")
    print("="*80)

    models = {}

    # Train LambdaMART
    print("\n" + "-"*80)
    lambdamart = LearnedRanker(model_type='lambdamart')
    lambdamart.train(training_features, n_folds=5, optimize_per_query_type=True)
    lambdamart.save(f'{output_dir}/lambdamart_model.pkl')
    models['lambdamart'] = lambdamart

    # Train RankNet
    print("\n" + "-"*80)
    ranknet = LearnedRanker(model_type='ranknet')
    ranknet.train(training_features, n_folds=5, optimize_per_query_type=True)
    ranknet.save(f'{output_dir}/ranknet_model.pkl')
    models['ranknet'] = ranknet

    # Train ListNet
    print("\n" + "-"*80)
    listnet = LearnedRanker(model_type='listnet')
    listnet.train(training_features, n_folds=5, optimize_per_query_type=True)
    listnet.save(f'{output_dir}/listnet_model.pkl')
    models['listnet'] = listnet

    return models


def export_learned_weights(models: Dict[str, LearnedRanker],
                          output_file: str = 'models/ranker/learned_weights.json'):
    """
    Export learned weights to JSON for easy inspection

    Args:
        models: Trained LTR models
        output_file: Output JSON file
    """
    weights_data = {}

    for model_name, model in models.items():
        weights_data[model_name] = {}

        for query_type, weights in model.query_type_weights.items():
            weights_data[model_name][query_type] = {
                'simrank_weight': weights.simrank_weight,
                'horn_index_weight': weights.horn_index_weight,
                'embedding_weight': weights.embedding_weight,
                'confidence': weights.confidence
            }

    # Save to JSON
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(weights_data, f, indent=2)

    print(f"\nLearned weights exported to: {output_file}")


def _load_gt_improved_as_ranked_docs(gt_improved_file: str = 'data/evaluation/ground_truth_improved.json'):
    """
    Load ground_truth_improved.json (82 queries) and convert each query's
    relevance_details into (documents, ground_truth) pairs for ensemble evaluation.

    Each entry in relevance_details has:
        doc_idx, relevance_score, components: {embedding, metadata, entities, simrank, cluster}

    We map:  simrank_score = components.simrank
             embedding_score = components.embedding (clipped to [0,1])
             horn_score = components.entities   (best proxy for entity importance)
             relevance_label = relevance_score  (continuous [0,1])

    Returns list of (query_id, documents, ground_truth) triples.
    """
    if not os.path.exists(gt_improved_file):
        return []

    with open(gt_improved_file) as f:
        gt_list = json.load(f)

    triples = []
    for entry in gt_list:
        query_id = entry['query_id']
        details = entry.get('relevance_details', [])
        if len(details) < 2:
            continue

        documents = []
        ground_truth = {}
        for d in details:
            doc_id = f"doc_{d['doc_idx']}"
            comp = d.get('components', {})
            sr = float(np.clip(comp.get('simrank', 0.0), 0.0, 1.0))
            em = float(np.clip(comp.get('embedding', 0.0), 0.0, 1.0))
            hn = float(np.clip(comp.get('entities', comp.get('metadata', 0.0)), 0.0, 1.0))
            rel = float(d.get('relevance_score', 0.0))
            documents.append(RankedDocument(
                doc_id=doc_id,
                simrank_score=sr,
                horn_score=hn,
                embedding_score=em,
            ))
            ground_truth[doc_id] = rel

        triples.append((query_id, documents, ground_truth))

    return triples


def evaluate_ensemble_methods(training_features: List[QueryDocFeatures],
                              output_file: str = 'evaluation/ltr_comparison.json',
                              gt_improved_file: str = 'data/evaluation/ground_truth_improved.json'):
    """
    Evaluate different ensemble fusion methods.

    Uses two data sources (merged, deduplicated by query_id):
    1. training_features (QueryDocFeatures with relevance labels)
    2. ground_truth_improved.json (82 queries with per-doc component scores)

    Args:
        training_features: Training data with ground truth
        output_file: Output JSON file with comparison results
        gt_improved_file: Path to ground_truth_improved.json for broader evaluation
    """
    print("\n" + "="*80)
    print("EVALUATING ENSEMBLE METHODS")
    print("="*80)

    fusion_results = {
        'cascade': [],
        'rrf': [],
        'borda': [],
        'combmnz': []
    }

    seen_query_ids = set()

    # --- Source 1: training features (may have ltr_score if available) ---
    query_groups: Dict[str, List] = {}
    for feature in training_features:
        query_groups.setdefault(feature.query_id, []).append(feature)

    for query_id, features in query_groups.items():
        seen_query_ids.add(query_id)
        documents = [
            RankedDocument(
                doc_id=f.doc_id,
                simrank_score=f.simrank_score,
                horn_score=f.horn_index_score,
                embedding_score=f.embedding_similarity,
            )
            for f in features
        ]
        ground_truth = {f.doc_id: float(f.relevance_label) for f in features}
        ndcg_scores = compare_fusion_methods(documents, ground_truth)
        for method, ndcg in ndcg_scores.items():
            fusion_results[method].append(ndcg)

    # --- Source 2: ground_truth_improved.json (broader coverage) ---
    gt_triples = _load_gt_improved_as_ranked_docs(gt_improved_file)
    added_from_gt = 0
    for query_id, documents, ground_truth in gt_triples:
        if query_id in seen_query_ids:
            continue  # already counted from training features
        ndcg_scores = compare_fusion_methods(documents, ground_truth)
        for method, ndcg in ndcg_scores.items():
            fusion_results[method].append(ndcg)
        seen_query_ids.add(query_id)
        added_from_gt += 1

    print(f"  Queries from training features: {len(query_groups)}")
    print(f"  Additional queries from GT improved: {added_from_gt}")
    print(f"  Total queries evaluated: {len(seen_query_ids)}")

    # Compute average NDCG for each method
    comparison_results = {}
    for method, scores in fusion_results.items():
        if scores:
            comparison_results[method] = {
                'mean_ndcg': float(np.mean(scores)),
                'std_ndcg': float(np.std(scores)),
                'num_queries': len(scores)
            }

    # Save results
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(comparison_results, f, indent=2)

    print("\nEnsemble Method Comparison:")
    print("-"*60)
    for method, results in sorted(comparison_results.items(), key=lambda x: x[1]['mean_ndcg'], reverse=True):
        print(f"{method.upper():15} NDCG@10: {results['mean_ndcg']:.4f} (+/- {results['std_ndcg']:.4f})")

    print(f"\nResults saved to: {output_file}")


def generate_training_summary(models: Dict[str, LearnedRanker],
                             training_features: List[QueryDocFeatures],
                             output_file: str = 'models/ranker/training_summary.md'):
    """
    Generate comprehensive training summary report

    Args:
        models: Trained LTR models
        training_features: Training data
        output_file: Output markdown file
    """
    print("\n" + "="*80)
    print("GENERATING TRAINING SUMMARY")
    print("="*80)

    # Collect statistics
    num_samples = len(training_features)
    num_queries = len(set(f.query_id for f in training_features))
    query_types = {}
    for f in training_features:
        qtype = f.query_type_encoding
        query_types[qtype] = query_types.get(qtype, 0) + 1

    # Write summary
    with open(output_file, 'w') as f:
        f.write("# Learning to Rank - Training Summary\n\n")

        # Dataset statistics
        f.write("## Dataset Statistics\n\n")
        f.write(f"- **Total training samples**: {num_samples}\n")
        f.write(f"- **Unique queries**: {num_queries}\n")
        f.write(f"- **Average samples per query**: {num_samples / num_queries:.1f}\n\n")

        f.write("### Query Type Distribution\n\n")
        type_names = {0: 'simple_keyword', 1: 'entity_focused', 2: 'concept_focused', 3: 'complex_nlp'}
        for qtype, count in sorted(query_types.items()):
            f.write(f"- **{type_names[qtype]}**: {count} samples ({100*count/num_samples:.1f}%)\n")

        # Model performance
        f.write("\n## Model Performance\n\n")
        f.write("Cross-validation NDCG@10 scores:\n\n")
        f.write("| Model | Mean NDCG@10 | Std Dev |\n")
        f.write("|-------|--------------|----------|\n")

        # Note: Would need to extract CV scores from training
        for model_name in models:
            f.write(f"| {model_name.upper()} | See training logs | - |\n")

        # Learned weights
        f.write("\n## Learned Weights\n\n")
        for model_name, model in models.items():
            f.write(f"### {model_name.upper()}\n\n")
            f.write("| Query Type | SimRank | Horn's Index | Embedding | Confidence |\n")
            f.write("|------------|---------|--------------|-----------|------------|\n")

            for qtype, weights in model.query_type_weights.items():
                f.write(f"| {qtype} | {weights.simrank_weight:.3f} | "
                       f"{weights.horn_index_weight:.3f} | {weights.embedding_weight:.3f} | "
                       f"{weights.confidence:.3f} |\n")
            f.write("\n")

        # Feature importance
        f.write("## Feature Importance\n\n")
        f.write("Top features from LambdaMART model:\n\n")

        if 'lambdamart' in models:
            lm = models['lambdamart'].model
            # model attribute is a LambdaMART wrapper; the sklearn estimator is lm.model
            sklearn_model = lm.model if hasattr(lm, 'model') else lm
            importances = sklearn_model.feature_importances_
            feature_names = QueryDocFeatures.feature_names()

            top_features = sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True)[:10]

            f.write("| Rank | Feature | Importance |\n")
            f.write("|------|---------|------------|\n")
            for rank, (name, imp) in enumerate(top_features, 1):
                f.write(f"| {rank} | {name} | {imp:.4f} |\n")

        # Recommendations
        f.write("\n## Recommendations\n\n")
        f.write("Based on learned weights:\n\n")

        # Analyze weight patterns
        f.write("1. **SimRank effectiveness**: Graph structure is ")
        avg_simrank = np.mean([w.simrank_weight for m in models.values() for w in m.query_type_weights.values()])
        if avg_simrank > 0.4:
            f.write("highly important (avg weight: {:.2f})\n".format(avg_simrank))
        else:
            f.write("moderately important (avg weight: {:.2f})\n".format(avg_simrank))

        f.write("2. **Horn's Index effectiveness**: Entity importance is ")
        avg_horn = np.mean([w.horn_index_weight for m in models.values() for w in m.query_type_weights.values()])
        if avg_horn > 0.3:
            f.write("significant (avg weight: {:.2f})\n".format(avg_horn))
        else:
            f.write("minor (avg weight: {:.2f})\n".format(avg_horn))

        f.write("3. **Embedding effectiveness**: Semantic similarity is ")
        avg_emb = np.mean([w.embedding_weight for m in models.values() for w in m.query_type_weights.values()])
        if avg_emb > 0.4:
            f.write("critical (avg weight: {:.2f})\n".format(avg_emb))
        else:
            f.write("supplementary (avg weight: {:.2f})\n".format(avg_emb))

        f.write("\n## Integration Guide\n\n")
        f.write("To use learned weights in recommender:\n\n")
        f.write("```python\n")
        f.write("from src.5_ranking.learned_ranker import LearnedRanker\n")
        f.write("from src.5_ranking.query_classifier import QueryTypeClassifier\n\n")
        f.write("# Load models\n")
        f.write("classifier = QueryTypeClassifier()\n")
        f.write("classifier.load('models/ranker/query_classifier.pkl')\n\n")
        f.write("ranker = LearnedRanker(model_type='lambdamart')\n")
        f.write("ranker.load('models/ranker/lambdamart_model.pkl')\n\n")
        f.write("# Classify query\n")
        f.write("query_type_id, query_type, confidence = classifier.predict(query_text, entities)\n\n")
        f.write("# Get adaptive weights\n")
        f.write("weights = ranker.get_weights_for_query_type(query_type)\n\n")
        f.write("# Apply to ranking\n")
        f.write("final_score = (weights.simrank_weight * simrank_score +\n")
        f.write("              weights.horn_index_weight * horn_score +\n")
        f.write("              weights.embedding_weight * embedding_score)\n")
        f.write("```\n")

    print(f"Training summary saved to: {output_file}")


def _build_synthetic_training_features(n_per_type: int = 30) -> List[QueryDocFeatures]:
    """
    Build a balanced synthetic training set covering all 4 query types.

    Generates plausible score distributions per query type based on known
    characteristics of each retrieval signal:
      - simple_keyword   → embedding dominates
      - entity_focused   → horn dominates
      - concept_focused  → balanced / simrank + horn
      - complex_nlp      → embedding + horn

    Args:
        n_per_type: Number of (query, doc) samples per query type.

    Returns:
        List of QueryDocFeatures suitable for LTR training.
    """
    rng = np.random.default_rng(42)

    # (query_type_id, type_name, score_means [sr, hn, em], relevance_fn)
    type_configs = [
        (0, "simple_keyword",  [0.3, 0.4, 0.6], lambda sr, hn, em: int(round(min(em * 3, 3)))),
        (1, "entity_focused",  [0.4, 0.7, 0.5], lambda sr, hn, em: int(round(min((hn + sr) / 2 * 3, 3)))),
        (2, "concept_focused", [0.5, 0.5, 0.5], lambda sr, hn, em: int(round(min((sr + hn + em) / 3 * 3, 3)))),
        (3, "complex_nlp",     [0.3, 0.5, 0.7], lambda sr, hn, em: int(round(min((em * 0.5 + hn * 0.5) * 3, 3)))),
    ]

    samples: List[QueryDocFeatures] = []
    for type_id, type_name, means, rel_fn in type_configs:
        for i in range(n_per_type):
            query_id = f"synth_{type_name}_q{i // 5}"  # 5 docs per query
            doc_id = f"synth_doc_{type_id}_{i}"

            sr = float(np.clip(rng.normal(means[0], 0.15), 0, 1))
            hn = float(np.clip(rng.normal(means[1], 0.15), 0, 1))
            em = float(np.clip(rng.normal(means[2], 0.15), 0, 1))
            relevance = rel_fn(sr, hn, em)

            samples.append(QueryDocFeatures(
                query_id=query_id,
                doc_id=doc_id,
                simrank_score=sr,
                horn_index_score=hn,
                embedding_similarity=em,
                simrank_normalized=sr,
                horn_index_normalized=hn,
                embedding_normalized=em,
                heritage_type_match=float(rng.random() > 0.5),
                domain_overlap=float(rng.random()),
                time_period_match=float(rng.random() > 0.6),
                region_match=float(rng.random() > 0.6),
                cluster_id=int(rng.integers(0, 8)),
                node_degree=float(rng.random()),
                doc_length=float(rng.random()),
                doc_completeness=float(rng.uniform(0.4, 1.0)),
                num_entities=int(rng.integers(0, 5)),
                query_length=int(rng.integers(2, 12)),
                query_complexity=float(rng.random()),
                query_type_encoding=type_id,
                relevance_label=relevance,
            ))

    print(f"Built {len(samples)} synthetic training samples "
          f"({n_per_type} per type × {len(type_configs)} types).")
    return samples


def main():
    """Main training pipeline"""
    print("\n" + "="*80)
    print("LEARNING TO RANK - TRAINING PIPELINE")
    print("="*80)

    # Step 1: Train query classifier
    classifier = train_query_classifier()

    # Step 2: Create training dataset
    print("\n" + "="*80)
    print("CREATING TRAINING DATASET")
    print("="*80)

    gt_file = 'data/evaluation/ground_truth_v2.0_dev.json'
    rec_file = 'data/evaluation/recommender_results.json'

    training_features: List[QueryDocFeatures] = []

    if os.path.exists(gt_file) and os.path.exists(rec_file):
        print("\nGround truth + recommender results found — building real features...")
        extractor = FeatureExtractor(
            kg_file='knowledge_graph/heritage_kg.gpickle',
            document_metadata_file='data/processed/document_metadata.json',
            entity_importance_file='data/entity_importance/computed_scores.json'
        )
        training_file = 'data/evaluation/ltr_training_features.pkl'
        training_features = create_training_dataset(
            ground_truth_file=gt_file,
            recommender_results_file=rec_file,
            feature_extractor=extractor,
            output_file=training_file
        )
        print(f"Real training samples: {len(training_features)}")

    # Augment (or replace if insufficient) with synthetic data covering all 4 types
    real_types = set(f.query_type_encoding for f in training_features)
    missing_types = {0, 1, 2, 3} - real_types
    if missing_types or len(training_features) < 40:
        n_synth_per_type = max(30, 40 - len(training_features) // 4)
        print(f"\nAugmenting with synthetic data "
              f"(missing types: {missing_types}, n_per_type={n_synth_per_type})...")
        synthetic = _build_synthetic_training_features(n_per_type=n_synth_per_type)
        training_features = training_features + synthetic
        print(f"Total training samples after augmentation: {len(training_features)}")

    # Step 3: Train LTR models
    if len(training_features) > 0:
        models = train_ltr_models(training_features)

        # Step 4: Export learned weights
        export_learned_weights(models)

        # Step 5: Evaluate ensemble methods
        evaluate_ensemble_methods(training_features)

        # Step 6: Generate summary
        generate_training_summary(models, training_features)

        print("\n" + "="*80)
        print("TRAINING COMPLETE")
        print("="*80)
        print("\nOutput files:")
        print("  - models/ranker/query_classifier.pkl")
        print("  - models/ranker/lambdamart_model.pkl")
        print("  - models/ranker/ranknet_model.pkl")
        print("  - models/ranker/listnet_model.pkl")
        print("  - models/ranker/learned_weights.json")
        print("  - models/ranker/training_summary.md")
        print("  - evaluation/ltr_comparison.json")
    else:
        print("\nError: No training features extracted")


if __name__ == '__main__':
    main()
