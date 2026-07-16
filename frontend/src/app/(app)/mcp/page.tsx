'use client';

import * as React from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Plug, Plus, Pencil, Trash2, Terminal, KeyRound, Settings2 } from 'lucide-react';
import { toast } from 'sonner';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { PageHeader } from '@/src/components/common/PageHeader';
import { EmptyState } from '@/src/components/common/EmptyState';
import { api } from '@/src/lib/api';
import { formatEnvVarDisplay, formatMcpCommand } from '@/src/lib/mcp-display';
import { useMcpConfig, queryKeys } from '@/src/lib/queries';
import type { McpServerConfig } from '@/src/types';

interface FormState {
  name: string;
  command: string;
  args: string;
  env: string;
  envFile: string;
  timeout: string;
  type: string;
  url: string;
  disabled: boolean;
}

const EMPTY_FORM: FormState = {
  name: '',
  command: '',
  args: '',
  env: '',
  envFile: '',
  timeout: '',
  type: 'stdio',
  url: '',
  disabled: false,
};

function configToForm(name: string, cfg: McpServerConfig): FormState {
  return {
    name,
    command: cfg.command ?? '',
    args: (cfg.args ?? []).join('\n'),
    env: Object.entries(cfg.env ?? {})
      .map(([k, v]) => `${k}=${v}`)
      .join('\n'),
    envFile: cfg.envFile ?? '',
    timeout: cfg.timeout != null ? String(cfg.timeout) : '',
    type: cfg.type ?? 'stdio',
    url: cfg.url ?? '',
    disabled: cfg.disabled ?? false,
  };
}

function formToConfig(form: FormState): McpServerConfig {
  const args = form.args.split('\n').map((s) => s.trim()).filter(Boolean);
  const env: Record<string, string> = {};
  form.env.split('\n').map((s) => s.trim()).filter(Boolean).forEach((line) => {
    const idx = line.indexOf('=');
    if (idx > 0) env[line.slice(0, idx).trim()] = line.slice(idx + 1).trim();
  });
  const cfg: McpServerConfig = { disabled: form.disabled };
  if (form.command.trim()) cfg.command = form.command.trim();
  if (args.length) cfg.args = args;
  if (Object.keys(env).length) cfg.env = env;
  if (form.envFile.trim()) cfg.envFile = form.envFile.trim();
  if (form.timeout.trim()) cfg.timeout = Number(form.timeout.trim());
  if (form.type.trim()) cfg.type = form.type.trim();
  if (form.url.trim()) cfg.url = form.url.trim();
  return cfg;
}

export default function McpPage() {
  const { data: config, isLoading } = useMcpConfig();
  const qc = useQueryClient();

  const [dialogOpen, setDialogOpen] = React.useState(false);
  const [editingName, setEditingName] = React.useState<string | null>(null);
  const [form, setForm] = React.useState<FormState>(EMPTY_FORM);
  const [deleteTarget, setDeleteTarget] = React.useState<string | null>(null);

  const servers = Object.entries(config?.mcpServers ?? {});

  const saveMutation = useMutation({
    mutationFn: ({ name, cfg }: { name: string; cfg: McpServerConfig }) => api.saveMcpServer(name, cfg),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.mcpConfig });
      setDialogOpen(false);
    },
    onError: (e: Error) => toast.error('Could not save server', { description: e.message }),
  });

  const deleteMutation = useMutation({
    mutationFn: (name: string) => api.deleteMcpServer(name),
    onSuccess: (_d, name) => {
      qc.invalidateQueries({ queryKey: queryKeys.mcpConfig });
      toast.success(`Removed ${name}`);
      setDeleteTarget(null);
    },
    onError: (e: Error) => toast.error('Could not delete server', { description: e.message }),
  });

  const openAdd = () => {
    setEditingName(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  };
  const openEdit = (name: string, cfg: McpServerConfig) => {
    setEditingName(name);
    setForm(configToForm(name, cfg));
    setDialogOpen(true);
  };

  const submit = () => {
    if (!form.name.trim()) {
      toast.error('Server name is required');
      return;
    }
    saveMutation.mutate(
      { name: form.name.trim(), cfg: formToConfig(form) },
      { onSuccess: () => toast.success(editingName ? `Updated ${form.name}` : `Added ${form.name}`) },
    );
  };

  const toggleDisabled = (name: string, enabled: boolean) => {
    // Disabled-only patch — server merges into stored entry (avoids re-posting full config).
    saveMutation.mutate(
      { name, cfg: { disabled: !enabled } },
      { onSuccess: () => toast.success(`${name} ${enabled ? 'enabled' : 'disabled'}`) },
    );
  };

  const set = (k: keyof FormState, v: string | boolean) => setForm((f) => ({ ...f, [k]: v }));

  return (
    <>
      <PageHeader
        eyebrow="Integrations"
        title="MCP Registry"
        description="Integration servers that expose tools to SDLC pipeline agents."
        actions={
          <Button className="gap-1.5 bg-teal-600 text-white hover:bg-teal-700" onClick={openAdd}>
            <Plus className="h-4 w-4" /> Add MCP Server
          </Button>
        }
      />

      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-48 w-full rounded-xl" />)}
        </div>
      ) : servers.length === 0 ? (
        <EmptyState icon={Plug} title="No MCP servers" description="Add a server to expose tools to agents." action={<Button onClick={openAdd} className="gap-1.5 bg-teal-600 text-white hover:bg-teal-700"><Plus className="h-4 w-4" /> Add MCP Server</Button>} />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {servers.map(([name, cfg]) => {
            const enabled = !cfg.disabled;
            return (
              <Card key={name} className="flex flex-col border-white/[0.06] bg-card/80 p-4 transition-all duration-300 hover:border-white/[0.12] hover:bg-card">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2.5">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-teal-500/10 text-teal-400 ring-1 ring-inset ring-teal-500/20">
                      <Plug className="h-4 w-4" />
                    </div>
                    <div className="min-w-0">
                      <p className="font-semibold text-foreground">{name}</p>
                    </div>
                  </div>
                  <Switch checked={enabled} onCheckedChange={(c) => toggleDisabled(name, c)} />
                </div>

                <div className="mt-3 space-y-2 text-xs">
                  <p className="flex items-start gap-1.5 text-muted-foreground">
                    <Terminal className="mt-0.5 h-3 w-3 shrink-0" />
                    <span className="break-all font-mono">{formatMcpCommand(cfg)}</span>
                  </p>
                  {cfg.env && Object.keys(cfg.env).length ? (
                    <div className="space-y-1.5">
                      <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                        Secrets &amp; config
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {Object.entries(cfg.env).map(([k, v]) => {
                          const display = formatEnvVarDisplay(k, v);
                          const Icon = display.kind === 'secret' ? KeyRound : Settings2;
                          return (
                            <span
                              key={k}
                              title={`${k}=${v}`}
                              className="inline-flex items-center gap-1 rounded-md border border-white/[0.06] bg-muted/40 px-2 py-1 text-[11px] text-foreground"
                            >
                              <Icon className="h-3 w-3 shrink-0 text-muted-foreground" />
                              <span className="font-medium">{display.label}</span>
                              <span className="text-muted-foreground">· {display.detail}</span>
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  ) : null}
                </div>

                <div className="mt-auto flex items-center justify-between border-t border-white/[0.06] pt-3">
                  <span className={`text-[11px] font-medium ${enabled ? 'text-emerald-400' : 'text-muted-foreground'}`}>
                    {enabled ? 'Enabled' : 'Disabled'}
                  </span>
                  <div className="flex gap-1.5">
                    <Button variant="ghost" size="sm" className="h-7 gap-1 px-2 text-xs" onClick={() => openEdit(name, cfg)}><Pencil className="h-3.5 w-3.5" /> Edit</Button>
                    <Button variant="ghost" size="sm" className="h-7 gap-1 px-2 text-xs text-red-400 hover:text-red-300" onClick={() => setDeleteTarget(name)}><Trash2 className="h-3.5 w-3.5" /> Delete</Button>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* Add / Edit dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-h-[85vh] max-w-lg overflow-y-auto border-white/[0.08] bg-card">
          <DialogHeader>
            <DialogTitle>{editingName ? `Edit ${editingName}` : 'Add MCP Server'}</DialogTitle>
            <DialogDescription>Configure how agents connect to this server. Reference secrets via ${'{'}env:NAME{'}'} - do not enter raw credentials.</DialogDescription>
          </DialogHeader>

          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="m-name">Server name</Label>
              <Input id="m-name" value={form.name} disabled={!!editingName} onChange={(e) => set('name', e.target.value)} placeholder="GitLab" className="border-white/[0.08] bg-white/[0.02]" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="m-command">command</Label>
              <Input id="m-command" value={form.command} onChange={(e) => set('command', e.target.value)} placeholder="npx" className="border-white/[0.08] bg-white/[0.02]" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="m-args">args (one per line)</Label>
              <Textarea id="m-args" rows={3} value={form.args} onChange={(e) => set('args', e.target.value)} placeholder={'-y\n@modelcontextprotocol/server-gitlab'} className="border-white/[0.08] bg-white/[0.02] font-mono text-xs" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="m-env">Environment variables</Label>
              <p className="text-[11px] text-muted-foreground">
                One per line. Reference secrets from <code className="rounded bg-muted/50 px-1">.env</code> with{' '}
                <code className="rounded bg-muted/50 px-1">${'{'}env:VAR_NAME{'}'}</code> - do not paste raw tokens.
              </p>
              <Textarea id="m-env" rows={3} value={form.env} onChange={(e) => set('env', e.target.value)} placeholder={'GITLAB_PERSONAL_ACCESS_TOKEN=${env:GITLAB_PERSONAL_ACCESS_TOKEN}'} className="border-white/[0.08] bg-white/[0.02] font-mono text-xs" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="m-envfile">envFile (optional)</Label>
                <Input id="m-envfile" value={form.envFile} onChange={(e) => set('envFile', e.target.value)} placeholder="${workspaceFolder}/.env" className="border-white/[0.08] bg-white/[0.02] font-mono text-xs" />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="m-timeout">timeout (optional)</Label>
                <Input id="m-timeout" value={form.timeout} onChange={(e) => set('timeout', e.target.value)} placeholder="60" inputMode="numeric" className="border-white/[0.08] bg-white/[0.02]" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="m-type">type (optional)</Label>
                <Input id="m-type" value={form.type} onChange={(e) => set('type', e.target.value)} placeholder="stdio" className="border-white/[0.08] bg-white/[0.02]" />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="m-url">url (remote, optional)</Label>
                <Input id="m-url" value={form.url} onChange={(e) => set('url', e.target.value)} placeholder="https://..." className="border-white/[0.08] bg-white/[0.02] font-mono text-xs" />
              </div>
            </div>
            <div className="flex items-center justify-between rounded-lg border border-white/[0.06] px-3 py-2">
              <Label htmlFor="m-disabled" className="cursor-pointer">Disabled</Label>
              <Switch id="m-disabled" checked={form.disabled} onCheckedChange={(c) => set('disabled', c)} />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" className="border-white/[0.08]" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button className="bg-teal-600 text-white hover:bg-teal-700" onClick={submit} disabled={saveMutation.isPending}>{saveMutation.isPending ? 'Saving\u2026' : editingName ? 'Save changes' : 'Add server'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirm */}
      <AlertDialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <AlertDialogContent className="border-white/[0.08] bg-card">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete &ldquo;{deleteTarget}&rdquo;?</AlertDialogTitle>
            <AlertDialogDescription>This permanently removes the server from the registry.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="border-white/[0.08]">Cancel</AlertDialogCancel>
            <AlertDialogAction className="bg-red-600 text-white hover:bg-red-700" onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget)}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
