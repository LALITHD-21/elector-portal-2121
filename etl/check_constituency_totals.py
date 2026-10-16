import os
import sys
from supabase import create_client
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv('web/.env.local')

sb = create_client(os.getenv('NEXT_PUBLIC_SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_ROLE_KEY'))

res_total = sb.from_('electors').select('*', count='exact', head=True).execute()
print(f"==================================================")
print(f"TOTAL ELECTORS IN DATABASE RIGHT NOW: {res_total.count}")
print(f"==================================================")

res_booths = sb.rpc('get_booths_summary').execute()
booths = res_booths.data or []
print(f"Total booths reported by get_booths_summary: {len(booths)}")

# Aggregate by part_number
counts_by_part = {}
names_by_part = {}
for b in booths:
    p = str(b.get('part_number'))
    counts_by_part[p] = counts_by_part.get(p, 0) + b.get('total_electors', 0)
    names_by_part[p] = b.get('polling_station_name') or ''

print("\nKey Polling Stations and Verified Elector Counts:")
key_parts = ['1', '4', '10', '13', '28', '32', '36', '72', '109', '112', '118', '124', '150', '151']
for p in key_parts:
    print(f"  Part {p:>3}: {counts_by_part.get(p, 0):>5} voters | {names_by_part.get(p, '')[:50]}")
