import os
import sys
import re
import json
import time
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')

env_path = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/web/.env.local'
load_dotenv(env_path)

PROD_URL = "https://web-murex-one-98.vercel.app"
valid_csv = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/etl/reports/phase4_dry_run_reconciliation/new_valid.csv'
df_inserted = pd.read_csv(valid_csv)

test_epics = df_inserted['epic_number'].tolist()
print(f"Executing high-speed parallel search proof for {len(test_epics)} EPICs against {PROD_URL}...")

headers = {'User-Agent': 'AntigravityAudit/1.0'}

def check_epic(epic):
    url = f"{PROD_URL}/api/search?q={urllib.parse.quote(epic)}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            rows = data.get('rows', [])
            found = any(r.get('epic_number') == epic for r in rows)
            return {
                "type": "newly_inserted_epic",
                "query": epic,
                "found": found,
                "total_returned": len(rows),
                "status_code": resp.status
            }
    except Exception as ex:
        return {
            "type": "newly_inserted_epic",
            "query": epic,
            "found": False,
            "error": str(ex)
        }

start_time = time.time()
results = []
missing_epics = []

with ThreadPoolExecutor(max_workers=10) as executor:
    futures = {executor.submit(check_epic, ep): ep for ep in test_epics}
    for f in as_completed(futures):
        res = f.result()
        results.append(res)
        if not res.get('found'):
            missing_epics.append(res.get('query'))

elapsed = time.time() - start_time
print(f"Verified all {len(test_epics)} EPICs in {elapsed:.2f} seconds!")
print(f"SUCCESS: Total Found = {len(test_epics) - len(missing_epics)}")
print(f"MISSING: Total Missing = {len(missing_epics)}")

# Step 2: Name search test
sample_names = df_inserted.dropna(subset=['name']).sample(n=min(50, len(df_inserted)), random_state=42)

def check_name(row):
    name = row['name']
    epic = row['epic_number']
    url = f"{PROD_URL}/api/search?q={urllib.parse.quote(name)}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            rows = data.get('rows', [])
            found = any(r.get('epic_number') == epic for r in rows)
            return {
                "type": "name_query",
                "query": name,
                "expected_epic": epic,
                "found": found,
                "total_returned": len(rows)
            }
    except Exception as ex:
        return {
            "type": "name_query",
            "query": name,
            "expected_epic": epic,
            "found": False,
            "error": str(ex)
        }

with ThreadPoolExecutor(max_workers=5) as executor:
    name_futures = [executor.submit(check_name, r) for _, r in sample_names.iterrows()]
    name_results = [f.result() for f in as_completed(name_futures)]
    results.extend(name_results)

name_found = sum(1 for nr in name_results if nr.get('found'))
print(f"Name search test: {name_found}/{len(sample_names)} exact target voters returned by name search.")

out_dir = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/etl/reports/phase5_insert_results'
os.makedirs(out_dir, exist_ok=True)
pd.DataFrame(results).to_csv(os.path.join(out_dir, 'search_proof.csv'), index=False)
print(f"Saved complete audit report to {out_dir}/search_proof.csv")
