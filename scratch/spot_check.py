import sys
import json
import random

sys.stdout.reconfigure(encoding='utf-8')
random.seed(42)

files = {
    'papers': 'data/papers.jsonl',
    'startups': 'data/startups.jsonl',
    'products': 'data/products.jsonl',
    'news': 'data/news.jsonl',
    'jobs': 'data/jobs.jsonl'
}

print("=== 3. DATA INTEGRITY SPOT CHECK ===")
for name, fpath in files.items():
    with open(fpath, encoding='utf-8') as f:
        records = [json.loads(line) for line in f if line.strip()]
    sample = random.sample(records, min(5, len(records)))
    print(f"\n--- {name.upper()} (5 Random Samples) ---")
    for i, r in enumerate(sample, 1):
        url = r.get('source', {}).get('url')
        is_valid = bool(url and (url.startswith('http://') or url.startswith('https://')))
        content_preview = str(r.get('content'))[:120].replace('\n', ' ')
        print(f"Sample #{i}:")
        print(f"  Source Name: {r.get('source', {}).get('name')}")
        print(f"  Source URL : {url}")
        print(f"  Real Fetched URL Confirmed: {is_valid}")
        print(f"  Data Content: {content_preview}...")
