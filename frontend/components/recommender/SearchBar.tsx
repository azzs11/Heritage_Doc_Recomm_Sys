"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const ENSEMBLE_OPTIONS = [
  { value: "", label: "Auto (Adaptive)" },
  { value: "rrf", label: "Reciprocal Rank Fusion" },
  { value: "borda", label: "Borda Count" },
  { value: "combmnz", label: "CombMNZ" },
  { value: "cascade", label: "Cascade" },
];

export default function SearchBar({
  defaultValue,
  defaultEnsemble,
}: {
  defaultValue?: string;
  defaultEnsemble?: string;
}) {
  const [query, setQuery] = useState(defaultValue ?? "");
  const [ensemble, setEnsemble] = useState(defaultEnsemble ?? "");
  const router = useRouter();

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    const params = new URLSearchParams({ q: query.trim() });
    if (ensemble) params.set("ensemble", ensemble);
    router.push(`/search?${params}`);
  };

  return (
    <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-2 w-full max-w-2xl mx-auto" role="search" aria-label="Search heritage documents">
      <div className="flex-1 relative">
        <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" aria-hidden="true">🔍</span>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search manuscripts, monuments, inscriptions…"
          aria-label="Search query"
          className="w-full pl-9 pr-4 py-3 rounded-xl border border-white/20 bg-white/10 text-white placeholder-white/50 focus:outline-none focus:ring-2 focus:ring-heritage-gold focus:bg-white/15 text-sm backdrop-blur-sm transition-all"
        />
      </div>
      <select
        value={ensemble}
        onChange={(e) => setEnsemble(e.target.value)}
        aria-label="Ranking method"
        className="px-3 py-3 rounded-xl border border-white/20 bg-white/10 text-white text-sm focus:outline-none focus:ring-2 focus:ring-heritage-gold backdrop-blur-sm"
      >
        {ENSEMBLE_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value} className="bg-heritage-dark text-white">
            {opt.label}
          </option>
        ))}
      </select>
      <button
        type="submit"
        aria-label="Submit search"
        className="bg-heritage-gold hover:bg-yellow-400 text-heritage-dark font-bold px-6 py-3 rounded-xl transition-all whitespace-nowrap shadow hover:shadow-lg hover:-translate-y-px"
      >
        Search
      </button>
    </form>
  );
}
