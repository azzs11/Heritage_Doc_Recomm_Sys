import evalData from "../../../results/evaluation_results.json";
import ltrData from "../../../evaluation/ltr_comparison.json";

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

// Key metrics we surface in the comparison table (in order)
const KEY_METRICS: { key: string; label: string; pct?: boolean }[] = [
  { key: "precision@5", label: "P@5" },
  { key: "precision@10", label: "P@10" },
  { key: "ndcg@5", label: "NDCG@5" },
  { key: "ndcg@10", label: "NDCG@10" },
  { key: "MAP", label: "MAP" },
  { key: "recall@10", label: "R@10" },
];

// ── Helpers ───────────────────────────────────────────────────────────────────

function pct(v: number) {
  return `${(v * 100).toFixed(1)}%`;
}

function Bar({ value, max, color = "bg-heritage-gold" }: { value: number; max: number; color?: string }) {
  const width = max > 0 ? (value / max) * 100 : 0;
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-parchment-300 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${width.toFixed(1)}%` }} />
      </div>
      <span className="text-xs text-heritage-dark w-10 text-right font-medium">{pct(value)}</span>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function EvaluationPage() {
  // find best value per metric for highlighting
  const bestPerMetric: Record<string, number> = {};
  for (const m of KEY_METRICS) {
    bestPerMetric[m.key] = Math.max(...methods.map((mt) => mt.metrics.accuracy[m.key] ?? 0));
  }
  const maxNdcg = Math.max(...ltrMethods.map(([, v]) => v.mean_ndcg));

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="font-serif text-3xl font-bold text-heritage-dark">Evaluation Dashboard</h1>
        <p className="text-sm text-heritage-brown mt-1">
          Offline comparison of 5 retrieval methods · {methods[0] && Object.keys(methods[0].metrics.accuracy).length} metrics evaluated
        </p>
      </div>

      {/* ── Section 1: Key metrics comparison table ── */}
      <section className="mb-10">
        <h2 className="font-serif text-xl font-semibold text-heritage-dark mb-4">Accuracy Comparison</h2>
        <div className="heritage-card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-parchment-300">
                <th className="text-left py-3 px-4 font-semibold text-heritage-brown">Method</th>
                {KEY_METRICS.map((m) => (
                  <th key={m.key} className="text-right py-3 px-3 font-semibold text-heritage-brown whitespace-nowrap">
                    {m.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {methods.map((mt) => (
                <tr key={mt.name} className="border-b border-parchment-200 last:border-0 hover:bg-parchment-100 transition-colors">
                  <td className="py-3 px-4 font-medium text-heritage-dark">{mt.name}</td>
                  {KEY_METRICS.map((m) => {
                    const val = mt.metrics.accuracy[m.key] ?? 0;
                    const isBest = Math.abs(val - bestPerMetric[m.key]) < 0.0001;
                    return (
                      <td
                        key={m.key}
                        className={`py-3 px-3 text-right tabular-nums ${
                          isBest ? "font-bold text-heritage-gold" : "text-heritage-dark"
                        }`}
                      >
                        {pct(val)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-[11px] text-gray-400 mt-2">
          Bold gold values = best in column. Metrics computed at k=5/10.
        </p>
      </section>

      {/* ── Section 2: NDCG@5 visual bars ── */}
      <section className="mb-10">
        <h2 className="font-serif text-xl font-semibold text-heritage-dark mb-4">NDCG@5 Breakdown</h2>
        <div className="heritage-card p-5 space-y-4">
          {methods
            .slice()
            .sort((a, b) => (b.metrics.accuracy["ndcg@5"] ?? 0) - (a.metrics.accuracy["ndcg@5"] ?? 0))
            .map((mt) => (
              <div key={mt.name}>
                <p className="text-xs text-heritage-brown mb-1">{mt.name}</p>
                <Bar value={mt.metrics.accuracy["ndcg@5"] ?? 0} max={1} />
              </div>
            ))}
        </div>
      </section>

      {/* ── Section 3: Two-col detail cards ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-10">
        {/* Diversity */}
        <div className="heritage-card p-5">
          <h3 className="font-serif font-semibold text-heritage-dark mb-4">Diversity Metrics</h3>
          <div className="space-y-4">
            {methods.map((mt) => (
              <div key={mt.name}>
                <p className="text-xs font-medium text-heritage-brown mb-1 truncate">{mt.name}</p>
                <div className="flex gap-4 text-[11px] text-gray-500">
                  <span>ILD: <strong className="text-heritage-dark">{pct(mt.metrics.diversity.intra_list_diversity)}</strong></span>
                  <span>Coverage: <strong className="text-heritage-dark">{pct(mt.metrics.diversity.coverage)}</strong></span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Heritage-specific */}
        <div className="heritage-card p-5">
          <h3 className="font-serif font-semibold text-heritage-dark mb-4">Heritage-Specific Metrics</h3>
          <div className="space-y-4">
            {methods.map((mt) => {
              const hs = mt.metrics.heritage_specific;
              return (
                <div key={mt.name}>
                  <p className="text-xs font-medium text-heritage-brown mb-1 truncate">{mt.name}</p>
                  <div className="flex gap-3 text-[11px] text-gray-500 flex-wrap">
                    <span>Temporal: <strong className="text-heritage-dark">{pct(hs.temporal_accuracy)}</strong></span>
                    <span>Spatial: <strong className="text-heritage-dark">{pct(hs.spatial_relevance)}</strong></span>
                    <span>Domain: <strong className="text-heritage-dark">{pct(hs.cultural_domain_alignment)}</strong></span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Efficiency */}
        <div className="heritage-card p-5">
          <h3 className="font-serif font-semibold text-heritage-dark mb-4">Query Efficiency</h3>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-parchment-200">
                <th className="text-left text-heritage-brown pb-2 text-xs font-semibold">Method</th>
                <th className="text-right text-heritage-brown pb-2 text-xs font-semibold">Latency (ms)</th>
                <th className="text-right text-heritage-brown pb-2 text-xs font-semibold">QPS</th>
              </tr>
            </thead>
            <tbody>
              {methods.map((mt) => (
                <tr key={mt.name} className="border-b border-parchment-100 last:border-0">
                  <td className="py-1.5 text-heritage-dark text-xs">{mt.name}</td>
                  <td className="py-1.5 text-right text-xs tabular-nums text-heritage-dark">
                    {mt.metrics.efficiency.avg_query_latency_ms.toFixed(3)}
                  </td>
                  <td className="py-1.5 text-right text-xs tabular-nums text-heritage-dark">
                    {Math.round(mt.metrics.efficiency.queries_per_second).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* LTR comparison */}
        <div className="heritage-card p-5">
          <h3 className="font-serif font-semibold text-heritage-dark mb-1">LTR Ensemble Comparison</h3>
          <p className="text-[11px] text-gray-400 mb-4">Mean NDCG across Cascade / RRF / Borda / CombMNZ</p>
          <div className="space-y-3">
            {ltrMethods
              .slice()
              .sort(([, a], [, b]) => b.mean_ndcg - a.mean_ndcg)
              .map(([name, v]) => (
                <div key={name}>
                  <div className="flex justify-between mb-1">
                    <span className="text-xs font-medium text-heritage-brown capitalize">{name}</span>
                    <span className="text-xs text-gray-400">{v.num_queries} quer{v.num_queries === 1 ? "y" : "ies"}</span>
                  </div>
                  <Bar value={v.mean_ndcg} max={maxNdcg} color="bg-heritage-brown" />
                </div>
              ))}
          </div>
        </div>
      </div>

      {/* ── Section 4: Full accuracy table (all k) ── */}
      <section>
        <h2 className="font-serif text-xl font-semibold text-heritage-dark mb-4">Full Accuracy Breakdown</h2>
        <div className="heritage-card overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-parchment-300">
                <th className="text-left py-3 px-4 font-semibold text-heritage-brown">Method</th>
                {["precision@5","recall@5","f1@5","ndcg@5","precision@10","recall@10","f1@10","ndcg@10","precision@20","recall@20","f1@20","ndcg@20","MAP"].map((k) => (
                  <th key={k} className="text-right py-3 px-2 font-semibold text-heritage-brown whitespace-nowrap">
                    {k}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {methods.map((mt) => (
                <tr key={mt.name} className="border-b border-parchment-200 last:border-0 hover:bg-parchment-100 transition-colors">
                  <td className="py-2 px-4 font-medium text-heritage-dark whitespace-nowrap">{mt.name}</td>
                  {["precision@5","recall@5","f1@5","ndcg@5","precision@10","recall@10","f1@10","ndcg@10","precision@20","recall@20","f1@20","ndcg@20","MAP"].map((k) => (
                    <td key={k} className="py-2 px-2 text-right tabular-nums text-heritage-dark">
                      {pct(mt.metrics.accuracy[k] ?? 0)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
