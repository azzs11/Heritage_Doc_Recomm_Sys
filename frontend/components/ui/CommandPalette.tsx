"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Search, Bookmark, BarChart3, Landmark, FlaskConical, ScrollText, X } from "lucide-react";

const QUICK_LINKS = [
  { label: "Browse Archives",  href: "/search",     icon: Search },
  { label: "Saved Documents",  href: "/saved",      icon: Bookmark },
  { label: "Dashboard",        href: "/dashboard",  icon: BarChart3 },
  { label: "Evaluation",       href: "/evaluation", icon: FlaskConical },
];

const HERITAGE_SITES = [
  "Taj Mahal", "Ajanta Caves", "Ellora Caves", "Hampi",
  "Khajuraho", "Qutb Minar", "Red Fort", "Sanchi Stupa",
  "Konark Sun Temple", "Rani Ki Vav", "Mahabalipuram",
];

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const router = useRouter();

  const close = useCallback(() => { setOpen(false); setQuery(""); }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [close]);

  const navigate = (href: string) => {
    router.push(href);
    close();
  };

  const search = (q: string) => {
    navigate(`/search?q=${encodeURIComponent(q)}`);
  };

  const filteredSites = HERITAGE_SITES.filter((s) =>
    s.toLowerCase().includes(query.toLowerCase())
  );

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center pt-[20vh]"
      onClick={close}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 backdrop-blur-sm" style={{ backgroundColor: "rgba(0,0,0,0.5)" }} />

      {/* Panel */}
      <div
        className="relative w-full max-w-lg mx-4 rounded-2xl shadow-2xl overflow-hidden"
        style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b" style={{ borderColor: "var(--border)" }}>
          <Search className="w-4 h-4 flex-shrink-0" style={{ color: "var(--text-muted)" }} />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && query) search(query); }}
            placeholder="Search heritage archive..."
            className="flex-1 bg-transparent outline-none text-sm"
            style={{ color: "var(--text-primary)" }}
          />
          <button onClick={close} className="p-1 rounded-md hover:opacity-70 transition-opacity">
            <X className="w-4 h-4" style={{ color: "var(--text-muted)" }} />
          </button>
        </div>

        <div className="max-h-80 overflow-y-auto">
          {/* Quick links — shown when no query */}
          {!query && (
            <div className="p-2">
              <p className="text-[10px] font-bold uppercase tracking-widest px-2 py-1.5" style={{ color: "var(--text-subtle)" }}>
                Quick navigation
              </p>
              {QUICK_LINKS.map(({ label, href, icon: Icon }) => (
                <button
                  key={href}
                  onClick={() => navigate(href)}
                  className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-left transition-colors hover:opacity-80"
                  style={{ color: "var(--text-primary)" }}
                  onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "var(--bg-muted)")}
                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "")}
                >
                  <Icon className="w-4 h-4 flex-shrink-0" style={{ color: "var(--accent-gold)" }} />
                  {label}
                </button>
              ))}
            </div>
          )}

          {/* Heritage sites */}
          <div className="p-2 border-t" style={{ borderColor: "var(--border)" }}>
            <p className="text-[10px] font-bold uppercase tracking-widest px-2 py-1.5" style={{ color: "var(--text-subtle)" }}>
              {query ? "Heritage sites" : "Popular sites"}
            </p>
            {filteredSites.slice(0, 7).map((site) => (
              <button
                key={site}
                onClick={() => search(site)}
                className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-left transition-colors"
                style={{ color: "var(--text-primary)" }}
                onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "var(--bg-muted)")}
                onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "")}
              >
                <ScrollText className="w-4 h-4 flex-shrink-0" style={{ color: "var(--accent-teal)" }} />
                {site}
              </button>
            ))}
            {query && filteredSites.length === 0 && (
              <button
                onClick={() => search(query)}
                className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-left"
                style={{ color: "var(--text-primary)" }}
                onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "var(--bg-muted)")}
                onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "")}
              >
                <Search className="w-4 h-4 flex-shrink-0" style={{ color: "var(--accent-gold)" }} />
                Search for &ldquo;{query}&rdquo;
              </button>
            )}
          </div>
        </div>

        {/* Footer hint */}
        <div className="flex items-center justify-between px-4 py-2 border-t text-[10px]"
             style={{ borderColor: "var(--border)", color: "var(--text-subtle)" }}>
          <span>↑↓ navigate · Enter search · Esc close</span>
          <kbd className="px-1.5 py-0.5 rounded text-[9px] font-mono border" style={{ borderColor: "var(--border)" }}>⌘K</kbd>
        </div>
      </div>
    </div>
  );
}
