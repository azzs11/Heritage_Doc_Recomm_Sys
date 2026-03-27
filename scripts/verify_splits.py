"""
verify_splits.py
----------------
Post-migration verification script.

Checks that well-known individual heritage entities can be found as direct
search results after the corpus has been split and reindexed.

Usage
-----
    python scripts/verify_splits.py

    # Add extra queries beyond the defaults
    python scripts/verify_splits.py --queries "Hampi" "Petra" "Stonehenge"

    # Also show the top-5 results for every query (verbose)
    python scripts/verify_splits.py --verbose

Exit code
---------
    0  — all checks passed
    1  — one or more checks failed (entity not in top results)
    2  — system could not be loaded (models missing, import error, etc.)
"""

import argparse
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

DEFAULT_QUERIES = [
    "Taj Mahal",
    "Angkor Wat",
    "Colosseum",
    "Machu Picchu",
    "Pyramids of Giza",
    "Stonehenge",
    "Alhambra",
    "Borobudur",
]

TOP_K = 10  # check within top-10 results


def load_system():
    """Load QueryProcessor and HeritageRecommender. Returns (qp, rec) or raises."""
    query_system_dir = os.path.join(PROJECT_ROOT, 'src', '6_query_system')
    if query_system_dir not in sys.path:
        sys.path.insert(0, query_system_dir)
    from query_processor import QueryProcessor
    from recommender import HeritageRecommender

    print('Loading QueryProcessor...')
    qp = QueryProcessor()

    print('Loading HeritageRecommender...')
    rec = HeritageRecommender()

    return qp, rec


def check_query(query: str, qp, rec, verbose: bool) -> bool:
    """
    Return True if `query` appears (case-insensitive) in the title of at
    least one of the top-K results.
    """
    parsed = qp.parse_query(query)
    results = rec.recommend(parsed, top_k=TOP_K, explain=False)

    query_lower = query.lower()
    found = any(query_lower in r.get('title', '').lower() for r in results)

    status = 'PASS' if found else 'FAIL'
    print(f"  [{status}] '{query}'", end='')

    if found:
        match = next(r for r in results if query_lower in r.get('title', '').lower())
        rank = results.index(match) + 1
        print(f" — found at rank {rank}: \"{match['title']}\"")
    else:
        print(f" — not found in top {TOP_K}")

    if verbose:
        for i, r in enumerate(results, 1):
            score = r.get('score', 0)
            print(f"       {i:2d}. [{score:.4f}] {r.get('title', '(no title)')}")

    return found


def main():
    parser = argparse.ArgumentParser(
        description='Verify that individual heritage entities are searchable after migration.'
    )
    parser.add_argument(
        '--queries', nargs='+', metavar='QUERY',
        help='Additional queries to check (in addition to defaults)'
    )
    parser.add_argument(
        '--only', nargs='+', metavar='QUERY',
        help='Check ONLY these queries (replaces defaults)'
    )
    parser.add_argument(
        '--verbose', '-v', action='store_true',
        help='Show top-K result titles for every query'
    )
    args = parser.parse_args()

    if args.only:
        queries = args.only
    else:
        queries = DEFAULT_QUERIES + (args.queries or [])

    print('=' * 60)
    print('Heritage Document Split Verification')
    print('=' * 60)
    print(f'Project root : {PROJECT_ROOT}')
    print(f'Queries      : {len(queries)}')
    print(f'Top-K        : {TOP_K}')
    print()

    # Load system
    try:
        qp, rec = load_system()
    except Exception as e:
        print(f'\nFailed to load system: {e}')
        print('Make sure you have run the full reindex pipeline first:')
        print('  python scripts/reindex_pipeline.py')
        sys.exit(2)

    print(f'\nRunning {len(queries)} verification queries...\n')

    passed = 0
    failed = 0
    for query in queries:
        ok = check_query(query, qp, rec, verbose=args.verbose)
        if ok:
            passed += 1
        else:
            failed += 1

    print('\n' + '=' * 60)
    print(f'Results: {passed} passed, {failed} failed out of {len(queries)} queries')
    print('=' * 60)

    if failed:
        print('\nSome entities were not found in top results.')
        print('Possible causes:')
        print('  • Those entities were not present in any document (check data/raw/)')
        print('  • Reindex was not run after migration (run scripts/reindex_pipeline.py)')
        print('  • Splitting thresholds excluded the relevant section (check MIN_SECTION_WORDS)')
        sys.exit(1)
    else:
        print('\nAll verification checks passed.')
        sys.exit(0)


if __name__ == '__main__':
    main()
