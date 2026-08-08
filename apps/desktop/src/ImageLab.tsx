import { useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  type DegradeResult,
  type DetectResult,
  type PluginSummary,
  type QualityVectorView,
  type SampleEntry,
} from "./api";

/** Deterministic operators with a single meaningful dial, for the preview slider. */
const DEGRADATIONS: { operator: string; label: string; key: string; min: number; max: number; step: number; start: number }[] = [
  { operator: "jpeg", label: "JPEG quality", key: "quality", min: 1, max: 100, step: 1, start: 100 },
  { operator: "resize", label: "Resolution scale", key: "scale", min: 0.05, max: 1, step: 0.05, start: 1 },
  { operator: "gaussian_blur", label: "Blur radius", key: "radius", min: 0, max: 8, step: 0.25, start: 0 },
  { operator: "gamma", label: "Gamma", key: "gamma", min: 0.2, max: 3, step: 0.1, start: 1 },
  { operator: "occlude", label: "Occlusion", key: "fraction", min: 0, max: 0.49, step: 0.01, start: 0 },
];

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
  const [degradation, setDegradation] = useState(DEGRADATIONS[0]);
  const [amount, setAmount] = useState(DEGRADATIONS[0].start);
  const [degraded, setDegraded] = useState<DegradeResult | null>(null);
  const [degradedResults, setDegradedResults] = useState<Record<string, QualityVectorView>>({});
  const [detection, setDetection] = useState<DetectResult | null>(null);
  const [showOverlay, setShowOverlay] = useState(true);

  useEffect(() => {
    api.samples(300).then((r) => setSamples(r.samples)).catch(() => setSamples([]));
  }, []);

  useEffect(() => {
    setResults({});
    setDegraded(null);
    setDegradedResults({});
    setDetection(null);
    setError(null);
  }, [selected?.path]);

  // Re-derive the preview when the dial moves. At `start` the operator would be a no-op, so the
  // original is shown rather than a pointless round-trip through the encoder.
  useEffect(() => {
    if (!selected) return;
    if (amount === degradation.start) {
      setDegraded(null);
      setDegradedResults({});
      return;
    }
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const result = await api.degrade(selected.path, degradation.operator, {
          [degradation.key]: amount,
        });
        if (!cancelled) {
          setDegraded(result);
          setDegradedResults({});
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    }, 180);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [selected, degradation, amount]);

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
        if (degraded) {
          const after = await api.assess(pluginId, degraded.path);
          setDegradedResults((current) => ({ ...current, [pluginId]: after.quality_vector }));
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setBusy(null);
      }
    },
    [selected, degraded],
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
                <button
                  onClick={async () => {
                    if (!selected) return;
                    setBusy("detect");
                    setError(null);
                    try {
                      setDetection(await api.detect(selected.path));
                    } catch (e) {
                      setError(e instanceof Error ? e.message : String(e));
                    } finally {
                      setBusy(null);
                    }
                  }}
                  disabled={busy !== null}
                >
                  {busy === "detect" ? "Detecting…" : "Detect face"}
                </button>
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

            <div className="lab-degrade">
              <select
                value={degradation.operator}
                onChange={(e) => {
                  const next = DEGRADATIONS.find((d) => d.operator === e.target.value)!;
                  setDegradation(next);
                  setAmount(next.start);
                }}
                aria-label="Degradation"
              >
                {DEGRADATIONS.map((d) => (
                  <option key={d.operator} value={d.operator}>{d.label}</option>
                ))}
              </select>
              <input
                type="range"
                min={degradation.min}
                max={degradation.max}
                step={degradation.step}
                value={amount}
                onChange={(e) => setAmount(Number(e.target.value))}
                aria-label={degradation.label}
              />
              <span className="lab-amount mono">{amount}</span>
              <button onClick={() => setAmount(degradation.start)} disabled={amount === degradation.start}>
                Reset
              </button>
              {degraded && (
                <span className="lab-hash mono" title="transform output hash">
                  {degraded.transform.output_sha256.slice(0, 12)}
                  {degraded.transform.deterministic ? " · deterministic" : " · stochastic"}
                </span>
              )}
            </div>

            <div className="lab-body">
              <figure className="lab-figure">
                <div className="lab-images">
                  <div className="lab-imgwrap">
                    <img src={api.imageUrl(selected.path)} alt={`Sample ${selected.name}`} />
                    {detection && showOverlay && <FaceOverlay detection={detection} />}
                    <span className="lab-imglabel">original</span>
                  </div>
                  {degraded && (
                    <div>
                      <img src={api.imageUrl(degraded.path)} alt="Degraded sample" />
                      <span className="lab-imglabel degraded">
                        {degradation.label} {amount}
                      </span>
                    </div>
                  )}
                </div>
                {detection && (
                  <div className="lab-detect">
                    <label>
                      <input
                        type="checkbox"
                        checked={showOverlay}
                        onChange={(e) => setShowOverlay(e.target.checked)}
                      />
                      overlay
                    </label>
                    <span>
                      {detection.n_faces} face{detection.n_faces === 1 ? "" : "s"}
                      {detection.detections[0] &&
                        ` · score ${detection.detections[0].det_score.toFixed(2)}`}
                    </span>
                    {detection.detections[0]?.pose_pitch_yaw_roll && (
                      <span className="mono">
                        pitch {detection.detections[0].pose_pitch_yaw_roll[0].toFixed(0)}° yaw{" "}
                        {detection.detections[0].pose_pitch_yaw_roll[1].toFixed(0)}° roll{" "}
                        {detection.detections[0].pose_pitch_yaw_roll[2].toFixed(0)}°
                      </span>
                    )}
                    {!detection.geometry_consistent && (
                      <span className="lab-geowarn">
                        geometry check failed: {detection.geometry_problems.join("; ")}
                      </span>
                    )}
                  </div>
                )}
                <figcaption className="mono">{selected.path}</figcaption>
              </figure>

              <div className="lab-results">
                {Object.keys(results).length === 0 && (
                  <p className="empty">Run an engine to see its components.</p>
                )}
                {Object.entries(results).map(([pluginId, vector]) => (
                  <EngineResult
                    key={pluginId}
                    pluginId={pluginId}
                    vector={vector}
                    degraded={degradedResults[pluginId] ?? null}
                  />
                ))}
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}

/**
 * The overlay is an SVG with a viewBox in ORIGINAL image pixels, laid over the img at 100%/100%.
 * That way the browser scales geometry and picture by exactly the same factor — computing screen
 * coordinates in JS would drift the moment the image is resized by CSS.
 */
function FaceOverlay({ detection }: { detection: DetectResult }) {
  return (
    <svg
      className="lab-overlay"
      viewBox={`0 0 ${detection.image_width} ${detection.image_height}`}
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      {detection.detections.map((face, index) => {
        const [x0, y0, x1, y1] = face.bbox;
        return (
          <g key={index}>
            <rect x={x0} y={y0} width={x1 - x0} height={y1 - y0} className="ov-box" />
            {(face.landmarks_106 ?? []).map(([x, y], i) => (
              <circle key={`l${i}`} cx={x} cy={y} r={1} className="ov-landmark" />
            ))}
            {face.keypoints.map(([x, y], i) => (
              <circle key={`k${i}`} cx={x} cy={y} r={2.4} className="ov-keypoint" />
            ))}
          </g>
        );
      })}
    </svg>
  );
}

function EngineResult({
  pluginId,
  vector,
  degraded,
}: {
  pluginId: string;
  vector: QualityVectorView;
  degraded: QualityVectorView | null;
}) {
  const unassessed = vector.components.filter((c) => !c.computed);
  const after = new Map((degraded?.components ?? []).map((c) => [c.name, c]));
  return (
    <section className="lab-engine">
      <h3>
        {pluginId}
        {vector.unified?.value !== null && vector.unified !== null && (
          <span className="lab-unified">
            {vector.unified.value?.toFixed(1)}
            {degraded?.unified?.value != null && vector.unified.value != null && (
              <span className={`lab-delta ${degraded.unified.value < vector.unified.value ? "down" : "up"}`}>
                {" → "}{degraded.unified.value.toFixed(1)}
              </span>
            )}
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
            {(() => {
              const post = after.get(component.name);
              if (!post || !component.computed || component.scalar === null) return null;
              if (!post.computed || post.scalar === null) {
                return <span className="lab-after gone">not assessed</span>;
              }
              const delta = post.scalar - component.scalar;
              if (Math.abs(delta) < 0.5) return <span className="lab-after same">=</span>;
              return (
                <span className={`lab-after ${delta < 0 ? "down" : "up"}`}>
                  {delta > 0 ? "+" : ""}{delta.toFixed(0)}
                </span>
              );
            })()}
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
