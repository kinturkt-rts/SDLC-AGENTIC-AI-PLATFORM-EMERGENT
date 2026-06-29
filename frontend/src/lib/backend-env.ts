import { readFileSync, existsSync } from 'fs';
import path from 'path';
import { getBackendRoot, getMonorepoRoot } from './repo-root';

let loaded = false;

function parseEnvFile(filePath: string, overwrite: boolean): void {
  if (!existsSync(filePath)) return;
  const text = readFileSync(filePath, 'utf-8');
  for (const line of text.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eq = trimmed.indexOf('=');
    if (eq < 1) continue;
    const key = trimmed.slice(0, eq).trim();
    let value = trimmed.slice(eq + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    if (!value) continue;
    if (overwrite || process.env[key] === undefined) {
      process.env[key] = value;
    }
  }
}

/** Load monorepo + backend .env files into process.env (server-side API routes only). */
export function loadBackendEnv(): void {
  if (loaded) return;
  const roots = [getMonorepoRoot(), getBackendRoot()];
  for (const root of roots) {
    parseEnvFile(path.join(root, '.env'), false);
  }
  for (const root of roots) {
    parseEnvFile(path.join(root, '.env.local'), true);
  }
  loaded = true;
}
