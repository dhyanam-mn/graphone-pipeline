import requests
import re

repos = [
    "DeepSoftwareAnalytics/SWE-Gate",
    "IBM/draco",
    "yutaizhou/bnn_pref",
    "victorlavrenko/answer-engineering",
    "nebula-1999/Interface-Induced-Trajectory-Censoring",
    "TomasGuija/rarf"
]

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

for repo in repos:
    url = f"https://github.com/{repo}"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        m = re.search(r'stargazers_count":\s*(\d+)', r.text) or re.search(r'id="repo-stars-counter-star"[^>]*title="([\d,]+)"', r.text) or re.search(r'id="repo-stars-counter-star"[^>]*>([\d\.\,kKmM]+)<', r.text)
        stars = m.group(1) if m else "N/A"
        print(f"Repo {repo} -> Stars: {stars}")
