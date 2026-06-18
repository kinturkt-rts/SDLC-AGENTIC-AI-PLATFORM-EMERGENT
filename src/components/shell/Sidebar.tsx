'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Hexagon, PanelLeftClose, PanelLeft } from 'lucide-react';
import { cn } from '@/lib/utils';
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
      <div className="flex h-14 items-center gap-2.5 border-b border-sidebar-border px-4">
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-teal-500 text-white">
          <Hexagon className="h-4 w-4" />
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <p className="text-[13px] font-semibold leading-tight text-sidebar-foreground">SDLC Agentic AI Platform</p>
            <p className="truncate text-[10px] uppercase tracking-wider text-muted-foreground">Control Plane</p>
          </div>
        )}
      </div>

      <nav className="flex-1 space-y-4 overflow-y-auto px-2 py-4">
        {navSections.map((section) => (
          <div key={section.title}>
            {!collapsed && (
              <p className="px-2 pb-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/70">
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
                      'flex items-center gap-3 rounded-md px-2 py-2 text-sm font-medium transition-colors',
                      active
                        ? 'bg-teal-500/10 text-teal-700 dark:text-teal-300'
                        : 'text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground',
                      collapsed && 'justify-center',
                    )}
                  >
                    <Icon className={cn('h-4 w-4 shrink-0', active && 'text-teal-600 dark:text-teal-400')} />
                    {!collapsed && <span className="truncate">{item.label}</span>}
                    {active && !collapsed && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-teal-500" />}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <button
        onClick={toggle}
        className="flex h-11 items-center gap-3 border-t border-sidebar-border px-4 text-sm text-muted-foreground hover:text-sidebar-foreground"
      >
        {collapsed ? <PanelLeft className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
        {!collapsed && <span>Collapse</span>}
      </button>
    </aside>
  );
}
