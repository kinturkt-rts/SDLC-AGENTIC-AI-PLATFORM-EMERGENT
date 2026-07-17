'use client';

import '@xyflow/react/dist/style.css';
import * as React from 'react';
import { ReactFlow, Background, Controls, type Node, type Edge } from '@xyflow/react';
import { useTheme } from 'next-themes';
import { Skeleton } from '@/components/ui/skeleton';
import { pipelineNodeTypes } from './nodes';
import type { PipelineDefinition } from '@/src/types';

function buildGraph(pipeline: PipelineDefinition): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];
  const edges: Edge[] = [];
  let x = 0;
  let prevId: string | null = null;

  pipeline.phases.forEach((ph, i) => {
    const phaseId = `phase-${i}`;
    nodes.push({
      id: phaseId,
      type: 'phase',
      position: { x, y: 40 },
      data: { phase: ph.phase, agent: ph.agent, index: i },
    });
    if (prevId) edges.push({ id: `${prevId}-${phaseId}`, source: prevId, target: phaseId, type: 'smoothstep', animated: false });
    prevId = phaseId;
    x += 230;

    if (ph.hitl) {
      const gateId = `gate-${i}`;
      nodes.push({ id: gateId, type: 'gate', position: { x, y: 52 }, data: { phase: ph.phase } });
      edges.push({ id: `${phaseId}-${gateId}`, source: phaseId, target: gateId, type: 'smoothstep', style: { stroke: 'rgb(245 158 11)' } });
      prevId = gateId;
      x += 200;
    }
  });

  return { nodes, edges };
}

export function PipelineFlow({ pipeline }: { pipeline: PipelineDefinition }) {
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => setMounted(true), []);

  const { nodes, edges } = React.useMemo(() => buildGraph(pipeline), [pipeline]);

  if (!mounted) return <Skeleton className="h-[280px] w-full rounded-lg" />;

  return (
    <div className="h-[280px] w-full overflow-hidden rounded-lg border border-border bg-card">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={pipelineNodeTypes}
        colorMode={resolvedTheme === 'light' ? 'light' : 'dark'}
        fitView
        fitViewOptions={{ padding: 0.15 }}
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
