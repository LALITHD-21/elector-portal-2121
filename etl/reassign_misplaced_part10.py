import os
import sys
import json
from supabase import create_client
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv('web/.env.local')

url = os.getenv('NEXT_PUBLIC_SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
sb = create_client(url, key)

with open('etl/stations_dump.json', 'r', encoding='utf-8') as f:
    stations = json.load(f)
p10_st = [s for s in stations if s.get('part_number') == '10'][0]

with open('etl/reports/part_10_extracted.json', 'r', encoding='utf-8') as f:
    p10 = json.load(f)

p10_epics = [r['epic_number'] for r in p10 if r.get('epic_number')]

# Find misplaced
misplaced_ids = []
for i in range(0, len(p10_epics), 1000):
    chunk = p10_epics[i:i+1000]
    res = sb.from_('electors').select('id, epic_number, part_number').in_('epic_number', chunk).execute()
    for row in (res.data or []):
        if str(row['part_number']) != '10':
            misplaced_ids.append(row['id'])

print(f"Total misplaced Part 10 electors to reassign: {len(misplaced_ids)}")

# Update in batches of 100
updated_count = 0
for i in range(0, len(misplaced_ids), 100):
    chunk_ids = misplaced_ids[i:i+100]
    res = sb.from_('electors').update({
        'part_number': '10',
        'polling_station_name': p10_st['name'],
        'polling_address': p10_st['address'],
        'district': 'Davanagere',
        'taluk': 'Davanagere',
        'ac_name': 'Davanagere South'
    }).in_('id', chunk_ids).execute()
    updated_count += len(res.data or [])

print(f"Successfully reassigned {updated_count} electors back to Part 10!")

# Verify Part 10 count now
res_p10 = sb.from_('electors').select('*', count='exact', head=True).eq('part_number', '10').execute()
print(f"Verified Part 10 total in DB now: {res_p10.count} (Official ERO target: 879)")
