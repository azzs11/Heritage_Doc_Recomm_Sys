"""
Heritage Gazetteer Builder — Stage 2

Reads classified_documents.json and produces data/gazetteer/heritage_gazetteer.json.

A gazetteer is a structured lookup table: surface_form → {
    canonical, entity_type, heritage_relevance,
    frequency, source_docs, classifications
}
Used by the query processor and NER pipeline to recognise heritage entities
without relying solely on spaCy's generic model.
"""

import json
import os
from collections import defaultdict

CLASSIFIED_PATH = "data/classified/classified_documents.json"
OUT_DIR = "data/gazetteer"
OUT_FILE = os.path.join(OUT_DIR, "heritage_gazetteer.json")

# ── canonical override map ────────────────────────────────────────────────────
# Maps lowercase surface variants → preferred canonical form
CANONICAL_OVERRIDES = {
    "taj mahal": "Taj Mahal",
    "red fort": "Red Fort",
    "qutub minar": "Qutub Minar",
    "qutb minar": "Qutub Minar",
    "india gate": "India Gate",
    "gateway of india": "Gateway of India",
    "ajanta caves": "Ajanta Caves",
    "ajanta": "Ajanta Caves",
    "ellora caves": "Ellora Caves",
    "ellora": "Ellora Caves",
    "khajuraho": "Khajuraho",
    "hampi": "Hampi",
    "fatehpur sikri": "Fatehpur Sikri",
    "konark": "Konark Sun Temple",
    "sanchi": "Sanchi Stupa",
    "nalanda": "Nalanda",
    "bodh gaya": "Bodh Gaya",
    "varanasi": "Varanasi",
    "madurai": "Madurai",
    "thanjavur": "Thanjavur",
    "mahabalipuram": "Mahabalipuram",
    "pattadakal": "Pattadakal",
    "aihole": "Aihole",
    "badami": "Badami",
    "mehrangarh": "Mehrangarh Fort",
    "amber fort": "Amber Fort",
    "mysore palace": "Mysore Palace",
    "victoria memorial": "Victoria Memorial",
    "charminar": "Charminar",
    "golconda": "Golconda Fort",
    "ashoka": "Ashoka",
    "akbar": "Akbar",
    "shah jahan": "Shah Jahan",
    "aurangzeb": "Aurangzeb",
    "mughal": "Mughal",
    "maurya": "Maurya",
    "gupta": "Gupta",
    "chola": "Chola",
    "unesco": "UNESCO",
    "asi": "Archaeological Survey of India",
    "archaeological survey of india": "Archaeological Survey of India",
    "intach": "INTACH",
}

# ── entity-type normalisation ─────────────────────────────────────────────────
ENTITY_TYPE_MAP = {
    "locations":     "location",
    "persons":       "person",
    "organizations": "organization",
    "monuments":     "monument",
    "dates":         "date",
}

# Monument-type keywords for heritage_relevance tagging
MONUMENT_KEYWORDS = {
    "temple", "fort", "palace", "mosque", "church", "stupa", "monastery",
    "tomb", "mausoleum", "memorial", "gateway", "gate", "tower", "minaret",
    "cave", "complex", "site", "ruins", "monument", "shrine", "mahal",
}

HERITAGE_TYPE_KEYWORDS = {
    "monument":     {"temple","fort","palace","monument","memorial","tomb","mosque","stupa","tower","gate"},
    "site":         {"site","complex","ruins","excavation","settlement","city"},
    "artifact":     {"sculpture","statue","painting","manuscript","inscription","coin","pottery"},
    "architecture": {"architecture","building","structure","design","style"},
    "tradition":    {"tradition","festival","ritual","custom","practice","dance","music"},
    "art":          {"art","carving","mural","fresco","relief","iconography"},
}

DOMAIN_KEYWORDS = {
    "religious":     {"temple","mosque","church","monastery","shrine","stupa","buddhist","hindu","jain","sikh"},
    "military":      {"fort","fortress","defense","battle","war","military","garrison","citadel"},
    "royal":         {"palace","king","emperor","sultan","maharaja","royal","dynasty"},
    "cultural":      {"culture","festival","heritage","art","music","dance","literature"},
    "archaeological":{"archaeological","excavation","ruins","ancient","prehistoric"},
    "architectural": {"architecture","design","construction","building"},
}


def canonical(text: str) -> str:
    key = text.strip().lower()
    return CANONICAL_OVERRIDES.get(key, text.strip().title())


def infer_heritage_relevance(surface: str, entity_type: str) -> list:
    """Infer which heritage categories this entity is relevant to."""
    sl = surface.lower()
    relevance = set()
    for htype, kws in HERITAGE_TYPE_KEYWORDS.items():
        if any(kw in sl for kw in kws):
            relevance.add(htype)
    for domain, kws in DOMAIN_KEYWORDS.items():
        if any(kw in sl for kw in kws):
            relevance.add(domain)
    # monuments and locations are always heritage-relevant
    if entity_type in ("monument", "location"):
        relevance.add("monument")
    return sorted(relevance) or ["general"]


def clean_surface(text: str) -> str:
    """Strip noise from extracted entity strings."""
    text = text.strip()
    # Remove newline-embedded duplicates like "World Heritage Site\nWorld Heritage Site"
    if "\n" in text:
        parts = [p.strip() for p in text.split("\n") if p.strip()]
        text = max(parts, key=len)
    return text


def build_gazetteer():
    print("=" * 65)
    print("HERITAGE GAZETTEER BUILDER")
    print("=" * 65)

    with open(CLASSIFIED_PATH, "r", encoding="utf-8") as f:
        docs = json.load(f)

    print(f"Loaded {len(docs)} classified documents")

    # ── aggregate entity occurrences ─────────────────────────────────────────
    # key: (canonical_form, entity_type)
    # value: {frequency, source_docs, raw_surfaces, classifications}
    entries: dict = defaultdict(lambda: {
        "frequency": 0,
        "source_docs": [],
        "raw_surfaces": set(),
        "heritage_types_seen": set(),
        "domains_seen": set(),
        "time_periods_seen": set(),
        "regions_seen": set(),
    })

    for doc in docs:
        doc_title = doc.get("title", "unknown")
        entities = doc.get("entities", {})
        classifications = doc.get("classifications", {})

        doc_htypes = set(classifications.get("heritage_types", []))
        doc_domains = set(classifications.get("domains", []))
        doc_period = classifications.get("time_period", "unknown")
        doc_region = classifications.get("region", "unknown")

        for field, etype in ENTITY_TYPE_MAP.items():
            if field == "dates":
                continue  # dates are not useful gazetteer entries
            for raw in entities.get(field, []):
                surface = clean_surface(raw)
                if not surface or len(surface) < 2:
                    continue
                can = canonical(surface)
                key = (can, etype)
                e = entries[key]
                e["frequency"] += 1
                if doc_title not in e["source_docs"]:
                    e["source_docs"].append(doc_title)
                e["raw_surfaces"].add(surface)
                e["heritage_types_seen"].update(doc_htypes)
                e["domains_seen"].update(doc_domains)
                if doc_period != "unknown":
                    e["time_periods_seen"].add(doc_period)
                if doc_region not in ("unknown", "india"):
                    e["regions_seen"].add(doc_region)

    print(f"Raw unique (canonical, type) pairs: {len(entries)}")

    # ── filter: drop extremely rare single-document noise ────────────────────
    # Keep everything with freq >= 1 — this is a gazetteer, not a stoplist.
    # But skip entries whose canonical form looks like sentence fragments.
    def looks_noisy(text: str) -> bool:
        words = text.split()
        if len(words) > 8:
            return True
        if text.startswith("The ") and len(words) > 5:
            return True
        return False

    filtered = {k: v for k, v in entries.items() if not looks_noisy(k[0])}
    print(f"After noise filter: {len(filtered)} entries")

    # ── build final gazetteer list ────────────────────────────────────────────
    gazetteer = []
    for (canonical_form, entity_type), data in sorted(
        filtered.items(), key=lambda x: -x[1]["frequency"]
    ):
        heritage_relevance = infer_heritage_relevance(canonical_form, entity_type)
        entry = {
            "canonical":          canonical_form,
            "entity_type":        entity_type,
            "aliases":            sorted(data["raw_surfaces"] - {canonical_form}),
            "frequency":          data["frequency"],
            "source_doc_count":   len(data["source_docs"]),
            "source_docs":        data["source_docs"][:20],   # cap for file size
            "heritage_relevance": heritage_relevance,
            "heritage_types":     sorted(data["heritage_types_seen"]),
            "domains":            sorted(data["domains_seen"]),
            "time_periods":       sorted(data["time_periods_seen"]),
            "regions":            sorted(data["regions_seen"]),
        }
        gazetteer.append(entry)

    # ── write output ──────────────────────────────────────────────────────────
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(gazetteer, f, indent=2, ensure_ascii=False)

    # ── summary ───────────────────────────────────────────────────────────────
    by_type: dict = defaultdict(int)
    for e in gazetteer:
        by_type[e["entity_type"]] += 1

    print(f"\n{'='*65}")
    print(f"GAZETTEER BUILT: {len(gazetteer)} entries")
    print(f"Output: {OUT_FILE}")
    print(f"\nBreakdown by entity type:")
    for etype, count in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"  {etype:<15} {count}")
    top10 = gazetteer[:10]
    print(f"\nTop 10 most frequent entries:")
    for e in top10:
        print(f"  [{e['entity_type']:<13}] {e['canonical']:<40} freq={e['frequency']}")
    print("=" * 65)


if __name__ == "__main__":
    build_gazetteer()
