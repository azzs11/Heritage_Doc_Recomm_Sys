import Link from "next/link";
import { Landmark } from "lucide-react";

export default function Footer() {
  return (
    <footer
      className="text-parchment-200 mt-16 border-t border-white/10"
      style={{ background: "linear-gradient(135deg, #2d1a0a 0%, #4a2c17 100%)" }}
    >
      {/* Noise texture */}
      <div className="noise-overlay relative">
      <div className="max-w-6xl mx-auto px-4 py-10">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-8 mb-8">
          {/* Brand */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <div className="w-7 h-7 rounded-lg bg-heritage-gold flex items-center justify-center shadow">
                <Landmark className="w-4 h-4 text-heritage-dark" />
              </div>
              <span className="font-serif font-bold text-white text-base">Heritage Recommender</span>
            </div>
            <p className="text-xs text-parchment-300 leading-relaxed opacity-80">
              AI-powered discovery of India's historical documents — manuscripts, inscriptions, and archival records.
            </p>
          </div>

          {/* Quick links */}
          <div>
            <h4 className="text-[11px] uppercase tracking-widest font-bold text-heritage-gold mb-3">Explore</h4>
            <ul className="space-y-1.5 text-sm">
              {([
                ["Browse Archives", "/search"],
                ["Medieval Records", "/search?q=medieval+sultanate+rajput&era=medieval"],
                ["Ancient Inscriptions", "/search?q=ancient+vedic+inscription&era=ancient"],
                ["UNESCO Sites", "/search?q=UNESCO+world+heritage"],
                ["Dashboard", "/dashboard"],
              ] as [string, string][]).map(([label, href]) => (
                <li key={href}>
                  <Link href={href} className="text-parchment-300 hover:text-heritage-gold transition-colors opacity-80 hover:opacity-100">
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Tech stack */}
          <div>
            <h4 className="text-[11px] uppercase tracking-widest font-bold text-heritage-gold mb-3">Powered By</h4>
            <div className="flex flex-wrap gap-2">
              {["Knowledge Graph", "SimRank", "FAISS", "Learning-to-Rank", "Sentence Embeddings", "Ensemble Ranking"].map((t) => (
                <span key={t} className="text-[10px] px-2 py-0.5 rounded-full border border-white/15 bg-white/5 text-parchment-300">
                  {t}
                </span>
              ))}
            </div>
          </div>
        </div>

        <div className="border-t border-white/10 pt-5 flex flex-col sm:flex-row items-center justify-between gap-2">
          <p className="text-[11px] text-parchment-300 opacity-60">Heritage Document Recommender System · 1,781 documents indexed</p>
          <p className="text-[11px] text-parchment-300 opacity-60">Knowledge Graph · Semantic Embeddings · Hybrid AI Ranking</p>
        </div>
      </div>
      </div>
    </footer>
  );
}
