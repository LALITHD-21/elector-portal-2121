import pandas as pd
import re

p = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/etl/reports/phase4_dry_run_reconciliation/new_valid.csv'
df = pd.read_csv(p)

def clean_name(n):
    if not n or pd.isna(n): return ''
    n = re.sub(r'[\$#@!~%^*()_+=\[\]{};:\"\'\<\>?/\\|]+', '', str(n)).strip()
    n = re.sub(r'\s+', ' ', n)
    return n

df['name'] = df['name'].apply(clean_name)
df['relative_name'] = df['relative_name'].apply(clean_name)

df.to_csv(p, index=False)
print('Cleaned names in new_valid.csv. Sample:')
print(df[['serial_number', 'epic_number', 'name', 'relative_name', 'part_number']].head(10).to_string(index=False))
