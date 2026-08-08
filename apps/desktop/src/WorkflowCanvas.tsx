import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  addEdge,
  Background,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
  type Connection,
  type Edge,
  type Node,
  type NodeProps,
  type NodeTypes,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { api, type NodeKind, type RunManifest } from "./api";

/**
 * W01 — the visual workflow editor.
 *
 * Drag a node kind onto the canvas, wire it up, edit parameters, run it.
 *
 * The connection rules are FETCHED from the backend (`/api/workflows/node-kinds`), not duplicated
 * here. ADR-0001 and ADR-0004: a frontend with its own copy of the type system would keep drawing
 * edges the executor rejects the moment the schema changes. `isValidConnection` enforces exactly
 * the backend's port table, so an edge that cannot be drawn is an edge that would not compile.
 */

type StudioNodeData = {
  kind: string;
  parameters: Record<string, unknown>;
  sweep: Record<string, unknown[]>;
  kinds: NodeKind[];
  status?: string;
  blockerId?: string | null;
  onChange: (id: string, patch: Partial<StudioNodeData>) => void;
};

const KIND_ACCENT: Record<string, string> = {
  dataset: "#6aa9ff",
  transform: "#c58af9",
  engine: "#4ec98a",
  feature_table: "#e0b341",
  scorer: "#e0b341",
  artifact: "#8b93a1",
};

function StudioNode({ id, data, selected }: NodeProps) {
  const nodeData = data as unknown as StudioNodeData;
  const spec = nodeData.kinds.find((k) => k.kind === nodeData.kind);
  const accent = KIND_ACCENT[nodeData.kind] ?? "#8b93a1";
  const blocked = Boolean(spec?.blocked_by);

  return (
    <div className={`wf-node ${selected ? "sel" : ""} ${blocked ? "blocked" : ""}`}>
      {spec && spec.inputs.length > 0 && (
        <Handle type="target" position={Position.Left} className="wf-handle" />
      )}
      <div className="wf-node-head" style={{ borderLeftColor: accent }}>
        <span className="wf-kind" style={{ color: accent }}>
          {nodeData.kind}
        </span>
        <span className="wf-id">{id}</span>
      </div>
      <div className="wf-node-body">
        {Object.entries(nodeData.parameters).length === 0 && Object.keys(nodeData.sweep).length === 0 ? (
          <span className="wf-empty">no parameters</span>
        ) : (
          <>
            {Object.entries(nodeData.parameters).map(([key, value]) => (
              <div key={key} className="wf-param">
                <span className="wf-key">{key}</span>
                <span className="wf-val">{String(value)}</span>
              </div>
            ))}
            {Object.entries(nodeData.sweep).map(([key, values]) => (
              <div key={key} className="wf-param sweep">
                <span className="wf-key">{key}</span>
                <span className="wf-val">sweep {JSON.stringify(values)}</span>
              </div>
            ))}
          </>
        )}
      </div>
      {blocked && <div className="wf-blocked">blocked · {spec?.blocked_by}</div>}
      {nodeData.status && (
        <div className={`wf-status st-${nodeData.status}`}>
          {nodeData.status}
          {nodeData.blockerId ? ` · ${nodeData.blockerId}` : ""}
        </div>
      )}
      {spec && spec.outputs.length > 0 && (
        <Handle type="source" position={Position.Right} className="wf-handle" />
      )}
    </div>
  );
}

const nodeTypes: NodeTypes = { studio: StudioNode };

let idCounter = 0;
const nextId = (kind: string) => `${kind}_${++idCounter}`;

function CanvasInner() {
  const [kinds, setKinds] = useState<NodeKind[]>([]);
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [name, setName] = useState("untitled-workflow");
  const [problems, setProblems] = useState<string[]>([]);
  const [digest, setDigest] = useState<string | null>(null);
  const [manifest, setManifest] = useState<RunManifest | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const wrapper = useRef<HTMLDivElement>(null);
  const { screenToFlowPosition } = useReactFlow();

  useEffect(() => {
    api.nodeKinds().then((r) => setKinds(r.kinds)).catch(() => setKinds([]));
  }, []);

  const patchNode = useCallback(
    (id: string, patch: Partial<StudioNodeData>) => {
      setNodes((current) =>
        current.map((n) => (n.id === id ? { ...n, data: { ...n.data, ...patch } } : n)),
      );
    },
    [setNodes],
  );

  /** Serialise the canvas into the same YAML the CLI accepts. */
  const toYaml = useCallback((): string => {
    const lines = ["version: 1", `name: ${name}`, "nodes:"];
    for (const node of nodes) {
      const d = node.data as unknown as StudioNodeData;
      lines.push(`  - id: ${node.id}`);
      lines.push(`    kind: ${d.kind}`);
      if (Object.keys(d.parameters).length) {
        lines.push("    parameters:");
        for (const [key, value] of Object.entries(d.parameters)) {
          lines.push(`      ${key}: ${JSON.stringify(value)}`);
        }
      }
      if (Object.keys(d.sweep).length) {
        lines.push("    sweep:");
        for (const [key, values] of Object.entries(d.sweep)) {
          lines.push(`      ${key}: ${JSON.stringify(values)}`);
        }
      }
    }
    lines.push("edges:");
    for (const edge of edges) {
      lines.push(`  - {source: ${edge.source}, target: ${edge.target}}`);
    }
    return lines.join("\n") + "\n";
  }, [name, nodes, edges]);

  /** The backend's port table decides which edges may exist. */
  const isValidConnection = useCallback(
    (connection: Connection | Edge) => {
      const source = nodes.find((n) => n.id === connection.source);
      const target = nodes.find((n) => n.id === connection.target);
      if (!source || !target || source.id === target.id) return false;
      const sourceSpec = kinds.find((k) => k.kind === (source.data as unknown as StudioNodeData).kind);
      const targetSpec = kinds.find((k) => k.kind === (target.data as unknown as StudioNodeData).kind);
      if (!sourceSpec || !targetSpec) return false;
      return sourceSpec.outputs.some((t) => targetSpec.inputs.includes(t));
    },
    [nodes, kinds],
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      if (!isValidConnection(connection)) {
        const source = nodes.find((n) => n.id === connection.source);
        const target = nodes.find((n) => n.id === connection.target);
        const s = kinds.find((k) => k.kind === (source?.data as unknown as StudioNodeData)?.kind);
        const t = kinds.find((k) => k.kind === (target?.data as unknown as StudioNodeData)?.kind);
        setMessage(
          `Refused: ${s?.kind} produces [${s?.outputs}], ${t?.kind} accepts [${t?.inputs}]`,
        );
        return;
      }
      setMessage(null);
      setEdges((current) => addEdge({ ...connection, animated: true }, current));
    },
    [isValidConnection, nodes, kinds, setEdges],
  );

  const addNode = useCallback(
    (kind: string, position?: { x: number; y: number }) => {
      const id = nextId(kind);
      setNodes((current) => [
        ...current,
        {
          id,
          type: "studio",
          position: position ?? { x: 80 + current.length * 40, y: 80 + current.length * 30 },
          data: { kind, parameters: {}, sweep: {}, kinds, onChange: patchNode } as never,
        },
      ]);
    },
    [kinds, patchNode, setNodes],
  );

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const kind = event.dataTransfer.getData("application/openfiqa-node");
      if (!kind) return;
      addNode(kind, screenToFlowPosition({ x: event.clientX, y: event.clientY }));
    },
    [addNode, screenToFlowPosition],
  );

  const validate = useCallback(async () => {
    try {
      const result = await api.validateWorkflow(toYaml());
      setProblems(result.problems);
      setDigest(result.workflow_sha256);
      setMessage(result.valid ? "Valid workflow." : `${result.problems.length} problem(s)`);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    }
  }, [toYaml]);

  const run = useCallback(async () => {
    setBusy(true);
    setMessage("Running…");
    try {
      const result = await api.runWorkflow(toYaml());
      setManifest(result);
      const byId = new Map(result.nodes.map((n) => [n.node_id, n]));
      setNodes((current) =>
        current.map((n) => {
          // A swept node expands to `id[param=value]`, so match on the base id too.
          const direct = byId.get(n.id);
          const expanded = result.nodes.find((r) => r.node_id.startsWith(`${n.id}[`));
          const match = direct ?? expanded;
          return match
            ? { ...n, data: { ...n.data, status: match.status, blockerId: match.blocker_id } }
            : n;
        }),
      );
      setMessage(`Run ${result.status}`);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [toYaml, setNodes]);

  const selected = useMemo(() => nodes.find((n) => n.selected) ?? null, [nodes]);

  return (
    <div className="wf-wrap">
      <aside className="wf-palette">
        <h3>Nodes</h3>
        <p className="wf-hint">Drag onto the canvas</p>
        {kinds.map((kind) => (
          <div
            key={kind.kind}
            className={`wf-chip ${kind.blocked_by ? "blocked" : ""}`}
            draggable
            onDragStart={(e) => {
              e.dataTransfer.setData("application/openfiqa-node", kind.kind);
              e.dataTransfer.effectAllowed = "move";
            }}
            onDoubleClick={() => addNode(kind.kind)}
            style={{ borderLeftColor: KIND_ACCENT[kind.kind] ?? "#8b93a1" }}
            title={`in: ${kind.inputs.join(", ") || "—"}\nout: ${kind.outputs.join(", ") || "—"}`}
          >
            <span>{kind.kind}</span>
            {kind.blocked_by && <span className="wf-chip-blocked">{kind.blocked_by}</span>}
          </div>
        ))}

        <h3 style={{ marginTop: 18 }}>Workflow</h3>
        <input
          className="wf-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          aria-label="Workflow name"
        />
        <div className="wf-actions">
          <button onClick={validate} disabled={busy}>Validate</button>
          <button onClick={run} disabled={busy || nodes.length === 0} className="primary">
            {busy ? "Running…" : "Run"}
          </button>
        </div>
        <button
          className="wf-export"
          onClick={() => navigator.clipboard?.writeText(toYaml())}
          disabled={nodes.length === 0}
        >
          Copy YAML
        </button>
        {digest && <p className="wf-digest mono">sha {digest.slice(0, 16)}…</p>}
      </aside>

      <div className="wf-canvas" ref={wrapper}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          isValidConnection={isValidConnection}
          nodeTypes={nodeTypes}
          onDrop={onDrop}
          onDragOver={(e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = "move";
          }}
          fitView
          proOptions={{ hideAttribution: false }}
        >
          <Background gap={16} color="#242933" />
          <Controls />
          <MiniMap pannable zoomable nodeColor={(n) => KIND_ACCENT[(n.data as never as StudioNodeData).kind] ?? "#8b93a1"} />
        </ReactFlow>
      </div>

      <aside className="wf-side">
        {message && <div className="wf-message">{message}</div>}

        {problems.length > 0 && (
          <section>
            <h3>Problems</h3>
            <ul className="wf-problems">
              {problems.map((p, i) => (
                <li key={i}>{p}</li>
              ))}
            </ul>
          </section>
        )}

        {selected && (
          <section>
            <h3>Parameters — {selected.id}</h3>
            <ParameterEditor
              node={selected}
              onChange={(parameters, sweep) => patchNode(selected.id, { parameters, sweep })}
            />
          </section>
        )}

        {manifest && (
          <section>
            <h3>Last run — {manifest.status}</h3>
            <ul className="wf-runlist">
              {manifest.nodes.map((n) => (
                <li key={n.node_id} className={`st-${n.status}`}>
                  <span className="mono">{n.node_id}</span>
                  <span>{n.status}{n.blocker_id ? ` · ${n.blocker_id}` : ""}</span>
                </li>
              ))}
            </ul>
          </section>
        )}
      </aside>
    </div>
  );
}

function ParameterEditor({
  node,
  onChange,
}: {
  node: Node;
  onChange: (parameters: Record<string, unknown>, sweep: Record<string, unknown[]>) => void;
}) {
  const data = node.data as unknown as StudioNodeData;
  const [text, setText] = useState("");
  const [sweepText, setSweepText] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setText(JSON.stringify(data.parameters, null, 2));
    setSweepText(JSON.stringify(data.sweep, null, 2));
    setError(null);
  }, [node.id]);

  const commit = () => {
    try {
      onChange(JSON.parse(text || "{}"), JSON.parse(sweepText || "{}"));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="wf-editor">
      <label>parameters</label>
      <textarea value={text} onChange={(e) => setText(e.target.value)} onBlur={commit} rows={7} />
      <label>sweep</label>
      <textarea
        value={sweepText}
        onChange={(e) => setSweepText(e.target.value)}
        onBlur={commit}
        rows={3}
      />
      {error && <p className="wf-error">{error}</p>}
    </div>
  );
}

export default function WorkflowCanvas() {
  return (
    <ReactFlowProvider>
      <CanvasInner />
    </ReactFlowProvider>
  );
}
