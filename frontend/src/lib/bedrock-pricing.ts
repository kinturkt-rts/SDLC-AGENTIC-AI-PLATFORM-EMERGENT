/** Estimated Bedrock on-demand USD per 1M tokens (Anthropic Claude via Bedrock). */

export interface ModelPricing {
  inputPerMillion: number;
  outputPerMillion: number;
  cacheReadPerMillion: number;
  cacheWritePerMillion: number;
}

const SONNET: ModelPricing = {
  inputPerMillion: 3,
  outputPerMillion: 15,
  cacheReadPerMillion: 0.3,
  cacheWritePerMillion: 3.75,
};

const OPUS: ModelPricing = {
  inputPerMillion: 15,
  outputPerMillion: 75,
  cacheReadPerMillion: 1.5,
  cacheWritePerMillion: 18.75,
};

const HAIKU: ModelPricing = {
  inputPerMillion: 0.8,
  outputPerMillion: 4,
  cacheReadPerMillion: 0.08,
  cacheWritePerMillion: 1,
};

const DEFAULT_PRICING = SONNET;

export function shortModelLabel(modelId: string): string {
  const mid = (modelId || '').toLowerCase();
  let family = 'unknown';
  if (mid.includes('opus')) family = 'opus';
  else if (mid.includes('sonnet')) family = 'sonnet';
  else if (mid.includes('haiku')) family = 'haiku';
  else return modelId.split('.').pop()?.slice(0, 24) || 'unknown';

  const verMatch = mid.match(/claude-(?:[\w-]+-)?(\d+-\d+)/) ?? mid.match(/(\d+-\d+)/);
  const ver = verMatch?.[1];
  return ver ? `${family}-${ver}` : family;
}

export function resolveModelPricing(modelId?: string, modelLabel?: string): ModelPricing {
  const label = (modelLabel || shortModelLabel(modelId ?? '')).toLowerCase();
  if (label.includes('opus')) return OPUS;
  if (label.includes('haiku')) return HAIKU;
  if (label.includes('sonnet')) return SONNET;
  return DEFAULT_PRICING;
}

export function estimateBedrockCostUsd(input: {
  inputTokens: number;
  outputTokens: number;
  cacheReadInputTokens?: number;
  cacheWriteInputTokens?: number;
  modelId?: string;
  modelLabel?: string;
}): number {
  const pricing = resolveModelPricing(input.modelId, input.modelLabel);
  const cacheRead = input.cacheReadInputTokens ?? 0;
  const cacheWrite = input.cacheWriteInputTokens ?? 0;
  const cost =
    (input.inputTokens * pricing.inputPerMillion +
      input.outputTokens * pricing.outputPerMillion +
      cacheRead * pricing.cacheReadPerMillion +
      cacheWrite * pricing.cacheWritePerMillion) /
    1_000_000;
  return Math.round(cost * 10000) / 10000;
}
