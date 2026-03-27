import Link from "next/link";
import DocumentCard from "./DocumentCard";
import { Document } from "@/lib/types";

interface Props {
  title: string;
  documents: Document[];
}

export default function RecommendationSection({ title, documents }: Props) {
  return (
    <section>
      <h2 className="section-title">{title}</h2>
      <div className="space-y-3">
        {documents.map((doc) => (
          <DocumentCard key={doc.id} document={doc} />
        ))}
      </div>
      <div className="mt-4 text-right">
        <Link
          href="/search"
          className="text-sm text-heritage-brown hover:text-heritage-dark font-medium transition-colors"
        >
          View More &rsaquo;
        </Link>
      </div>
    </section>
  );
}
