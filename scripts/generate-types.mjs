/**
 * Generate TypeScript types from the JSON Schema source of truth.
 *
 * ADR-0004 says frontend and backend types may not diverge. Until this script existed that was
 * policy rather than mechanism — someone had to remember. Now the types are generated, and
 * `--check` fails when the committed output no longer matches the schemas, so a schema edit that
 * skips regeneration breaks the build instead of silently shipping a stale frontend type.
 */

import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { compile } from "json-schema-to-typescript";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..");
const SCHEMA_DIR = join(root, "packages", "schemas");
const OUT = join(root, "apps", "desktop", "src", "generated", "schema-types.ts");

const BANNER = `/* eslint-disable */
/**
 * GENERATED FILE — DO NOT EDIT.
 *
 * Source of truth: packages/schemas/*.json (ADR-0004).
 * Regenerate with:  pnpm generate:types
 * CI check:         pnpm check:types-fresh
 */
`;

async function generate() {
  const scientific = JSON.parse(
    await readFile(join(SCHEMA_DIR, "scientific-objects.schema.json"), "utf8"),
  );
  const plugin = JSON.parse(await readFile(join(SCHEMA_DIR, "plugin.schema.json"), "utf8"));

  const chunks = [BANNER];

  // Each $defs entry becomes an exported interface. Compiling them individually (rather than
  // compiling the wrapper object) keeps the emitted names identical to the schema definition
  // names, which is what makes a drift between the two sides visible.
  for (const [name, subschema] of Object.entries(scientific.$defs)) {
    const standalone = { ...subschema, title: name, $defs: scientific.$defs };
    chunks.push(
      await compile(standalone, name, {
        bannerComment: "",
        additionalProperties: false,
        declareExternallyReferenced: false,
        unknownAny: false,
      }),
    );
  }

  chunks.push(
    await compile(plugin, "PluginManifest", {
      bannerComment: "",
      additionalProperties: false,
      unknownAny: false,
    }),
  );

  return chunks.join("\n");
}

const output = await generate();

if (process.argv.includes("--check")) {
  let existing;
  try {
    existing = await readFile(OUT, "utf8");
  } catch {
    console.error(`✗ ${OUT} does not exist. Run: pnpm generate:types`);
    process.exit(1);
  }
  if (existing !== output) {
    console.error(
      "✗ Generated types are stale — packages/schemas has changed since they were written.\n" +
        "  Run: pnpm generate:types",
    );
    process.exit(1);
  }
  console.log("✓ Generated types match the schemas.");
} else {
  await writeFile(OUT, output, "utf8");
  console.log(`✓ Wrote ${OUT}`);
}
