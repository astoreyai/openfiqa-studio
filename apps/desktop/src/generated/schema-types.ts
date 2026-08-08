/* eslint-disable */
/**
 * GENERATED FILE — DO NOT EDIT.
 *
 * Source of truth: packages/schemas/*.json (ADR-0004).
 * Regenerate with:  pnpm generate:types
 * CI check:         pnpm check:types-fresh
 */

/**
 * Which implementation produced a value. Version strings alone are not a sufficient provenance key — ofiqpy reports 0.1.1 in pyproject and 0.1.0 at runtime (B-P01-05) — so commit is required whenever it is knowable.
 */
export interface EngineRef {
  engine_id: "ofiqpy" | "openfiqa" | "ofiq_quality" | "ofiq_project";
  version: string | null;
  commit: string | null;
  runtime?: string | null;
  config_digest?: string | null;
}

/**
 * A score is meaningless without its definition. This block is required on every score-bearing object, which is what prevents three different unified scores from sharing a column.
 */
export interface ScoreSemantics {
  /**
   * Stable identifier for what the number means, e.g. ofiqpy.UnifiedQualityScore, openfiqa.profile_score, ofiq_quality.predicted_score. Never reuse an id across engines.
   */
  definition_id: string;
  /**
   * [min, max]. Expressed as a bounded numeric array rather than a prefixItems tuple: the 2020-12 tuple form is not supported by the TypeScript emitter and silently generated `never[]`, which is exactly the frontend/backend divergence ADR-0004 exists to prevent.
   *
   * @minItems 2
   * @maxItems 2
   */
  range?: [number, number];
  /**
   * unknown is a legitimate persisted value. P01 could not verify direction for any engine; recording unknown is required, guessing is not.
   */
  direction: "higher_is_better" | "lower_is_better" | "unknown";
  /**
   * e.g. iso-29794-5
   */
  standard?: string | null;
  standard_version?: string | null;
}

/**
 * The ONLY way a score may be represented. There is deliberately no plain number form — a bare float cannot carry which engine produced it or what it means, and admitting one is how cross-engine conflation happens silently.
 */
export interface EngineScore {
  value: number | null;
  engine: EngineRef;
  semantics: ScoreSemantics;
  state: ScientificState;
}

/**
 * These are ordered but NOT automatically promoted. A value may only advance when the evidence for that specific transition exists. Any US-FIQA score computed through the defective polarity map (B-P01-03) is capped at COMPUTED.
 */
export type ScientificState = "COMPUTED" | "VALIDATED" | "REPRODUCED" | "CONFORMANT" | "PUBLICATION_READY";

/**
 * One ISO-style component. ofiqpy returns (raw, scalar) per component; raw polarity varies per component and is mis-declared upstream for 10 of 27 (B-P01-03), which is why raw and scalar are separate fields and raw carries its own polarity.
 */
export interface QualityComponent {
  name: string;
  raw: number | null;
  scalar: number | null;
  raw_polarity: "quality_magnitude" | "defect_magnitude" | "unknown";
  /**
   * Which revision of the polarity map produced raw_polarity. Required for audit while B-P01-03 is open.
   */
  polarity_map_revision?: string | null;
}

/**
 * The complete component output of ONE extractor on ONE sample. Not comparable element-wise across engines without an explicit comparison method.
 */
export interface QualityVector {
  sample_id: string;
  engine: EngineRef;
  /**
   * @minItems 1
   */
  components: [QualityComponent, ...QualityComponent[]];
  /**
   * Present only when the engine itself emits one. Never synthesised by the studio.
   */
  unified?: EngineScore | null;
  /**
   * Path to the preserved unparsed engine output.
   */
  raw_output?: string | null;
  state: ScientificState;
}

/**
 * A distinct type from QualityVector, forced by P01/C3. ofiq-quality consumes 47 columns of which only 27 are extractor output; the other 20 come from a feature-engineering stage that no published distribution exposes (B-P01-01). Modelling this as a QualityVector would hide that gap.
 */
export interface FeatureTable {
  /**
   * @minItems 1
   */
  columns: [string, ...string[]];
  /**
   * sha256 of the column contract. The known US-FIQA contract is 3b6ec824ab4768410bcb98b9d7f14e391abb25fd0d85f619dfafacbd89872410.
   */
  contract_digest: string;
  column_order_significant: true;
  /**
   * Null is legitimate and currently correct: no packaged producer exists (B-P01-01).
   */
  produced_by: EngineRef | null;
  engineering_stage?: {
    implementation: string;
    polarity_map_revision?: string | null;
    derived_columns?: string[];
  } | null;
  rows?: number;
  storage: "csv" | "parquet";
  path: string;
}

/**
 * Bytes stay on disk and are referenced, never inlined into metadata. classification is required so a restricted sample cannot reach a public export by omission.
 */
export interface ImageSample {
  sample_id: string;
  path: string;
  sha256: string;
  classification: "PUBLIC" | "RESTRICTED" | "PRIVATE" | "SYNTHETIC" | "GENERATED";
  subject_id?: string | null;
  session_id?: string | null;
  /**
   * What permits this sample's use. Required to be non-null for anything but PUBLIC before P05 may import it.
   */
  authorization?: string | null;
  transform_history?: TransformRecord[];
}

/**
 * P05's gate requires interactive preview and batch execution to call the same implementation and agree for deterministic settings. Recording implementation plus both hashes is what makes that checkable rather than asserted.
 */
export interface TransformRecord {
  transform_id: string;
  implementation: string;
  parameters: {};
  seed?: number | null;
  deterministic: boolean;
  input_sha256: string;
  output_sha256: string;
}

export interface ComparisonScore {
  pair_id: string;
  value: number;
  matcher: string;
  semantics: ScoreSemantics;
  label: "genuine" | "impostor" | "unknown";
}

/**
 * Cross-engine comparison must name its method. There is no default, because the default people reach for — compare the raw numbers — is the invalid one.
 */
export interface CrossEngineComparison {
  method:
    | "raw_side_by_side"
    | "rank"
    | "percentile"
    | "standardized"
    | "calibrated_mapping"
    | "correlation"
    | "downstream_utility";
  /**
   * @minItems 2
   */
  engines: [EngineRef, EngineRef, ...EngineRef[]];
  /**
   * Pinned false. No comparison may claim engine scores are numerically equivalent.
   */
  asserts_numeric_equivalence: false;
  /**
   * Per-feature, never one global epsilon.
   */
  tolerance?: number | null;
}

/**
 * Every executable capability enters the studio through this contract. A plugin declares what it needs and what it produces; the registry never infers a capability that was not declared, and never reports a capability as available when its runtime is missing.
 */
export interface OpenFIQAStudioPluginManifest {
  plugin_id: string;
  name: string;
  version: string;
  /**
   * FeatureEngineering is not in the original series list. P01/C3 established it as a required stage between extraction and unified scoring; without a kind for it the gap is unrepresentable.
   */
  kind:
    | "QualityEngine"
    | "Matcher"
    | "Detector"
    | "Landmark"
    | "Transform"
    | "Model"
    | "Trainer"
    | "Evaluator"
    | "Visualizer"
    | "Script"
    | "FeatureEngineering";
  implementation: {
    /**
     * B-P01-06: there is no shared interpreter. python_inprocess is only legal when the plugin imports cleanly in the control plane's own environment, which no engine currently does.
     */
    mode: "python_inprocess" | "python_subprocess" | "cli_subprocess" | "native_binary";
    entry_point: string;
    /**
     * Per-engine environment resolution. Required for every mode except python_inprocess.
     */
    environment?: {
      interpreter?: string | null;
      venv?: string | null;
      env_lock?: string | null;
      /**
       * Environment variables the engine cannot run without. ofiqpy raises FileNotFoundError without OFIQPY_OFIQ_DATA, so this is a hard requirement, not configuration.
       */
      required_env?: {
        [k: string]: string;
      };
      /**
       * Config or weights the engine loads from a repository other than its own. A package's own licence does not cover these, so the supplying repository, commit, and licence are all recorded.
       */
      external_data_dependency?: {
        blocker_id?: string | null;
        supplies: string[];
        from_repository: string;
        from_commit?: string | null;
        license: string;
        note?: string | null;
      } | null;
    } | null;
  };
  /**
   * Typed ports referencing $defs in scientific-objects.schema.json. A port type of FeatureTable is what stops an extractor being wired directly into ofiq-quality.
   */
  ports: {
    inputs: Port[];
    outputs: Port[];
  };
  /**
   * JSON Schema for this plugin's parameters.
   */
  parameter_schema?: {};
  /**
   * "unknown" is a required option, not a convenience. P01 left batch and gpu unresolved for ofiqpy; the registry must be able to say so rather than assert false.
   */
  capabilities: {
    batch: true | false | "unknown";
    gpu: true | false | "unknown";
    deterministic: true | false | "unknown";
  };
  /**
   * How the registry represents an engine it cannot run. A BLOCKED plugin is listed with its reason and refuses execution — it is never hidden, and never presented as working. Symmetrically, AVAILABLE is a claim that must be paid for with a recorded execution.
   */
  availability: {
    [k: string]: any;
  };
  provenance: {
    source_repository?: string | null;
    commit?: string | null;
    license?: string | null;
    public: boolean;
  };
}
export interface Port {
  name: string;
  type:
    | "ImageSample"
    | "Dataset"
    | "QualityVector"
    | "FeatureTable"
    | "EngineScore"
    | "ComparisonScore"
    | "Embedding"
    | "Model"
    | "Artifact"
    | "PairSet";
  cardinality: "one" | "many";
  required: boolean;
}
