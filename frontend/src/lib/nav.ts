import {
  LayoutDashboard,
  Workflow,
  UserCheck,
  FolderKanban,
  GitBranch,
  Bot,
  Network,
  FileBox,
  Database,
  Plug,
  ScrollText,
  Settings,
  Coins,
  Info,
  type LucideIcon,
} from 'lucide-react';

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
}

export interface NavSection {
  title: string;
  items: NavItem[];
}

export const navSections: NavSection[] = [
  {
    title: 'Operate',
    items: [
      { label: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
      { label: 'Pipeline Runs', href: '/runs', icon: Workflow },
      { label: 'HITL Approved Gates', href: '/checkpoints', icon: UserCheck },
    ],
  },
  {
    title: 'Design',
    items: [
      { label: 'Projects', href: '/projects', icon: FolderKanban },
      { label: 'Pipelines', href: '/pipelines', icon: GitBranch },
      { label: 'Agents', href: '/agents', icon: Bot },
      { label: 'Orchestrator', href: '/orchestrator', icon: Network },
    ],
  },
  {
    title: 'Assets',
    items: [
      { label: 'Artifacts', href: '/artifacts', icon: FileBox },
      { label: 'Context', href: '/context', icon: Database },
    ],
  },
  {
    title: 'Integrations',
    items: [{ label: 'MCP Registry', href: '/mcp', icon: Plug }],
  },
  {
    title: 'Observe',
    items: [
      { label: 'Token usage', href: '/tokens', icon: Coins },
      { label: 'Logs', href: '/logs', icon: ScrollText },
    ],
  },
  {
    title: 'Admin',
    items: [
      { label: 'Settings', href: '/settings', icon: Settings },
      { label: 'About', href: '/about', icon: Info },
    ],
  },
];
