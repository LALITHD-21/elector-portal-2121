const { createClient } = require('@supabase/supabase-js');
const fs = require('fs');

const envLines = fs.readFileSync('web/.env.local', 'utf-8').split('\n');
const env = {};
for (const line of envLines) {
  const trimmed = line.trim();
  if (trimmed && !trimmed.startsWith('#') && trimmed.includes('=')) {
    const idx = trimmed.indexOf('=');
    const k = trimmed.slice(0, idx).trim();
    let v = trimmed.slice(idx + 1).trim();
    if (v.startsWith('"') && v.endsWith('"')) v = v.slice(1, -1);
    env[k] = v;
  }
}

const supabase = createClient(env.NEXT_PUBLIC_SUPABASE_URL, env.SUPABASE_SERVICE_ROLE_KEY);

async function check() {
  const { data, error } = await supabase.from('gift_distributions').select('id').limit(1);
  if (error) {
    console.log('gift_distributions table status:', error.message);
  } else {
    console.log('gift_distributions table already exists!');
  }
}
check();
