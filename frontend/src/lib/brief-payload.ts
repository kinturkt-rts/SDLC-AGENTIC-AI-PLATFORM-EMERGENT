interface BriefBody {
  feature?: unknown;
  targetApp?: unknown;
  content?: unknown;
  contentBase64?: unknown;
  runId?: unknown;
}

export function decodeBriefContent(body: BriefBody): string {
  if (typeof body.content === 'string' && body.content.trim()) {
    return body.content;
  }
  if (typeof body.contentBase64 === 'string' && body.contentBase64.trim()) {
    try {
      return Buffer.from(body.contentBase64.trim(), 'base64').toString('utf-8');
    } catch {
      throw new Error('contentBase64 is not valid base64');
    }
  }
  return '';
}
