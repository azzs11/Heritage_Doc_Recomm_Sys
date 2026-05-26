"use client";

import Link from "next/link";
import { useState } from "react";
import { Document } from "@/lib/types";
import { Bookmark, BookmarkCheck, Globe, Landmark, MapPin, Search, Archive } from "lucide-react";

interface Props {
  document: Document;
  showExplanation?: boolean;
}

const SOURCE_ICONS: Record<string, React.ElementType> = {
  Wikipedia:                         Globe,
  UNESCO:                            Landmark,
  "Indian Heritage":                 Landmark,
  "UNESCO World Heritage":           Landmark,
  "Archaeological Survey of India":  Search,
  "Ministry of Culture, India":      Landmark,
  "Internet Archive":                Archive,
};

const ERA_STYLE: Record<string, { pill: string; bar: string }> = {
  ancient:  { pill: "bg-amber-50  text-amber-800  border-amber-200",  bar: "from-amber-400 to-amber-600" },
  medieval: { pill: "bg-orange-50 text-orange-800 border-orange-200", bar: "from-orange-400 to-orange-600" },
  modern:   { pill: "bg-teal-50   text-teal-800   border-teal-200",   bar: "from-teal-400   to-teal-600" },
};

const TYPE_ICONS: Record<string, string> = {
  temple: "🛕", fort: "🏰", mosque: "🕌", palace: "🏯",
  church: "⛪", stupa: "🪨", monastery: "🏯", tomb: "🪦",
  mausoleum: "🪦", shrine: "⛩️", gate: "🚪", tower: "🗼",
  cave: "🪨", museum: "🏛️", garden: "🌿", mahal: "🏰",
  monument: "🗿", site: "📍", architecture: "🏗️",
};

const TYPE_BG: Record<string, string> = {
  temple: "bg-orange-50 border-orange-100",
  fort:   "bg-stone-50  border-stone-100",
  mosque: "bg-teal-50   border-teal-100",
  palace: "bg-amber-50  border-amber-100",
  mausoleum: "bg-purple-50 border-purple-100",
  default:   "bg-parchment-50 border-parchment-200",
};

// Signal metadata for the explainability panel
const SIGNALS = [
  {
    key: "embedding" as const,
    label: "Semantic Similarity",
    description: "How closely the content meaning matches",
    color: "bg-heritage-teal",
    trackColor: "bg-teal-100",
    textColor: "text-heritage-teal",
    icon: "◈",
  },
  {
    key: "simrank" as const,
    label: "Graph Relatedness",
    description: "Structural connection via Knowledge Graph",
    color: "bg-heritage-brown",
    trackColor: "bg-amber-100",
    textColor: "text-heritage-brown",
    icon: "◉",
  },
  {
    key: "horn" as const,
    label: "Heritage Importance",
    description: "Entity significance weight (Horn's Index)",
    color: "bg-heritage-gold",
    trackColor: "bg-yellow-100",
    textColor: "text-yellow-700",
    icon: "◆",
  },
] as const;

function ScoreBar({
  label,
  description,
  value,
  color,
  trackColor,
  textColor,
  icon,
}: {
  label: string;
  description: string;
  value: number;
  color: string;
  trackColor: string;
  textColor: string;
  icon: string;
}) {
  const pct = Math.round(Math.min(value * 100, 100));
  const strength =
    pct >= 65 ? "Strong" : pct >= 35 ? "Moderate" : pct >= 10 ? "Weak" : "—";

  return (
    <div className="space-y-0.5">
      <div className="flex items-center justify-between">
        <span className={`text-[10px] font-bold ${textColor} flex items-center gap-1`}>
          <span className="text-[9px]">{icon}</span>
          {label}
        </span>
        <span className={`text-[10px] font-semibold ${textColor}`}>
          {pct > 0 ? `${pct}%` : "—"}
          <span className="text-[9px] font-normal text-gray-400 ml-1">({strength})</span>
        </span>
      </div>
      <div className={`h-1.5 w-full ${trackColor} rounded-full overflow-hidden`}>
        <div
          className={`h-full ${color} rounded-full transition-all duration-500`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-[9px] text-gray-400 leading-tight">{description}</p>
    </div>
  );
}

export default function DocumentCard({ document: doc, showExplanation }: Props) {
  const [whyOpen, setWhyOpen] = useState(false);
  const [saved, setSaved] = useState(false);

  const saveDoc = (e: React.MouseEvent) => {
    e.preventDefault();
    try {
      const stored = localStorage.getItem("heritage_saved_docs");
      const savedDocs: Document[] = stored ? JSON.parse(stored) : [];
      if (!savedDocs.find((d) => d.id === doc.id)) {
        savedDocs.push(doc);
        localStorage.setItem("heritage_saved_docs", JSON.stringify(savedDocs));
      }
      setSaved(true);
    } catch { /* ignore */ }
  };

  const toggleWhy = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setWhyOpen((v) => !v);
  };

  const scorePercent  = doc.score != null ? Math.round(doc.score * 100) : null;
  const SourceIcon    = doc.source ? (SOURCE_ICONS[doc.source] ?? Globe) : Globe;
  const typeKey       = doc.type?.toLowerCase() ?? "";
  const typeIcon      = TYPE_ICONS[typeKey] ?? "📜";
  const iconBg        = TYPE_BG[typeKey] ?? TYPE_BG.default;
  const eraStyle      = doc.era ? (ERA_STYLE[doc.era.toLowerCase()] ?? null) : null;
  const scoreColor    = scorePercent != null
    ? scorePercent >= 70 ? "text-emerald-600" : scorePercent >= 40 ? "text-heritage-gold" : "text-gray-400"
    : null;
  const barColor      = eraStyle?.bar ?? "from-heritage-gold to-heritage-brown";

  // Only show "Why?" when we have component scores and a real search is happening
  const hasComponentScores =
    showExplanation &&
    doc.component_scores != null &&
    Object.values(doc.component_scores).some((v) => v > 0);

  // Shared entities to surface in the panel
  const sharedLocations = doc.entities?.locations?.slice(0, 3) ?? [];
  const sharedPersons   = doc.entities?.persons?.slice(0, 2) ?? [];

  return (
    <Link href={`/document/${encodeURIComponent(doc.id)}`} aria-label={`View document: ${doc.title}`}>
      <div
        className="card-glow gradient-border group relative rounded-2xl overflow-hidden flex flex-col h-full cursor-pointer transition-all duration-250 hover:-translate-y-1"
        style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}
      >

        {/* Coloured top bar */}
        <div className={`h-[3px] w-full bg-gradient-to-r ${barColor}`} />

        <div className="flex gap-3 p-4 flex-1">
          {/* Icon badge */}
          <div className={`w-11 h-11 rounded-xl border flex-shrink-0 flex items-center justify-center text-xl ${iconBg}`}>
            {typeIcon}
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <h3 className="font-serif font-bold text-heritage-dark text-sm leading-snug line-clamp-2 group-hover:text-heritage-brown transition-colors">
              {doc.title}
            </h3>

            {doc.source && (
              <p className="text-[11px] mt-0.5 font-medium flex items-center gap-1" style={{ color: "var(--text-muted)" }}>
                <SourceIcon className="w-3 h-3 inline-block" />
                {doc.source}
              </p>
            )}

            {/* Pill tags */}
            <div className="flex flex-wrap gap-1 mt-1.5">
              {doc.era && eraStyle && (
                <span className={`tag-pill border ${eraStyle.pill}`}>{doc.era}</span>
              )}
              {doc.type && (
                <span className="tag-pill bg-parchment-50 text-heritage-dark border-parchment-300">{doc.type}</span>
              )}
              {doc.region && (
                <span className="tag-pill bg-heritage-teal/10 text-heritage-teal border-heritage-teal/20 flex items-center gap-0.5">
                  <MapPin className="w-2.5 h-2.5 inline-block" />
                  {doc.region}
                </span>
              )}
            </div>

            {/* Summary */}
            {doc.summary && (
              <p className="text-[11px] text-gray-500 mt-2 line-clamp-2 leading-relaxed">
                {doc.summary}
              </p>
            )}

            {/* Keywords */}
            {doc.keywords && doc.keywords.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {doc.keywords.slice(0, 4).map((kw) => (
                  <span key={kw} className="px-1.5 py-px bg-parchment-50 border border-parchment-200 rounded-md text-[10px] text-heritage-dark">
                    {kw}
                  </span>
                ))}
              </div>
            )}

            {showExplanation && doc.explanations && doc.explanations.length > 0 && (
              <p className="text-[10px] italic text-heritage-brown mt-1.5 line-clamp-1 opacity-70">
                ✦ {doc.explanations[0]}
              </p>
            )}
          </div>
        </div>

        {/* ── Explainability panel (inline, toggled) ──────────────────── */}
        {whyOpen && hasComponentScores && (
          <div
            className="mx-3 mb-3 rounded-xl p-3 space-y-2.5"
            style={{ border: "1px solid var(--border)", backgroundColor: "var(--bg-muted)" }}
            onClick={(e) => e.preventDefault()}
          >
            <p className="text-[10px] font-bold text-heritage-dark uppercase tracking-widest mb-1 flex items-center gap-1.5">
              <span className="opacity-60">⬡</span> Why recommended
            </p>

            {SIGNALS.map((sig) => (
              <ScoreBar
                key={sig.key}
                label={sig.label}
                description={sig.description}
                value={doc.component_scores![sig.key] ?? 0}
                color={sig.color}
                trackColor={sig.trackColor}
                textColor={sig.textColor}
                icon={sig.icon}
              />
            ))}

            {/* Shared entities */}
            {(sharedLocations.length > 0 || sharedPersons.length > 0) && (
              <div className="pt-1.5 border-t border-parchment-200">
                <p className="text-[9px] font-bold text-gray-400 uppercase tracking-widest mb-1">
                  Shared entities
                </p>
                <div className="flex flex-wrap gap-1">
                  {sharedLocations.map((loc) => (
                    <Link
                      key={loc}
                      href={`/search?q=${encodeURIComponent(loc)}`}
                      onClick={(e) => e.stopPropagation()}
                      className="px-1.5 py-px bg-teal-50 border border-teal-100 rounded text-[9px] text-heritage-teal font-medium hover:opacity-75 transition-opacity"
                    >
                      📍 {loc}
                    </Link>
                  ))}
                  {sharedPersons.map((p) => (
                    <Link
                      key={p}
                      href={`/search?q=${encodeURIComponent(p)}`}
                      onClick={(e) => e.stopPropagation()}
                      className="px-1.5 py-px bg-amber-50 border border-amber-100 rounded text-[9px] text-amber-700 font-medium hover:opacity-75 transition-opacity"
                    >
                      👤 {p}
                    </Link>
                  ))}
                </div>
              </div>
            )}

            {/* Cluster label */}
            {doc.cluster_label && (
              <div className="pt-1 border-t border-parchment-200 flex items-center gap-1.5">
                <span className="text-[9px] text-gray-400 font-bold uppercase tracking-widest">Cluster</span>
                <span className="text-[9px] px-1.5 py-px bg-heritage-dark/5 border border-heritage-dark/10 rounded text-heritage-dark font-medium">
                  {doc.cluster_label}
                </span>
              </div>
            )}
          </div>
        )}

        {/* Footer bar */}
        <div className="px-4 py-2.5 border-t flex items-center justify-between gap-2"
             style={{ backgroundColor: "var(--bg-muted)", borderColor: "var(--border)" }}>
          {scorePercent !== null ? (
            <div className="flex flex-col gap-1 flex-1 min-w-0">
              {hasComponentScores ? (() => {
                const cs = doc.component_scores!;
                const total = (cs.embedding ?? 0) + (cs.simrank ?? 0) + (cs.horn ?? 0) || 1;
                const embW  = ((cs.embedding ?? 0) / total * 100).toFixed(1);
                const srW   = ((cs.simrank  ?? 0) / total * 100).toFixed(1);
                const hnW   = ((cs.horn     ?? 0) / total * 100).toFixed(1);
                return (
                  <>
                    <div className="flex h-1.5 w-full rounded-full overflow-hidden gap-px" title="Signal breakdown: Semantic | Graph | Heritage">
                      <div className="bg-heritage-teal   rounded-l-full" style={{ width: `${embW}%` }} title={`Semantic ${embW}%`} />
                      <div className="bg-heritage-brown"                  style={{ width: `${srW}%`  }} title={`Graph ${srW}%`} />
                      <div className="bg-heritage-gold   rounded-r-full" style={{ width: `${hnW}%`  }} title={`Heritage ${hnW}%`} />
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-[9px] text-gray-400 flex items-center gap-2">
                        <span className="flex items-center gap-0.5"><span className="inline-block w-1.5 h-1.5 rounded-full bg-heritage-teal" />Semantic</span>
                        <span className="flex items-center gap-0.5"><span className="inline-block w-1.5 h-1.5 rounded-full bg-heritage-brown" />Graph</span>
                        <span className="flex items-center gap-0.5"><span className="inline-block w-1.5 h-1.5 rounded-full bg-heritage-gold" />Heritage</span>
                      </span>
                      <span className={`text-[10px] font-bold ${scoreColor} ml-auto`}>{scorePercent}%</span>
                    </div>
                  </>
                );
              })() : (
                <div className="flex items-center gap-2">
                  <div className="h-1.5 w-24 bg-parchment-200 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full bg-gradient-to-r ${barColor} transition-all`}
                      style={{ width: `${Math.min(scorePercent, 100)}%` }}
                    />
                  </div>
                  <span className={`text-[10px] font-bold ${scoreColor}`}>{scorePercent}%</span>
                </div>
              )}
            </div>
          ) : (
            <div className="flex-1" />
          )}

          <div className="flex items-center gap-2">
            {/* Why button — only when component scores exist */}
            {hasComponentScores && (
              <button
                onClick={toggleWhy}
                title="Why was this recommended?"
                aria-label={whyOpen ? "Close explanation" : "Why was this recommended?"}
                aria-expanded={whyOpen}
                className={`text-[9px] font-bold px-2 py-0.5 rounded-full border transition-all ${
                  whyOpen
                    ? "bg-heritage-dark text-heritage-gold border-heritage-dark"
                    : "bg-white text-heritage-brown border-parchment-300 hover:border-heritage-brown"
                }`}
              >
                {whyOpen ? "✕ close" : "Why?"}
              </button>
            )}

            <button
              onClick={saveDoc}
              title="Save document"
              aria-label={saved ? "Document saved" : "Save document"}
              aria-pressed={saved}
              className={`transition-all ${saved ? "opacity-100 text-heritage-gold scale-110" : "opacity-0 group-hover:opacity-100 text-heritage-gold hover:scale-125"}`}
            >
              {saved
                ? <BookmarkCheck className="w-4 h-4" />
                : <Bookmark className="w-4 h-4" />
              }
            </button>
          </div>
        </div>
      </div>
    </Link>
  );
}
