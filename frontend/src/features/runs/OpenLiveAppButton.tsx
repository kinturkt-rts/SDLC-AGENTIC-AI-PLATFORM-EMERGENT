'use client';

import { Rocket, ExternalLink } from 'lucide-react';

export function OpenLiveAppButton({ url }: { url: string }) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      data-testid="open-live-app-button"
      className="group flex items-center gap-3 rounded-xl border border-emerald-500/40 bg-emerald-500/[0.08] px-5 py-4 transition-all hover:border-emerald-400/60 hover:bg-emerald-500/[0.14] hover:shadow-[0_0_28px_-6px_rgba(16,185,129,0.55)]"
    >
      <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-emerald-500 text-white transition-transform group-hover:scale-105">
        <Rocket className="h-5 w-5" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-base font-semibold text-emerald-300">Open Live App</span>
        <span className="block truncate text-xs text-emerald-400/70">{url}</span>
      </span>
      <ExternalLink className="h-5 w-5 shrink-0 text-emerald-400 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
    </a>
  );
}
