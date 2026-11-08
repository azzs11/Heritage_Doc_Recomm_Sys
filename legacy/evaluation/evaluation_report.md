# Heritage Document Recommender — Evaluation Report

_Generated: 2026-03-28 01:18:49_

---

## Overview

| Field | Value |
|-------|-------|
| Overall grade | 🟡 **B (Good)** |
| Evaluation timestamp | 2025-11-30T02:45:14.396103 |
| Queries evaluated | 1 |
---

## Method Accuracy Comparison

| Method | precision@5 | precision@10 | ndcg@5 | ndcg@10 | MAP | recall@10 |
|--------|--------|--------|--------|--------|--------|--------|
| Embedding-Only (FAISS) | 7.6% | 8.8% | 7.8% | 8.7% | 4.6% | 6.6% |
| SimRank-Only | **76.8%** | **53.0%** | **82.3%** | **70.0%** | **53.5%** | **50.6%** |
| Hybrid (50-50) | 66.8% | 46.4% | 72.2% | 61.4% | 42.2% | 44.9% |
| Hybrid (70% Embedding) | 59.6% | 38.6% | 65.3% | 53.2% | 33.7% | 37.0% |
| Hybrid (30% Embedding) | 70.4% | 49.0% | 76.2% | 65.1% | 48.9% | 47.3% |

_Bold = best in column._

---

## NDCG@5 Visual Comparison

```
SimRank-Only                   ████████████████████ 82.3%
Hybrid (30% Embedding)         ███████████████████░ 76.2%
Hybrid (50-50)                 ██████████████████░░ 72.2%
Hybrid (70% Embedding)         ████████████████░░░░ 65.3%
Embedding-Only (FAISS)         ██░░░░░░░░░░░░░░░░░░ 7.8%
```

---

## Diversity & Heritage-Specific Metrics

| Method | ILD | Coverage | Temporal Acc | Spatial Rel | Domain Align |
|--------|-----|----------|-------------|-------------|--------------|
| Embedding-Only (FAISS) | 60.3% | 75.3% | 62.6% | 41.2% | 47.8% |
| SimRank-Only | 51.4% | 68.6% | 71.4% | 51.2% | 53.9% |
| Hybrid (50-50) | 55.1% | 69.1% | 68.4% | 46.8% | 52.8% |
| Hybrid (70% Embedding) | 57.0% | 71.3% | 64.0% | 41.6% | 50.4% |
| Hybrid (30% Embedding) | 53.4% | 68.3% | 69.2% | 48.6% | 53.8% |

---

## Query Efficiency

| Method | Latency (ms) | QPS |
|--------|-------------|-----|
| Embedding-Only (FAISS) | 0.164 ms | 6,100 |
| SimRank-Only | 0.128 ms | 7,824 |
| Hybrid (50-50) | 0.151 ms | 6,636 |
| Hybrid (70% Embedding) | 0.137 ms | 7,304 |
| Hybrid (30% Embedding) | 0.144 ms | 6,932 |

---

## LTR Ensemble Comparison

| Method | Mean NDCG | Std Dev | Queries |
|--------|-----------|---------|---------|
| COMBMNZ | 0.7502 | ±0.0000 | 1 |
| BORDA | 0.7498 | ±0.0000 | 1 |
| RRF | 0.6591 | ±0.0000 | 1 |
| CASCADE | 0.6215 | ±0.0000 | 1 |

---

## System Quality Breakdown

### Diversity

| Metric | Value |
|--------|-------|
| Temporal Entropy | 0.9503 |
| Spatial Dispersion Km | 930.1389 |
| Cultural Diversity | 0.6200 |
| Novelty Rate | 0.7000 |

_Poor: Recommendations lack diversity, may be too concentrated_

### Fairness

| Metric | Value |
|--------|-------|
| Cluster Representation Score | 0.7975 |
| Source Bias Pvalue | 0.0000 |
| Temporal Bias Kl | 0.1151 |
| Geographic Bias Ratio | 1.5000 |
| Cluster Exposure | 0: 0.300, 3: 0.300, 5: 0.300, 6: 0.100 |

_Good: Generally fair, minor biases detected_

### Explanation Quality

| Metric | Value |
|--------|-------|
| Avg Correctness | 3.0000 |
| Avg Diversity | 0.4000 |
| Avg Path Length | 3.0000 |

_Poor: Explanation quality needs improvement_

### User Experience

| Metric | Value |
|--------|-------|
| Expected Ctr | 0.2967 |
| Session Success Rate | 1.0000 |
| Discovery Potential | 0.1000 |

_Good: Reasonable user satisfaction expected_

### Robustness

| Metric | Value |
|--------|-------|
| Perturbation Ndcg Drop | 0.0800 |
| Longtail Performance | 0.6500 |
| Coldstart Recall | 0.5500 |

_Excellent: System is robust to query variations_


---

## Full Accuracy Breakdown (all k)

| Method | precision@5 | recall@5 | f1@5 | ndcg@5 | precision@10 | recall@10 | f1@10 | ndcg@10 | precision@20 | recall@20 | f1@20 | ndcg@20 | MAP |
|--------|------|------|------|------|------|------|------|------|------|------|------|------|------|
| Embedding-Only (FAISS) | 7.6% | 2.8% | 3.9% | 7.8% | 8.8% | 6.6% | 7.2% | 8.7% | 10.9% | 19.0% | 13.2% | 13.8% | 4.6% |
| SimRank-Only | 76.8% | 39.2% | 49.1% | 82.3% | 53.0% | 50.6% | 48.9% | 70.0% | 33.7% | 60.7% | 41.2% | 68.1% | 53.5% |
| Hybrid (50-50) | 66.8% | 34.2% | 43.0% | 72.2% | 46.4% | 44.9% | 43.2% | 61.4% | 27.3% | 51.3% | 33.9% | 58.2% | 42.2% |
| Hybrid (70% Embedding) | 59.6% | 29.7% | 37.8% | 65.3% | 38.6% | 37.0% | 35.9% | 53.2% | 22.0% | 41.5% | 27.5% | 49.7% | 33.7% |
| Hybrid (30% Embedding) | 70.4% | 36.3% | 45.4% | 76.2% | 49.0% | 47.3% | 45.5% | 65.1% | 32.2% | 57.8% | 39.4% | 64.3% | 48.9% |

---

## Notes

- All accuracy metrics computed on ground-truth annotations from `data/evaluation/`.
- SimRank-Only achieves highest relevance (NDCG@5 ≈ 82%) at the cost of lower diversity.
- CombMNZ and Borda are the best LTR ensemble methods (~75% NDCG).
- LTR models trained on 54 samples from 1 query type; retrain with more diverse queries for full benefit.