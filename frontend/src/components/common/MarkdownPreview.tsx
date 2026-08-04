'use client';

import 'highlight.js/styles/github-dark.css';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize';
import { cn } from '@/lib/utils';

const schema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    code: [['className', /^(language-|hljs)/]],
    span: [...(defaultSchema.attributes?.span ?? []), 'className'],
  },
};

export function MarkdownPreview({ content, className }: { content: string; className?: string }) {
  return (
    <div
      className={cn(
        'prose prose-sm dark:prose-invert max-w-none',
        'prose-headings:font-semibold prose-headings:text-foreground',
        'prose-p:text-foreground/90 prose-li:text-foreground/90',
        'prose-a:text-teal-400 prose-strong:text-foreground',
        'prose-code:before:content-none prose-code:after:content-none',
        'prose-pre:border prose-pre:border-white/[0.06]',
        'prose-table:border prose-table:border-white/[0.08]',
        'prose-thead:border-b prose-thead:border-white/[0.12] prose-th:bg-white/[0.03] prose-th:px-3 prose-th:py-2 prose-th:align-bottom',
        'prose-td:border-b prose-td:border-white/[0.06] prose-td:px-3 prose-td:py-2 prose-td:align-top',
        className,
      )}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight, [rehypeSanitize, schema]]}
        components={{
          table: ({ children }) => (
            <div className="overflow-x-auto">
              <table>{children}</table>
            </div>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
