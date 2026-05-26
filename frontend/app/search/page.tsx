import { Suspense } from "react";
import FilterSidebar from "@/components/search/FilterSidebar";
import ResultsWithCompare from "@/components/search/ResultsWithCompare";
import SearchBar from "@/components/recommender/SearchBar";
import Loader from "@/components/ui/Loader";
import ErrorState from "@/components/ui/ErrorState";
import { searchDocuments, listDocuments } from "@/lib/api";
import { Document, ParsedQuery } from "@/lib/types";

interface Props {
  searchParams: { q?: string; era?: string; region?: string; type?: string; page?: string; ensemble?: string };
}

async function Results({ searchParams }: Props) {
  const query = searchParams.q ?? "";
  const page = Number(searchParams.page ?? 1);
  const filters = {
    era:    searchParams.era    ? [searchParams.era]    : undefined,
    region: searchParams.region ? [searchParams.region] : undefined,
    type:   searchParams.type   ? [searchParams.type]   : undefined,
  };

  let documents: Document[] = [];
  let total = 0;
  let queryType: string | undefined;
  let ensembleMethod: string | undefined;
  let parsedQuery: ParsedQuery | undefined;
  let error: string | null = null;

  try {
    if (query) {
      const res = await searchDocuments(query, filters, 20, true, searchParams.ensemble);
      documents = res.documents;
      total = res.total;
      queryType = res.query_type;
      ensembleMethod = res.ensemble_method;
      parsedQuery = res.parsed_query;
    } else {
      const res = await listDocuments(page, 20, filters);
      documents = res.documents;
      total = res.total;
    }
  } catch {
    error = "Could not reach backend. Make sure FastAPI is running on port 8000.";
  }

  if (error) return <ErrorState title="Backend not connected" message={error} />;

  return (
    <ResultsWithCompare
      query={query}
      filters={filters}
      documents={documents}
      total={total}
      currentPage={page}
      showExplanation={!!query}
      queryType={queryType}
      ensembleMethod={ensembleMethod}
      parsedQuery={parsedQuery}
      searchParams={Object.fromEntries(
        Object.entries(searchParams).filter(([, v]) => v !== undefined) as [string, string][]
      )}
    />
  );
}

export default function SearchPage({ searchParams }: Props) {
  return (
    <div>
      {/* Search hero strip */}
      <div
        className="px-4 py-8 border-b border-parchment-200"
        style={{ background: "linear-gradient(135deg, #4a2c17 0%, #6b4226 100%)" }}
      >
        <div className="max-w-6xl mx-auto">
          <h1 className="font-serif text-2xl font-bold text-white mb-4">Browse Archives</h1>
          <SearchBar defaultValue={searchParams.q} defaultEnsemble={searchParams.ensemble} />
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 py-8">
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
    </div>
  );
}
