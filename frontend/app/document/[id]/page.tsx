import { Suspense } from "react";
import Link from "next/link";
import EntityTag from "@/components/knowledge-graph/EntityTag";
import RelatedEntitiesPanel from "@/components/knowledge-graph/RelatedEntitiesPanel";
import GraphViewer from "@/components/knowledge-graph/GraphViewer";
import DocumentCard from "@/components/recommender/DocumentCard";
import Loader from "@/components/ui/Loader";
import ErrorState from "@/components/ui/ErrorState";
import { getDocument, searchDocuments } from "@/lib/api";
import { Entity } from "@/lib/types";

interface Props {
  params: { id: string };
}

async function DocumentContent({ id }: { id: string }) {
  let doc;
  try {
    doc = await getDocument(decodeURIComponent(id));
  } catch {
    return <ErrorState title="Document not found" message={`Could not load document: ${id}`} />;
  }

  // Build entities list from document data
  const entities: Entity[] = [
    ...(doc.entities?.locations ?? []).slice(0, 4).map((n, i) => ({
      id: `loc-${i}`, name: n, type: "locations", count: 1,
    })),
    ...(doc.entities?.persons ?? []).slice(0, 3).map((n, i) => ({
      id: `per-${i}`, name: n, type: "persons", count: 1,
    })),
    ...(doc.entities?.organizations ?? []).slice(0, 3).map((n, i) => ({
      id: `org-${i}`, name: n, type: "organizations", count: 1,
    })),
  ];

  // Fetch related documents using doc's first keyword
  let related: import("@/lib/types").Document[] = [];
  try {
    const relQuery = doc.keywords?.[0] ?? doc.title;
    const res = await searchDocuments(relQuery, {}, 4);
    related = res.documents.filter((d) => d.id !== doc.id).slice(0, 3);
  } catch { /* non-fatal */ }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
      {/* Main */}
      <div className="lg:col-span-2 space-y-6">
        {/* Header */}
        <div className="heritage-card p-6">
          <div className="flex items-start gap-4">
            <div className="w-20 h-24 bg-heritage-brown rounded flex-shrink-0 flex items-center justify-center text-white text-3xl">
              📜
            </div>
            <div>
              <h1 className="font-serif text-2xl font-bold text-heritage-dark mb-1">{doc.title}</h1>
              {doc.source && (
                <p className="text-sm font-medium text-heritage-brown mb-1">📄 {doc.source}</p>
              )}
              <div className="flex flex-wrap gap-2 text-sm text-gray-500 mb-3 capitalize">
                {doc.type && <span className="px-2 py-0.5 bg-parchment-200 rounded text-xs">{doc.type}</span>}
                {doc.era && <span className="px-2 py-0.5 bg-parchment-200 rounded text-xs">{doc.era}</span>}
                {doc.region && <span className="px-2 py-0.5 bg-parchment-200 rounded text-xs">{doc.region}</span>}
              </div>
              {doc.url && (
                <a href={doc.url} target="_blank" rel="noopener noreferrer"
                  className="text-xs text-blue-600 underline hover:text-blue-800">
                  View original source ↗
                </a>
              )}
            </div>
          </div>
        </div>

        {/* Keywords */}
        {doc.keywords && doc.keywords.length > 0 && (
          <div className="heritage-card p-5">
            <h2 className="section-title">Keywords</h2>
            <div className="flex flex-wrap gap-2">
              {doc.keywords.map((kw) => (
                <Link
                  key={kw}
                  href={`/search?q=${encodeURIComponent(kw)}`}
                  className="px-2.5 py-1 bg-parchment-200 border border-parchment-300 rounded-full text-xs text-heritage-dark hover:bg-parchment-300 transition-colors"
                >
                  {kw}
                </Link>
              ))}
            </div>
          </div>
        )}

        {/* Entities */}
        {entities.length > 0 && (
          <div className="heritage-card p-5">
            <h2 className="section-title">Entities</h2>
            <div className="flex flex-wrap gap-2">
              {entities.map((e) => <EntityTag key={e.id} entity={e} />)}
            </div>
          </div>
        )}

        {/* Graph Viewer — placeholder until D3 integration */}
        <div className="heritage-card p-5">
          <h2 className="section-title">Knowledge Graph</h2>
          <GraphViewer />
        </div>

        {/* Related Documents */}
        {related.length > 0 && (
          <div>
            <h2 className="section-title">Related Documents</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {related.map((d) => <DocumentCard key={d.id} document={d} />)}
            </div>
          </div>
        )}
      </div>

      {/* Sidebar */}
      <aside className="space-y-6">
        {entities.length > 0 && <RelatedEntitiesPanel entities={entities} />}

        <div className="heritage-card p-5">
          <h2 className="section-title">Metadata</h2>
          <dl className="space-y-2 text-sm">
            {[
              ["Source", doc.source],
              ["Cluster", doc.cluster_label],
              ["Domain", doc.classifications?.domains?.filter(d => d.toLowerCase() !== "unknown").join(", ")],
              ["Style", doc.classifications?.architectural_styles?.filter(s => s.toLowerCase() !== "unknown").join(", ")],
              ["Period", doc.era],
              ["Region", doc.region ?? null],
              ["Words", doc.word_count?.toLocaleString()],
            ]
              .filter(([, v]) => v && String(v).toLowerCase() !== "unknown")
              .map(([label, value]) => (
                <div key={label as string} className="flex justify-between gap-2">
                  <dt className="text-heritage-brown font-medium shrink-0">{label}</dt>
                  <dd className="text-heritage-dark text-right capitalize">{value as string}</dd>
                </div>
              ))}
          </dl>
        </div>
      </aside>
    </div>
  );
}

export default function DocumentPage({ params }: Props) {
  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <Suspense fallback={<Loader message="Loading document..." />}>
        <DocumentContent id={params.id} />
      </Suspense>
    </div>
  );
}
