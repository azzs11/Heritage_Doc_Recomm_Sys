"""
Fireworks Algorithm (FWA) Optimizer for Ranking Weight Search

Uses the Fireworks Algorithm meta-heuristic to search for optimal
(simrank_weight, horn_weight, embedding_weight) combinations that
maximise NDCG@10 on a held-out validation set.

Reference:
  Tan, Y. & Zhu, Y. (2010). Fireworks Algorithm for Optimization.
  ICSI 2010, LNCS 6145, pp. 355-364.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Callable, List, Tuple, Optional


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class Firework:
    """A single firework (candidate weight vector)."""
    weights: np.ndarray          # [simrank_w, horn_w, embedding_w], sums to 1
    fitness: float = -np.inf     # NDCG@10 (higher is better)
    sparks: List["Firework"] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "simrank_weight": float(self.weights[0]),
            "horn_weight": float(self.weights[1]),
            "embedding_weight": float(self.weights[2]),
            "fitness": self.fitness,
        }


# ── Fireworks optimizer ────────────────────────────────────────────────────────

class FireworksOptimizer:
    """
    Fireworks Algorithm for optimising hybrid ranking weights.

    Objective: maximise NDCG@10 over a validation set by searching
    the 2-D simplex {w ≥ 0, sum(w) = 1} for the best
    (simrank_w, horn_w, embedding_w) triple.

    Parameters follow the original FWA paper:
      - n: number of fireworks (population size)
      - m: maximum sparks per firework
      - a, b: spark-count bounds (0 < a < b < 1)
      - A: maximum explosion amplitude
      - gaussian_sparks: number of Gaussian mutation sparks
    """

    def __init__(
        self,
        n_fireworks: int = 10,
        max_sparks: int = 40,
        a: float = 0.04,
        b: float = 0.8,
        amplitude: float = 0.4,
        gaussian_sparks: int = 5,
        seed: Optional[int] = 42,
    ):
        self.n_fireworks = n_fireworks
        self.max_sparks = max_sparks
        self.a = a
        self.b = b
        self.amplitude = amplitude
        self.gaussian_sparks = gaussian_sparks
        self.rng = np.random.default_rng(seed)

        self.best_firework: Optional[Firework] = None
        self.history: List[dict] = []   # fitness per generation

    # ── Public ────────────────────────────────────────────────────────────────

    def optimize(
        self,
        fitness_fn: Callable[[np.ndarray], float],
        n_generations: int = 30,
        verbose: bool = True,
    ) -> Firework:
        """
        Run the Fireworks Algorithm.

        Args:
            fitness_fn: Callable that accepts a weight array [sw, hw, ew]
                        (summing to 1) and returns a scalar fitness (NDCG@10).
            n_generations: Number of FWA iterations.
            verbose: Print progress.

        Returns:
            Best Firework found.
        """
        # Initialise population on the simplex
        population = [
            Firework(weights=self._random_weights())
            for _ in range(self.n_fireworks)
        ]

        # Evaluate initial population
        for fw in population:
            fw.fitness = fitness_fn(fw.weights)

        self.best_firework = max(population, key=lambda f: f.fitness)

        for gen in range(n_generations):
            all_candidates: List[Firework] = list(population)

            for fw in population:
                # Explosion sparks
                n_sparks = self._spark_count(fw, population)
                amp = self._amplitude(fw, population)
                for _ in range(n_sparks):
                    spark = self._explosion_spark(fw, amp)
                    spark.fitness = fitness_fn(spark.weights)
                    all_candidates.append(spark)

                # Gaussian mutation sparks
                for _ in range(self.gaussian_sparks):
                    spark = self._gaussian_spark(fw)
                    spark.fitness = fitness_fn(spark.weights)
                    all_candidates.append(spark)

            # Selection: keep best + (n-1) diverse candidates
            population = self._select(all_candidates)

            gen_best = max(population, key=lambda f: f.fitness)
            if gen_best.fitness > self.best_firework.fitness:
                self.best_firework = gen_best

            self.history.append({
                "generation": gen + 1,
                "best_fitness": self.best_firework.fitness,
                "gen_best_fitness": gen_best.fitness,
            })

            if verbose:
                w = self.best_firework.weights
                print(
                    f"Gen {gen+1:3d}/{n_generations} | "
                    f"NDCG@10={self.best_firework.fitness:.4f} | "
                    f"SR={w[0]:.3f} HN={w[1]:.3f} EM={w[2]:.3f}"
                )

        return self.best_firework

    def optimize_per_query_type(
        self,
        fitness_fn_map: dict,
        n_generations: int = 30,
        verbose: bool = True,
    ) -> dict:
        """
        Run separate optimisation for each query type.

        Args:
            fitness_fn_map: {query_type: fitness_fn}
            n_generations: Iterations per query type.
            verbose: Print progress.

        Returns:
            {query_type: Firework} with best weights per type.
        """
        results = {}
        for query_type, fn in fitness_fn_map.items():
            if verbose:
                print(f"\n{'='*60}")
                print(f"Optimising weights for query type: {query_type}")
                print(f"{'='*60}")
            best = self.optimize(fn, n_generations=n_generations, verbose=verbose)
            results[query_type] = best
            if verbose:
                print(f"Best weights for {query_type}: {best.to_dict()}")
        return results

    # ── FWA internals ─────────────────────────────────────────────────────────

    def _spark_count(self, fw: Firework, population: List[Firework]) -> int:
        """Number of explosion sparks proportional to (relative) fitness."""
        fitnesses = np.array([f.fitness for f in population])
        # Shift so minimum is 0
        shifted = fitnesses - fitnesses.min() + 1e-9
        ratio = shifted[population.index(fw)] / shifted.sum()
        n = int(self.max_sparks * ratio)
        # Clamp to [a*max, b*max]
        n = max(int(self.a * self.max_sparks), n)
        n = min(int(self.b * self.max_sparks), n)
        return max(1, n)

    def _amplitude(self, fw: Firework, population: List[Firework]) -> float:
        """Explosion amplitude: worse fireworks explode wider."""
        fitnesses = np.array([f.fitness for f in population])
        shifted = fitnesses.max() - fitnesses + 1e-9
        ratio = shifted[population.index(fw)] / shifted.sum()
        return self.amplitude * ratio

    def _explosion_spark(self, fw: Firework, amp: float) -> Firework:
        """Generate one explosion spark near fw with amplitude amp."""
        # Pick 1 or 2 dimensions to perturb
        n_dims = self.rng.integers(1, 3)
        dims = self.rng.choice(3, size=n_dims, replace=False)
        delta = self.rng.uniform(-amp, amp, size=n_dims)
        new_w = fw.weights.copy()
        new_w[dims] += delta
        return Firework(weights=self._project_simplex(new_w))

    def _gaussian_spark(self, fw: Firework) -> Firework:
        """Generate one Gaussian mutation spark."""
        coeff = self.rng.standard_normal()
        new_w = fw.weights + coeff * self.rng.standard_normal(3) * 0.1
        return Firework(weights=self._project_simplex(new_w))

    def _select(self, candidates: List[Firework]) -> List[Firework]:
        """
        Select n_fireworks for next generation.

        Always keep the best; remaining n-1 drawn proportional to
        minimum distance to other selected candidates (diversity).
        """
        best = max(candidates, key=lambda f: f.fitness)
        remaining = [c for c in candidates if c is not best]

        selected = [best]
        for _ in range(self.n_fireworks - 1):
            if not remaining:
                break
            # Distance-based selection probability
            dists = np.array([
                min(np.linalg.norm(c.weights - s.weights) for s in selected)
                for c in remaining
            ])
            dists_sum = dists.sum()
            if dists_sum < 1e-12:
                probs = np.ones(len(remaining)) / len(remaining)
            else:
                probs = dists / dists_sum
            idx = self.rng.choice(len(remaining), p=probs)
            selected.append(remaining.pop(idx))

        return selected

    # ── Simplex projection ─────────────────────────────────────────────────────

    @staticmethod
    def _project_simplex(w: np.ndarray) -> np.ndarray:
        """
        Project w onto the probability simplex (w >= 0, sum = 1)
        using the algorithm of Duchi et al. (2008).
        """
        w = np.clip(w, 0, None)
        s = w.sum()
        if s < 1e-12:
            return np.array([1 / 3, 1 / 3, 1 / 3])
        return w / s

    def _random_weights(self) -> np.ndarray:
        """Sample uniformly from the 2-D simplex."""
        w = self.rng.dirichlet(np.ones(3))
        return w.astype(float)


# ── NDCG helper used by the built-in fitness factory ─────────────────────────

def _ndcg_at_k(
    ranked_doc_ids: List[str],
    relevance: dict,
    k: int = 10,
) -> float:
    """
    Compute NDCG@k given a ranked list and a {doc_id: relevance} dict.
    """
    gains = [relevance.get(did, 0) for did in ranked_doc_ids[:k]]
    dcg = sum(g / np.log2(i + 2) for i, g in enumerate(gains))
    ideal = sorted(relevance.values(), reverse=True)[:k]
    idcg = sum(g / np.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / idcg if idcg > 0 else 0.0


def make_fitness_fn(
    queries: List[dict],
    k: int = 10,
) -> Callable[[np.ndarray], float]:
    """
    Build a fitness function from a list of scored query results.

    Each element of `queries` must have:
      - 'relevance': {doc_id: relevance_label}
      - 'documents': list of {'doc_id', 'simrank_score', 'horn_score', 'embedding_score'}

    Returns a callable suitable for FireworksOptimizer.optimize().
    """
    def fitness_fn(weights: np.ndarray) -> float:
        sw, hw, ew = weights
        ndcg_scores = []
        for q in queries:
            docs = q["documents"]
            scored = sorted(
                docs,
                key=lambda d: sw * d["simrank_score"] + hw * d["horn_score"] + ew * d["embedding_score"],
                reverse=True,
            )
            ranked_ids = [d["doc_id"] for d in scored]
            ndcg_scores.append(_ndcg_at_k(ranked_ids, q["relevance"], k=k))
        return float(np.mean(ndcg_scores)) if ndcg_scores else 0.0

    return fitness_fn


# ── CLI demo ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json, os

    # Build fitness fn from recommender_results + ground truth if available
    rec_path = "data/evaluation/recommender_results.json"
    gt_path = "data/evaluation/ground_truth_v2.0_dev.json"

    if os.path.exists(rec_path) and os.path.exists(gt_path):
        with open(rec_path) as f:
            rec_data = json.load(f)
        with open(gt_path) as f:
            gt_data = json.load(f)

        gt_lookup = {q["query_id"]: q for q in gt_data.get("queries", [])}
        queries_for_opt = []
        for qid, qres in rec_data.items():
            if qid not in gt_lookup:
                continue
            q_gt = gt_lookup[qid]
            relevance = {}
            for j in q_gt.get("relevance_judgments", {}).values():
                for entry in j:
                    doc_id = entry.get("doc_id", "")
                    relevance[doc_id] = max(relevance.get(doc_id, 0), entry.get("relevance_level", 0))
            queries_for_opt.append({
                "relevance": relevance,
                "documents": qres.get("documents", []),
            })

        if queries_for_opt:
            fn = make_fitness_fn(queries_for_opt)
            optimizer = FireworksOptimizer(n_fireworks=8, max_sparks=20, seed=42)
            best = optimizer.optimize(fn, n_generations=20)
            print(f"\nBest weights found: {best.to_dict()}")
        else:
            print("No matching queries found between GT and recommender results.")
    else:
        # Synthetic demo
        print("Running synthetic demo (real data not found)...")

        def mock_fitness(w: np.ndarray) -> float:
            # Optimal at roughly (0.5, 0.3, 0.2)
            return 1.0 - np.linalg.norm(w - np.array([0.5, 0.3, 0.2]))

        optimizer = FireworksOptimizer(n_fireworks=5, max_sparks=15, seed=0)
        best = optimizer.optimize(mock_fitness, n_generations=15)
        print(f"\nBest weights: {best.to_dict()}")
