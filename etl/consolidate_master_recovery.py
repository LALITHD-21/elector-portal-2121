import os
import sys
import re
import json
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')
sys.path.append('.')
sys.path.append('etl')

# 1. Load Excel recovery (268 voters)
p_excel = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/etl/reports/all_booths_recovery_set/new_valid_missing_voters.csv'
df_excel = pd.read_csv(p_excel, dtype=str)
print(f"1. Excel recovery set: {len(df_excel)} voters")

# 2. Load Quarantine recovery (39 voters)
p_quar = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/etl/reports/phase4_dry_run_reconciliation/quarantine_recovered_new_valid.csv'
if os.path.exists(p_quar):
    df_quar = pd.read_csv(p_quar, dtype=str)
else:
    try:
        from etl.resolve_quarantine_batch import df_resolved
    except Exception:
        from resolve_quarantine_batch import df_resolved
    p_already = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/etl/reports/all_booths_recovery_set/already_in_db.csv'
    db_epics = set(pd.read_csv(p_already)['epic_number'].tolist()) if os.path.exists(p_already) else set()
    df_quar = df_resolved[~df_resolved['resolved_epic'].str.upper().isin(db_epics)].copy()
    df_quar['epic_number'] = df_quar['resolved_epic']
print(f"2. Quarantine recovery set: {len(df_quar)} voters")

# 3. Load Part 140 PDF recovery (61 voters)
p_p140 = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/etl/reports/batch_140_20261016_123941/new_voters.csv'
df_p140 = pd.read_csv(p_p140, dtype=str) if os.path.exists(p_p140) else pd.DataFrame()
print(f"3. Part 140 PDF recovery set: {len(df_p140)} voters")

# Combine all sets
combined = pd.concat([df_excel, df_quar, df_p140], ignore_index=True)
print(f"\nTotal combined candidates: {len(combined)}")

# Clean and validate
std_pattern = r'^[A-Z]{3}\d{7}$'
clean_rows = []
seen_epics = set()

address_tokens = [r'\(TQ\)', r'\(DIST\)', r'\(POST\)', r'\(VTC\)', r'\bROAD\b', r'\bCROSS\b', r'\bEXTENSION\b', r'\bLAYOUT\b', r'\bCOLONY\b', r'\bSTREET\b']

for _, r in combined.iterrows():
    epic = str(r.get('epic_number') or '').strip().upper()
    name = str(r.get('name') or '').strip()
    
    if not re.match(std_pattern, epic): continue
    if not name or len(name) < 3 or name.lower() in ['none', 'null', 'nan']: continue
    if any(re.search(tok, name.upper()) for tok in address_tokens): continue
    if epic in seen_epics: continue
    
    seen_epics.add(epic)
    clean_rows.append(r.to_dict())

df_master = pd.DataFrame(clean_rows)
print(f"Unique, pristine, verified missing voters ready for insert: {len(df_master)}")

# Add batch provenance
batch_id = 'batch_master_recovery_20261016'
df_master['import_batch_id'] = batch_id
df_master['imported_at'] = pd.Timestamp.now().isoformat()

out_dir = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/etl/reports/master_recovery_final'
os.makedirs(out_dir, exist_ok=True)

df_master.to_csv(os.path.join(out_dir, 'new_valid_master.csv'), index=False)
df_master.to_excel(os.path.join(out_dir, 'new_valid_master.xlsx'), index=False)

rollback_sql = f'''-- TRANSACTIONAL ROLLBACK SCRIPT FOR BATCH {batch_id}
BEGIN;
DELETE FROM electors WHERE import_batch_id = '{batch_id}';
COMMIT;
'''
with open(os.path.join(out_dir, 'rollback.sql'), 'w', encoding='utf-8') as f:
    f.write(rollback_sql)

print("\nBreakdown by Booth/Part Number (Top 20):")
print(df_master['part_number'].value_counts().head(20))
