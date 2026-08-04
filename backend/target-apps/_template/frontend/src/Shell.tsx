// Fixed app-shell layout — NOT LLM-generated. Screens are supplied via
// `children` (the LLM's <Routes> tree); nav items are data, not markup.
//
// Navigation stays on a parent-passed `onNavigate` callback (never <Link>/
// useNavigate() called directly in a leaf nav row) so the frontend-agent's
// wired-callbacks gate keeps a real prop to check, even though real
// react-router-dom routing (via App.tsx's <Routes>) still drives the URL.
// App.tsx wires this up as: `<Shell onNavigate={navigate} ...>` (navigate
// from useNavigate() — its (to: string) => void signature matches directly,
// no wrapper needed).
import type { ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { useTheme } from "next-themes";
import { LogOut, Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface ShellNavItem {
  label: string;
  to: string;
  icon?: ReactNode;
}

export interface ShellProps {
  brandName: string;
  navItems: ShellNavItem[];
  onNavigate: (to: string) => void;
  onLogout: () => void;
  children: ReactNode;
}

export function Shell({ brandName, navItems, onNavigate, onLogout, children }: ShellProps) {
  const location = useLocation();
  const { resolvedTheme, setTheme } = useTheme();
  const isDark = resolvedTheme !== "light";

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <aside className="flex w-60 shrink-0 flex-col gap-8 border-r border-border bg-card p-8">
        <div className="flex items-start justify-between gap-2 pr-1">
          <div className="min-w-0 flex-1 text-lg font-bold leading-tight">{brandName}</div>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Toggle theme"
            className="shrink-0"
            onClick={() => setTheme(isDark ? "light" : "dark")}
          >
            {isDark ? <Sun className="size-4" /> : <Moon className="size-4" />}
          </Button>
        </div>
        <nav className="flex flex-col gap-1">
          {navItems.map((item) => {
            const isActive = location.pathname === item.to;
            return (
              <button
                key={item.to}
                type="button"
                onClick={() => onNavigate(item.to)}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3.5 py-2.5 text-left text-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                )}
              >
                {item.icon}
                {item.label}
              </button>
            );
          })}
        </nav>
        <Button variant="default" className="mt-auto w-full gap-2" onClick={onLogout}>
          <LogOut className="size-4" />
          Log out
        </Button>
      </aside>
      <main className="min-w-0 flex-1 p-8">{children}</main>
    </div>
  );
}
