import { useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  type Health,
  type PluginList,
  type PluginSummary,
  type Project,
  type RunSummary,
} from "./api";
import { CommandPalette, usePaletteHotkey, type Command } from "./CommandPalette";
import { LogPanel } from "./LogPanel";

type View = "engines" | "projects";

/**
 * The IDE frame: Explorer | Workspace | Inspector, with the run log beneath.
 *
 * Per ADR-0001 this component computes no scientific quantity — it does not average a score,
 * rescale a component, or place two engines on one axis. It lays out what the backend decided.
 */
export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [plugins, setPlugins] = useState<PluginList | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [selected, setSelected] = useState<PluginSummary | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [view, setView] = useState<View>("engines");
  const [paletteOpen, setPaletteOpen] = useState(false);

  usePaletteHotkey(setPaletteOpen);

  const refresh = useCallback(async () => {
    try {
      const [h, p, pr, r] = await Promise.all([
        api.health(),
        api.plugins(),
        api.projects(),
        api.runs(),
      ]);
      setHealth(h);
      setPlugins(p);
      setProjects(pr.projects);
      setRuns(r.runs);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), 4000);
    return () => clearInterval(timer);
  }, [refresh]);

  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(null), 8000);
    return () => clearTimeout(timer);
  }, [notice]);

  const commands = useMemo<Command[]>(() => {
    const base: Command[] = [
      {
        id: "view.engines",
        title: "Go to: Engines",
        hint: "view",
        run: () => setView("engines"),
      },
      {
        id: "view.projects",
        title: "Go to: Projects",
        hint: "view",
        run: () => setView("projects"),
      },
      {
        id: "project.new",
        title: "New project…",
        hint: "POST /api/projects",
        run: async () => {
          const name = window.prompt("Project name");
          if (!name) return;
          const project = await api.createProject(name);
          setView("projects");
          setNotice(`Created project ${project.name} (${project.id})`);
          await refresh();
        },
      },
      {
        id: "run.interpreter",
        title: "Run: report control-plane interpreter",
        hint: "real subprocess",
        run: async () => {
          const run = await api.createRun("interpreter", [
            "python3",
            "-c",
            "import sys, platform; print(sys.version); print(platform.platform())",
          ]);
          setSelectedRunId(run.run_id);
          await refresh();
        },
      },
      { id: "app.refresh", title: "Refresh", hint: "re-read backend state", run: refresh },
    ];

    for (const plugin of plugins?.plugins ?? []) {
      base.push({
        id: `engine.run.${plugin.plugin_id}`,
        title: `Execute engine: ${plugin.name}`,
        hint: plugin.availability.state,
        run: async () => {
          setSelected(plugin);
          try {
            const run = await api.runPlugin(plugin.plugin_id);
            setSelectedRunId(run.run_id);
            await refresh();
          } catch (e) {
            // The backend's refusal carries the blocker id or the phase that owns the gap.
            // Surfacing it verbatim is the point — a generic "failed" would hide the reason.
            setNotice(e instanceof Error ? e.message : String(e));
          }
        },
      });
    }
    return base;
  }, [plugins, refresh]);

  return (
    <div className="ide">
      <header className="menubar">
        <span className="brand">OpenFIQA Studio</span>
        <span className="subtitle">Biometric Quality &amp; Verification IDE</span>
        <button className="palette-trigger" onClick={() => setPaletteOpen(true)}>
          ⌘K
        </button>
        <span className={`conn ${error ? "down" : health ? "up" : "wait"}`}>
          {error
            ? `backend unreachable — ${error}`
            : health
              ? `backend ok · v${health.api_version}`
              : "connecting…"}
        </span>
      </header>

      {notice && (
        <div className="notice" role="status">
          {notice}
          <button onClick={() => setNotice(null)}>×</button>
        </div>
      )}

      <div className="body">
        <aside className="explorer">
          <section className="panel">
            <h2>{view === "engines" ? `Engines (${plugins?.counts.total ?? 0})` : `Projects (${projects.length})`}</h2>
            {view === "engines"
              ? plugins?.plugins.map((plugin) => (
                  <button
                    key={plugin.plugin_id}
                    className={`row ${selected?.plugin_id === plugin.plugin_id ? "sel" : ""}`}
                    onClick={() => setSelected(plugin)}
                  >
                    <StateDot state={plugin.availability.state} />
                    <span className="rowname">{plugin.name}</span>
                    <span className="rowver">{plugin.version}</span>
                  </button>
                ))
              : projects.length === 0
                ? <p className="empty">No projects yet. Press ⌘K → New project.</p>
                : projects.map((project) => (
                    <div key={project.id} className="row">
                      <span className="rowname">{project.name}</span>
                      <span className="rowver">{project.id}</span>
                    </div>
                  ))}
          </section>
        </aside>

        <main className="workspace">
          {selected ? <PluginDetail plugin={selected} /> : <Placeholder counts={plugins?.counts} />}
        </main>

        <aside className="inspector">
          <section className="panel">
            <h2>Inspector</h2>
            {selected ? (
              <dl className="kv">
                <dt>Kind</dt><dd>{selected.kind}</dd>
                <dt>Mode</dt><dd>{selected.mode}</dd>
                <dt>Inputs</dt><dd>{selected.inputs.join(", ") || "—"}</dd>
                <dt>Outputs</dt><dd>{selected.outputs.join(", ") || "—"}</dd>
                <dt>Batch</dt><dd>{String(selected.capabilities.batch)}</dd>
                <dt>GPU</dt><dd>{String(selected.capabilities.gpu)}</dd>
                <dt>License</dt><dd>{selected.provenance.license ?? "—"}</dd>
                <dt>Public</dt><dd>{String(selected.provenance.public)}</dd>
                <dt>Commit</dt>
                <dd className="mono">{selected.provenance.commit?.slice(0, 12) ?? "—"}</dd>
              </dl>
            ) : (
              <p className="empty">Select an engine.</p>
            )}
          </section>
        </aside>
      </div>

      <LogPanel
        runs={runs}
        selectedRunId={selectedRunId}
        onSelectRun={setSelectedRunId}
        onRunsChanged={refresh}
      />

      <footer className="statusbar">
        <span>Runs: {runs.length}</span>
        <span>Executable engines: {plugins?.counts.executable ?? 0}</span>
        <span>Blocked: {plugins?.counts.blocked ?? 0}</span>
        <span className="mono">{api.base}</span>
      </footer>

      <CommandPalette commands={commands} open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  );
}

function StateDot({ state }: { state: PluginSummary["availability"]["state"] }) {
  return <span className={`dot ${state.toLowerCase()}`} title={state} />;
}

function PluginDetail({ plugin }: { plugin: PluginSummary }) {
  const { availability } = plugin;
  return (
    <article className="detail">
      <h1>{plugin.name}</h1>
      <p className="lede">
        <StateDot state={availability.state} /> {availability.state}
        {availability.blocker_id ? ` · ${availability.blocker_id}` : ""}
      </p>

      {availability.reason && <p className="reason">{availability.reason}</p>}

      {availability.verified_by && (
        <div className="evidence">
          <h3>Verified by execution</h3>
          <p>
            {availability.verified_by.corpus} · rc={availability.verified_by.rc}
            {availability.verified_by.n_components !== null
              ? ` · ${availability.verified_by.n_components} components`
              : ""}
          </p>
        </div>
      )}

      {availability.state === "BLOCKED" && (
        <p className="note">
          This engine stays listed rather than hidden. Execution is refused with its blocker id so
          the reason is visible instead of surfacing as an unexplained failure.
        </p>
      )}
    </article>
  );
}

function Placeholder({ counts }: { counts?: PluginList["counts"] }) {
  return (
    <article className="detail">
      <h1>Workspace</h1>
      <p className="lede">
        {counts
          ? `${counts.total} engines registered — ${counts.executable} executable, ${counts.blocked} blocked, ${counts.unverified} unverified.`
          : "Waiting for the control plane…"}
      </p>
      <p className="note">
        Graph, image, code and evaluation views arrive with later build phases. This frame proves
        the shell observes the backend; it does not stand in for those views.
      </p>
    </article>
  );
}
