const inflight = new Map<string, Promise<unknown>>();
const cache = new Map<string, { expiresAt: number; value: unknown }>();

/** TTL cache with in-flight deduplication for expensive server reads. */
export async function cachedAsync<T>(key: string, ttlMs: number, fn: () => Promise<T>): Promise<T> {
  const now = Date.now();
  const hit = cache.get(key);
  if (hit && hit.expiresAt > now) return hit.value as T;

  const pending = inflight.get(key);
  if (pending) return pending as Promise<T>;

  const promise = fn()
    .then((value) => {
      cache.set(key, { expiresAt: Date.now() + ttlMs, value });
      inflight.delete(key);
      return value;
    })
    .catch((err) => {
      inflight.delete(key);
      throw err;
    });

  inflight.set(key, promise);
  return promise;
}

export function invalidateCacheKey(key: string): void {
  cache.delete(key);
  inflight.delete(key);
}
