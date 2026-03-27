# Learning to Rank - Training Summary

## Dataset Statistics

- **Total training samples**: 54
- **Unique queries**: 1
- **Average samples per query**: 54.0

### Query Type Distribution

- **concept_focused**: 54 samples (100.0%)

## Model Performance

Cross-validation NDCG@10 scores:

| Model | Mean NDCG@10 | Std Dev |
|-------|--------------|----------|
| LAMBDAMART | See training logs | - |
| RANKNET | See training logs | - |
| LISTNET | See training logs | - |

## Learned Weights

### LAMBDAMART

| Query Type | SimRank | Horn's Index | Embedding | Confidence |
|------------|---------|--------------|-----------|------------|
| simple_keyword | 0.400 | 0.300 | 0.300 | 0.500 |
| entity_focused | 0.400 | 0.300 | 0.300 | 0.500 |
| concept_focused | 0.116 | 0.653 | 0.230 | 1.000 |
| complex_nlp | 0.400 | 0.300 | 0.300 | 0.500 |

### RANKNET

| Query Type | SimRank | Horn's Index | Embedding | Confidence |
|------------|---------|--------------|-----------|------------|
| simple_keyword | 0.400 | 0.300 | 0.300 | 0.500 |
| entity_focused | 0.400 | 0.300 | 0.300 | 0.500 |
| concept_focused | 0.447 | 0.437 | 0.117 | 1.000 |
| complex_nlp | 0.400 | 0.300 | 0.300 | 0.500 |

### LISTNET

| Query Type | SimRank | Horn's Index | Embedding | Confidence |
|------------|---------|--------------|-----------|------------|
| simple_keyword | 0.400 | 0.300 | 0.300 | 0.500 |
| entity_focused | 0.400 | 0.300 | 0.300 | 0.500 |
| concept_focused | 0.447 | 0.437 | 0.117 | 1.000 |
| complex_nlp | 0.400 | 0.300 | 0.300 | 0.500 |

## Feature Importance

Top features from LambdaMART model:

| Rank | Feature | Importance |
|------|---------|------------|
| 1 | horn_index_score | 0.2610 |
| 2 | horn_index_normalized | 0.2446 |
| 3 | node_degree | 0.2283 |
| 4 | embedding_similarity | 0.0920 |
| 5 | embedding_normalized | 0.0801 |
| 6 | simrank_normalized | 0.0474 |
| 7 | simrank_score | 0.0465 |
| 8 | heritage_type_match | 0.0000 |
| 9 | domain_overlap | 0.0000 |
| 10 | time_period_match | 0.0000 |

## Recommendations

Based on learned weights:

1. **SimRank effectiveness**: Graph structure is moderately important (avg weight: 0.38)
2. **Horn's Index effectiveness**: Entity importance is significant (avg weight: 0.35)
3. **Embedding effectiveness**: Semantic similarity is supplementary (avg weight: 0.26)

## Integration Guide

To use learned weights in recommender:

```python
from src.5_ranking.learned_ranker import LearnedRanker
from src.5_ranking.query_classifier import QueryTypeClassifier

# Load models
classifier = QueryTypeClassifier()
classifier.load('models/ranker/query_classifier.pkl')

ranker = LearnedRanker(model_type='lambdamart')
ranker.load('models/ranker/lambdamart_model.pkl')

# Classify query
query_type_id, query_type, confidence = classifier.predict(query_text, entities)

# Get adaptive weights
weights = ranker.get_weights_for_query_type(query_type)

# Apply to ranking
final_score = (weights.simrank_weight * simrank_score +
              weights.horn_index_weight * horn_score +
              weights.embedding_weight * embedding_score)
```
