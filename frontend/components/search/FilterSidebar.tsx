"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

const FILTERS = {
  Era: ["ancient", "medieval", "modern"],
  Region: ["north", "south", "east", "west"],
  Type: ["monument", "site", "architecture", "art", "temple", "fort", "palace", "mosque"],
};

interface Props {
  defaultEra?: string;
  defaultRegion?: string;
  defaultType?: string;
}

export default function FilterSidebar({ defaultEra, defaultRegion, defaultType }: Props) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [era, setEra] = useState(defaultEra ?? "");
  const [region, setRegion] = useState(defaultRegion ?? "");
  const [type, setType] = useState(defaultType ?? "");

  const apply = () => {
    const params = new URLSearchParams(searchParams.toString());
    if (era) params.set("era", era); else params.delete("era");
    if (region) params.set("region", region); else params.delete("region");
    if (type) params.set("type", type); else params.delete("type");
    params.delete("page");
    router.push(`/search?${params}`);
  };

  const clear = () => {
    setEra(""); setRegion(""); setType("");
    const params = new URLSearchParams(searchParams.toString());
    ["era", "region", "type", "page"].forEach((k) => params.delete(k));
    router.push(`/search?${params}`);
  };

  return (
    <div className="bg-white border border-parchment-200 rounded-2xl shadow-sm overflow-hidden" role="region" aria-label="Search filters">
      {/* Header */}
      <div className="px-5 py-4 border-b border-parchment-100 bg-heritage-dark">
        <h2 className="font-serif font-bold text-white text-base flex items-center gap-2">
          <span className="text-heritage-gold" aria-hidden="true">▼</span> Filters
        </h2>
      </div>

      <div className="p-5 space-y-5">
        {Object.entries(FILTERS).map(([group, options]) => {
          const value = group === "Era" ? era : group === "Region" ? region : type;
          const setter = group === "Era" ? setEra : group === "Region" ? setRegion : setType;
          return (
            <fieldset key={group}>
              <legend className="text-[10px] font-bold uppercase tracking-widest text-heritage-gold mb-2.5 flex items-center gap-1.5">
                <span className="w-3 h-px bg-heritage-gold inline-block" aria-hidden="true" />
                {group}
              </legend>
              <ul className="space-y-1" role="radiogroup" aria-label={`Filter by ${group}`}>
                {options.map((opt) => {
                  const active = value === opt;
                  return (
                    <li key={opt}>
                      <label
                        className={`flex items-center gap-2.5 cursor-pointer text-sm px-3 py-1.5 rounded-lg transition-all capitalize
                          ${active
                            ? "bg-heritage-dark text-white font-semibold"
                            : "text-heritage-dark hover:bg-parchment-100"
                          }`}
                      >
                        <span
                          className={`w-3.5 h-3.5 rounded-full border flex-shrink-0 transition-all
                            ${active ? "bg-heritage-gold border-heritage-gold" : "border-parchment-300 bg-white"}`}
                          aria-hidden="true"
                        />
                        <input
                          type="radio"
                          name={group}
                          checked={active}
                          onChange={() => setter(active ? "" : opt)}
                          className="sr-only"
                          aria-label={`${group}: ${opt}`}
                        />
                        {opt}
                      </label>
                    </li>
                  );
                })}
              </ul>
            </fieldset>
          );
        })}

        <button onClick={apply} className="btn-primary w-full text-sm mt-2" aria-label="Apply selected filters">
          Apply Filters
        </button>
        <button onClick={clear} className="text-xs text-heritage-medium hover:text-heritage-rust underline w-full text-center transition-colors" aria-label="Clear all filters">
          Clear all filters
        </button>
      </div>
    </div>
  );
}
