import pandas as pd
import re

p = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/etl/reports/phase4_dry_run_reconciliation/quarantine_review.xlsx'
df = pd.read_excel(p)
print(f"Total quarantined rows: {len(df)}")
print("\nBreakdown of reasons:")
print(df['quarantine_reason'].value_counts().head(10))

has_sugg = df[df['suggested_fix'].notna()].copy()
print(f"\nRows with suggested fix: {len(has_sugg)}")

std_pattern = r'^[A-Z]{3}\d{7}$'
valid_suggs = has_sugg[has_sugg['suggested_fix'].str.match(std_pattern, na=False)].copy()
print(f"Suggested fixes matching standard format: {len(valid_suggs)}")
print("\nSample 15 valid suggested fixes:")
print(valid_suggs[['serial_number', 'epic_number', 'suggested_fix', 'name', 'part_number']].head(15).to_string(index=False))
