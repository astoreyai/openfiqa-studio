import { useEffect, useState } from "react";
import { api, type Health, type PluginList, type PluginSummary, type Project, type RunSummary } from "./api";

/**
 * The IDE frame: Explorer | Workspace | Inspector, with a status strip beneath.
 *
 * Everything shown here is served by the control plane. Per ADR-0001 this component computes no
 * scientific quantity — it does not average a score, rescale a component, or place two engines on
 * one axis. It lays out what the backend already decided.
 */
export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [plugins, setPlugins] = useState<PluginList | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<PluginSummary | null>(null);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const [h, p, pr, r] = await Promise.all([
          api.health(),
          api.plugins(),
          api.projects(),
          api.runs(),
        ]);
        if (cancelled) return;
        setHealth(h);
        setPlugins(p);
        setProjects(pr.projects);
        setRuns(r.runs);
        setError(null);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    };
    poll();
    const timer = setInterval(poll, 4000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  return (
    <div className="ide">
      <header className="menubar">
        <span className="brand">OpenFIQA Studio</span>
        <span className="subtitle">Biometric Quality &amp; Verification IDE</span>
        <span className={`conn ${error ? "down" : health ? "up" : "wait"}`}>
          {error ? `backend unreachable — ${error}` : health ? `backend ok · v${health.api_version}` : "connecting…"}
        </span>
      </header>

      <div className="body">
        <aside className="explorer">
          <Section title={`Engines (${plugins?.counts.total ?? 0})`}>
            {plugins?.plugins.map((plugin) => (
              <button
                key={plugin.plugin_id}
                className={`row ${selected?.plugin_id === plugin.plugin_id ? "sel" : ""}`}
                onClick={() => setSelected(plugin)}
              >
                <StateDot state={plugin.availability.state} />
                <span className="rowname">{plugin.name}</span>
                <span className="rowver">{plugin.version}</span>
              </button>
            ))}
          </Section>

          <Section title={`Projects (${projects.length})`}>
            {projects.length === 0 ? (
              <p className="empty">No projects yet.</p>
            ) : (
              projects.map((project) => (
                <div key={project.id} className="row">
                  <span className="rowname">{project.name}</span>
                  <span className="rowver">{project.id}</span>
                </div>
              ))
            )}
          </Section>
        </aside>

        <main className="workspace">
          {selected ? <PluginDetail plugin={selected} /> : <Placeholder counts={plugins?.counts} />}
        </main>

        <aside className="inspector">
          <Section title="Inspector">
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
          </Section>
        </aside>
      </div>

      <footer className="statusbar">
        <span>Runs: {runs.length}</span>
        <span>Executable engines: {plugins?.counts.executable ?? 0}</span>
        <span>Blocked: {plugins?.counts.blocked ?? 0}</span>
        <span className="mono">{api.base}</span>
      </footer>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="panel">
      <h2>{title}</h2>
      {children}
    </section>
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
