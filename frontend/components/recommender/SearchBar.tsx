"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const ENSEMBLE_OPTIONS = [
  { value: "", label: "Auto" },
  { value: "weighted", label: "Weighted" },
  { value: "reciprocal_rank", label: "Reciprocal Rank" },
  { value: "learned", label: "Learned" },
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
    <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-2 w-full max-w-2xl mx-auto">
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search documents..."
        className="flex-1 px-4 py-2.5 rounded border border-parchment-300 bg-white text-heritage-dark placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-heritage-gold text-sm"
      />
      <select
        value={ensemble}
        onChange={(e) => setEnsemble(e.target.value)}
        className="px-3 py-2.5 rounded border border-parchment-300 bg-white text-heritage-dark text-sm focus:outline-none focus:ring-2 focus:ring-heritage-gold"
      >
        {ENSEMBLE_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      <button type="submit" className="btn-primary whitespace-nowrap">
        Browse
      </button>
    </form>
  );
}
