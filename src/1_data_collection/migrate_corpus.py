"""
migrate_corpus.py
-----------------
One-time migration script: scans the existing data/raw/ corpus, detects all
aggregated documents, splits them into individual per-entity documents, and
optionally triggers the full downstream reprocessing pipeline.

Usage
-----
    # Preview what will be split (no files written)
    python src/1_data_collection/migrate_corpus.py --dry-run

    # Run the migration
    python src/1_data_collection/migrate_corpus.py

    # Run migration then immediately reindex
    python src/1_data_collection/migrate_corpus.py --reindex

    # Save the summary report to a file
    python src/1_data_collection/migrate_corpus.py --report migration_report.json
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime

# Allow running from any working directory
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src', '1_data_collection'))

from detect_and_split import process_directory  # noqa: E402


RAW_DIR = os.path.join(PROJECT_ROOT, 'data', 'raw')

REINDEX_STAGES = [
    ('src/2_preprocessing/clean_data.py',               'Stage 2 — Clean data'),
    ('src/2_preprocessing/2_extract_metadata_spaCy.py', 'Stage 3 — Extract metadata (spaCy)'),
    ('src/3_representation/3_generate_embeddings.py',   'Stage 4 — Generate embeddings'),
    ('src/3_representation/4_train_autoencoder.py',     'Stage 5 — Train autoencoder + clustering'),
    ('src/4_knowledge_graph/build_faiss_index.py',      'Stage 6 — Build FAISS index'),
    ('src/4_knowledge_graph/5_build_knowledge_graph.py','Stage 7 — Build knowledge graph'),
    ('src/4_knowledge_graph/horn_index.py',             'Stage 8 — Compute Horn\'s index'),
    ('src/4_knowledge_graph/compute_simrank.py',        'Stage 9 — Compute SimRank matrix'),
]


def _banner(text: str):
    print('\n' + '=' * 60)
    print(text)
    print('=' * 60)


def run_migration(raw_dir: str, dry_run: bool) -> dict:
    """Run detection + split over raw_dir. Returns summary dict."""
    mode_label = '[DRY RUN] ' if dry_run else ''
    _banner(f"{mode_label}Heritage Corpus Migration")
    print(f"  Raw dir : {raw_dir}")
    print(f"  Dry run : {dry_run}")
    print(f"  Started : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = process_directory(raw_dir, dry_run=dry_run)

    # Aggregate stats
    total         = len(results)
    split_files   = [r for r in results if r['status'] == 'split']
    skipped_files = [r for r in results if r['status'] == 'skipped']
    already_done  = [r for r in results if r['status'] == 'already_split']
    error_files   = [r for r in results if r['status'] == 'error']
    docs_created  = sum(r['children_created'] for r in split_files)

    summary = {
        'run_at':              datetime.now().isoformat(),
        'dry_run':             dry_run,
        'raw_dir':             raw_dir,
        'total_scanned':       total,
        'aggregated_found':    len(split_files),
        'split_docs_created':  docs_created,
        'already_split':       len(already_done),
        'skipped_not_aggregated': len(skipped_files),
        'errors':              [{'file': r['file'], 'error': r['error']} for r in error_files],
        'split_detail': [
            {
                'parent':   os.path.basename(r['file']),
                'children': r['child_filenames'],
                'sections_skipped': r['sections_skipped'],
            }
            for r in split_files
        ],
    }

    # Print results
    _banner(f"{mode_label}Migration Results")
    print(f"  Total scanned         : {total}")
    print(f"  Aggregated found      : {len(split_files)}")
    print(f"  Split docs created    : {docs_created}")
    print(f"  Already split (skipped): {len(already_done)}")
    print(f"  Not aggregated        : {len(skipped_files)}")
    print(f"  Errors                : {len(error_files)}")

    if split_files:
        print('\nDocuments split:')
        for r in split_files:
            print(f"  {os.path.basename(r['file'])}")
            for child in r['child_filenames']:
                print(f"    → {child}")

    if error_files:
        print('\nErrors:')
        for r in error_files:
            print(f"  {r['file']}: {r['error']}")

    print(f"\nFinished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return summary


def run_reindex():
    """Run the full downstream pipeline (stages 2-9)."""
    _banner('Reindexing Pipeline')
    print('Running all pipeline stages to reindex the expanded corpus...\n')

    for script_rel, label in REINDEX_STAGES:
        script_path = os.path.join(PROJECT_ROOT, script_rel)
        if not os.path.exists(script_path):
            print(f'  ⚠  {label} — script not found: {script_path}, skipping')
            continue

        print(f'\n  ▶  {label}')
        print(f'     {script_path}')
        result = subprocess.run(
            [sys.executable, script_path],
            cwd=PROJECT_ROOT,
        )
        if result.returncode != 0:
            print(f'\n  ✗  {label} failed (exit code {result.returncode})')
            print('     Aborting reindex. Fix the error and re-run with --reindex.')
            sys.exit(result.returncode)
        print(f'  ✓  {label} complete')

    _banner('Reindex Complete')
    print('All pipeline stages finished successfully.')
    print('Run scripts/verify_splits.py to confirm search results.')


def main():
    parser = argparse.ArgumentParser(
        description='Detect and split aggregated heritage documents, then optionally reindex.'
    )
    parser.add_argument(
        '--raw-dir', default=RAW_DIR,
        help=f'Path to raw documents directory (default: {RAW_DIR})'
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Preview changes without writing any files'
    )
    parser.add_argument(
        '--reindex', action='store_true',
        help='After migration, run the full downstream reindex pipeline'
    )
    parser.add_argument(
        '--report', default=None, metavar='PATH',
        help='Save JSON summary report to this path'
    )
    args = parser.parse_args()

    if not os.path.isdir(args.raw_dir):
        print(f'Error: raw-dir does not exist: {args.raw_dir}')
        sys.exit(1)

    summary = run_migration(args.raw_dir, dry_run=args.dry_run)

    if args.report:
        with open(args.report, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
        print(f'\nReport saved to: {args.report}')

    if args.reindex:
        if args.dry_run:
            print('\n[DRY RUN] --reindex ignored in dry-run mode.')
        elif summary['aggregated_found'] == 0 and summary['split_docs_created'] == 0:
            print('\nNo new documents were split — reindex skipped.')
        else:
            run_reindex()


if __name__ == '__main__':
    main()
