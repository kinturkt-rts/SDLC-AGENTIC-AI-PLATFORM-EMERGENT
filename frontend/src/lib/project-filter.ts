/** Routes where the topbar project filter is shown and list content is scoped by project. */
const PROJECT_SCOPED_ROUTES = ['/tokens', '/artifacts', '/context', '/runs', '/checkpoints', '/logs'] as const;

export function shouldShowProjectFilter(pathname: string | null): boolean {
  if (!pathname) return false;
  return PROJECT_SCOPED_ROUTES.some(
    (route) => pathname === route || pathname.startsWith(`${route}/`),
  );
}
