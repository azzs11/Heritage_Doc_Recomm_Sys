"use client";

import { useState } from "react";
import DocumentCard from "@/components/recommender/DocumentCard";
import CompareView from "@/components/search/CompareView";
import Link from "next/link";
import { Document, SearchFilters, ParsedQuery } from "@/lib/types";

const QUERY_TYPE_COLORS: Record<string, string> = {
  factual:     "bg-blue-100 text-blue-700 border-blue-200",
  exploratory: "bg-purple-100 text-purple-700 border-purple-200",
  navigational:"bg-green-100 text-green-700 border-green-200",
  analytical:  "bg-amber-100 text-amber-700 border-amber-200",
};
const QUERY_TYPE_LABELS: Record<string, string> = {
  factual:     "Factual query",
  exploratory: "Exploratory query",
  navigational:"Navigational query",
  analytical:  "Analytical query",
};

const PAGE_SIZE = 20;

// ── Query Understanding pill definitions ─────────────────────────────────────

const PILL_GROUPS: {
  key: keyof ParsedQuery;
  icon: string;
  label: string;
  color: string;
  linkable?: boolean;
}[] = [
  { key: "locations",           icon: "📍", label: "Location",   color: "bg-teal-50 text-heritage-teal border-teal-200",      linkable: true  },
  { key: "persons",             icon: "👤", label: "Person",     color: "bg-amber-50 text-amber-700 border-amber-200",        linkable: true  },
  { key: "organizations",       icon: "🏛️", label: "Org",        color: "bg-purple-50 text-purple-700 border-purple-200",     linkable: true  },
  { key: "heritage_types",      icon: "🏰", label: "Type",       color: "bg-orange-50 text-orange-700 border-orange-200",     linkable: false },
  { key: "architectural_styles",icon: "🏗️", label: "Style",      color: "bg-indigo-50 text-indigo-700 border-indigo-200",     linkable: false },
  { key: "domains",             icon: "🔖", label: "Domain",     color: "bg-rose-50 text-rose-700 border-rose-200",           linkable: false },
  { key: "region",              icon: "🗺️", label: "Region",     color: "bg-green-50 text-green-700 border-green-200",        linkable: false },
  { key: "time_period",         icon: "⏳", label: "Era",        color: "bg-blue-50 text-blue-700 border-blue-200",           linkable: false },
];

function QueryUnderstandingPanel({ parsed }: { parsed: ParsedQuery }) {
  const pills: { value: string; icon: string; color: string; linkable: boolean }[] = [];

  for (const group of PILL_GROUPS) {
    const raw = parsed[group.key];
    const values: string[] = Array.isArray(raw)
      ? (raw as string[]).filter(Boolean)
      : raw
      ? [raw as string]
      : [];
    for (const v of values) {
      pills.push({ value: v, icon: group.icon, color: group.color, linkable: group.linkable ?? false });
    }
  }

  if (pills.length === 0) return null;

  return (
    <div className="mb-4 px-4 py-2.5 bg-white border border-parchment-200 rounded-xl flex flex-wrap items-center gap-2 text-[11px]">
      <span className="text-heritage-brown font-semibold shrink-0">Query understood as:</span>
      {pills.map(({ value, icon, color, linkable }, i) =>
        linkable ? (
          <Link
            key={i}
            href={`/search?q=${encodeURIComponent(value)}`}
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border font-medium capitalize hover:opacity-80 transition-opacity ${color}`}
          >
            {icon} {value}
          </Link>
        ) : (
          <span
            key={i}
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border font-medium capitalize ${color}`}
          >
            {icon} {value}
          </span>
        )
      )}
    </div>
  );
}

interface Props {
  query: string;
  filters: SearchFilters;
  documents: Document[];
  total?: number;
  currentPage?: number;
  showExplanation?: boolean;
  queryType?: string;
  ensembleMethod?: string;
  parsedQuery?: ParsedQuery;
  searchParams?: Record<string, string>;
}

function buildPageUrl(searchParams: Record<string, string>, page: number): string {
  const p = new URLSearchParams(searchParams);
  p.set("page", String(page));
  return `/search?${p.toString()}`;
}

export default function ResultsWithCompare({
  query,
  filters,
  documents,
  total,
  currentPage = 1,
  showExplanation,
  queryType,
  ensembleMethod,
  parsedQuery,
  searchParams = {},
}: Props) {
  const [mode, setMode] = useState<"hybrid" | "compare">("hybrid");

  if (documents.length === 0) {
    return (
      <div className="bg-white border border-parchment-200 rounded-2xl p-14 text-center shadow-sm">
        <p className="text-5xl mb-4">🔍</p>
        <p className="font-serif text-lg font-bold text-heritage-dark mb-1">No documents found</p>
        <p className="text-sm text-heritage-medium">Try a different query or remove filters.</p>
      </div>
    );
  }

  const qtColor = queryType
    ? (QUERY_TYPE_COLORS[queryType.toLowerCase()] ?? "bg-gray-100 text-gray-600 border-gray-200")
    : null;
  const qtLabel = queryType
    ? (QUERY_TYPE_LABELS[queryType.toLowerCase()] ?? queryType)
    : null;

  const totalCount  = total ?? documents.length;
  const totalPages  = Math.ceil(totalCount / PAGE_SIZE);
  const hasPrev     = currentPage > 1;
  const hasNext     = currentPage < totalPages;
  const topScore    = documents[0]?.score ?? 0;
  const lowRelevance = topScore < 0.1 && searchParams.q;

  return (
    <div aria-label="Search results" aria-live="polite">
      {/* ── Results header ───────────────────────────────────────────── */}
      <div className="flex items-center justify-between mb-5 flex-wrap gap-2">
        <div>
          <p className="text-sm font-semibold text-heritage-dark" aria-atomic="true">
            {totalCount} {totalCount === 1 ? "result" : "results"}
            {searchParams.q
              ? <span className="font-normal text-heritage-medium"> for <em>"{searchParams.q}"</em></span>
              : ""}
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {queryType && qtColor && (
            <span className={`text-[11px] px-2.5 py-1 rounded-full border font-semibold ${qtColor}`}>
              {qtLabel}
            </span>
          )}
          {ensembleMethod && mode === "hybrid" && (
            <span className="text-[11px] px-2.5 py-1 rounded-full border bg-heritage-dark text-heritage-gold border-heritage-medium font-semibold capitalize">
              ✦ {ensembleMethod} ranking
            </span>
          )}

          {/* ── Mode toggle — only visible when there's a query ── */}
          {query && (
            <div className="flex items-center rounded-lg border border-parchment-300 overflow-hidden text-[11px] font-semibold" role="group" aria-label="View mode">
              <button
                onClick={() => setMode("hybrid")}
                aria-pressed={mode === "hybrid"}
                aria-label="Show hybrid results"
                className={`px-3 py-1.5 transition-colors ${
                  mode === "hybrid"
                    ? "bg-heritage-dark text-heritage-gold"
                    : "bg-white text-heritage-brown hover:bg-parchment-100"
                }`}
              >
                Hybrid
              </button>
              <button
                onClick={() => setMode("compare")}
                aria-pressed={mode === "compare"}
                aria-label="Compare hybrid vs baseline results"
                className={`px-3 py-1.5 border-l border-parchment-300 transition-colors ${
                  mode === "compare"
                    ? "bg-heritage-dark text-heritage-gold"
                    : "bg-white text-heritage-brown hover:bg-parchment-100"
                }`}
              >
                ⇄ vs Baseline
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Low-relevance warning */}
      {lowRelevance && mode === "hybrid" && (
        <div className="mb-4 px-4 py-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800 flex items-start gap-2">
          <span className="text-base">⚠️</span>
          <span>Showing closest matches — no exact documents found. Results may be broadly related.</span>
        </div>
      )}

      {/* ── Query understanding panel ────────────────────────────────── */}
      {query && parsedQuery && mode === "hybrid" && (
        <QueryUnderstandingPanel parsed={parsedQuery} />
      )}

      {/* ── Hybrid grid ─────────────────────────────────────────────── */}
      {mode === "hybrid" && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4" role="list" aria-label="Document results">
            {documents.map((doc) => (
              <div key={doc.id} role="listitem">
                <DocumentCard document={doc} showExplanation={showExplanation} />
              </div>
            ))}
          </div>

          {totalPages > 1 && (
            <nav className="flex items-center justify-center gap-2 mt-6" aria-label="Pagination">
              {hasPrev ? (
                <Link
                  href={buildPageUrl(searchParams, currentPage - 1)}
                  className="px-3 py-1.5 text-sm rounded border border-parchment-300 bg-white text-heritage-dark hover:bg-parchment-100 transition-colors"
                  aria-label="Previous page"
                >
                  ← Previous
                </Link>
              ) : (
                <span className="px-3 py-1.5 text-sm rounded border border-parchment-200 bg-parchment-100 text-heritage-brown opacity-50 cursor-not-allowed" aria-disabled="true">
                  ← Previous
                </span>
              )}
              <span className="text-sm text-heritage-brown px-2">
                Page {currentPage} of {totalPages}
              </span>
              {hasNext ? (
                <Link
                  href={buildPageUrl(searchParams, currentPage + 1)}
                  className="px-3 py-1.5 text-sm rounded border border-parchment-300 bg-white text-heritage-dark hover:bg-parchment-100 transition-colors"
                  aria-label="Next page"
                >
                  Next →
                </Link>
              ) : (
                <span className="px-3 py-1.5 text-sm rounded border border-parchment-200 bg-parchment-100 text-heritage-brown opacity-50 cursor-not-allowed" aria-disabled="true">
                  Next →
                </span>
              )}
            </nav>
          )}
        </>
      )}

      {/* ── Compare split view ──────────────────────────────────────── */}
      {mode === "compare" && (
        <CompareView query={query} filters={filters} hybridDocs={documents} />
      )}
    </div>
  );
}
