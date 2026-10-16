import os
from supabase import create_client

def get_supabase():
    env = {}
    with open('web/.env.local', 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return create_client(env['NEXT_PUBLIC_SUPABASE_URL'], env['SUPABASE_SERVICE_ROLE_KEY'])

if __name__ == '__main__':
    sb = get_supabase()
    res = sb.table('electors').select('*').eq('epic_number', 'ZFB2474765').execute()
    print('Row for ZFB2474765:', res.data)
