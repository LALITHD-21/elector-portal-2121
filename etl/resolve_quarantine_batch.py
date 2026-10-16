import pandas as pd
import re

p = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/etl/reports/phase4_dry_run_reconciliation/quarantine_review.xlsx'
df = pd.read_excel(p)
has_sugg = df[df['suggested_fix'].notna()].copy()

std_pattern = r'^[A-Z]{3}\d{7}$'

def resolve_ocr_epic(epic):
    if not epic or pd.isna(epic): return None
    s = str(epic).strip().upper()
    
    # Rule 1: NM0 -> NMO (letter O)
    if s.startswith('NM0'):
        s = 'NMO' + s[3:]
        
    # Rule 2: NMOD + 6 digits -> NMO0 + 6 digits
    if re.match(r'^NMOD\d{6}$', s):
        s = 'NMO0' + s[4:]
        
    # Rule 3: NMOO + 6 digits -> NMO0 + 6 digits
    if re.match(r'^NMOO\d{6}$', s):
        s = 'NMO0' + s[4:]
        
    # Rule 4: NMOO + 7 digits -> NMO + 7 digits
    if re.match(r'^NMOO\d{7}$', s):
        s = 'NMO' + s[4:]
        
    # Rule 5: 3 letters + 6 digits -> pad 0 to 7 digits
    if re.match(r'^[A-Z]{3}\d{6}$', s):
        s = s[:3] + '0' + s[3:]
        
    # Rule 6: 3 letters + 0 + 7 digits (8 digits) -> 3 letters + 7 digits
    if re.match(r'^[A-Z]{3}0\d{7}$', s):
        s = s[:3] + s[4:]
        
    # Rule 7: SGZ / 5GZ prefix
    if s.startswith('5GZ') or s.startswith('$GZ'):
        s = 'SGZ' + s[3:]
        
    if re.match(std_pattern, s):
        return s
    return None

resolved = []
for idx, r in has_sugg.iterrows():
    orig = r['epic_number']
    fixed = resolve_ocr_epic(orig)
    if fixed:
        d = r.to_dict()
        d['resolved_epic'] = fixed
        resolved.append(d)

df_resolved = pd.DataFrame(resolved)
print(f"Total evaluated from quarantine: {len(has_sugg)}")
print(f"Successfully and deterministically resolved to standard ^[A-Z]{{3}}\d{{7}}$: {len(df_resolved)}")
print("\nSample 20 resolved records:")
cols = ['serial_number', 'epic_number', 'resolved_epic', 'name', 'part_number', 'source_page_or_row']
print(df_resolved[cols].head(20).to_string(index=False))
