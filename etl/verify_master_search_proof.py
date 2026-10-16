import os
import sys
import json
import time
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

inserted_json_path = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/etl/reports/master_recovery_final/inserted_electors.json'
with open(inserted_json_path, 'r', encoding='utf-8') as f:
    inserted_records = json.load(f)

test_epics = [r['epic_number'] for r in inserted_records if r.get('epic_number')]
print(f"Executing parallel search proof for {len(test_epics)} newly inserted master recovery EPICs...")

PROD_URL = "https://web-murex-one-98.vercel.app"
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
                "epic": epic,
                "found": found,
                "returned_rows": len(rows),
                "status": resp.status
            }
    except Exception as ex:
        return {
            "epic": epic,
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
            missing_epics.append(res.get('epic'))

elapsed = time.time() - start_time
print(f"\nSearch Proof Completed in {elapsed:.2f} seconds!")
print(f"Total Verified: {len(test_epics)}")
print(f"SUCCESS: Total Found = {len(test_epics) - len(missing_epics)} ({((len(test_epics) - len(missing_epics)) / len(test_epics))*100:.1f}%)")
print(f"MISSING: Total Missing = {len(missing_epics)}")

out_dir = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/etl/reports/master_recovery_final'
pd.DataFrame(results).to_csv(os.path.join(out_dir, 'search_proof.csv'), index=False)
print(f"Saved complete search proof audit report to {out_dir}/search_proof.csv")
