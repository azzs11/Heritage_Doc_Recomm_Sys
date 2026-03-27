"use client";

import Link from "next/link";
import { Document } from "@/lib/types";

interface Props {
  document: Document;
  showSaveButton?: boolean;
  showExplanation?: boolean;
}

const SOURCE_ICONS: Record<string, string> = {
  Wikipedia: "🌐",
  UNESCO: "🏛️",
  "Indian Heritage": "🇮🇳",
  "UNESCO World Heritage": "🏛️",
  "Archaeological Survey of India": "🔍",
  "Ministry of Culture, India": "🏛️",
  "Internet Archive": "📦",
};

export default function DocumentCard({ document: doc, showExplanation }: Props) {
  const saveDoc = (e: React.MouseEvent) => {
    e.preventDefault();
    try {
      const stored = localStorage.getItem("heritage_saved_docs");
      const saved: Document[] = stored ? JSON.parse(stored) : [];
      if (!saved.find((d) => d.id === doc.id)) {
        saved.push(doc);
        localStorage.setItem("heritage_saved_docs", JSON.stringify(saved));
      }
    } catch { /* ignore */ }
  };

  const scoreLabel = doc.score != null ? `${(doc.score * 100).toFixed(1)}% relevance` : null;

  // Build metadata tags — only non-null values
  const metaTags = [doc.type, doc.era, doc.region].filter(Boolean);

  const sourceIcon = doc.source ? (SOURCE_ICONS[doc.source] ?? "📄") : null;

  return (
    <Link href={`/document/${encodeURIComponent(doc.id)}`}>
      <div className="heritage-card p-4 flex gap-3 cursor-pointer hover:bg-parchment-200 transition-colors group">
        {/* Thumbnail */}
        <div className="w-14 h-16 bg-heritage-brown rounded flex-shrink-0 flex items-center justify-center text-white text-xl">
          📜
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <h3 className="font-serif font-semibold text-heritage-dark text-sm leading-snug line-clamp-2">
            {doc.title}
          </h3>

          {/* Source — prominent, right under title */}
          {doc.source && (
            <p className="text-xs text-heritage-brown mt-0.5 font-medium">
              {sourceIcon} {doc.source}
            </p>
          )}

          {/* Metadata tags */}
          {metaTags.length > 0 && (
            <p className="text-xs text-gray-500 mt-0.5 capitalize">
              {metaTags.join(" · ")}
            </p>
          )}

          {/* Summary */}
          {doc.summary && (
            <p className="text-xs text-gray-600 mt-1.5 line-clamp-2 leading-snug">
              {doc.summary}
            </p>
          )}

          {/* Keywords */}
          {doc.keywords && doc.keywords.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1.5">
              {doc.keywords.slice(0, 3).map((kw) => (
                <span key={kw} className="px-1.5 py-0.5 bg-parchment-200 border border-parchment-300 rounded text-[10px] text-heritage-dark leading-tight">
                  {kw}
                </span>
              ))}
            </div>
          )}

          {/* Explanation from recommender */}
          {showExplanation && doc.explanations && doc.explanations.length > 0 && (
            <p className="text-[10px] italic text-heritage-brown mt-1 line-clamp-2">{doc.explanations[0]}</p>
          )}

          {/* Relevance score */}
          {scoreLabel && (
            <p className="text-[10px] text-heritage-gold mt-1 font-medium">{scoreLabel}</p>
          )}
        </div>

        {/* Save button */}
        <button
          onClick={saveDoc}
          title="Save document"
          className="text-heritage-gold opacity-0 group-hover:opacity-100 hover:text-heritage-brown transition-all flex-shrink-0 self-start mt-1"
        >
          🔖
        </button>
      </div>
    </Link>
  );
}
