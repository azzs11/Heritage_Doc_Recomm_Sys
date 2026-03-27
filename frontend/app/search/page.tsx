import { Suspense } from "react";
import FilterSidebar from "@/components/search/FilterSidebar";
import ResultsList from "@/components/search/ResultsList";
import SearchBar from "@/components/recommender/SearchBar";
import Loader from "@/components/ui/Loader";
import ErrorState from "@/components/ui/ErrorState";
import { searchDocuments, listDocuments } from "@/lib/api";
import { Document } from "@/lib/types";

interface Props {
  searchParams: { q?: string; era?: string; region?: string; type?: string; page?: string; ensemble?: string };
}

async function Results({ searchParams }: Props) {
  const query = searchParams.q ?? "";
  const page = Number(searchParams.page ?? 1);
  const filters = {
    era: searchParams.era ? [searchParams.era] : undefined,
    region: searchParams.region ? [searchParams.region] : undefined,
    type: searchParams.type ? [searchParams.type] : undefined,
  };

  let documents: Document[] = [];
  let total = 0;
  let queryType: string | undefined;
  let ensembleMethod: string | undefined;
  let error: string | null = null;

  try {
    if (query) {
      const res = await searchDocuments(query, filters, 20, true, searchParams.ensemble);
      documents = res.documents;
      total = res.total;
      queryType = res.query_type;
      ensembleMethod = res.ensemble_method;
    } else {
      const docs = await listDocuments(page, 20, filters);
      documents = docs as Document[];
      total = docs.length > 0 ? (docs[0] as any).total ?? docs.length : 0;
    }
  } catch (e) {
    error = "Could not reach backend. Make sure FastAPI is running on port 8000.";
  }

  if (error) return <ErrorState title="Backend not connected" message={error} />;

  return (
    <ResultsList
      documents={documents}
      total={total}
      currentPage={page}
      showExplanation={!!query}
      queryType={queryType}
      ensembleMethod={ensembleMethod}
      searchParams={Object.fromEntries(
        Object.entries(searchParams).filter(([, v]) => v !== undefined) as [string, string][]
      )}
    />
  );
}

export default function SearchPage({ searchParams }: Props) {
  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <div className="mb-6">
        <h1 className="font-serif text-3xl font-bold text-heritage-dark mb-4">Browse Archives</h1>
        <SearchBar defaultValue={searchParams.q} defaultEnsemble={searchParams.ensemble} />
      </div>

      <div className="flex flex-col md:flex-row gap-6">
        <aside className="md:w-64 flex-shrink-0">
          <FilterSidebar
            defaultEra={searchParams.era}
            defaultRegion={searchParams.region}
            defaultType={searchParams.type}
          />
        </aside>
        <div className="flex-1">
          <Suspense fallback={<Loader message="Searching..." />}>
            <Results searchParams={searchParams} />
          </Suspense>
        </div>
      </div>
    </div>
  );
}
