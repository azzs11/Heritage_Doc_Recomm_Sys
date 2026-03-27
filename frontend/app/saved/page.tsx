"use client";

import { useEffect, useState } from "react";
import DocumentCard from "@/components/recommender/DocumentCard";
import { Document } from "@/lib/types";

export default function SavedPage() {
  const [saved, setSaved] = useState<Document[]>([]);

  useEffect(() => {
    try {
      const stored = localStorage.getItem("heritage_saved_docs");
      if (stored) setSaved(JSON.parse(stored));
    } catch { /* ignore */ }
  }, []);

  const remove = (id: string) => {
    const updated = saved.filter((d) => d.id !== id);
    setSaved(updated);
    localStorage.setItem("heritage_saved_docs", JSON.stringify(updated));
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <h1 className="font-serif text-3xl font-bold text-heritage-dark mb-6">Saved Documents</h1>

      {saved.length === 0 ? (
        <div className="heritage-card p-12 text-center text-heritage-brown">
          <p className="text-4xl mb-3">🔖</p>
          <p className="font-serif text-lg">No saved documents yet.</p>
          <p className="text-sm mt-1">
            Browse the archive and click 🔖 on any document to save it here.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {saved.map((doc) => (
            <div key={doc.id} className="relative">
              <DocumentCard document={doc} />
              <button
                onClick={() => remove(doc.id)}
                className="absolute top-2 right-2 text-xs bg-parchment-200 hover:bg-red-100 text-heritage-brown px-2 py-1 rounded"
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
