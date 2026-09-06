import json

with open("data/products.jsonl", encoding="utf-8") as f:
    products = [json.loads(line) for line in f if line.strip()]

total = len(products)
platform_pattern = [p for p in products if p["content"]["productName"].endswith(" Platform")]
distinct_products = [p for p in products if not p["content"]["productName"].endswith(" Platform")]

print(f"Total Product Records: {total}")
print(f"Auto-generated Pattern ('{{Startup}} Platform') Records: {len(platform_pattern)}")
print(f"Genuinely Distinct Scraped Product Records: {len(distinct_products)}")

print("\n--- 10 SAMPLE GENUINELY DISTINCT PRODUCTS ---")
for i, p in enumerate(distinct_products[:10], 1):
    print(f"[{i}] Product: {p['content']['productName']} | Source: {p['source']['name']} | URL: {p['source']['url']}")
    print(f"    Description: {p['content']['description'][:120]}")
