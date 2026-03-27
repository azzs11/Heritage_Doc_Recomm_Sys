"""
detect_and_split.py
-------------------
Detects aggregated heritage documents (Wikipedia articles that bundle multiple
distinct heritage entities into a single document) and splits them into
individual per-entity documents.

Detection is content-based — a document does NOT need to have "list" in its
title to be treated as aggregated.

Detection algorithm:
    1. Parse Wikipedia == Heading == section boundaries from content
    2. Count sections that have >= MIN_SECTION_WORDS words of body text
    3. If qualifying_section_count >= MIN_SECTIONS → aggregated

Split output schema matches the existing raw JSON schema exactly, with three
new optional fields added to both parent and child docs:
    - is_aggregated (bool): True on parent, False on children
    - split_ids (list[str]): populated on parent with child filenames
    - parent_doc (str|None): populated on children with parent filename
"""

import re
import json
import os
from collections import namedtuple
from datetime import datetime

# ── Thresholds ──────────────────────────────────────────────────────────────
MIN_SECTIONS = 3          # minimum qualifying sections to flag as aggregated
MIN_SECTION_WORDS = 80    # minimum words per section to count as substantive

# Sections whose headings match these patterns are boilerplate — skip them
SKIP_HEADINGS = re.compile(
    r'^(references|see also|external links|notes|further reading|'
    r'bibliography|sources|footnotes|gallery|citations|appendix)$',
    re.IGNORECASE
)

SplitResult = namedtuple('SplitResult', ['original', 'children', 'skipped_sections'])


# ── Section parsing ──────────────────────────────────────────────────────────

def _parse_sections(content: str) -> list[tuple[str, str]]:
    """
    Split Wikipedia-markup content on top-level (== Heading ==) boundaries.

    Returns a list of (heading, body) tuples. The text before the first
    heading is returned with heading="" (intro section).
    """
    # Match == ... == at start of line (top-level only; === is nested)
    pattern = re.compile(r'^==\s+(.+?)\s+==$', re.MULTILINE)
    headings = list(pattern.finditer(content))

    if not headings:
        return [("", content.strip())]

    sections = []

    # Text before first heading
    intro = content[:headings[0].start()].strip()
    if intro:
        sections.append(("", intro))

    for i, match in enumerate(headings):
        heading = match.group(1).strip()
        start = match.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(content)
        body = content[start:end].strip()
        sections.append((heading, body))

    return sections


def _word_count(text: str) -> int:
    return len(text.split())


def _first_sentences(text: str, n: int = 2) -> str:
    """Extract the first n sentences from text as a summary."""
    # Split on sentence-ending punctuation followed by whitespace
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return ' '.join(sentences[:n]).strip()


# ── Detection ─────────────────────────────────────────────────────────────────

def detect_aggregated(raw_doc: dict) -> bool:
    """
    Return True if the document contains multiple distinct heritage entity
    sections, making it an aggregated document that should be split.
    """
    content = raw_doc.get('content', '')
    if not content:
        return False

    # Already processed — skip children (parent_doc set) and known non-aggregated
    if raw_doc.get('parent_doc'):
        return False
    if raw_doc.get('is_aggregated') is True:
        # Already split in a previous run; don't re-split
        return False

    sections = _parse_sections(content)
    qualifying = [
        (h, b) for h, b in sections
        if h and not SKIP_HEADINGS.match(h) and _word_count(b) >= MIN_SECTION_WORDS
    ]
    return len(qualifying) >= MIN_SECTIONS


# ── Splitting ─────────────────────────────────────────────────────────────────

def split_document(raw_doc: dict, parent_filename: str) -> SplitResult:
    """
    Split an aggregated document into individual per-section documents.

    Each child document has the same schema as a raw collected document.
    The parent document is updated in-place with is_aggregated=True and
    split_ids listing the child filenames.

    Returns a SplitResult with:
        original   — mutated parent dict (is_aggregated=True, split_ids set)
        children   — list of (filename, dict) tuples for each child
        skipped_sections — count of sections dropped for being too short/boilerplate
    """
    content = raw_doc.get('content', '')
    sections = _parse_sections(content)

    parent_stem = os.path.splitext(parent_filename)[0]

    children = []
    skipped = 0
    child_index = 0

    for heading, body in sections:
        # Skip intro (no heading) and boilerplate headings
        if not heading:
            continue
        if SKIP_HEADINGS.match(heading):
            skipped += 1
            continue
        if _word_count(body) < MIN_SECTION_WORDS:
            skipped += 1
            continue

        child_filename = f"{parent_stem}_split_{child_index:03d}.json"
        child_doc = {
            'title': heading,
            'url': raw_doc.get('url', ''),
            'content': body,
            'summary': _first_sentences(body, n=2),
            'categories': raw_doc.get('categories', []),
            'source': raw_doc.get('source', ''),
            'fetched_at': raw_doc.get('fetched_at', datetime.now().isoformat()),
            'is_aggregated': False,
            'split_ids': [],
            'parent_doc': parent_filename,
        }
        children.append((child_filename, child_doc))
        child_index += 1

    # Mutate parent
    raw_doc['is_aggregated'] = True
    raw_doc['split_ids'] = [fname for fname, _ in children]

    return SplitResult(original=raw_doc, children=children, skipped_sections=skipped)


# ── File-level helpers ────────────────────────────────────────────────────────

def process_file(filepath: str, dry_run: bool = False) -> dict:
    """
    Load a single raw JSON file, detect if aggregated, split if so.

    In dry_run mode no files are written; the return dict describes what
    *would* happen.

    Returns a status dict:
        {
          "file": str,
          "status": "split" | "skipped" | "error" | "already_split",
          "children_created": int,
          "sections_skipped": int,
          "child_filenames": list[str],
          "error": str | None
        }
    """
    result = {
        'file': filepath,
        'status': 'skipped',
        'children_created': 0,
        'sections_skipped': 0,
        'child_filenames': [],
        'error': None,
    }

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            raw_doc = json.load(f)
    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)
        return result

    # Already split in a previous run
    if raw_doc.get('is_aggregated') is True:
        result['status'] = 'already_split'
        result['child_filenames'] = raw_doc.get('split_ids', [])
        return result

    if not detect_aggregated(raw_doc):
        return result  # status = skipped

    parent_filename = os.path.basename(filepath)
    output_dir = os.path.dirname(filepath)
    split = split_document(raw_doc, parent_filename)

    result['status'] = 'split'
    result['children_created'] = len(split.children)
    result['sections_skipped'] = split.skipped_sections
    result['child_filenames'] = [fname for fname, _ in split.children]

    if not dry_run:
        # Write children
        for child_filename, child_doc in split.children:
            child_path = os.path.join(output_dir, child_filename)
            with open(child_path, 'w', encoding='utf-8') as f:
                json.dump(child_doc, f, indent=2, ensure_ascii=False)

        # Overwrite parent with updated is_aggregated / split_ids
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(split.original, f, indent=2, ensure_ascii=False)

    return result


def process_directory(raw_dir: str, dry_run: bool = False) -> list[dict]:
    """
    Walk raw_dir recursively, process every *.json file.

    Returns list of per-file status dicts from process_file().
    """
    results = []
    for root, _, files in os.walk(raw_dir):
        for fname in sorted(files):
            if not fname.lower().endswith('.json'):
                continue
            filepath = os.path.join(root, fname)
            res = process_file(filepath, dry_run=dry_run)
            results.append(res)
    return results


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Detect and split aggregated heritage documents in data/raw/'
    )
    parser.add_argument(
        '--raw-dir', default='data/raw',
        help='Path to raw documents directory (default: data/raw)'
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Preview what would be split without writing any files'
    )
    parser.add_argument(
        '--file', default=None,
        help='Process a single file instead of the whole directory'
    )
    args = parser.parse_args()

    if args.file:
        res = process_file(args.file, dry_run=args.dry_run)
        print(json.dumps(res, indent=2))
    else:
        results = process_directory(args.raw_dir, dry_run=args.dry_run)

        total = len(results)
        split_count = sum(1 for r in results if r['status'] == 'split')
        docs_created = sum(r['children_created'] for r in results)
        already = sum(1 for r in results if r['status'] == 'already_split')
        errors = [r for r in results if r['status'] == 'error']

        mode = '[DRY RUN] ' if args.dry_run else ''
        print(f"\n{mode}Aggregated Document Detection & Split")
        print("=" * 50)
        print(f"  Total scanned   : {total}")
        print(f"  Aggregated found: {split_count}")
        print(f"  Split docs made : {docs_created}")
        print(f"  Already split   : {already}")
        print(f"  Errors          : {len(errors)}")

        if split_count:
            print("\nSplit documents:")
            for r in results:
                if r['status'] == 'split':
                    print(f"  {os.path.basename(r['file'])} -> {r['children_created']} children")

        if errors:
            print("\nErrors:")
            for r in errors:
                print(f"  {r['file']}: {r['error']}")
