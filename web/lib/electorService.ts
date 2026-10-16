import { Elector } from '@/lib/types';
import { normalizeEpic, isValidEpic } from '@/lib/utils';

// In-memory cache for ultra-fast (0ms) repeated lookups
const electorCache = new Map<string, Elector | null>();

/**
 * Prime or update the in-memory cache with an elector record.
 */
export function primeElectorCache(epic: string, elector: Elector | null) {
  const normalized = normalizeEpic(epic);
  if (normalized) {
    electorCache.set(normalized, elector);
  }
}

/**
 * Check if an EPIC is already present in cache.
 */
export function isEpicCached(epic: string): boolean {
  const normalized = normalizeEpic(epic);
  return electorCache.has(normalized);
}

/**
 * Prefetch an elector record in the background to guarantee 0ms instant search response.
 */
export function prefetchElectorByEpic(rawEpic: string) {
  const epic = normalizeEpic(rawEpic);
  if (epic && isValidEpic(epic) && !electorCache.has(epic)) {
    getElectorByEpic(epic).catch(() => {});
  }
}

/**
 * Get an elector by EPIC card number with in-memory caching and server API lookup.
 * Returns { elector, error, fromCache, durationMs }
 */
export async function getElectorByEpic(rawEpic: string): Promise<{
  elector: Elector | null;
  error: string | null;
  fromCache: boolean;
  durationMs: number;
}> {
  const startTime = performance.now();
  const epic = normalizeEpic(rawEpic);

  if (!epic || !isValidEpic(epic)) {
    return {
      elector: null,
      error: 'Invalid EPIC format. Expected voter ID format (e.g. TYA0633792 or WWS579886).',
      fromCache: false,
      durationMs: 0,
    };
  }

  // 1. Return from in-memory cache if available (0ms instant)
  if (electorCache.has(epic)) {
    const cached = electorCache.get(epic) ?? null;
    return {
      elector: cached,
      error: null,
      fromCache: true,
      durationMs: Math.round(performance.now() - startTime),
    };
  }

  // 2. Query server API route
  try {
    const res = await fetch(`/api/elector/${encodeURIComponent(epic)}`);
    
    if (res.ok) {
      const data = await res.json();
      const electorRecord = (data as Elector) || null;
      electorCache.set(epic, electorRecord);

      return {
        elector: electorRecord,
        error: null,
        fromCache: false,
        durationMs: Math.round(performance.now() - startTime),
      };
    }

    if (res.status === 404) {
      electorCache.set(epic, null);
      return {
        elector: null,
        error: null,
        fromCache: false,
        durationMs: Math.round(performance.now() - startTime),
      };
    }

    // Try to parse server error payload for exact cause
    const errorBody = await res.json().catch(() => null);
    const serverMessage = errorBody?.error || 'Error retrieving elector profile.';

    return {
      elector: null,
      error: serverMessage,
      fromCache: false,
      durationMs: Math.round(performance.now() - startTime),
    };
  } catch (err: any) {
    console.error('Unexpected lookup error:', err);
    return {
      elector: null,
      error: err?.message || 'Network connection error.',
      fromCache: false,
      durationMs: Math.round(performance.now() - startTime),
    };
  }
}

/**
 * Permanently update an elector record in Supabase and refresh in-memory cache.
 */
export async function updateElectorRecord(
  rawEpic: string,
  updatedFields: Partial<Elector>
): Promise<{ elector: Elector | null; error: string | null }> {
  const epic = normalizeEpic(rawEpic);

  if (!epic) {
    return { elector: null, error: 'Invalid EPIC number' };
  }

  try {
    const res = await fetch(`/api/elector/${encodeURIComponent(epic)}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(updatedFields),
    });

    if (!res.ok) {
      const errorBody = await res.json().catch(() => null);
      return {
        elector: null,
        error: errorBody?.error || 'Failed to update elector record.',
      };
    }

    const updatedElector = (await res.json()) as Elector;
    
    // Update cache with updated record
    primeElectorCache(epic, updatedElector);

    return { elector: updatedElector, error: null };
  } catch (err: any) {
    console.error('Error updating elector:', err);
    return {
      elector: null,
      error: err?.message || 'Network error updating elector record.',
    };
  }
}

