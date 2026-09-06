import requests
import re
import json

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
r = requests.get("https://www.ycombinator.com/companies", headers=headers)

match = re.search(r'window\.AlgoliaOpts\s*=\s*(\{.+?\});', r.text)
if match:
    opts = json.loads(match.group(1))
    print("Found YC Algolia Opts:", opts)
    app_id = opts.get("app")
    key = opts.get("key")
    
    # Query YC Algolia API
    url = f"https://{app_id}-dsn.algolia.net/1/indexes/YCCompany_production/query?x-algolia-agent=Algolia%20for%20JavaScript&x-algolia-api-key={key}&x-algolia-application-id={app_id}"
    
    payload = {"params": "query=AI&hitsPerPage=100"}
    res = requests.post(url, json=payload, headers=headers)
    print("Algolia query status:", res.status_code)
    if res.status_code == 200:
        hits = res.json().get("hits", [])
        print(f"Found {len(hits)} real YC AI Companies!")
        for h in hits[:10]:
            print(f"  Company Name: {h.get('name')} | Batch: {h.get('batch')} | Website: {h.get('website')} | Tagline: {h.get('one_liner')}")
else:
    print("Could not find AlgoliaOpts")
