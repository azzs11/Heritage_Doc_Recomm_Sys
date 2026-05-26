# Learning to Rank (LTR) Implementation

## Overview

This implementation replaces manual weight tuning with a principled machine learning approach that learns optimal component weights from ground truth data. The system features query-type-specific adaptation, multiple LTR models, and sophisticated ensemble methods.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     ADAPTIVE RECOMMENDER                         │
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐     │
│  │   Query      │    │  LTR Model   │    │   Ensemble   │     │
│  │ Classifier   │───>│  (Learned    │───>│   Ranker     │     │
│  │              │    │   Weights)   │    │              │     │
│  └──────────────┘    └──────────────┘    └──────────────┘     │
│         │                    │                    │             │
│         v                    v                    v             │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Query-Type-Specific Weights                  │  │
│  │  simple_keyword   │ entity_focused │ concept │ complex   │  │
│  │  [0.3, 0.2, 0.5]  │ [0.5, 0.4, 0.1] │ ...    │ ...       │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Feature Extractor (`feature_extractor.py`)

Extracts 18 features for each query-document pair:

**Component Scores (6 features):**
- SimRank score (raw + normalized)
- Horn's Index score (raw + normalized)
- Embedding similarity (raw + normalized)

**Query-Document Overlap (4 features):**
- Heritage type match (binary + weighted)
- Domain overlap (Jaccard similarity)
- Time period match
- Region match

**Document Features (4 features):**
- Cluster membership
- Node degree in knowledge graph
- Document length (normalized)
- Metadata completeness

**Query Features (4 features):**
- Number of extracted entities
- Query length
- Query complexity (linguistic)
- Query type encoding (0-3)

### 2. Query Type Classifier (`query_classifier.py`)

Classifies queries into 4 types for adaptive weighting:

| Type | Description | Example | Expected Weights |
|------|-------------|---------|------------------|
| **Simple Keyword** | 1-3 word queries | "mughal forts" | Heavy on embeddings (0.3, 0.2, 0.5) |
| **Entity Focused** | Specific monuments/persons | "taj mahal history" | Heavy on graph (0.5, 0.4, 0.1) |
| **Concept Focused** | Styles, domains, periods | "indo-islamic architecture" | Graph + embeddings (0.4, 0.2, 0.4) |
| **Complex NLP** | Natural language questions | "what are the main features of..." | Balanced (0.4, 0.3, 0.3) |

**Classification Features:**
- Query length
- Number of entities
- Question words (how, why, what, etc.)
- Temporal/spatial keywords
- Comparison keywords
- Average word length
- Monument name presence

**Model:** RandomForest classifier with TF-IDF features

### 3. LTR Models (`learned_ranker.py`)

Three ranking models implemented:

#### a) LambdaMART
- **Algorithm:** Gradient boosted decision trees with lambda gradients
- **Optimization:** Directly optimizes NDCG@10
- **Advantages:** Interpretable feature importance, robust performance
- **Best for:** Production use, explainability

#### b) RankNet
- **Algorithm:** Neural pairwise ranking
- **Loss:** Learns pairwise preferences via sigmoid cross-entropy
- **Advantages:** Can learn complex non-linear relationships
- **Best for:** Large datasets with many pairwise comparisons

#### c) ListNet
- **Algorithm:** Listwise ranking with probability distributions
- **Loss:** KL divergence between predicted and true ranking distributions
- **Advantages:** Considers entire ranking list, not just pairs
- **Best for:** When list-level optimization is critical

### 4. Ensemble Methods (`ensemble_ranker.py`)

Four fusion strategies:

#### a) Re-ranking Cascade
```
Stage 1: FAISS retrieves top-100 (embedding-based)
    ↓
Stage 2: SimRank re-ranks top-100 (graph structure)
    ↓
Stage 3: Horn's Index refines top-20 (entity importance)
    ↓
Stage 4: LTR model final ranking (learned model)
```
- **Best for:** Complex queries requiring multi-faceted evaluation
- **Time complexity:** O(n log n) for each stage

#### b) Reciprocal Rank Fusion (RRF)
```
RRF_score(d) = Σ [1 / (k + rank_i(d))]
```
- **Robust to score scale differences**
- **No normalization needed**
- **Best for:** General-purpose fusion
- **k parameter:** 60 (standard)

#### c) Borda Count
```
Points(d) = Σ (n - rank_i(d))
```
- **Rank-based, not score-based**
- **Democratic voting scheme**
- **Best for:** Simple queries, stable rankings

#### d) CombMNZ
```
Score(d) = (Σ norm_score_i) × (# systems that retrieved d)
```
- **Rewards consensus across methods**
- **Penalizes documents retrieved by only one method**
- **Best for:** Entity-focused queries

### 5. Adaptive Recommender (`adaptive_recommender.py`)

Main integration class that:
1. Classifies query type
2. Retrieves learned weights for that type
3. Applies ensemble ranking
4. Falls back to fixed weights if confidence is low
5. Provides ranking explanations

**Confidence-Based Blending:**
```python
if confidence < 0.5:
    weight = α × learned_weight + (1 - α) × fallback_weight
    where α = confidence
```

## Training Procedure

### Step 1: Train Query Classifier
```bash
python src/5_ranking/query_classifier.py
```
- Uses 40 synthetic training queries (10 per type)
- 5-fold cross-validation
- Saves to: `models/ranker/query_classifier.pkl`

### Step 2: Generate Ground Truth
```bash
python src/7_evaluation/ground_truth_generator.py
```
- Creates 50 seed queries + synthetic variants
- Multi-annotator validation (Cohen's Kappa ≥ 0.6)
- 4-level relevance grading
- Saves to: `data/evaluation/ground_truth_v2.0_dev.json`

### Step 3: Generate Recommender Results
```bash
python src/1_recommender/recommender.py --evaluate
```
- Runs recommender on all ground truth queries
- Saves component scores (SimRank, Horn, embedding)
- Output: `data/evaluation/recommender_results.json`

### Step 4: Train LTR Models
```bash
python src/5_ranking/train_ltr.py
```
- Extracts 18 features per query-doc pair
- Trains LambdaMART, RankNet, ListNet
- 5-fold cross-validation
- Extracts query-type-specific weights
- Saves models to: `models/ranker/`

### Step 5: Evaluate Ensemble Methods
- Compares cascade, RRF, Borda, CombMNZ
- Computes NDCG@10 for each method
- Saves comparison to: `evaluation/ltr_comparison.json`

## Usage

### Basic Usage
```python
from src.5_ranking.adaptive_recommender import AdaptiveRecommender

# Initialize
recommender = AdaptiveRecommender(
    classifier_path='models/ranker/query_classifier.pkl',
    ranker_path='models/ranker/lambdamart_model.pkl',
    use_ensemble=True,
    ensemble_method='rrf'  # or 'cascade', 'borda', 'combmnz', 'adaptive'
)

# Prepare documents with component scores
documents = [
    {
        'doc_id': 'doc_001',
        'title': 'Taj Mahal Architecture',
        'simrank_score': 0.85,
        'horn_score': 0.92,
        'embedding_score': 0.78
    },
    # ... more documents
]

# Rank documents
ranked = recommender.rank_documents(
    documents=documents,
    query_text='mughal architecture',
    query_entities=['mughal architecture'],
    query_complexity=0.4
)

# Get top results
for doc in ranked[:10]:
    print(f"{doc['rank']}. {doc['title']} (score: {doc['final_score']:.4f})")
```

### Getting Adaptive Weights Only
```python
weights, query_type = recommender.get_adaptive_weights(
    query_text='ancient buddhist temples',
    query_entities=['buddhist temples']
)

print(f"Query type: {query_type}")
print(f"Weights: SimRank={weights.simrank_weight:.3f}, "
      f"Horn={weights.horn_index_weight:.3f}, "
      f"Embedding={weights.embedding_weight:.3f}")
```

### Explaining Rankings
```python
# Get explanation for top document
explanation = recommender.explain_ranking(ranked[0], weights)
print(explanation)
```

Output:
```
Ranking for: Taj Mahal Architecture
  Final score: 0.8567

  Component contributions:
    SimRank:   0.8500 × 0.400 = 0.3400
    Horn:      0.9200 × 0.300 = 0.2760
    Embedding: 0.7800 × 0.300 = 0.2340

  Primary ranking factor: graph structure (SimRank) (0.3400)
```

## Integration with Existing Recommender

Update `src/1_recommender/recommender.py`:

```python
from src.5_ranking.adaptive_recommender import AdaptiveRecommender

class HeritageDocumentRecommender:
    def __init__(self):
        # ... existing initialization ...

        # Add adaptive ranker
        self.adaptive_ranker = AdaptiveRecommender(
            use_ensemble=True,
            ensemble_method='adaptive'
        )

    def search(self, query_text: str, top_k: int = 10):
        # ... existing search logic ...

        # Get component scores
        documents = self._get_candidate_documents(query_text)

        # Add component scores
        for doc in documents:
            doc['simrank_score'] = self._compute_simrank(query_entities, doc)
            doc['horn_score'] = self._compute_horn_weighted(query_entities, doc)
            doc['embedding_score'] = self._compute_embedding_similarity(query_text, doc)

        # Use adaptive ranking
        ranked_documents = self.adaptive_ranker.rank_documents(
            documents=documents,
            query_text=query_text,
            query_entities=query_entities,
            query_complexity=self._compute_complexity(query_text)
        )

        return ranked_documents[:top_k]
```

## Expected Performance Improvements

Based on LTR literature and heritage domain characteristics:

| Metric | Baseline (Fixed Weights) | LTR (Learned Weights) | Improvement |
|--------|-------------------------|----------------------|-------------|
| **NDCG@10** | 0.65-0.70 | 0.75-0.85 | +15-25% |
| **MAP** | 0.55-0.60 | 0.65-0.75 | +15-20% |
| **MRR** | 0.70-0.75 | 0.80-0.90 | +10-15% |

**Why improvements occur:**
1. **Query-specific optimization:** Different queries need different weights
2. **Data-driven:** Weights learned from actual user relevance judgments
3. **Non-linear relationships:** Neural models (RankNet/ListNet) capture complex patterns
4. **Ensemble diversity:** Multiple ranking signals complement each other

## Continuous Learning

The system supports continuous improvement:

### 1. Logging User Interactions
```python
# Log query and clicked documents
interaction_log = {
    'query_id': query_id,
    'query_text': query_text,
    'clicked_docs': [doc_id_1, doc_id_2],
    'dwell_times': [45, 120],  # seconds
    'timestamp': timestamp
}
```

### 2. Periodic Retraining
```bash
# Every month or when N new interactions collected
python src/5_ranking/train_ltr.py --incremental --new_data interaction_logs.json
```

### 3. A/B Testing
```python
# Test new weight configuration
if user_id % 10 == 0:  # 10% of users
    use_new_weights = True
else:
    use_old_weights = True

# Track metrics for both groups
```

### 4. Distribution Shift Monitoring
```python
# Detect if query patterns are changing
current_query_type_dist = compute_distribution(recent_queries)
baseline_dist = load_distribution('models/ranker/baseline_distribution.json')

kl_divergence = compute_kl_div(current_query_type_dist, baseline_dist)

if kl_divergence > threshold:
    trigger_retraining()
```

## Fallback Strategy

The system includes robust fallback mechanisms:

```python
if model_unavailable or model_confidence < 0.3:
    # Fall back to proven fixed weights
    weights = {
        'simrank': 0.4,
        'horn_index': 0.3,
        'embedding': 0.3
    }
    log_fallback_case(query_id, reason)
```

**Fallback triggers:**
- Model files not found
- Model confidence < 0.3
- Prediction error/exception
- Query type not in training data

## File Structure

```
src/5_ranking/
├── feature_extractor.py       # Feature engineering (18 features)
├── query_classifier.py         # Query type classification
├── learned_ranker.py           # LTR models (LambdaMART, RankNet, ListNet)
├── ensemble_ranker.py          # Ensemble fusion methods
├── adaptive_recommender.py     # Main integration class
└── train_ltr.py               # Training pipeline script

models/ranker/
├── query_classifier.pkl        # Trained query classifier
├── lambdamart_model.pkl       # LambdaMART model + weights
├── ranknet_model.pkl          # RankNet model + weights
├── listnet_model.pkl          # ListNet model + weights
├── learned_weights.json       # Human-readable weights
└── training_summary.md        # Training report

evaluation/
└── ltr_comparison.json        # Ensemble method comparison

data/evaluation/
├── ltr_training_features.pkl  # Training dataset (features)
└── recommender_results.json   # Component scores for ground truth queries
```

## Hyperparameters

### LambdaMART
```python
n_estimators = 100      # Number of trees
max_depth = 6          # Tree depth
learning_rate = 0.1    # Boosting learning rate
```

### RankNet / ListNet
```python
hidden_dim = 64        # Hidden layer size
learning_rate = 0.001  # Adam optimizer
dropout = 0.2          # Dropout rate
epochs = 50            # Training epochs
batch_size = 32        # Pairwise batch size (RankNet)
```

### Ensemble Methods
```python
rrf_k = 60            # RRF constant
cascade_stages = [100, 20]  # Documents per stage
```

## Interpretability

The framework emphasizes explainability:

### 1. Feature Importance (LambdaMART)
```python
importances = model.feature_importances_
feature_names = QueryDocFeatures.feature_names()

for name, imp in zip(feature_names, importances):
    print(f"{name}: {imp:.4f}")
```

### 2. Weight Sensitivity Analysis
```python
# Test how NDCG changes when varying weights
for alpha in np.linspace(0, 1, 11):
    weights = [alpha, (1-alpha)/2, (1-alpha)/2]
    ndcg = evaluate_with_weights(weights)
    plot(alpha, ndcg)
```

### 3. Case Studies
- Show example queries where learned weights outperform fixed
- Identify query types with largest improvements
- Analyze failure cases

### 4. Ablation Study
```python
# Remove each component and measure NDCG drop
baseline_ndcg = evaluate_full_model()

for component in ['simrank', 'horn', 'embedding']:
    ndcg_without = evaluate_without_component(component)
    importance = baseline_ndcg - ndcg_without
    print(f"{component} importance: {importance:.4f}")
```

## Regularization

Prevents overfitting to small training sets:

### 1. L2 Regularization
```python
# In neural models
optimizer = optim.Adam(model.parameters(), weight_decay=1e-4)
```

### 2. Weight Normalization
```python
# Constrain weights to sum to 1.0
weights = weights / weights.sum()
```

### 3. Stability Penalty
```python
# Penalize large differences between query type weights
penalty = sum(||w_i - w_j||^2 for all pairs (i,j))
loss = ranking_loss + λ × penalty
```

### 4. Cross-Validation
```python
# 5-fold CV to detect overfitting
kfold = KFold(n_splits=5, shuffle=True)
for train_idx, val_idx in kfold.split(X):
    # Train and validate
```

## Next Steps

1. **Generate ground truth data** (50+ annotated queries)
2. **Run recommender in evaluation mode** (get component scores)
3. **Train LTR models** (`train_ltr.py`)
4. **Compare ensemble methods** (identify best fusion strategy)
5. **Integrate with recommender** (update `recommender.py`)
6. **Deploy A/B test** (measure real-world impact)
7. **Setup continuous learning** (collect user interactions)

## References

- **LambdaMART:** Burges (2010) - "From RankNet to LambdaRank to LambdaMART"
- **RankNet:** Burges et al. (2005) - "Learning to Rank using Gradient Descent"
- **ListNet:** Cao et al. (2007) - "Learning to Rank: From Pairwise to Listwise"
- **RRF:** Cormack et al. (2009) - "Reciprocal Rank Fusion outperforms Condorcet"
- **Heritage IR:** Identifies domain-specific importance (UNESCO, scholarly impact)

## Contact

For questions or issues with LTR implementation, see:
- Documentation: This file
- Code: `src/5_ranking/`
- Training logs: `models/ranker/training_summary.md`
