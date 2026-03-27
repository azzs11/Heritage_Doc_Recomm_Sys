import Link from "next/link";
import DocumentCard from "@/components/recommender/DocumentCard";
import { Document } from "@/lib/types";

const QUERY_TYPE_COLORS: Record<string, string> = {
  factual: "bg-blue-100 text-blue-700 border-blue-200",
  exploratory: "bg-purple-100 text-purple-700 border-purple-200",
  navigational: "bg-green-100 text-green-700 border-green-200",
  analytical: "bg-amber-100 text-amber-700 border-amber-200",
};

const QUERY_TYPE_LABELS: Record<string, string> = {
  factual: "Factual query",
  exploratory: "Exploratory query",
  navigational: "Navigational query",
  analytical: "Analytical query",
};

const PAGE_SIZE = 20;

interface Props {
  documents: Document[];
  total?: number;
  currentPage?: number;
  showExplanation?: boolean;
  queryType?: string;
  ensembleMethod?: string;
  searchParams?: Record<string, string>;
}

function buildPageUrl(searchParams: Record<string, string>, page: number): string {
  const p = new URLSearchParams(searchParams);
  p.set("page", String(page));
  return `/search?${p.toString()}`;
}

export default function ResultsList({
  documents,
  total,
  currentPage = 1,
  showExplanation,
  queryType,
  ensembleMethod,
  searchParams = {},
}: Props) {
  if (documents.length === 0) {
    return (
      <div className="heritage-card p-12 text-center text-heritage-brown">
        <p className="text-3xl mb-3">🔍</p>
        <p className="font-serif text-lg">No documents found.</p>
        <p className="text-sm mt-1">Try a different query or remove filters.</p>
      </div>
    );
  }

  const qtColor = queryType
    ? (QUERY_TYPE_COLORS[queryType.toLowerCase()] ?? "bg-gray-100 text-gray-600 border-gray-200")
    : null;
  const qtLabel = queryType
    ? (QUERY_TYPE_LABELS[queryType.toLowerCase()] ?? queryType)
    : null;

  const totalCount = total ?? documents.length;
  const totalPages = Math.ceil(totalCount / PAGE_SIZE);
  const hasPrev = currentPage > 1;
  const hasNext = currentPage < totalPages;

  // Warn if top result score is very low (< 0.1) — likely weak matches
  const topScore = documents[0]?.score ?? 0;
  const lowRelevance = topScore < 0.1 && searchParams.q;

  return (
    <div>
      {/* Results header */}
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <p className="text-sm text-heritage-brown">
          {totalCount} {totalCount === 1 ? "result" : "results"} found
          {searchParams.q ? ` for "${searchParams.q}"` : ""}
        </p>
        <div className="flex items-center gap-2">
          {queryType && qtColor && (
            <span className={`text-[11px] px-2 py-0.5 rounded-full border font-medium ${qtColor}`}>
              {qtLabel}
            </span>
          )}
          {ensembleMethod && (
            <span className="text-[11px] px-2 py-0.5 rounded-full border bg-parchment-200 text-heritage-brown border-parchment-300 font-medium capitalize">
              {ensembleMethod} ranking
            </span>
          )}
        </div>
      </div>

      {/* Low-relevance warning */}
      {lowRelevance && (
        <div className="mb-3 px-3 py-2 bg-amber-50 border border-amber-200 rounded text-xs text-amber-700">
          ⚠ Showing closest matches — no exact documents found for this query. Results may be broadly related.
        </div>
      )}

      <div className="space-y-3">
        {documents.map((doc) => (
          <DocumentCard key={doc.id} document={doc} showExplanation={showExplanation} />
        ))}
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 mt-6">
          {hasPrev ? (
            <Link
              href={buildPageUrl(searchParams, currentPage - 1)}
              className="px-3 py-1.5 text-sm rounded border border-parchment-300 bg-white text-heritage-dark hover:bg-parchment-100 transition-colors"
            >
              ← Previous
            </Link>
          ) : (
            <span className="px-3 py-1.5 text-sm rounded border border-parchment-200 bg-parchment-100 text-heritage-brown opacity-50 cursor-not-allowed">
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
            >
              Next →
            </Link>
          ) : (
            <span className="px-3 py-1.5 text-sm rounded border border-parchment-200 bg-parchment-100 text-heritage-brown opacity-50 cursor-not-allowed">
              Next →
            </span>
          )}
        </div>
      )}
    </div>
  );
}
