#!/usr/bin/env node
/**
 * Syncs actual experiment outputs (research/results/*.json) into
 * web/public/research/ so the Research dashboard serves real numbers only.
 * Run after experiments:  node scripts/sync-research.mjs
 */
import { copyFileSync, mkdirSync, readdirSync, existsSync } from "fs";
import { join } from "path";

const SRC = join(process.cwd(), "research", "results");
const DST = join(process.cwd(), "web", "public", "research");

if (!existsSync(SRC)) {
  console.error("No research/results directory. Run the experiments first:");
  console.error("  cd ml-service && python scripts/run_experiments.py");
  process.exit(1);
}

mkdirSync(DST, { recursive: true });
const files = readdirSync(SRC).filter((f) => f.endsWith(".json"));
if (files.length === 0) {
  console.error("research/results contains no JSON files.");
  process.exit(1);
}
for (const f of files) {
  copyFileSync(join(SRC, f), join(DST, f));
  console.log(`synced ${f}`);
}
console.log(`\n${files.length} result file(s) synced to web/public/research/`);
