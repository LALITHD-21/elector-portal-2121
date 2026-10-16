import pandas as pd
import re

p = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/etl/reports/all_booths_extracted/all_excel_electors.csv'
df = pd.read_csv(p)

print(f"Total rows extracted: {len(df):,}")
print("Columns:", df.columns.tolist())

has_epic = df['epic_number'].notna() & (df['epic_number'] != '')
print(f"Rows with EPIC: {has_epic.sum():,} ({has_epic.mean()*100:.1f}%)")
print(f"Rows without EPIC: {(~has_epic).sum():,}")

std_pattern = r'^[A-Z]{3}\d{7}$'
matches_std = df['epic_number'].apply(lambda x: bool(re.match(std_pattern, str(x))) if pd.notna(x) else False)
print(f"Rows with exact standard EPIC: {matches_std.sum():,}")

unique_std = df[matches_std].drop_duplicates(subset=['epic_number']).copy()
print(f"Unique standard EPICs extracted: {len(unique_std):,}")
print("\nSample 10 rows:")
print(unique_std[['part_number', 'serial_number', 'epic_number', 'name', 'relative_name', 'age', 'sex']].head(10).to_string(index=False))
