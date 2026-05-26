"use client";

import Link from "next/link";

interface Topic { label: string; q: string }

export function TopicPills({ topics }: { topics: Topic[] }) {
  return (
    <div className="flex flex-wrap gap-2.5">
      {topics.map((t) => (
        <Link
          key={t.label}
          href={`/search?q=${encodeURIComponent(t.q)}`}
          className="group flex items-center gap-1.5 px-4 py-2 rounded-full border shadow-sm text-sm font-medium transition-all duration-200 hover:shadow-md topic-pill"
        >
          <span>{t.label}</span>
          <span className="text-heritage-gold text-xs opacity-0 group-hover:opacity-100 transition-opacity">→</span>
        </Link>
      ))}
    </div>
  );
}
