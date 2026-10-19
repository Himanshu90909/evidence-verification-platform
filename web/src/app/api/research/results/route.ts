import { NextResponse } from "next/server";
import { readdir, readFile } from "fs/promises";
import path from "path";

export const dynamic = "force-dynamic";

/**
 * Serves actual experiment outputs produced by the research pipeline
 * (ml-service/scripts/run_experiments.py -> research/results/*.json).
 * The dashboard must never display invented numbers: if no experiment files
 * exist it returns an explicit `available: false` instead of placeholder data.
 */
export async function GET() {
  try {
    const dir = path.join(process.cwd(), "public", "research");
    const files = (await readdir(dir)).filter((f) => f.endsWith(".json"));
    if (files.length === 0) {
      return NextResponse.json({ available: false, results: {} }, { status: 200 });
    }
    const results: Record<string, unknown> = {};
    for (const file of files.sort()) {
      const raw = await readFile(path.join(dir, file), "utf-8");
      try {
        results[file.replace(/\.json$/, "")] = JSON.parse(raw);
      } catch {
        // skip malformed files
      }
    }
    return NextResponse.json({ available: true, results });
  } catch (err) {
    return NextResponse.json(
      { available: false, error: err instanceof Error ? err.message : "unavailable" },
      { status: 200 }
    );
  }
}
