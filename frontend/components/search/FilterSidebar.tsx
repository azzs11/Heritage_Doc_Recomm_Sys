"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

const FILTERS = {
  Era: ["ancient", "medieval", "modern"],
  Region: ["north", "south", "east", "west", "central"],
  Type: ["monument", "site", "artifact", "temple", "fort", "palace", "mosque"],
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
    <div className="heritage-card p-5 space-y-5">
      <h2 className="font-serif font-bold text-heritage-dark text-base border-b border-parchment-200 pb-2">
        Filters
      </h2>

      {Object.entries(FILTERS).map(([group, options]) => {
        const value = group === "Era" ? era : group === "Region" ? region : type;
        const setter = group === "Era" ? setEra : group === "Region" ? setRegion : setType;
        return (
          <div key={group}>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-heritage-brown mb-2">
              {group}
            </h3>
            <ul className="space-y-1">
              {options.map((opt) => (
                <li key={opt}>
                  <label className="flex items-center gap-2 cursor-pointer text-sm text-heritage-dark hover:text-heritage-brown capitalize">
                    <input
                      type="radio"
                      name={group}
                      checked={value === opt}
                      onChange={() => setter(value === opt ? "" : opt)}
                      className="accent-heritage-brown"
                    />
                    {opt}
                  </label>
                </li>
              ))}
            </ul>
          </div>
        );
      })}

      <button onClick={apply} className="btn-primary w-full text-sm">Apply Filters</button>
      <button onClick={clear} className="text-xs text-heritage-brown underline w-full text-center">
        Clear all
      </button>
    </div>
  );
}
