"use client";

import { useEffect, useState, useTransition } from "react";
import { Document, SearchFilters } from "@/lib/types";

// ── Thin result row ────────────────────────────────────────────────────────────

function RankRow({
  rank,
  doc,
  highlight,
}: {
  rank: number;
  doc: Document;
  highlight?: "up" | "down" | "same" | "new";
}) {
  const pct = doc.score != null ? Math.round(doc.score * 100) : null;

  const badgeStyle: Record<string, string> = {
    up:   "bg-emerald-50 text-emerald-700 border-emerald-200",
    down: "bg-red-50 text-red-600 border-red-200",
    same: "bg-parchment-50 text-heritage-brown border-parchment-200",
    new:  "bg-blue-50 text-blue-700 border-blue-200",
  };
  const badgeLabel: Record<string, string> = {
    up: "↑ higher", down: "↓ lower", same: "same", new: "new",
  };

  return (
    <div className="flex items-center gap-2.5 py-2 px-3 rounded-xl hover:bg-parchment-50 transition-colors group">
      {/* Rank number */}
      <span className="w-5 text-center text-[11px] font-bold text-heritage-brown opacity-60 flex-shrink-0">
        {rank}
      </span>

      {/* Title + meta */}
      <div className="flex-1 min-w-0">
        <p className="text-xs font-semibold text-heritage-dark leading-snug line-clamp-1">
          {doc.title}
        </p>
        <div className="flex items-center gap-1.5 mt-0.5">
          {doc.era && (
            <span className="text-[9px] text-heritage-brown capitalize">{doc.era}</span>
          )}
          {doc.era && doc.type && <span className="text-[9px] text-gray-300">·</span>}
          {doc.type && (
            <span className="text-[9px] text-gray-400 capitalize">{doc.type}</span>
          )}
        </div>
      </div>

      {/* Score */}
      {pct !== null && (
        <span className="text-[10px] font-bold text-heritage-brown flex-shrink-0 w-8 text-right">
          {pct}%
        </span>
      )}

      {/* Highlight badge */}
      {highlight && highlight !== "same" && (
        <span className={`text-[9px] px-1.5 py-px rounded-full border font-semibold flex-shrink-0 ${badgeStyle[highlight]}`}>
          {badgeLabel[highlight]}
        </span>
      )}
    </div>
  );
}

// ── Column header ──────────────────────────────────────────────────────────────

function ColHeader({
  label,
  sublabel,
  accent,
}: {
  label: string;
  sublabel: string;
  accent: string;
}) {
  return (
    <div className={`px-4 py-3 rounded-t-2xl border-b border-parchment-200 ${accent}`}>
      <p className="text-xs font-bold text-heritage-dark">{label}</p>
      <p className="text-[10px] text-heritage-brown mt-0.5">{sublabel}</p>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

interface Props {
  query: string;
  filters: SearchFilters;
  hybridDocs: Document[];   // already fetched by the server component
}

export default function CompareView({ query, filters, hybridDocs }: Props) {
  const [baselineDocs, setBaselineDocs] = useState<Document[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [, startTransition] = useTransition();

  useEffect(() => {
    if (!query) return;
    setBaselineDocs(null);
    setError(null);

    startTransition(async () => {
      try {
        // Dynamic import so the api module isn't bundled into the server component
        const { searchBaseline } = await import("@/lib/api");
        const res = await searchBaseline(query, filters, 10);
        setBaselineDocs(res.documents);
      } catch {
        setError("Could not load baseline results.");
      }
    });
  }, [query, JSON.stringify(filters)]);

  // Build rank maps for diff highlights
  const hybridRankMap = new Map(hybridDocs.slice(0, 10).map((d, i) => [d.id, i + 1]));
  const baselineRankMap = new Map((baselineDocs ?? []).map((d, i) => [d.id, i + 1]));

  function highlight(docId: string, side: "hybrid" | "baseline"): "up" | "down" | "same" | "new" | undefined {
    const hybridRank = hybridRankMap.get(docId);
    const baselineRank = baselineRankMap.get(docId);
    if (side === "hybrid") {
      if (baselineRank === undefined) return "new";           // appears in hybrid, not baseline
      if (hybridRank! < baselineRank) return "up";
      if (hybridRank! > baselineRank) return "down";
      return "same";
    } else {
      if (hybridRank === undefined) return "new";             // appears in baseline, not hybrid
      if (baselineRank! < hybridRank) return "up";
      if (baselineRank! > hybridRank) return "down";
      return "same";
    }
  }

  const hybrid10 = hybridDocs.slice(0, 10);

  // Count how many results differ in top-5
  const hybrid5Ids  = new Set(hybrid10.slice(0, 5).map((d) => d.id));
  const baseline5Ids = new Set((baselineDocs ?? []).slice(0, 5).map((d) => d.id));
  const overlap5 = Array.from(hybrid5Ids).filter((id) => baseline5Ids.has(id)).length;
  const diffCount = 5 - overlap5;

  return (
    <div className="space-y-4">
      {/* Summary banner */}
      {baselineDocs && (
        <div className="flex items-center gap-3 px-4 py-2.5 bg-white border border-parchment-200 rounded-xl text-xs">
          <span className="text-heritage-dark font-semibold">Top-5 comparison:</span>
          {diffCount === 0 ? (
            <span className="text-gray-500">Both methods return identical top-5 results for this query.</span>
          ) : (
            <span className="text-gray-500">
              <span className="font-bold text-heritage-dark">{diffCount}</span> of 5 results differ between hybrid and cosine-only.
              <span className="ml-1.5 text-heritage-brown font-medium">Hybrid reranked using SimRank + Horn's Index.</span>
            </span>
          )}
        </div>
      )}

      {/* Two-column grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

        {/* Hybrid column */}
        <div className="bg-white border border-parchment-200 rounded-2xl overflow-hidden shadow-sm">
          <ColHeader
            label="Hybrid System"
            sublabel="SimRank · Horn's Index · Embeddings"
            accent="bg-gradient-to-r from-heritage-dark/5 to-heritage-brown/5"
          />
          <div className="p-2 divide-y divide-parchment-100">
            {hybrid10.map((doc, i) => (
              <RankRow
                key={doc.id}
                rank={i + 1}
                doc={doc}
                highlight={baselineDocs ? highlight(doc.id, "hybrid") : undefined}
              />
            ))}
          </div>
        </div>

        {/* Baseline column */}
        <div className="bg-white border border-parchment-200 rounded-2xl overflow-hidden shadow-sm">
          <ColHeader
            label="Cosine Similarity (Baseline)"
            sublabel="Embedding similarity only — no graph"
            accent="bg-gradient-to-r from-blue-50 to-indigo-50"
          />
          {!baselineDocs && !error && (
            <div className="p-8 flex flex-col items-center gap-2 text-center">
              <div className="w-5 h-5 border-2 border-heritage-gold border-t-transparent rounded-full animate-spin" />
              <p className="text-xs text-gray-400">Loading baseline…</p>
            </div>
          )}
          {error && (
            <div className="p-6 text-xs text-red-500 text-center">{error}</div>
          )}
          {baselineDocs && (
            <div className="p-2 divide-y divide-parchment-100">
              {baselineDocs.slice(0, 10).map((doc, i) => (
                <RankRow
                  key={doc.id}
                  rank={i + 1}
                  doc={doc}
                  highlight={highlight(doc.id, "baseline")}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 px-1 text-[10px] text-gray-400">
        <span className="font-semibold text-gray-500">Legend:</span>
        <span><span className="text-emerald-600 font-bold">↑ higher</span> — ranked higher in this method</span>
        <span><span className="text-red-500 font-bold">↓ lower</span> — ranked lower in this method</span>
        <span><span className="text-blue-600 font-bold">new</span> — only in this method's top 10</span>
      </div>
    </div>
  );
}
