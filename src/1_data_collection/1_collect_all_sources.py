import subprocess
import os
import sys
from datetime import datetime

# Allow detect_and_split to be imported regardless of working directory
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

def run_scraper(script_name, description):
    """Run a scraper script"""
    print(f"\n{'='*70}")
    print(f"RUNNING: {description}")
    print(f"{'='*70}\n")
    
    try:
        subprocess.run(['python', script_name], check=True)
        print(f"\n✓ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n✗ {description} failed: {e}")
        return False

def main():
    print("\n" + "="*70)
    print("MULTI-SOURCE HERITAGE DOCUMENT COLLECTOR")
    print("="*70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nThis will collect documents from 4 sources:")
    print("  1. Wikipedia (general heritage)")
    print("  2. UNESCO World Heritage Sites")
    print("  3. Indian Heritage Monuments")
    print("  4. Archive.org Historical Documents")
    print("\nEstimated time: 20-30 minutes")
    print("="*70)
    
    input("\nPress Enter to start collection...")
    
    scrapers = [
        ('src/1a_collect_wikipedia.py', 'Wikipedia Heritage Scraper'),
        ('src/1c_collect_indian_heritage.py', 'Indian Heritage Scraper'),
        ('src/1d_collect_archives.py', 'Archive.org Scraper'),
        ('src/1b_collect_unesco.py', 'UNESCO Scraper (slowest - save for last)'),
    ]
    
    results = []
    for script, desc in scrapers:
        if os.path.exists(script):
            success = run_scraper(script, desc)
            results.append((desc, success))
        else:
            print(f"\n⚠ Warning: {script} not found, skipping...")
            results.append((desc, False))
    
    # Summary
    print("\n" + "="*70)
    print("COLLECTION SUMMARY")
    print("="*70)

    for desc, success in results:
        status = "✓ SUCCESS" if success else "✗ FAILED"
        print(f"{status}: {desc}")

    print(f"\nEnd time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nCheck data/raw/ for collected documents")
    print("="*70)

    # Step 5: Auto-detect and split aggregated documents
    print("\n" + "="*70)
    print("STEP 5: DETECT & SPLIT AGGREGATED DOCUMENTS")
    print("="*70)
    try:
        from detect_and_split import process_directory
        split_results = process_directory('data/raw/', dry_run=False)
        split_count   = sum(1 for r in split_results if r['status'] == 'split')
        docs_created  = sum(r['children_created'] for r in split_results if r['status'] == 'split')
        errors        = [r for r in split_results if r['status'] == 'error']
        print(f"  Aggregated docs found : {split_count}")
        print(f"  Individual docs created: {docs_created}")
        if errors:
            print(f"  Errors                : {len(errors)}")
            for r in errors:
                print(f"    {r['file']}: {r['error']}")
        print("✓ Split step complete")
    except Exception as e:
        print(f"⚠ Split step failed: {e}")
        print("  Run manually: python src/1_data_collection/migrate_corpus.py")

if __name__ == "__main__":
    main()