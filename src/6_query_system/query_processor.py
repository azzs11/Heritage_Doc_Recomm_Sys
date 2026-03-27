"""
Query Processor for Heritage Document Recommendation System

Parses natural language queries to extract:
- Heritage types (temple, fort, monument, etc.)
- Domains (religious, military, royal, etc.)
- Time periods (ancient, medieval, modern)
- Regions (North India, Rajasthan, etc.)
- Architectural styles (Mughal, Dravidian, etc.)
- Named entities (locations, persons, organizations)

Uses spaCy for NLP and classification schemas from metadata extraction.
"""

import spacy
import re
import json
import os
from typing import Dict, List, Set
from sentence_transformers import SentenceTransformer
import numpy as np


class QueryProcessor:
    """Processes natural language queries for heritage document search."""

    # Classification schemas (from 2_extract_metadata_spaCy.py)
    HERITAGE_TYPES = {
        'monument', 'site', 'artifact', 'architecture', 'tradition', 'art',
        'temple', 'fort', 'palace', 'mosque', 'church', 'monastery', 'stupa',
        'pagoda', 'shrine', 'cathedral', 'fortress', 'citadel', 'castle',
        'mansion', 'haveli', 'memorial', 'statue', 'tomb', 'cenotaph'
    }

    DOMAINS = {
        'religious', 'military', 'royal', 'cultural', 'archaeological', 'architectural',
        'spiritual', 'defensive', 'residential', 'commemorative', 'sacred', 'worship'
    }

    TIME_PERIODS = {
        'ancient': ['ancient', 'prehistoric', 'vedic', 'maurya', 'gupta'],
        'medieval': ['medieval', 'mughal', 'sultanate', 'vijayanagara', 'maratha', 'rajput'],
        'modern': ['modern', 'colonial', 'british', 'contemporary', 'post-independence']
    }

    INDIAN_REGIONS = {
        'north': ['north', 'northern', 'delhi', 'punjab', 'haryana', 'himachal', 'uttarakhand', 'uttar pradesh', 'jammu', 'kashmir'],
        'south': ['south', 'southern', 'tamil nadu', 'kerala', 'karnataka', 'andhra pradesh', 'telangana'],
        'east': ['east', 'eastern', 'west bengal', 'odisha', 'bihar', 'jharkhand', 'sikkim'],
        'west': ['west', 'western', 'rajasthan', 'gujarat', 'maharashtra', 'goa'],
        'central': ['central', 'madhya pradesh', 'chhattisgarh']
    }

    ARCHITECTURAL_STYLES = {
        'indo-islamic', 'mughal', 'dravidian', 'nagara', 'vesara', 'buddhist',
        'colonial', 'rajput', 'maratha', 'vijayanagara', 'hoysala', 'chalukya',
        'pallava', 'chola', 'indo-saracenic'
    }

    # Default gazetteer path — relative to project root
    GAZETTEER_PATH = "data/gazetteer/heritage_gazetteer.json"

    def __init__(
        self,
        embedding_model_name: str = 'all-MiniLM-L6-v2',
        gazetteer_path: str = None,
    ):
        """
        Initialize query processor.

        Args:
            embedding_model_name: Name of sentence transformer model
            gazetteer_path: Path to heritage_gazetteer.json (optional override)
        """
        print(f"Loading spaCy model...")
        try:
            self.nlp = spacy.load('en_core_web_sm')
        except OSError:
            print("Downloading spaCy model 'en_core_web_sm'...")
            import subprocess
            subprocess.run(['python', '-m', 'spacy', 'download', 'en_core_web_sm'])
            self.nlp = spacy.load('en_core_web_sm')

        print(f"Loading embedding model: {embedding_model_name}...")
        self.embedding_model = SentenceTransformer(embedding_model_name)

        # Load gazetteer for high-recall entity lookup
        gaz_path = gazetteer_path or self.GAZETTEER_PATH
        self._gaz_locations: dict = {}      # lower surface → canonical
        self._gaz_persons: dict = {}
        self._gaz_organizations: dict = {}
        self._gaz_monuments: dict = {}
        self._load_gazetteer(gaz_path)

        print("Query processor initialized successfully!")

    def _load_gazetteer(self, path: str) -> None:
        """Load the heritage gazetteer and build fast lookup dicts keyed by lowercase surface forms."""
        if not os.path.exists(path):
            print(f"Gazetteer not found at {path} — entity lookup will rely on spaCy only.")
            return
        with open(path, "r", encoding="utf-8") as f:
            entries = json.load(f)
        bucket_map = {
            "location":     self._gaz_locations,
            "person":       self._gaz_persons,
            "organization": self._gaz_organizations,
            "monument":     self._gaz_monuments,
        }
        for entry in entries:
            etype = entry.get("entity_type")
            bucket = bucket_map.get(etype)
            if bucket is None:
                continue
            canonical = entry["canonical"]
            # Index by canonical (lower) and all known aliases
            surfaces = [canonical] + entry.get("aliases", [])
            for s in surfaces:
                key = s.strip().lower()
                if key and key not in bucket:
                    bucket[key] = canonical
        total = sum(len(b) for b in bucket_map.values())
        print(f"Gazetteer loaded: {total} surface forms across {len(entries)} entries")

    def _gazetteer_lookup(self, query_lower: str) -> Dict[str, List[str]]:
        """Scan query text for gazetteer matches (longest-match, greedy left-to-right)."""
        hits: Dict[str, List[str]] = {
            "locations": [], "persons": [], "organizations": [], "monuments": []
        }
        buckets = [
            (self._gaz_locations,     "locations"),
            (self._gaz_persons,       "persons"),
            (self._gaz_organizations, "organizations"),
            (self._gaz_monuments,     "monuments"),
        ]
        for bucket, key in buckets:
            seen = set()
            for surface, canonical in bucket.items():
                # whole-word boundary match
                if re.search(r'\b' + re.escape(surface) + r'\b', query_lower):
                    if canonical.lower() not in seen:
                        seen.add(canonical.lower())
                        hits[key].append(canonical)
        return hits

    def parse_query(self, query_text: str) -> Dict:
        """
        Parse natural language query to extract heritage attributes.

        Args:
            query_text: Natural language query (e.g., "Mughal temples in North India")

        Returns:
            Dictionary with extracted attributes:
            - heritage_types: Set of heritage types
            - domains: Set of domains
            - time_period: Detected time period (ancient/medieval/modern)
            - region: Detected region (north/south/east/west/central)
            - architectural_styles: Set of architectural styles
            - locations: List of location entities
            - persons: List of person entities
            - organizations: List of organization entities
            - query_embedding: 384-dim embedding vector
            - original_query: Original query text
        """
        query_lower = query_text.lower()
        doc = self.nlp(query_text)

        parsed = {
            'heritage_types': set(),
            'domains': set(),
            'time_period': None,
            'region': None,
            'architectural_styles': set(),
            'locations': [],
            'persons': [],
            'organizations': [],
            'query_embedding': None,
            'original_query': query_text
        }

        # Extract heritage types
        for heritage_type in self.HERITAGE_TYPES:
            if heritage_type in query_lower:
                parsed['heritage_types'].add(heritage_type)

        # Extract domains
        for domain in self.DOMAINS:
            if domain in query_lower:
                parsed['domains'].add(domain)

        # Infer domains from heritage types and architectural styles
        if 'temple' in parsed['heritage_types'] or 'mosque' in parsed['heritage_types'] or \
           'church' in parsed['heritage_types'] or 'monastery' in parsed['heritage_types'] or \
           'stupa' in parsed['heritage_types'] or 'shrine' in parsed['heritage_types'] or \
           'cathedral' in parsed['heritage_types']:
            parsed['domains'].add('religious')

        if 'fort' in parsed['heritage_types'] or 'fortress' in parsed['heritage_types'] or \
           'citadel' in parsed['heritage_types'] or 'castle' in parsed['heritage_types']:
            parsed['domains'].add('military')

        if 'palace' in parsed['heritage_types'] or 'haveli' in parsed['heritage_types'] or \
           'mansion' in parsed['heritage_types']:
            parsed['domains'].add('royal')

        if 'architecture' in parsed['heritage_types'] or parsed['architectural_styles']:
            parsed['domains'].add('architectural')

        # Extract time period
        for period, keywords in self.TIME_PERIODS.items():
            for keyword in keywords:
                if keyword in query_lower:
                    parsed['time_period'] = period
                    break
            if parsed['time_period']:
                break

        # Extract region
        for region, keywords in self.INDIAN_REGIONS.items():
            for keyword in keywords:
                if keyword in query_lower:
                    parsed['region'] = region
                    break
            if parsed['region']:
                break

        # Extract architectural styles
        for style in self.ARCHITECTURAL_STYLES:
            if style in query_lower:
                parsed['architectural_styles'].add(style)

        # Extract named entities using spaCy
        for ent in doc.ents:
            if ent.label_ == 'GPE' or ent.label_ == 'LOC':
                parsed['locations'].append(ent.text)
            elif ent.label_ == 'PERSON':
                parsed['persons'].append(ent.text)
            elif ent.label_ == 'ORG':
                parsed['organizations'].append(ent.text)

        # Augment with gazetteer lookup (fills gaps spaCy misses)
        gaz_hits = self._gazetteer_lookup(query_lower)
        seen_locs = {l.lower() for l in parsed['locations']}
        seen_pers = {p.lower() for p in parsed['persons']}
        seen_orgs = {o.lower() for o in parsed['organizations']}
        for loc in gaz_hits['locations']:
            if loc.lower() not in seen_locs:
                parsed['locations'].append(loc)
                seen_locs.add(loc.lower())
        for per in gaz_hits['persons']:
            if per.lower() not in seen_pers:
                parsed['persons'].append(per)
                seen_pers.add(per.lower())
        for org in gaz_hits['organizations']:
            if org.lower() not in seen_orgs:
                parsed['organizations'].append(org)
                seen_orgs.add(org.lower())
        # Monuments feed into heritage_types and locations
        for mon in gaz_hits['monuments']:
            if mon.lower() not in seen_locs:
                parsed['locations'].append(mon)
                seen_locs.add(mon.lower())

        # Generate query embedding
        parsed['query_embedding'] = self.embedding_model.encode(
            query_text,
            normalize_embeddings=True
        )

        return parsed

    def format_parsed_query(self, parsed: Dict) -> str:
        """
        Format parsed query for display.

        Args:
            parsed: Parsed query dictionary

        Returns:
            Formatted string representation
        """
        lines = [
            f"Query: {parsed['original_query']}",
            "-" * 60
        ]

        if parsed['heritage_types']:
            lines.append(f"Heritage Types: {', '.join(parsed['heritage_types'])}")

        if parsed['domains']:
            lines.append(f"Domains: {', '.join(parsed['domains'])}")

        if parsed['time_period']:
            lines.append(f"Time Period: {parsed['time_period']}")

        if parsed['region']:
            lines.append(f"Region: {parsed['region']}")

        if parsed['architectural_styles']:
            lines.append(f"Architectural Styles: {', '.join(parsed['architectural_styles'])}")

        if parsed['locations']:
            lines.append(f"Locations: {', '.join(parsed['locations'])}")

        if parsed['persons']:
            lines.append(f"Persons: {', '.join(parsed['persons'])}")

        if parsed['organizations']:
            lines.append(f"Organizations: {', '.join(parsed['organizations'])}")

        lines.append(f"Embedding: {parsed['query_embedding'].shape}")

        return '\n'.join(lines)


def main():
    """Test query processor with example queries."""
    processor = QueryProcessor()

    test_queries = [
        "Mughal temples in North India",
        "Ancient forts in Rajasthan",
        "Buddhist stupas and monasteries",
        "Dravidian temples in South India",
        "Colonial architecture in Mumbai",
        "Medieval palaces of Maratha kings",
        "Religious monuments of Vijayanagara empire"
    ]

    print("\n" + "=" * 80)
    print("QUERY PROCESSOR TEST")
    print("=" * 80 + "\n")

    for query in test_queries:
        parsed = processor.parse_query(query)
        print(processor.format_parsed_query(parsed))
        print()


if __name__ == '__main__':
    main()
