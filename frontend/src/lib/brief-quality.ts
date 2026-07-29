/** Minimum substance for a product brief before starting the pipeline.
 * Shortest real backend/inputs/*.txt briefs are ~600+ chars / 100+ words. */
const MIN_CHARS = 100;
const MIN_WORDS = 15;

/**
 * Returns an error message when the brief is empty, too short, or look like mash;
 * otherwise null (ok to submit).
 */
export function validateProductBrief(content: string): string | null {
  const text = content.trim();
  if (!text) return 'content is empty';

  const words = text.split(/\s+/).filter(Boolean);
  if (text.length < MIN_CHARS || words.length < MIN_WORDS) {
    return (
      'Brief looks too short or incomplete. Paste a real product brief ' +
      '(who it is for, what it does, key features) - roughly 15+ words.'
    );
  }

  const letters = (text.match(/[a-zA-Z]/g) ?? []).length;
  const nonSpace = text.replace(/\s/g, '').length;
  if (nonSpace > 0 && letters / nonSpace < 0.4) {
    return 'Brief must be readable text (letters), not symbols or noise.';
  }

  return null;
}
