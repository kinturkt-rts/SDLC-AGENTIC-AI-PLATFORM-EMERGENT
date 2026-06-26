// Deterministic-ish relative timestamps anchored at module load.
export const now = Date.now();

export const minsAgo = (m: number): string =>
  new Date(now - m * 60_000).toISOString();

export const secsAgo = (s: number): string =>
  new Date(now - s * 1000).toISOString();

export const daysAgo = (d: number): string =>
  new Date(now - d * 86_400_000).toISOString();
