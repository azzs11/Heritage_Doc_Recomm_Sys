import { Suspense } from "react";
import Loader from "@/components/ui/Loader";
import ErrorState from "@/components/ui/ErrorState";
import { getSystemStats, getMetrics, checkHealth, getKGStats } from "@/lib/api";

// Colour cycle for stacked bars
const BAR_COLORS = [
  "bg-heritage-teal",
  "bg-heritage-brown",
  "bg-heritage-gold",
  "bg-heritage-rust",
  "bg-heritage-light",
];

async function DashboardContent() {
  let stats, metrics, health, kgStats;

  try {
    [stats, metrics, health, kgStats] = await Promise.all([
      getSystemStats(),
      getMetrics().catch(() => null),
      checkHealth(),
      getKGStats().catch(() => null),
    ]);
  } catch {
    return (
      <ErrorState
        title="Backend not connected"
        message="Start FastAPI: uvicorn api.main:app --reload --port 8000"
      />
    );
  }

  const metricCards = [
    { label: "Total Documents", value: stats.total_documents.toLocaleString(), icon: "📄" },
    { label: "Knowledge Graph Nodes", value: stats.kg_nodes.toLocaleString(), icon: "🔗" },
    { label: "KG Edges", value: stats.kg_edges.toLocaleString(), icon: "↔️" },
    {
      label: "Avg Query Latency",
      value: metrics?.efficiency?.avg_query_latency_ms
        ? `${metrics.efficiency.avg_query_latency_ms.toFixed(1)} ms`
        : "—",
      icon: "⚡",
    },
  ];

  const accuracyMetrics = metrics?.accuracy
    ? Object.entries(metrics.accuracy).slice(0, 6)
    : null;

  const heritageMetrics = metrics?.heritage_specific
    ? Object.entries(metrics.heritage_specific)
    : null;

  return (
    <>
      {/* Status bar */}
      <div className="flex items-center gap-4 mb-6 flex-wrap">
        <div className="flex items-center gap-2">
          <span
            className={`w-2.5 h-2.5 rounded-full ${health?.recommender_loaded ? "bg-green-500" : "bg-yellow-400"}`}
          />
          <span className="text-sm text-heritage-brown">
            {health?.recommender_loaded
              ? `Recommender loaded · ${health.documents_indexed} documents indexed`
              : "Recommender loading..."}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`w-2.5 h-2.5 rounded-full ${health?.adaptive_ranker_loaded ? "bg-green-500" : "bg-yellow-400"}`}
          />
          <span className="text-sm text-heritage-brown">
            {health?.adaptive_ranker_loaded ? "Adaptive ranker loaded" : "Adaptive ranker unavailable"}
          </span>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {metricCards.map((m) => (
          <div key={m.label} className="heritage-card p-5">
            <div className="text-3xl mb-2">{m.icon}</div>
            <div className="text-2xl font-bold text-heritage-dark font-serif">{m.value}</div>
            <div className="text-xs text-heritage-brown uppercase tracking-wide mt-1">{m.label}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* KG Structure — enriched card */}
        <div className="heritage-card p-5">
          <h3 className="font-serif font-semibold text-heritage-dark mb-1">Knowledge Graph Structure</h3>
          <p className="text-[11px] text-gray-400 mb-4">Heterogeneous graph powering SimRank similarity</p>

          {/* Density + Avg Degree chips */}
          {kgStats && (
            <div className="flex gap-3 mb-4">
              <div className="flex-1 bg-parchment-50 border border-parchment-200 rounded-lg p-2.5 text-center">
                <p className="text-[10px] text-heritage-brown font-semibold uppercase tracking-wide">Density</p>
                <p className="font-bold text-heritage-dark font-serif text-base">{kgStats.density.toFixed(4)}</p>
              </div>
              <div className="flex-1 bg-parchment-50 border border-parchment-200 rounded-lg p-2.5 text-center">
                <p className="text-[10px] text-heritage-brown font-semibold uppercase tracking-wide">Avg Degree</p>
                <p className="font-bold text-heritage-dark font-serif text-base">{kgStats.average_degree.toFixed(1)}</p>
              </div>
            </div>
          )}

          {/* Node type stacked bar */}
          <p className="text-[10px] font-bold text-heritage-brown uppercase tracking-wide mb-1.5">Node Types</p>
          {(() => {
            const entries = Object.entries(stats.node_types) as [string, number][];
            const total = entries.reduce((s, [, c]) => s + c, 0) || 1;
            return (
              <>
                <div className="flex h-3 rounded-full overflow-hidden gap-px mb-2">
                  {entries.map(([type, count], i) => (
                    <div
                      key={type}
                      className={`${BAR_COLORS[i % BAR_COLORS.length]} first:rounded-l-full last:rounded-r-full`}
                      style={{ width: `${(count / total * 100).toFixed(1)}%` }}
                      title={`${type}: ${count.toLocaleString()}`}
                    />
                  ))}
                </div>
                <div className="flex flex-wrap gap-x-3 gap-y-1">
                  {entries.map(([type, count], i) => (
                    <span key={type} className="flex items-center gap-1 text-[10px] text-heritage-brown">
                      <span className={`inline-block w-2 h-2 rounded-full ${BAR_COLORS[i % BAR_COLORS.length]}`} />
                      <span className="capitalize">{type}</span>
                      <span className="text-gray-400">({count.toLocaleString()})</span>
                    </span>
                  ))}
                </div>
              </>
            );
          })()}

          {/* Edge type stacked bar */}
          {kgStats && Object.keys(kgStats.edge_types).length > 0 && (
            <div className="mt-4">
              <p className="text-[10px] font-bold text-heritage-brown uppercase tracking-wide mb-1.5">Edge / Relation Types</p>
              {(() => {
                const entries = Object.entries(kgStats.edge_types) as [string, number][];
                const total = entries.reduce((s, [, c]) => s + c, 0) || 1;
                return (
                  <>
                    <div className="flex h-3 rounded-full overflow-hidden gap-px mb-2">
                      {entries.map(([rel, count], i) => (
                        <div
                          key={rel}
                          className={`${BAR_COLORS[i % BAR_COLORS.length]} first:rounded-l-full last:rounded-r-full`}
                          style={{ width: `${(count / total * 100).toFixed(1)}%` }}
                          title={`${rel}: ${count.toLocaleString()}`}
                        />
                      ))}
                    </div>
                    <div className="flex flex-wrap gap-x-3 gap-y-1">
                      {entries.map(([rel, count], i) => (
                        <span key={rel} className="flex items-center gap-1 text-[10px] text-heritage-brown">
                          <span className={`inline-block w-2 h-2 rounded-full ${BAR_COLORS[i % BAR_COLORS.length]}`} />
                          <span className="capitalize">{rel.replace(/_/g, " ")}</span>
                          <span className="text-gray-400">({count.toLocaleString()})</span>
                        </span>
                      ))}
                    </div>
                  </>
                );
              })()}
            </div>
          )}
        </div>

        {/* Accuracy metrics */}
        <div className="heritage-card p-5">
          <h3 className="font-serif font-semibold text-heritage-dark mb-4">Evaluation Metrics</h3>
          {accuracyMetrics ? (
            <dl className="space-y-2">
              {accuracyMetrics.map(([key, val]) => (
                <div key={key} className="flex justify-between items-center text-sm">
                  <dt className="text-heritage-brown">{key}</dt>
                  <dd className="font-semibold text-heritage-dark">
                    {typeof val === "number" ? val.toFixed(3) : String(val)}
                  </dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="text-sm text-heritage-brown opacity-70">
              Run evaluation to see metrics:<br />
              <code className="text-xs bg-parchment-200 px-1 rounded">python src/7_evaluation/run_evaluation.py</code>
            </p>
          )}
        </div>

        {/* Heritage-specific metrics */}
        <div className="heritage-card p-5">
          <h3 className="font-serif font-semibold text-heritage-dark mb-4">Heritage-Specific Metrics</h3>
          {heritageMetrics ? (
            <dl className="space-y-2">
              {heritageMetrics.map(([key, val]) => (
                <div key={key} className="flex justify-between items-center text-sm">
                  <dt className="text-heritage-brown capitalize">{key.replace(/_/g, " ")}</dt>
                  <dd className="font-semibold text-heritage-dark">
                    {typeof val === "number" ? `${(val * 100).toFixed(1)}%` : String(val)}
                  </dd>
                </div>
              ))}
            </dl>
          ) : (
            <div className="h-24 bg-parchment-200 rounded flex items-center justify-center text-heritage-brown text-sm">
              No evaluation data yet
            </div>
          )}
        </div>

        {/* Efficiency */}
        <div className="heritage-card p-5">
          <h3 className="font-serif font-semibold text-heritage-dark mb-4">System Efficiency</h3>
          {metrics?.efficiency ? (
            <dl className="space-y-2">
              {Object.entries(metrics.efficiency).map(([key, val]) => (
                <div key={key} className="flex justify-between items-center text-sm">
                  <dt className="text-heritage-brown capitalize">{key.replace(/_/g, " ")}</dt>
                  <dd className="font-semibold text-heritage-dark">
                    {typeof val === "number" ? val.toFixed(2) : String(val)}
                  </dd>
                </div>
              ))}
            </dl>
          ) : (
            <div className="h-24 bg-parchment-200 rounded flex items-center justify-center text-heritage-brown text-sm">
              No efficiency data yet
            </div>
          )}
        </div>
      </div>
    </>
  );
}

export default function DashboardPage() {
  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="font-serif text-3xl font-bold text-heritage-dark">System Dashboard</h1>
        <p className="text-sm text-heritage-brown mt-1">Live data from FastAPI backend</p>
      </div>
      <Suspense fallback={<Loader message="Loading dashboard..." />}>
        <DashboardContent />
      </Suspense>
    </div>
  );
}
