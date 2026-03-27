import { Suspense } from "react";
import SearchBar from "@/components/recommender/SearchBar";
import RecommendationSection from "@/components/recommender/RecommendationSection";
import Loader from "@/components/ui/Loader";
import ErrorState from "@/components/ui/ErrorState";
import { getRecommendations, listDocuments } from "@/lib/api";
import { Document } from "@/lib/types";
import Link from "next/link";

const COLLECTIONS = [
  { id: "medieval", name: "Medieval Records", era: "medieval" },
  { id: "ancient", name: "Ancient Inscriptions", era: "ancient" },
  { id: "modern", name: "Colonial Archives", era: "modern" },
];

async function HomeContent() {
  let documents: Document[] = [];
  let error: string | null = null;

  try {
    const res = await getRecommendations("Indian heritage monuments temples forts UNESCO", 6);
    documents = res.documents;
  } catch {
    // Fallback to listing documents if backend cold-starting
    try {
      documents = (await listDocuments(1, 5)) as Document[];
    } catch (e) {
      error = "Backend not reachable. Start the FastAPI server: uvicorn api.main:app --reload --port 8000";
    }
  }

  if (error) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-10">
        <ErrorState title="Backend not connected" message={error} />
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-10 grid grid-cols-1 lg:grid-cols-3 gap-8">
      <div className="lg:col-span-2">
        <RecommendationSection title="Recommended for You" documents={documents} />
      </div>

      <aside>
        <h2 className="section-title">Popular Collections</h2>
        <div className="grid grid-cols-1 gap-3">
          {COLLECTIONS.map((col) => (
            <Link
              key={col.id}
              href={`/search?era=${col.era}`}
              className="heritage-card p-0 overflow-hidden cursor-pointer group"
            >
              <div className="h-24 bg-heritage-brown flex items-end p-3 group-hover:bg-heritage-medium transition-colors">
                <span className="text-white font-semibold font-serif text-sm">{col.name}</span>
              </div>
            </Link>
          ))}
        </div>

        <div className="mt-6 grid grid-cols-2 gap-3">
          <Link href="/saved" className="heritage-card p-4 text-center hover:bg-parchment-200 transition-colors">
            <span className="block text-2xl mb-1">🔖</span>
            <span className="text-sm font-semibold text-heritage-brown">Saved Documents</span>
          </Link>
          <Link href="/search" className="heritage-card p-4 text-center hover:bg-parchment-200 transition-colors">
            <span className="block text-2xl mb-1">🕐</span>
            <span className="text-sm font-semibold text-heritage-brown">Browse All</span>
          </Link>
        </div>
      </aside>
    </div>
  );
}

export default function HomePage() {
  return (
    <div className="min-h-screen">
      {/* Hero */}
      <section
        className="relative bg-heritage-dark text-white py-16 px-4"
        style={{
          backgroundImage: "linear-gradient(rgba(74,44,23,0.85), rgba(74,44,23,0.85)), url('/parchment-bg.jpg')",
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
      >
        <div className="max-w-4xl mx-auto text-center">
          <h1 className="font-serif text-4xl md:text-5xl font-bold mb-3 tracking-wide">
            Heritage Document Recommender System
          </h1>
          <p className="text-parchment-200 mb-8 text-lg">
            Discover historical manuscripts, inscriptions, and archival records
          </p>
          <SearchBar />
        </div>
      </section>

      <Suspense fallback={<Loader message="Loading recommendations..." />}>
        <HomeContent />
      </Suspense>
    </div>
  );
}
