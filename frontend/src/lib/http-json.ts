/** UTF-8 safe base64 for brief uploads (avoids WAF false positives on SQL/auth text). */
export function encodeUtf8Base64(text: string): string {
  const bytes = new TextEncoder().encode(text);
  let binary = '';
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary);
}

function friendlyNonJsonError(status: number, raw: string): string {
  const snippet = raw.replace(/\s+/g, ' ').trim().slice(0, 160);
  if (status === 403 && /cloudfront|could not be satisfied|request blocked/i.test(raw)) {
    return (
      'Upload blocked by CloudFront/WAF security rules. Briefs with SQL, auth, or password ' +
      'examples can trigger false positives. Retry now (base64 upload), or ask ops to allow ' +
      '/api/v1/inputs through WAF.'
    );
  }
  if (status === 413) {
    return 'Brief is too large (max 256 KB). Shorten the text and retry.';
  }
  if (status === 502 || status === 503 || status === 504) {
    return `Platform temporarily unavailable (HTTP ${status}). Wait a moment and retry.`;
  }
  if (status >= 500) {
    return `Server error (HTTP ${status}). Check platform logs or retry shortly.`;
  }
  if (snippet) {
    return `Unexpected response (HTTP ${status}): ${snippet}`;
  }
  return `Unexpected response (HTTP ${status}). The server returned HTML instead of JSON.`;
}

export async function readJsonResponse<T = Record<string, unknown>>(
  res: Response,
): Promise<{ ok: true; data: T } | { ok: false; error: string }> {
  const contentType = res.headers.get('content-type') ?? '';
  const raw = await res.text();

  if (contentType.includes('application/json') || raw.trim().startsWith('{') || raw.trim().startsWith('[')) {
    try {
      const data = JSON.parse(raw) as T;
      if (!res.ok) {
        const message =
          typeof (data as { error?: unknown }).error === 'string'
            ? (data as { error: string }).error
            : `Request failed (HTTP ${res.status})`;
        return { ok: false, error: message };
      }
      return { ok: true, data };
    } catch {
      // fall through to HTML/plain handling
    }
  }

  return { ok: false, error: friendlyNonJsonError(res.status, raw) };
}
