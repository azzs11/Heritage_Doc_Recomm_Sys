"""Count-only probe for every collection source.

Saves one JSON file per source to results/probes/{date}-{source}-count.json,
recording the date, query used, and count returned. Run this before writing
any collector; use the numbers to calibrate per-entity and per-source caps.

Usage:
    uv run python scripts/probe_counts.py

Requirements (.env):
    CONTACT_EMAIL       included in User-Agent
    SMITHSONIAN_API_KEY register at https://api.data.gov/signup/
    ZENODO_TOKEN        register at https://zenodo.org/account/settings/applications/
"""

import json
import os
import time
from collections import Counter
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "")
SMITHSONIAN_API_KEY = os.environ.get("SMITHSONIAN_API_KEY", "")
ZENODO_TOKEN = os.environ.get("ZENODO_TOKEN", "")
REPO_URL = "https://github.com/aryananand-04/heritage_doc_recomm"

if not CONTACT_EMAIL:
    raise SystemExit("Set CONTACT_EMAIL in .env before running probes.")

HEADERS = {
    "User-Agent": (
        f"Heritage-Doc-Collect/0.1 ({REPO_URL}; contact: {CONTACT_EMAIL})"
    )
}

PROBES_DIR = Path("results/probes")
PROBES_DIR.mkdir(parents=True, exist_ok=True)
TODAY = date.today().isoformat()


def save(source: str, data: dict) -> None:
    data["date"] = TODAY
    data["source"] = source
    path = PROBES_DIR / f"{TODAY}-{source}-count.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  → {path}")


def _sparql(query: str) -> dict:
    """POST a SPARQL query to the Wikidata endpoint and return parsed JSON."""
    r = requests.post(
        "https://query.wikidata.org/sparql",
        data={"query": query, "format": "json"},
        headers={**HEADERS, "Accept": "application/sparql-results+json"},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()


def probe_wikidata() -> None:
    print("Wikidata: seed entity counts...")
    time.sleep(1)

    # Total seed count across all four seed types
    q_total = """
SELECT (COUNT(DISTINCT ?item) AS ?n) WHERE {
  { ?item wdt:P1371 ?id ; wdt:P17 wd:Q668 . }
  UNION { ?item wdt:P1435 wd:Q9259  ; wdt:P17 wd:Q668 . }
  UNION { ?item wdt:P1435 wd:Q1459900 ; wdt:P17 wd:Q668 . }
  UNION { ?item wdt:P31/wdt:P279* wd:Q164950 ; wdt:P17 wd:Q668 . }
}
"""
    total = int(_sparql(q_total)["results"]["bindings"][0]["n"]["value"])
    time.sleep(1)

    # Dynasty sub-count using P17 = India directly
    q_dynasty_p17 = """
SELECT (COUNT(DISTINCT ?item) AS ?n) WHERE {
  ?item wdt:P31/wdt:P279* wd:Q164950 ;
        wdt:P17 wd:Q668 .
}
"""
    dynasty_p17 = int(_sparql(q_dynasty_p17)["results"]["bindings"][0]["n"]["value"])
    time.sleep(1)

    # Dynasty sub-count using located-in chain (fallback: catches dynasties
    # whose items use P131 to India rather than P17 directly)
    q_dynasty_located = """
SELECT (COUNT(DISTINCT ?item) AS ?n) WHERE {
  ?item wdt:P31/wdt:P279* wd:Q164950 .
  FILTER NOT EXISTS { ?item wdt:P17 wd:Q668 . }
  ?item wdt:P131+ ?admin .
  ?admin wdt:P17 wd:Q668 .
}
"""
    dynasty_located = int(
        _sparql(q_dynasty_located)["results"]["bindings"][0]["n"]["value"]
    )
    time.sleep(1)

    # Sample 10 seed QIDs (for Wikipedia sitelink probe below)
    q_sample = """
SELECT DISTINCT ?item WHERE {
  { ?item wdt:P1371 ?id ; wdt:P17 wd:Q668 . }
  UNION { ?item wdt:P1435 wd:Q9259 ; wdt:P17 wd:Q668 . }
}
ORDER BY ?item
LIMIT 10
"""
    bindings = _sparql(q_sample)["results"]["bindings"]
    sample_qids = [b["item"]["value"].rsplit("/", 1)[-1] for b in bindings]

    note = (
        "dynasty_via_P17 + dynasty_via_located = total dynasty seeds. "
        "If combined < 20, expand using a verified QID list of major Indian dynasties "
        "(e.g. Q33296 Mughal Empire, Q15242416 Mughal dynasty, Chola, Gupta, Maurya, "
        "Vijayanagara, Maratha) and report added count."
    )

    save("wikidata", {
        "queries": {
            "total_seed": q_total.strip(),
            "dynasty_P17": q_dynasty_p17.strip(),
            "dynasty_located_in": q_dynasty_located.strip(),
            "sample_QIDs": q_sample.strip(),
        },
        "total_seed_entities": total,
        "dynasty_via_P17": dynasty_p17,
        "dynasty_via_located_in": dynasty_located,
        "sample_qids_for_wikipedia_probe": sample_qids,
        "note": note,
    })

    return sample_qids


def probe_wikipedia(sample_qids: list) -> None:
    print("Wikipedia: sitelink coverage on sample QIDs...")
    results = []
    for qid in sample_qids:
        time.sleep(0.5)
        r = requests.get(
            f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json",
            headers=HEADERS,
            timeout=30,
        )
        if r.status_code != 200:
            continue
        entity = r.json().get("entities", {}).get(qid, {})
        sitelinks = entity.get("sitelinks", {})
        results.append({
            "qid": qid,
            "label_en": entity.get("labels", {}).get("en", {}).get("value", ""),
            "has_en": "enwiki" in sitelinks,
            "has_hi": "hiwiki" in sitelinks,
            "has_kn": "knwiki" in sitelinks,
            "has_sa": "sawiki" in sitelinks,
        })

    save("wikipedia", {
        "query": "Special:EntityData/{qid}.json — sitelinks check",
        "sample_size": len(results),
        "has_en": sum(1 for r in results if r["has_en"]),
        "has_hi": sum(1 for r in results if r["has_hi"]),
        "has_kn": sum(1 for r in results if r["has_kn"]),
        "has_sa": sum(1 for r in results if r["has_sa"]),
        "detail": results,
        "note": (
            "Re-run with the full seed QID list after the Wikidata probe "
            "to get representative coverage percentages."
        ),
    })


def probe_wikisource(sample_entity: str = "Taj Mahal") -> None:
    print("Wikisource: title search count...")
    r = requests.get(
        "https://en.wikisource.org/w/api.php",
        params={
            "action": "query",
            "list": "search",
            "srsearch": sample_entity,
            "srnamespace": "0",
            "srlimit": "1",
            "format": "json",
        },
        headers=HEADERS,
        timeout=30,
    )
    r.raise_for_status()
    total = r.json()["query"]["searchinfo"]["totalhits"]
    save("wikisource", {
        "query": f"action=query&list=search&srsearch={sample_entity}&srnamespace=0",
        "sample_entity": sample_entity,
        "total_hits_for_sample": total,
        "note": (
            "This is hits for one entity; run for a sample of 10 seed entities "
            "and sum to estimate total Wikisource coverage."
        ),
    })


def probe_internet_archive() -> None:
    print("Internet Archive: count + language values in sample of 200...")
    base_q = 'subject:"India" AND mediatype:texts'

    # Total count
    r_count = requests.get(
        "https://archive.org/advancedsearch.php",
        params={"q": base_q, "rows": "0", "output": "json"},
        headers=HEADERS,
        timeout=60,
    )
    r_count.raise_for_status()
    total = r_count.json()["response"]["numFound"]
    time.sleep(2)

    # Sample 200 to find actual language field values
    r_sample = requests.get(
        "https://archive.org/advancedsearch.php",
        params={
            "q": base_q,
            "fl[]": "identifier,language,licenseurl,possible-copyright-status",
            "rows": "200",
            "output": "json",
            "sort": "downloads desc",
        },
        headers=HEADERS,
        timeout=60,
    )
    r_sample.raise_for_status()
    docs = r_sample.json()["response"]["docs"]

    lang_counter: Counter = Counter()
    license_counter: Counter = Counter()
    pcs_counter: Counter = Counter()

    for doc in docs:
        lang = doc.get("language")
        if isinstance(lang, list):
            for lv in lang:
                lang_counter[str(lv)] += 1
        elif lang:
            lang_counter[str(lang)] += 1

        lu = doc.get("licenseurl", "")
        license_counter[str(lu) if lu else "(none)"] += 1

        pcs = doc.get("possible-copyright-status", "")
        pcs_counter[str(pcs) if pcs else "(none)"] += 1

    save("internet_archive", {
        "query": base_q,
        "total_items": total,
        "sample_size": len(docs),
        "language_values": dict(lang_counter.most_common(40)),
        "licenseurl_values": dict(license_counter.most_common(20)),
        "possible_copyright_status_values": dict(pcs_counter.most_common(10)),
        "note": (
            "Fix the language filter in internet_archive.py using the exact "
            "strings in language_values. Accept items where licenseurl contains "
            "creativecommons.org or publicdomain, OR possible-copyright-status "
            "is NOT_IN_COPYRIGHT / NOT_IN_COPYRIGHT_US."
        ),
    })


def probe_met() -> None:
    print("Met Museum: Indian objects count...")
    r = requests.get(
        "https://collectionapi.metmuseum.org/public/collection/v1/search",
        params={"q": "India", "departmentId": "6", "isPublicDomain": "true"},
        headers=HEADERS,
        timeout=30,
    )
    r.raise_for_status()
    total = r.json().get("total", 0)
    save("met", {
        "query": "q=India&departmentId=6&isPublicDomain=true",
        "endpoint": "https://collectionapi.metmuseum.org/public/collection/v1/search",
        "total": total,
    })


def probe_cleveland() -> None:
    print("Cleveland Museum: Indian objects count (three culture strings)...")
    counts = {}
    for culture in ("India", "Indian subcontinent", "South Asia"):
        time.sleep(0.5)
        r = requests.get(
            "https://openaccess-api.clevelandart.org/api/artworks/",
            params={"culture": culture, "has_image": "1", "shareitem": "1",
                    "limit": "1", "skip": "0"},
            headers=HEADERS,
            timeout=30,
        )
        r.raise_for_status()
        counts[culture] = r.json().get("info", {}).get("total", 0)

    save("cleveland", {
        "query": "culture=X&has_image=1&shareitem=1",
        "counts_by_culture_string": counts,
        "note": "Sum deduplicated across culture strings when writing the collector.",
    })


def probe_chicago() -> None:
    print("Art Institute of Chicago: Indian objects count...")
    r = requests.post(
        "https://api.artic.edu/api/v1/artworks/search",
        json={
            "query": {"bool": {"must": [
                {"term": {"is_public_domain": True}},
                {"match": {"place_of_origin": "India"}},
            ]}},
            "fields": ["id"],
            "limit": 0,
        },
        headers={**HEADERS, "Content-Type": "application/json"},
        timeout=30,
    )
    r.raise_for_status()
    total = r.json().get("pagination", {}).get("total", 0)
    save("chicago", {
        "query": "place_of_origin=India AND is_public_domain=true",
        "endpoint": "https://api.artic.edu/api/v1/artworks/search",
        "total": total,
    })


def probe_smithsonian() -> None:
    if not SMITHSONIAN_API_KEY:
        print("Smithsonian: SMITHSONIAN_API_KEY not set — skipping.")
        save("smithsonian", {
            "total": None,
            "skipped": "SMITHSONIAN_API_KEY not set in .env",
        })
        return
    print("Smithsonian: Indian objects count...")
    r = requests.get(
        "https://api.si.edu/openaccess/api/v1.0/search",
        params={"q": "India", "rows": "0", "api_key": SMITHSONIAN_API_KEY},
        headers=HEADERS,
        timeout=30,
    )
    r.raise_for_status()
    total = r.json().get("response", {}).get("rowCount", 0)
    save("smithsonian", {
        "query": "q=India&rows=0",
        "endpoint": "https://api.si.edu/openaccess/api/v1.0/search",
        "total": total,
    })


def probe_wellcome() -> None:
    print("Wellcome Collection: Indic manuscript count...")
    r = requests.get(
        "https://api.wellcomecollection.org/catalogue/v2/works",
        params={
            "query": "India",
            "languages": "san,hin,tam,kan,tel,ben",
            "workType": "a,k",
            "pageSize": "1",
        },
        headers=HEADERS,
        timeout=30,
    )
    r.raise_for_status()
    total = r.json().get("totalResults", 0)
    save("wellcome", {
        "query": "query=India&languages=san,hin,tam,kan,tel,ben&workType=a,k",
        "endpoint": "https://api.wellcomecollection.org/catalogue/v2/works",
        "total": total,
    })


def probe_siddham() -> None:
    print("SIDDHAM (Zenodo): Indian inscription count...")
    headers = dict(HEADERS)
    if ZENODO_TOKEN:
        headers["Authorization"] = f"Bearer {ZENODO_TOKEN}"
    else:
        print("  (no ZENODO_TOKEN — using unauthenticated limits: 30 req/min search)")
    r = requests.get(
        "https://zenodo.org/api/records",
        params={"communities": "siddham", "q": "india", "size": "1", "page": "1"},
        headers=headers,
        timeout=30,
    )
    r.raise_for_status()
    total = r.json().get("hits", {}).get("total", 0)
    save("siddham", {
        "query": "communities=siddham&q=india",
        "endpoint": "https://zenodo.org/api/records",
        "authenticated": bool(ZENODO_TOKEN),
        "total": total,
    })


def main() -> None:
    print("Running collection probes — results in results/probes/\n")
    sample_qids = probe_wikidata()
    probe_wikipedia(sample_qids)
    probe_wikisource()
    probe_internet_archive()
    probe_met()
    probe_cleveland()
    probe_chicago()
    probe_smithsonian()
    probe_wellcome()
    probe_siddham()
    print("\nDone. Report the counts back to agree final caps before writing any collector.")


if __name__ == "__main__":
    main()
