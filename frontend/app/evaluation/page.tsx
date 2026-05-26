"use client";

// Data served from public/data/ — stable path independent of project structure
import evalData from "@/public/data/evaluation_results.json";
import ltrData from "@/public/data/ltr_comparison.json";

// ── Types ─────────────────────────────────────────────────────────────────────

interface MethodMetrics {
  name: string;
  config: { name: string; weight: number };
  metrics: {
    accuracy: Record<string, number>;
    diversity: Record<string, number>;
    heritage_specific: Record<string, number>;
    efficiency: Record<string, number>;
  };
}

interface LtrEntry {
  mean_ndcg: number;
  std_ndcg: number;
  num_queries: number;
}

// ── Static data ───────────────────────────────────────────────────────────────

const methods = Object.values(evalData) as MethodMetrics[];
const ltrMethods = Object.entries(ltrData) as [string, LtrEntry][];

// Ordered by embedding weight for the tradeoff chart
const ORDERED = [
  "simrank_only",
  "hybrid_sr_heavy",
  "hybrid_balanced",
  "hybrid_emb_heavy",
  "embedding_only",
] as const;

const orderedMethods = ORDERED.map(
  (k) => (evalData as Record<string, MethodMetrics>)[k]
);

// Short labels for charts
const SHORT_LABELS: Record<string, string> = {
  "SimRank-Only": "SimRank",
  "Hybrid (30% Embedding)": "Hybrid\n30% Emb",
  "Hybrid (50-50)": "Hybrid\n50-50",
  "Hybrid (70% Embedding)": "Hybrid\n70% Emb",
  "Embedding-Only (FAISS)": "Embedding",
};

const EMB_WEIGHTS: Record<string, number> = {
  "SimRank-Only": 0,
  "Hybrid (30% Embedding)": 30,
  "Hybrid (50-50)": 50,
  "Hybrid (70% Embedding)": 70,
  "Embedding-Only (FAISS)": 100,
};

// ── Palette ───────────────────────────────────────────────────────────────────

const METHOD_COLORS: Record<string, string> = {
  "SimRank-Only":           "bg-heritage-teal",
  "Hybrid (30% Embedding)": "bg-heritage-gold",
  "Hybrid (50-50)":         "bg-heritage-brown",
  "Hybrid (70% Embedding)": "bg-heritage-light",
  "Embedding-Only (FAISS)": "bg-heritage-rust",
};

const METHOD_BORDER: Record<string, string> = {
  "SimRank-Only":           "border-heritage-teal",
  "Hybrid (30% Embedding)": "border-heritage-gold",
  "Hybrid (50-50)":         "border-heritage-brown",
  "Hybrid (70% Embedding)": "border-heritage-light",
  "Embedding-Only (FAISS)": "border-heritage-rust",
};

const METHOD_TEXT: Record<string, string> = {
  "SimRank-Only":           "text-heritage-teal",
  "Hybrid (30% Embedding)": "text-heritage-gold",
  "Hybrid (50-50)":         "text-heritage-brown",
  "Hybrid (70% Embedding)": "text-heritage-light",
  "Embedding-Only (FAISS)": "text-heritage-rust",
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function pct(v: number, decimals = 1) {
  return `${(v * 100).toFixed(decimals)}%`;
}

// ── Sub-components ────────────────────────────────────────────────────────────

function CalloutBadge({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: string;
  sub: string;
  color: string;
}) {
  return (
    <div className={`heritage-card p-5 border-t-4 ${color}`}>
      <p className="text-xs text-heritage-brown font-semibold uppercase tracking-wide mb-1">{label}</p>
      <p className="font-serif text-2xl font-bold text-heritage-dark">{value}</p>
      <p className="text-[11px] text-gray-400 mt-1 leading-snug">{sub}</p>
    </div>
  );
}

/** Horizontal bar with label and value */
function HBar({
  label,
  value,
  max,
  color,
  annotation,
}: {
  label: string;
  value: number;
  max: number;
  color: string;
  annotation?: string;
}) {
  const w = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div className="group">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-heritage-brown font-medium truncate max-w-[160px]">{label}</span>
        <div className="flex items-center gap-2">
          {annotation && (
            <span className="text-[10px] text-gray-400 italic">{annotation}</span>
          )}
          <span className="text-xs font-bold text-heritage-dark tabular-nums w-12 text-right">{pct(value)}</span>
        </div>
      </div>
      <div className="h-3 bg-parchment-100 rounded-full overflow-hidden border border-parchment-200">
        <div
          className={`h-full ${color} rounded-full transition-all duration-700`}
          style={{ width: `${w.toFixed(1)}%` }}
        />
      </div>
    </div>
  );
}

/** Grouped bar chart: for each method, show precision and ILD side by side */
function TradeoffChart() {
  const BAR_H = 28; // px height per metric strip
  const GAP = 16;
  const LABEL_W = 96;
  const CHART_W = 340;

  return (
    <div className="overflow-x-auto">
      <div className="min-w-[500px]">
        {/* Legend */}
        <div className="flex gap-6 mb-5 text-xs text-heritage-brown font-medium">
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-3 h-3 rounded-sm bg-heritage-teal" /> Precision@5 (accuracy)
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-3 h-3 rounded-sm bg-heritage-rust opacity-70" /> Intra-List Diversity
          </span>
        </div>

        {/* Rows */}
        <div className="space-y-4">
          {orderedMethods.map((mt) => {
            const p5 = mt.metrics.accuracy["precision@5"] ?? 0;
            const ild = mt.metrics.diversity.intra_list_diversity ?? 0;
            const embW = EMB_WEIGHTS[mt.name] ?? 0;
            const isSweet = mt.name === "Hybrid (30% Embedding)";
            return (
              <div key={mt.name} className={`relative ${isSweet ? "rounded-lg ring-2 ring-heritage-gold ring-offset-1 bg-parchment-50 p-2" : ""}`}>
                {isSweet && (
                  <span className="absolute -top-3 right-2 text-[10px] font-bold text-heritage-gold bg-white px-2 py-0.5 rounded-full border border-heritage-gold">
                    sweet spot
                  </span>
                )}
                <div className="flex items-center gap-3">
                  {/* Axis label */}
                  <div className="text-right shrink-0" style={{ width: LABEL_W }}>
                    <p className="text-[11px] font-semibold text-heritage-dark leading-tight">
                      {SHORT_LABELS[mt.name]?.replace("\n", " ")}
                    </p>
                    <p className="text-[9px] text-gray-400">{embW}% emb</p>
                  </div>

                  {/* Bars */}
                  <div className="flex-1 space-y-1">
                    {/* Precision bar */}
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-[10px] bg-parchment-100 rounded-full overflow-hidden border border-parchment-200">
                        <div
                          className="h-full bg-heritage-teal rounded-full"
                          style={{ width: `${(p5 * 100).toFixed(1)}%` }}
                        />
                      </div>
                      <span className="text-[10px] tabular-nums text-heritage-teal font-bold w-10 text-right">{pct(p5)}</span>
                    </div>
                    {/* ILD bar */}
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-[10px] bg-parchment-100 rounded-full overflow-hidden border border-parchment-200">
                        <div
                          className="h-full bg-heritage-rust opacity-70 rounded-full"
                          style={{ width: `${(ild * 100).toFixed(1)}%` }}
                        />
                      </div>
                      <span className="text-[10px] tabular-nums text-heritage-rust font-bold w-10 text-right">{pct(ild)}</span>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* X-axis annotation */}
        <div className="flex justify-between mt-4 px-[calc(96px+12px)] text-[9px] text-gray-400">
          <span>← SimRank-dominated</span>
          <span>Embedding-dominated →</span>
        </div>
      </div>
    </div>
  );
}

/** Radar-style score card for a single method */
function MethodScoreCard({ mt, highlight }: { mt: MethodMetrics; highlight?: boolean }) {
  const acc = mt.metrics.accuracy;
  const div = mt.metrics.diversity;
  const hs  = mt.metrics.heritage_specific;

  const scores = [
    { label: "P@5", value: acc["precision@5"] ?? 0, max: 1 },
    { label: "NDCG@5", value: acc["ndcg@5"] ?? 0, max: 1 },
    { label: "MAP", value: acc["MAP"] ?? 0, max: 1 },
    { label: "Diversity", value: div.intra_list_diversity ?? 0, max: 1 },
    { label: "Temporal", value: hs.temporal_accuracy ?? 0, max: 1 },
    { label: "Spatial", value: hs.spatial_relevance ?? 0, max: 1 },
  ];

  const color = METHOD_COLORS[mt.name] ?? "bg-heritage-brown";
  const border = METHOD_BORDER[mt.name] ?? "border-heritage-brown";
  const textColor = METHOD_TEXT[mt.name] ?? "text-heritage-brown";

  return (
    <div className={`heritage-card p-5 ${highlight ? `border-2 ${border}` : ""}`}>
      <div className="flex items-start justify-between mb-4">
        <div>
          <p className={`text-sm font-bold ${textColor}`}>{mt.name}</p>
          <p className="text-[10px] text-gray-400">{EMB_WEIGHTS[mt.name]}% embedding weight</p>
        </div>
        {highlight && (
          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full text-white ${color}`}>
            Recommended
          </span>
        )}
      </div>
      <div className="space-y-2.5">
        {scores.map((s) => (
          <HBar key={s.label} label={s.label} value={s.value} max={s.max} color={color} />
        ))}
      </div>
    </div>
  );
}

// ── Key metrics comparison table ───────────────────────────────────────────────

const TABLE_METRICS = [
  { key: "precision@5", label: "P@5" },
  { key: "ndcg@5",      label: "NDCG@5" },
  { key: "MAP",         label: "MAP" },
  { key: "recall@10",   label: "R@10" },
  { key: "intra_list_diversity", label: "ILD", diversity: true },
  { key: "coverage",             label: "Coverage", diversity: true },
];

// ── Page ──────────────────────────────────────────────────────────────────────

export default function EvaluationPage() {
  const simrankOnly = (evalData as Record<string, MethodMetrics>)["simrank_only"];
  const hybridSweet = (evalData as Record<string, MethodMetrics>)["hybrid_sr_heavy"];
  const embOnly     = (evalData as Record<string, MethodMetrics>)["embedding_only"];

  // best per metric for table highlight
  const bestPerMetric: Record<string, number> = {};
  for (const m of TABLE_METRICS) {
    if (m.diversity) {
      bestPerMetric[m.key] = Math.max(...methods.map((mt) => mt.metrics.diversity[m.key] ?? 0));
    } else {
      bestPerMetric[m.key] = Math.max(...methods.map((mt) => mt.metrics.accuracy[m.key] ?? 0));
    }
  }

  const maxLtrNdcg = Math.max(...ltrMethods.map(([, v]) => v.mean_ndcg));

  return (
    <div className="max-w-6xl mx-auto px-4 py-10">

      {/* ── Header ── */}
      <div className="mb-10">
        <p className="text-xs font-semibold uppercase tracking-widest text-heritage-gold mb-2">System Evaluation</p>
        <h1 className="font-serif text-3xl font-bold text-heritage-dark mb-3">
          How Does the Recommender Actually Perform?
        </h1>
        <p className="text-sm text-heritage-brown max-w-2xl leading-relaxed">
          We compared five retrieval configurations — from pure embedding search to pure knowledge-graph similarity —
          across 50 test queries with graded relevance judgements (0–3 scale). The headline number,{" "}
          <strong>Embedding-Only P@5 = 7.6%</strong>, looks alarming in isolation. The charts below explain why, and
          show how the hybrid system recovers.
        </p>
      </div>

      {/* ── Callout strip ── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-12">
        <CalloutBadge
          label="SimRank P@5"
          value="76.8%"
          sub="Knowledge-graph structure alone"
          color="border-heritage-teal"
        />
        <CalloutBadge
          label="Hybrid (30% Emb) P@5"
          value="70.4%"
          sub="Best precision–diversity balance"
          color="border-heritage-gold"
        />
        <CalloutBadge
          label="Embedding-Only P@5"
          value="7.6%"
          sub="Semantic search alone — explains the low headline"
          color="border-heritage-rust"
        />
        <CalloutBadge
          label="Embedding Diversity"
          value="75.3%"
          sub="Coverage — highest of all methods"
          color="border-heritage-brown"
        />
      </div>

      {/* ── Story section 1: The Tradeoff ── */}
      <section className="mb-12">
        <h2 className="font-serif text-xl font-semibold text-heritage-dark mb-1">
          The Precision–Diversity Tradeoff
        </h2>
        <p className="text-sm text-heritage-brown mb-6 max-w-2xl leading-relaxed">
          As you increase the embedding weight from 0 % to 100 %, precision
          (teal) collapses while intra-list diversity (rust) rises. The sweet
          spot is <strong>30 % embedding</strong>: you keep most of SimRank's
          precision while recovering meaningful result variety.
        </p>
        <div className="heritage-card p-6">
          <TradeoffChart />
        </div>
      </section>

      {/* ── Story section 2: Why embedding-only looks bad ── */}
      <section className="mb-12">
        <h2 className="font-serif text-xl font-semibold text-heritage-dark mb-1">
          Why Does Embedding-Only Score So Low?
        </h2>
        <p className="text-sm text-heritage-brown mb-6 max-w-2xl leading-relaxed">
          Our ground truth was built from the knowledge graph — documents connected via shared
          entities (location, dynasty, period) are considered relevant. Sentence embeddings capture
          surface-level semantics; they surface stylistically similar texts but miss the structural
          co-occurrence signal that defines heritage relevance in this corpus.{" "}
          <strong>This is a feature, not a bug</strong>: it validates that the KG encodes meaningful
          domain knowledge that embeddings alone cannot recover.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <MethodScoreCard mt={simrankOnly} />
          <MethodScoreCard mt={hybridSweet} highlight />
          <MethodScoreCard mt={embOnly} />
        </div>
      </section>

      {/* ── Story section 3: Full comparison table ── */}
      <section className="mb-12">
        <h2 className="font-serif text-xl font-semibold text-heritage-dark mb-1">
          All Methods at a Glance
        </h2>
        <p className="text-sm text-heritage-brown mb-4">
          Bold gold values mark the best in each column.
        </p>
        <div className="heritage-card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-parchment-300 bg-parchment-50">
                <th className="text-left py-3 px-4 font-semibold text-heritage-brown">Method</th>
                <th className="py-3 px-3 text-center text-[10px] font-semibold text-heritage-brown uppercase tracking-wide" colSpan={4}>
                  Accuracy
                </th>
                <th className="py-3 px-3 text-center text-[10px] font-semibold text-heritage-brown uppercase tracking-wide border-l border-parchment-200" colSpan={2}>
                  Diversity
                </th>
              </tr>
              <tr className="border-b border-parchment-200">
                <th className="text-left py-2 px-4 text-[10px] font-semibold text-heritage-brown" />
                {TABLE_METRICS.map((m, i) => (
                  <th
                    key={m.key}
                    className={`text-right py-2 px-3 text-[10px] font-semibold text-heritage-brown whitespace-nowrap ${i === 4 ? "border-l border-parchment-200" : ""}`}
                  >
                    {m.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {orderedMethods.map((mt) => {
                const isSweet = mt.name === "Hybrid (30% Embedding)";
                return (
                  <tr
                    key={mt.name}
                    className={`border-b border-parchment-200 last:border-0 transition-colors ${isSweet ? "bg-parchment-50" : "hover:bg-parchment-100"}`}
                  >
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <span className={`inline-block w-2 h-2 rounded-full ${METHOD_COLORS[mt.name] ?? "bg-gray-400"}`} />
                        <span className="font-medium text-heritage-dark text-sm">{mt.name}</span>
                        {isSweet && (
                          <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-heritage-gold text-white">★</span>
                        )}
                      </div>
                    </td>
                    {TABLE_METRICS.map((m, i) => {
                      const val = m.diversity
                        ? (mt.metrics.diversity[m.key] ?? 0)
                        : (mt.metrics.accuracy[m.key] ?? 0);
                      const isBest = Math.abs(val - bestPerMetric[m.key]) < 0.0001;
                      return (
                        <td
                          key={m.key}
                          className={`py-3 px-3 text-right tabular-nums text-sm ${
                            isBest
                              ? "font-bold text-heritage-gold"
                              : "text-heritage-dark"
                          } ${i === 4 ? "border-l border-parchment-200" : ""}`}
                        >
                          {pct(val)}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* ── Story section 4: Heritage-specific breakdown ── */}
      <section className="mb-12">
        <h2 className="font-serif text-xl font-semibold text-heritage-dark mb-1">
          Domain-Specific Quality
        </h2>
        <p className="text-sm text-heritage-brown mb-6 max-w-2xl">
          Beyond standard IR metrics, we measure how well each method preserves temporal context,
          geographic proximity, and cultural domain alignment — critical for a heritage corpus.
        </p>
        <div className="heritage-card p-6">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-8">
            {(["temporal_accuracy", "spatial_relevance", "cultural_domain_alignment"] as const).map((key) => {
              const labels: Record<string, string> = {
                temporal_accuracy:         "Temporal Accuracy",
                spatial_relevance:         "Spatial Relevance",
                cultural_domain_alignment: "Cultural Domain Alignment",
              };
              const descriptions: Record<string, string> = {
                temporal_accuracy:         "Are retrieved docs from the same era?",
                spatial_relevance:         "Are retrieved docs geographically close?",
                cultural_domain_alignment: "Do docs share the same cultural domain?",
              };
              return (
                <div key={key}>
                  <p className="text-xs font-bold text-heritage-dark mb-0.5">{labels[key]}</p>
                  <p className="text-[10px] text-gray-400 mb-3 italic">{descriptions[key]}</p>
                  <div className="space-y-2.5">
                    {orderedMethods.map((mt) => (
                      <HBar
                        key={mt.name}
                        label={SHORT_LABELS[mt.name]?.replace("\n", " ") ?? mt.name}
                        value={mt.metrics.heritage_specific[key] ?? 0}
                        max={1}
                        color={METHOD_COLORS[mt.name] ?? "bg-heritage-brown"}
                      />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ── Story section 5: LTR Ensemble ── */}
      <section className="mb-12">
        <h2 className="font-serif text-xl font-semibold text-heritage-dark mb-1">
          Re-Ranking with Learned Fusion
        </h2>
        <p className="text-sm text-heritage-brown mb-6 max-w-2xl leading-relaxed">
          After hybrid scoring, four fusion strategies re-rank results using learned weights.
          All four converge near NDCG ≈ 0.99 on the training distribution —{" "}
          <strong>Borda Count edges out the others</strong> by a slim margin while maintaining lower
          variance. In production the Cascade method is preferred for latency reasons.
        </p>
        <div className="heritage-card p-6">
          <div className="space-y-4">
            {ltrMethods
              .slice()
              .sort(([, a], [, b]) => b.mean_ndcg - a.mean_ndcg)
              .map(([name, v]) => {
                const isBest = name === "borda";
                return (
                  <div key={name} className={`${isBest ? "rounded-lg bg-parchment-50 p-2 ring-1 ring-heritage-gold" : ""}`}>
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className={`text-sm font-bold capitalize text-heritage-dark`}>{name}</span>
                        {isBest && (
                          <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-heritage-gold text-white">best</span>
                        )}
                      </div>
                      <div className="text-right">
                        <span className="text-sm font-bold text-heritage-dark tabular-nums">{pct(v.mean_ndcg, 2)}</span>
                        <span className="text-[10px] text-gray-400 ml-2">±{pct(v.std_ndcg, 2)}</span>
                        <span className="text-[10px] text-gray-400 ml-2">({v.num_queries} queries)</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-3 bg-parchment-100 rounded-full overflow-hidden border border-parchment-200">
                        <div
                          className="h-full bg-heritage-brown rounded-full"
                          style={{ width: `${((v.mean_ndcg / maxLtrNdcg) * 100).toFixed(2)}%` }}
                        />
                      </div>
                      {/* Uncertainty band overlay — visual only */}
                      <span className="text-[10px] text-gray-400 w-8">σ {(v.std_ndcg * 100).toFixed(1)}</span>
                    </div>
                  </div>
                );
              })}
          </div>
          <p className="text-[10px] text-gray-400 mt-4">
            Trained on 83 queries. Near-perfect scores reflect training-set evaluation;
            expect lower but still competitive NDCG on held-out queries.
          </p>
        </div>
      </section>

      {/* ── Story section 6: Latency vs Quality ── */}
      <section className="mb-12">
        <h2 className="font-serif text-xl font-semibold text-heritage-dark mb-1">
          Latency vs. Quality
        </h2>
        <p className="text-sm text-heritage-brown mb-6">
          All methods run well under 1 ms per query. SimRank is fastest; adding embedding search adds
          marginal overhead while boosting diversity.
        </p>
        <div className="heritage-card p-6 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-parchment-200">
                <th className="text-left py-2 px-3 text-[10px] font-semibold text-heritage-brown">Method</th>
                <th className="text-right py-2 px-3 text-[10px] font-semibold text-heritage-brown">Latency (ms)</th>
                <th className="text-right py-2 px-3 text-[10px] font-semibold text-heritage-brown">QPS</th>
                <th className="text-right py-2 px-3 text-[10px] font-semibold text-heritage-brown">P@5</th>
                <th className="text-right py-2 px-3 text-[10px] font-semibold text-heritage-brown">ILD</th>
              </tr>
            </thead>
            <tbody>
              {orderedMethods.map((mt) => {
                const isSweet = mt.name === "Hybrid (30% Embedding)";
                return (
                  <tr
                    key={mt.name}
                    className={`border-b border-parchment-100 last:border-0 ${isSweet ? "bg-parchment-50 font-semibold" : ""}`}
                  >
                    <td className="py-2 px-3">
                      <div className="flex items-center gap-2">
                        <span className={`inline-block w-2 h-2 rounded-full ${METHOD_COLORS[mt.name] ?? "bg-gray-400"}`} />
                        <span className="text-heritage-dark text-xs">{mt.name}</span>
                      </div>
                    </td>
                    <td className="py-2 px-3 text-right tabular-nums text-xs text-heritage-dark">
                      {mt.metrics.efficiency.avg_query_latency_ms.toFixed(3)} ms
                    </td>
                    <td className="py-2 px-3 text-right tabular-nums text-xs text-heritage-dark">
                      {Math.round(mt.metrics.efficiency.queries_per_second).toLocaleString()}
                    </td>
                    <td className="py-2 px-3 text-right tabular-nums text-xs text-heritage-dark">
                      {pct(mt.metrics.accuracy["precision@5"] ?? 0)}
                    </td>
                    <td className="py-2 px-3 text-right tabular-nums text-xs text-heritage-dark">
                      {pct(mt.metrics.diversity.intra_list_diversity ?? 0)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* ── Takeaway footer ── */}
      <div className="heritage-card p-6 border-l-4 border-heritage-gold bg-parchment-50">
        <h3 className="font-serif text-lg font-semibold text-heritage-dark mb-2">Key Takeaways</h3>
        <ul className="text-sm text-heritage-brown space-y-1.5 list-none">
          <li>
            <strong className="text-heritage-dark">SimRank dominates precision</strong> because our
            ground truth is graph-derived — documents connected through shared heritage entities score highest.
          </li>
          <li>
            <strong className="text-heritage-dark">Embedding-only is not broken</strong> — it is doing
            its job (semantic similarity) but the evaluation signal favours structural co-occurrence.
            It contributes diversity.
          </li>
          <li>
            <strong className="text-heritage-dark">Hybrid (30 % embedding)</strong> is the recommended
            configuration: P@5 = 70.4 %, ILD = 53.4 %, MAP = 48.9 % — the best overall profile.
          </li>
          <li>
            <strong className="text-heritage-dark">Next step</strong>: collect real user relevance
            judgements to validate whether graph-based relevance matches user intent in practice.
          </li>
        </ul>
      </div>
    </div>
  );
}
