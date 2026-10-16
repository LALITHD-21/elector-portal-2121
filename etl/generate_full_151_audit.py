import os
import sys
import re
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')

env_path = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/web/.env.local'
load_dotenv(env_path)

SUPABASE_URL = os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

out_dir = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/etl/reports/audit_phase2'
os.makedirs(out_dir, exist_ok=True)

headers = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Range-Unit': 'items',
    'Prefer': 'count=exact'
}

print("Fetching electoral statistics per booth across all 151 booths from Supabase...")

def audit_booth(part_num):
    part_str = str(part_num)
    electors = []
    offset = 0
    batch_size = 1000
    
    while True:
        url = f"{SUPABASE_URL}/rest/v1/electors?part_number=eq.{part_str}&select=serial_number,epic_number&limit={batch_size}&offset={offset}"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                cr = resp.headers.get('content-range')
                total = int(cr.split('/')[1]) if cr else 0
                data = json.loads(resp.read().decode('utf-8'))
                if not data: break
                electors.extend(data)
                offset += len(data)
                if offset >= total or len(data) < batch_size: break
        except Exception as e:
            return {
                "Part": part_num,
                "Status": "ERROR",
                "DB_Count": 0,
                "Max_Serial": 0,
                "Distinct_Serials": 0,
                "Missing_Count": 0,
                "Gaps_Count": 0,
                "Sample_Gaps": str(e)
            }

    db_count = len(electors)
    serials = [e['serial_number'] for e in electors if e.get('serial_number') is not None]
    distinct_serials = set(serials)
    max_serial = max(distinct_serials) if distinct_serials else 0
    
    expected_set = set(range(1, max_serial + 1)) if max_serial > 0 else set()
    gaps = sorted(list(expected_set - distinct_serials))
    
    status = "OK" if len(gaps) == 0 else "SHORT"
    
    return {
        "Part": part_num,
        "Status": status,
        "DB_Count": db_count,
        "Max_Serial": max_serial,
        "Distinct_Serials": len(distinct_serials),
        "Expected_Electors": max_serial,
        "Gaps_Count": len(gaps),
        "Sample_Gaps": ", ".join(str(g) for g in gaps[:15]) + ("..." if len(gaps) > 15 else ""),
        "all_gaps": gaps
    }

results = []
all_gaps_records = []

with ThreadPoolExecutor(max_workers=10) as executor:
    futures = {executor.submit(audit_booth, p): p for p in range(1, 152)}
    for f in as_completed(futures):
        res = f.result()
        all_gaps = res.pop('all_gaps', [])
        for g in all_gaps:
            all_gaps_records.append({"Part": res["Part"], "Missing_Serial": g})
        results.append(res)

df_results = pd.DataFrame(results).sort_values("Part")
df_gaps = pd.DataFrame(all_gaps_records)

# Save reports
csv_path = os.path.join(out_dir, 'coverage_report_updated.csv')
xlsx_path = os.path.join(out_dir, 'coverage_report_updated.xlsx')
gaps_csv = os.path.join(out_dir, 'serial_gaps_updated.csv')

df_results.to_csv(csv_path, index=False)
df_results.to_excel(xlsx_path, index=False)
df_gaps.to_csv(gaps_csv, index=False)

# Summary calculations
total_db = df_results['DB_Count'].sum()
total_expected = df_results['Expected_Electors'].sum()
total_gaps = len(df_gaps)
short_booths = len(df_results[df_results['Status'] == 'SHORT'])
ok_booths = len(df_results[df_results['Status'] == 'OK'])

summary_md = f"""# Updated 151-Booth Full Coverage Audit
- **Audit Timestamp**: {pd.Timestamp.now().isoformat()}
- **Total Electors Active in Database**: {total_db:,}
- **Expected Max Serial Space**: {total_expected:,}
- **Total Missing Serial Positions Identified**: {total_gaps:,}
- **Booths 100% Complete & Continuous**: {ok_booths} booths
- **Booths with Missing Serials (SHORT)**: {short_booths} booths
- **Reports Saved to**: `{out_dir}`
"""
with open(os.path.join(out_dir, 'summary.md'), 'w', encoding='utf-8') as f:
    f.write(summary_md)

print("\n" + summary_md)
print("\nTop 15 Booths with Largest Missing Gaps:")
top_short = df_results.sort_values('Gaps_Count', ascending=False).head(15)
print(top_short[['Part', 'Status', 'DB_Count', 'Max_Serial', 'Gaps_Count', 'Sample_Gaps']].to_string(index=False))
