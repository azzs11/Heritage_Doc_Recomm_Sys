"""
reindex_pipeline.py
-------------------
Convenience script that runs all downstream pipeline stages (2-9) in order
after the corpus has been updated (e.g., after migrate_corpus.py splits
aggregated documents).

Usage
-----
    python scripts/reindex_pipeline.py              # run all stages
    python scripts/reindex_pipeline.py --from 4     # start from stage 4
    python scripts/reindex_pipeline.py --only 6 7   # run only stages 6 and 7

Stages
------
    2  clean_data.py                    — clean raw documents
    3  2_extract_metadata_spaCy.py      — extract entities + classification
    4  3_generate_embeddings.py         — generate 384-dim embeddings
    5  4_train_autoencoder.py           — autoencoder + K-means clustering
    6  build_faiss_index.py             — build FAISS HNSW + Flat index
    7  5_build_knowledge_graph.py       — build NetworkX knowledge graph
    8  horn_index.py                    — compute Horn's index weights
    9  compute_simrank.py               — compute SimRank similarity matrix
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

STAGES = [
    (2, 'src/2_preprocessing/clean_data.py',                'Clean data'),
    (3, 'src/2_preprocessing/2_extract_metadata_spaCy.py',  'Extract metadata (spaCy NER)'),
    (4, 'src/3_representation/3_generate_embeddings.py',    'Generate embeddings'),
    (5, 'src/3_representation/4_train_autoencoder.py',      'Train autoencoder + clustering'),
    (6, 'src/4_knowledge_graph/build_faiss_index.py',       'Build FAISS index'),
    (7, 'src/4_knowledge_graph/5_build_knowledge_graph.py', 'Build knowledge graph'),
    (8, 'src/4_knowledge_graph/horn_index.py',              "Compute Horn's index"),
    (9, 'src/4_knowledge_graph/compute_simrank.py',         'Compute SimRank matrix'),
]


def run_stage(stage_num: int, script_rel: str, label: str) -> bool:
    script_path = os.path.join(PROJECT_ROOT, script_rel)
    print(f'\n[Stage {stage_num}] {label}')
    print(f'  Script : {script_path}')

    if not os.path.exists(script_path):
        print(f'  ⚠  Script not found — skipping')
        return True  # non-fatal; skip missing stages

    start = datetime.now()
    result = subprocess.run(
        [sys.executable, script_path],
        cwd=PROJECT_ROOT,
    )
    elapsed = (datetime.now() - start).total_seconds()

    if result.returncode != 0:
        print(f'  ✗  Failed (exit {result.returncode}) after {elapsed:.1f}s')
        return False

    print(f'  ✓  Done in {elapsed:.1f}s')
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Run heritage document pipeline reindex stages 2-9.'
    )
    parser.add_argument(
        '--from', dest='from_stage', type=int, default=2, metavar='N',
        help='Start from stage N (default: 2)'
    )
    parser.add_argument(
        '--only', nargs='+', type=int, metavar='N',
        help='Run only these stage numbers (e.g. --only 6 7 8)'
    )
    args = parser.parse_args()

    if args.only:
        stages_to_run = [s for s in STAGES if s[0] in args.only]
    else:
        stages_to_run = [s for s in STAGES if s[0] >= args.from_stage]

    if not stages_to_run:
        print('No stages to run. Check --from / --only arguments.')
        sys.exit(1)

    print('=' * 60)
    print('Heritage Document Reindex Pipeline')
    print('=' * 60)
    print(f'Project root : {PROJECT_ROOT}')
    print(f'Stages       : {[s[0] for s in stages_to_run]}')
    print(f'Started      : {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

    for stage_num, script_rel, label in stages_to_run:
        ok = run_stage(stage_num, script_rel, label)
        if not ok:
            print(f'\nPipeline aborted at stage {stage_num}.')
            print('Fix the error above and re-run with:')
            print(f'  python scripts/reindex_pipeline.py --from {stage_num}')
            sys.exit(1)

    print('\n' + '=' * 60)
    print('All stages complete.')
    print(f'Finished: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('\nNext step: run scripts/verify_splits.py to confirm search results.')
    print('=' * 60)


if __name__ == '__main__':
    main()
