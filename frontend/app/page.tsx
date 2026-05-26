import { Suspense } from "react";
import SearchBar from "@/components/recommender/SearchBar";
import Link from "next/link";
import { getSystemStats } from "@/lib/api";
import { SpotlightHero } from "@/components/hero/SpotlightHero";
import { TextScramble } from "@/components/hero/TextScramble";
import { MagneticButton } from "@/components/hero/MagneticButton";
import { HeritageMarquee } from "@/components/hero/HeritagMarquee";
import { TopicPills } from "@/components/home/TopicPills";
import {
  Search, Bookmark, BarChart3, Landmark,
  ScrollText, Globe, Sword, Mountain,
  Sparkles, BookOpen, Network,
} from "lucide-react";

const COLLECTIONS = [
  {
    id: "medieval",
    name: "Medieval Records",
    subtitle: "800 – 1700 CE",
    description: "Sultanate dynasties, Rajput kingdoms & medieval temple architecture",
    query: "medieval sultanate rajput dynasty temple fort",
    era: "medieval",
    accent: "from-amber-800 via-heritage-dark to-stone-900",
    Icon: Sword,
  },
  {
    id: "ancient",
    name: "Ancient Inscriptions",
    subtitle: "3000 BCE – 700 CE",
    description: "Vedic civilisations, Mauryan edicts & early stone inscriptions",
    query: "ancient vedic inscription maurya stone edict",
    era: "ancient",
    accent: "from-heritage-dark via-stone-800 to-amber-950",
    Icon: Mountain,
  },
  {
    id: "colonial",
    name: "Colonial Archives",
    subtitle: "1700 – 1950 CE",
    description: "British colonial records, independence movement & modern heritage",
    query: "colonial british archive independence monument",
    era: "modern",
    accent: "from-heritage-teal via-heritage-medium to-heritage-dark",
    Icon: ScrollText,
  },
];

const FEATURED_TOPICS = [
  { label: "Mughal Architecture", q: "mughal architecture agra delhi" },
  { label: "Buddhist Stupas",     q: "buddhist stupa monastery sanchi" },
  { label: "Chola Temples",       q: "chola temple south india dynasty" },
  { label: "UNESCO World Heritage", q: "UNESCO world heritage site india" },
  { label: "Rajput Forts",        q: "rajput fort palace rajasthan" },
  { label: "Rock Edicts",         q: "ashoka rock edict inscription pillar" },
  { label: "Step Wells",          q: "stepwell vav water architecture" },
  { label: "Cave Temples",        q: "cave temple ajanta ellora sculpture" },
];

const STATIC_STATS = [
  { value: "3,000+", label: "Years of History" },
  { value: "5",      label: "Regions" },
  { value: "AI",     label: "Powered Ranking" },
];

// Bento grid items — asymmetric feature tiles
const BENTO_ITEMS = [
  {
    href: "/search",
    Icon: Search,
    label: "Browse All",
    desc: "Full archive search across every document",
    wide: true,
    accent: "#c8a84b",
  },
  {
    href: "/saved",
    Icon: Bookmark,
    label: "Saved",
    desc: "Your bookmarked documents",
    wide: false,
    accent: "#2a7c6f",
  },
  {
    href: "/dashboard",
    Icon: BarChart3,
    label: "Dashboard",
    desc: "System metrics & analytics",
    wide: false,
    accent: "#8b5e3c",
  },
  {
    href: "/search?q=UNESCO+world+heritage",
    Icon: Globe,
    label: "UNESCO Sites",
    desc: "Explore world heritage records",
    wide: false,
    accent: "#b84c2a",
  },
  {
    href: "/evaluation",
    Icon: Network,
    label: "Evaluation",
    desc: "Model performance & ranking metrics",
    wide: false,
    accent: "#4a2c17",
  },
];

// ── Async sub-components ──────────────────────────────────────────────────────

async function StatsStrip() {
  let totalDocs: number | null = null;
  try {
    const stats = await getSystemStats();
    totalDocs = stats.total_documents ?? null;
  } catch { /* non-fatal */ }

  const STATS = [
    { value: totalDocs != null ? totalDocs.toLocaleString() : "—", label: "Documents" },
    ...STATIC_STATS,
  ];

  return (
    <div className="max-w-6xl mx-auto grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
      {STATS.map((s) => (
        <div key={s.label} className="py-1">
          <div className="font-serif text-2xl font-bold text-heritage-gold tabular-nums">{s.value}</div>
          <div className="text-[11px] uppercase tracking-widest text-parchment-300 opacity-80 mt-0.5">{s.label}</div>
        </div>
      ))}
    </div>
  );
}

function StatsStripSkeleton() {
  return (
    <div className="max-w-6xl mx-auto grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
      {[...Array(4)].map((_, i) => (
        <div key={i} className="py-1 animate-pulse">
          <div className="h-7 w-16 bg-white/20 rounded mx-auto mb-1" />
          <div className="h-3 w-20 bg-white/10 rounded mx-auto" />
        </div>
      ))}
    </div>
  );
}

async function CollectionCards() {
  let eraCounts: Record<string, number> = {};
  try {
    const stats = await getSystemStats();
    eraCounts = stats.era_counts ?? {};
  } catch { /* non-fatal */ }

  const collections = COLLECTIONS.map((col) => ({
    ...col,
    tag: eraCounts[col.era] != null ? `${eraCounts[col.era].toLocaleString()} documents` : null,
  }));

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 mb-14">
      {collections.map((col, i) => {
        const Icon = col.Icon;
        return (
          <Link
            key={col.id}
            href={`/search?q=${encodeURIComponent(col.query)}&era=${col.era}`}
            className={`group relative overflow-hidden rounded-2xl shadow-md hover:shadow-xl transition-all duration-300 hover:-translate-y-1 gradient-border fade-up fade-up-delay-${i + 1}`}
          >
            {/* Background */}
            <div className={`h-52 bg-gradient-to-br ${col.accent} relative`}>
              <div
                className="absolute inset-0 opacity-10"
                style={{ backgroundImage: "radial-gradient(circle at 20% 80%, #c8a84b 0%, transparent 50%)" }}
              />
              <div className="collection-card-overlay absolute inset-0" />
              {/* Icon replacing emoji */}
              <div className="absolute top-4 right-4 opacity-60 group-hover:opacity-100 group-hover:scale-110 transition-all">
                <Icon className="w-9 h-9 text-white" />
              </div>
              {col.tag && (
                <div className="absolute top-4 left-4">
                  <span className="text-[10px] bg-white/15 border border-white/20 rounded-full px-2.5 py-1 text-white font-medium backdrop-blur-sm">
                    {col.tag}
                  </span>
                </div>
              )}
              <div className="absolute bottom-0 left-0 right-0 p-5">
                <p className="text-parchment-300 text-[10px] uppercase tracking-widest font-semibold mb-0.5">{col.subtitle}</p>
                <h3 className="text-white font-bold font-serif text-xl leading-tight">{col.name}</h3>
              </div>
            </div>
            <div
              className="px-5 py-4 border-t transition-colors"
              style={{ backgroundColor: "var(--bg-card)", borderColor: "var(--border)" }}
            >
              <p className="text-xs leading-snug" style={{ color: "var(--text-muted)" }}>{col.description}</p>
              <div className="flex items-center gap-1 mt-2">
                <span className="text-[11px] font-bold text-heritage-teal">Explore collection</span>
                <span className="text-heritage-teal text-xs group-hover:translate-x-1 transition-transform inline-block">→</span>
              </div>
            </div>
          </Link>
        );
      })}
    </div>
  );
}

function CollectionCardsSkeleton() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 mb-14">
      {[...Array(3)].map((_, i) => (
        <div key={i} className="rounded-2xl overflow-hidden shadow-md animate-pulse">
          <div className="h-52" style={{ backgroundColor: "var(--border)" }} />
          <div className="px-5 py-4 border-t" style={{ backgroundColor: "var(--bg-card)", borderColor: "var(--border)" }}>
            <div className="h-3 w-3/4 rounded mb-2" style={{ backgroundColor: "var(--border)" }} />
            <div className="h-3 w-1/2 rounded"    style={{ backgroundColor: "var(--border-subtle)" }} />
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function HomePage() {
  return (
    <div className="min-h-screen">

      {/* ── Hero ──────────────────────────────────────────────────────── */}
      <SpotlightHero>
        <section
          className="relative hero-shimmer noise-overlay text-white overflow-hidden"
          style={{ backgroundImage: "linear-gradient(135deg, #2d1a0a 0%, #4a2c17 40%, #3a2010 100%)" }}
        >
          {/* Decorative grid */}
          <div
            className="absolute inset-0 opacity-[0.04]"
            style={{
              backgroundImage: "linear-gradient(#c8a84b 1px, transparent 1px), linear-gradient(90deg, #c8a84b 1px, transparent 1px)",
              backgroundSize: "48px 48px",
            }}
          />
          {/* Gold glow orb */}
          <div className="absolute -top-24 -right-24 w-96 h-96 rounded-full bg-heritage-gold opacity-[0.06] blur-3xl pointer-events-none" />
          <div className="absolute -bottom-12 -left-12 w-64 h-64 rounded-full bg-heritage-teal opacity-[0.04] blur-3xl pointer-events-none" />

          <div className="relative max-w-5xl mx-auto text-center px-4 py-24">
            {/* Status badge */}
            <div className="inline-flex items-center gap-2 bg-white/10 border border-white/15 rounded-full px-4 py-1.5 mb-6 backdrop-blur-sm">
              <span className="w-1.5 h-1.5 rounded-full bg-heritage-gold animate-pulse" />
              <span className="text-[11px] font-semibold tracking-[0.18em] uppercase text-parchment-200">
                Knowledge Graph · Semantic AI · Learning-to-Rank
              </span>
            </div>

            {/* Hero title with text scramble */}
            <h1 className="font-serif text-5xl md:text-6xl font-bold mb-5 leading-tight tracking-tight">
              <TextScramble text="Explore India's" />
              {" "}
              <span
                style={{
                  background: "linear-gradient(90deg, #c8a84b, #e8c96e, #c8a84b)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  backgroundSize: "200% auto",
                  animation: "shimmer 4s linear infinite",
                }}
              >
                Heritage Archive
              </span>
            </h1>

            <p className="text-parchment-200 mb-10 text-lg max-w-2xl mx-auto leading-relaxed opacity-90">
              Discover manuscripts, inscriptions, and archival records spanning 3,000 years — powered by a hybrid AI recommendation engine.
            </p>

            <div className="max-w-2xl mx-auto mb-8">
              <SearchBar />
            </div>

            {/* Magnetic CTA buttons */}
            <div className="flex items-center justify-center gap-3 mb-8">
              <MagneticButton>
                <Link
                  href="/search"
                  className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-heritage-gold text-heritage-dark font-bold text-sm shadow-lg hover:shadow-xl hover:bg-yellow-400 transition-all"
                >
                  <Search className="w-4 h-4" />
                  Browse Archive
                </Link>
              </MagneticButton>
              <MagneticButton>
                <Link
                  href="/search?q=UNESCO+world+heritage"
                  className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-white/10 border border-white/20 text-white font-semibold text-sm backdrop-blur-sm hover:bg-white/20 transition-all"
                >
                  <Landmark className="w-4 h-4" />
                  UNESCO Sites
                </Link>
              </MagneticButton>
            </div>

            {/* Quick topic chips */}
            <div className="flex flex-wrap justify-center gap-2">
              {["Taj Mahal", "Mughal Architecture", "Buddhist Stupa", "Chola Temple"].map((s) => (
                <Link
                  key={s}
                  href={`/search?q=${encodeURIComponent(s)}`}
                  className="text-[11px] px-3 py-1 rounded-full bg-white/10 border border-white/15 text-parchment-200 hover:bg-white/20 hover:text-white transition-all"
                >
                  {s}
                </Link>
              ))}
            </div>
          </div>
        </section>
      </SpotlightHero>

      {/* ── Stats strip ───────────────────────────────────────────────── */}
      <div className="stat-strip text-white py-5 px-4">
        <Suspense fallback={<StatsStripSkeleton />}>
          <StatsStrip />
        </Suspense>
      </div>

      {/* ── Heritage Marquee ──────────────────────────────────────────── */}
      <HeritageMarquee />

      {/* ── Main content ──────────────────────────────────────────────── */}
      <div className="max-w-6xl mx-auto px-4 py-12">

        {/* Collections */}
        <div className="flex items-end justify-between mb-6">
          <h2 className="section-title mb-0">Popular Collections</h2>
          <Link href="/search" className="text-xs font-semibold hover:underline" style={{ color: "var(--accent-teal)" }}>
            View all →
          </Link>
        </div>

        <Suspense fallback={<CollectionCardsSkeleton />}>
          <CollectionCards />
        </Suspense>

        {/* Featured topics */}
        <div className="mb-14">
          <div className="flex items-end justify-between mb-5">
            <h2 className="section-title mb-0">Browse by Topic</h2>
          </div>
          <TopicPills topics={FEATURED_TOPICS} />
        </div>

        {/* Bento grid — Quick Access */}
        <div className="mb-4">
          <h2 className="section-title">Quick Access</h2>
          {(() => {
            const wideItem = BENTO_ITEMS[0];
            const WideIcon = wideItem.Icon;
            return (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 auto-rows-fr">
            {/* Wide tile */}
            <Link
              href={wideItem.href}
              className="card-glow gradient-border group col-span-2 rounded-2xl p-6 flex items-center gap-4 hover:-translate-y-1 transition-all duration-200 shadow-sm"
              style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}
            >
              <div
                className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 shadow"
                style={{ backgroundColor: `${wideItem.accent}22` }}
              >
                <WideIcon className="w-6 h-6" style={{ color: wideItem.accent }} />
              </div>
              <div>
                <div className="text-base font-bold font-serif" style={{ color: "var(--text-primary)" }}>{wideItem.label}</div>
                <div className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>{wideItem.desc}</div>
              </div>
              <span className="ml-auto text-lg opacity-30 group-hover:opacity-100 group-hover:translate-x-1 transition-all" style={{ color: wideItem.accent }}>→</span>
            </Link>

            {/* Small tiles */}
            {BENTO_ITEMS.slice(1).map((item) => {
              const ItemIcon = item.Icon;
              return (
              <Link
                key={item.href}
                href={item.href}
                className="card-glow gradient-border group rounded-2xl p-5 flex flex-col items-start hover:-translate-y-1 transition-all duration-200 shadow-sm"
                style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}
              >
                <div
                  className="w-9 h-9 rounded-lg flex items-center justify-center mb-3 shadow-sm"
                  style={{ backgroundColor: `${item.accent}22` }}
                >
                  <ItemIcon className="w-5 h-5" style={{ color: item.accent }} />
                </div>
                <div className="text-sm font-bold font-serif" style={{ color: "var(--text-primary)" }}>{item.label}</div>
                <div className="text-[11px] mt-0.5 leading-snug" style={{ color: "var(--text-muted)" }}>{item.desc}</div>
              </Link>
              );
            })}
          </div>
          );
        })()}
        </div>

      </div>
    </div>
  );
}
