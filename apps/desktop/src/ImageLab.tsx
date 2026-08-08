import { useCallback, useEffect, useMemo, useState } from "react";
import { api, type PluginSummary, type QualityVectorView, type SampleEntry } from "./api";

/**
 * I07 — the Image Laboratory.
 *
 * A sample, the engine outputs for it, and every component score side by side.
 *
 * Per ADR-0001 nothing here is computed. The bars render `scalar` exactly as the backend supplied
 * it; a component the engine could not assess renders as "not assessed" rather than as zero,
 * because a zero-length bar in a quality view reads as "very poor", which is the same lie the
 * FailureToAssess sentinel would have told.
 *
 * Two engines are never merged into one list. They report different component vocabularies —
 * ofiqpy uses names, openfiqa uses C01..C28 — and no verified mapping exists.
 */
export default function ImageLab({ plugins }: { plugins: PluginSummary[] }) {
  const [samples, setSamples] = useState<SampleEntry[]>([]);
  const [selected, setSelected] = useState<SampleEntry | null>(null);
  const [results, setResults] = useState<Record<string, QualityVectorView>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    api.samples(300).then((r) => setSamples(r.samples)).catch(() => setSamples([]));
  }, []);

  useEffect(() => {
    setResults({});
    setError(null);
  }, [selected?.path]);

  const executable = useMemo(
    () => plugins.filter((p) => p.executable),
    [plugins],
  );

  const assess = useCallback(
    async (pluginId: string) => {
      if (!selected) return;
      setBusy(pluginId);
      setError(null);
      try {
        const body = await api.assess(pluginId, selected.path);
        setResults((current) => ({ ...current, [pluginId]: body.quality_vector }));
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setBusy(null);
      }
    },
    [selected],
  );

  const shown = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    return needle
      ? samples.filter((s) => s.subject_id.toLowerCase().includes(needle))
      : samples;
  }, [samples, filter]);

  return (
    <div className="lab-wrap">
      <aside className="lab-list">
        <input
          className="lab-filter"
          placeholder={`Filter ${samples.length} samples…`}
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          aria-label="Filter samples by subject"
        />
        {shown.map((sample) => (
          <button
            key={sample.path}
            className={`lab-item ${selected?.path === sample.path ? "sel" : ""}`}
            onClick={() => setSelected(sample)}
          >
            <span className="lab-subject">{sample.subject_id.replace(/_/g, " ")}</span>
            <span className="lab-file">{sample.name}</span>
          </button>
        ))}
        {shown.length === 0 && <p className="empty">No samples match.</p>}
      </aside>

      <main className="lab-main">
        {!selected ? (
          <p className="empty">Select a sample to inspect it.</p>
        ) : (
          <>
            <header className="lab-head">
              <h2>{selected.subject_id.replace(/_/g, " ")}</h2>
              <span className="mono">{selected.name}</span>
              <div className="lab-actions">
                {executable.map((plugin) => (
                  <button
                    key={plugin.plugin_id}
                    onClick={() => void assess(plugin.plugin_id)}
                    disabled={busy !== null}
                    title={
                      plugin.availability.state === "DEGRADED"
                        ? `DEGRADED — ${plugin.availability.blocker_id}`
                        : undefined
                    }
                  >
                    {busy === plugin.plugin_id ? "Running…" : `Assess: ${plugin.name}`}
                    {plugin.availability.state === "DEGRADED" && <span className="warn-dot" />}
                  </button>
                ))}
              </div>
            </header>

            {error && <div className="lab-error">{error}</div>}

            <div className="lab-body">
              <figure className="lab-figure">
                <img src={api.imageUrl(selected.path)} alt={`Sample ${selected.name}`} />
                <figcaption className="mono">{selected.path}</figcaption>
              </figure>

              <div className="lab-results">
                {Object.keys(results).length === 0 && (
                  <p className="empty">Run an engine to see its components.</p>
                )}
                {Object.entries(results).map(([pluginId, vector]) => (
                  <EngineResult key={pluginId} pluginId={pluginId} vector={vector} />
                ))}
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}

function EngineResult({ pluginId, vector }: { pluginId: string; vector: QualityVectorView }) {
  const unassessed = vector.components.filter((c) => !c.computed);
  return (
    <section className="lab-engine">
      <h3>
        {pluginId}
        {vector.unified?.value !== null && vector.unified !== null && (
          <span className="lab-unified">
            {vector.unified.value?.toFixed(1)}
            <em>{vector.unified.semantics.definition_id}</em>
          </span>
        )}
      </h3>
      <p className="lab-state">
        state {vector.state} · engine {vector.engine.commit?.slice(0, 12) ?? "—"}
        {vector.engine.config_digest && ` · weights ${vector.engine.config_digest.slice(0, 12)}`}
      </p>

      <ul className="lab-components">
        {vector.components.map((component) => (
          <li key={component.name}>
            <span className="lab-cname">{component.name}</span>
            {component.computed && component.scalar !== null ? (
              <>
                <span className="lab-bar">
                  <span
                    className={`lab-fill ${component.scalar < 30 ? "low" : component.scalar < 70 ? "mid" : "high"}`}
                    style={{ width: `${Math.max(0, Math.min(100, component.scalar))}%` }}
                  />
                </span>
                <span className="lab-score">{component.scalar.toFixed(0)}</span>
              </>
            ) : (
              // Not a zero bar. An unassessed component is missing information, not bad quality.
              <span className="lab-unassessed">not assessed</span>
            )}
          </li>
        ))}
      </ul>

      {unassessed.length > 0 && (
        <p className="lab-note">
          {unassessed.length} component{unassessed.length === 1 ? "" : "s"} could not be assessed
          and carry no score.
        </p>
      )}
    </section>
  );
}
