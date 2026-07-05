'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { PanelLeftClose, PanelLeft } from 'lucide-react';
import { cn } from '@/lib/utils';
import { BrandMark } from '@/src/components/common/BrandMark';
import { navSections } from '@/src/lib/nav';
import { useUiStore } from '@/src/store/ui-store';

export function Sidebar() {
  const pathname = usePathname();
  const collapsed = useUiStore((s) => s.sidebarCollapsed);
  const toggle = useUiStore((s) => s.toggleSidebar);

  return (
    <aside
      className={cn(
        'sticky top-0 flex h-screen shrink-0 flex-col border-r border-sidebar-border bg-sidebar transition-[width] duration-200',
        collapsed ? 'w-[68px]' : 'w-60',
      )}
    >
      {/* ── Branding ──────────────────────────── */}
      <div className="flex h-14 items-center gap-2.5 border-b border-sidebar-border px-4">
        <BrandMark />
        {!collapsed && (
          <div className="min-w-0">
            <p className="text-[12px] font-bold leading-snug tracking-tight text-sidebar-foreground">
              SDLC Agentic AI Platform
            </p>
            <p className="truncate text-[10px] font-medium uppercase tracking-[0.12em] text-muted-foreground/60">
              Control Plane
            </p>
          </div>
        )}
      </div>

      {/* ── Navigation ────────────────────────── */}
      <nav className="flex-1 space-y-5 overflow-y-auto px-2.5 py-4">
        {navSections.map((section) => (
          <div key={section.title}>
            {!collapsed && (
              <p className="mb-1.5 px-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground/50">
                {section.title}
              </p>
            )}
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const active = pathname === item.href || pathname.startsWith(item.href + '/');
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    title={collapsed ? item.label : undefined}
                    className={cn(
                      'group flex items-center gap-3 rounded-lg px-2.5 py-2 text-[13px] font-medium transition-all duration-150',
                      active
                        ? 'bg-teal-500/10 text-teal-300 shadow-sm shadow-teal-500/5'
                        : 'text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground',
                      collapsed && 'justify-center px-2',
                    )}
                  >
                    <Icon className={cn(
                      'h-[18px] w-[18px] shrink-0 transition-colors',
                      active ? 'text-teal-400' : 'text-muted-foreground/60 group-hover:text-muted-foreground',
                    )} />
                    {!collapsed && <span className="truncate">{item.label}</span>}
                    {active && !collapsed && (
                      <span className="ml-auto h-1.5 w-1.5 rounded-full bg-teal-400 shadow-sm shadow-teal-400/50" />
                    )}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* ── Collapse Toggle ───────────────────── */}
      <button
        onClick={toggle}
        className="flex h-11 items-center gap-3 border-t border-sidebar-border px-4 text-[13px] text-muted-foreground/60 transition-colors hover:text-sidebar-foreground"
      >
        {collapsed ? <PanelLeft className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
        {!collapsed && <span>Collapse</span>}
      </button>
    </aside>
  );
}
