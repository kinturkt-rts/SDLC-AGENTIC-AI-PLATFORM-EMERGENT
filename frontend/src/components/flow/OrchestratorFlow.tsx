'use client';

import '@xyflow/react/dist/style.css';
import * as React from 'react';
import { ReactFlow, Background, Controls, type Node, type Edge } from '@xyflow/react';
import { useTheme } from 'next-themes';
import { Skeleton } from '@/components/ui/skeleton';
import { orchestratorNodeTypes } from './nodes';
import type { Agent } from '@/src/types';

function buildGraph(orchestrator: Agent | undefined, specialists: Agent[]): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];
  const edges: Edge[] = [];
  const cx = 0;
  const cy = 0;
  const radius = 280;

  nodes.push({
    id: 'orchestrator',
    type: 'orchestrator',
    position: { x: cx - 90, y: cy - 24 },
    data: { label: orchestrator?.displayName ?? 'Orchestrator', sub: orchestrator?.name ?? 'orchestrator-agent' },
  });

  const n = specialists.length;
  specialists.forEach((a, i) => {
    const angle = (i / n) * 2 * Math.PI - Math.PI / 2;
    const x = cx + radius * Math.cos(angle) - 75;
    const y = cy + radius * 0.75 * Math.sin(angle) - 20;
    nodes.push({
      id: a.id,
      type: 'agent',
      position: { x, y },
      data: { label: a.displayName, sub: a.name, status: a.availability },
    });
    edges.push({
      id: `orchestrator-${a.id}`,
      source: 'orchestrator',
      target: a.id,
      type: 'straight',
      animated: a.availability === 'online',
      style: { stroke: a.availability === 'offline' ? 'rgb(239 68 68)' : 'rgb(20 184 166)', strokeWidth: 1.5, opacity: 0.55 },
    });
  });

  return { nodes, edges };
}

export function OrchestratorFlow({
  orchestrator,
  specialists,
}: {
  orchestrator: Agent | undefined;
  specialists: Agent[];
}) {
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => setMounted(true), []);

  const { nodes, edges } = React.useMemo(
    () => buildGraph(orchestrator, specialists),
    [orchestrator, specialists],
  );

  if (!mounted) return <Skeleton className="h-[520px] w-full rounded-lg" />;

  return (
    <div className="h-[520px] w-full overflow-hidden rounded-lg border border-border bg-card">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={orchestratorNodeTypes}
        colorMode={resolvedTheme === 'light' ? 'light' : 'dark'}
        fitView
        fitViewOptions={{ padding: 0.25 }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        edgesFocusable={false}
        zoomOnScroll
        panOnDrag
        minZoom={0.3}
        maxZoom={1.5}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={16} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
