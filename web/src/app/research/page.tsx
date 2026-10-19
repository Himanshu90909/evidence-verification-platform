"use client";

import { useEffect, useState } from "react";

/* eslint-disable @typescript-eslint/no-explicit-any */

interface ResearchData {
  available: boolean;
  results: Record<string, any>;
}

function pct(x: number | undefined | null) {
  return x == null ? "—" : `${(x * 100).toFixed(2)}%`;
}

function MetricBar({ label, value }: { label: string; value: number | null | undefined }) {
  return (
    <div>
      <div className="flex justify-between text-xs">
        <span className="text-slate-500">{label}</span>
        <span className="font-mono font-semibold text-slate-800">{pct(value ?? null)}</span>
      </div>
      <div className="mt-1 h-1.5 rounded-full bg-slate-200">
        <div className="h-1.5 rounded-full bg-slate-700" style={{ width: `${Math.min((value ?? 0) * 100, 100)}%` }} />
      </div>
    </div>
  );
}

export default function ResearchPage() {
  const [data, setData] = useState<ResearchData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/research/results")
      .then((r) => r.json())
      .then(setData)
      .catch(() => setError("Failed to load research results"));
  }, []);

  const r = data?.results ?? {};

  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight">Research / Experiments</h1>
      <p className="mt-1 text-sm text-slate-500">
        Actual experimental results from the research evaluation pipeline (FEVER validation split).
        These values are loaded from experiment output files — never hard-coded.
      </p>

      {error && <p className="mt-4 text-sm text-red-600">{error}</p>}

      {data && !data.available && (
        <div className="card mt-6 border-amber-200 bg-amber-50 text-sm text-amber-800">
          No experiment results found. Run{" "}
          <code className="mono">python ml-service/scripts/run_experiments.py</code> to generate them.
        </div>
      )}

      {/* Meta */}
      {r.meta && (
        <div className="mt-6 grid gap-4 md:grid-cols-4">
          <div className="card"><p className="label">Dataset</p><p className="mono mt-2">{r.meta.dataset}</p></div>
          <div className="card"><p className="label">Eval split / claims</p><p className="mono mt-2">{r.meta.eval_split} · {r.meta.n_nli_claims ?? "—"}</p></div>
          <div className="card"><p className="label">Retrieval queries</p><p className="mono mt-2">{r.meta.n_retrieval_claims ?? "—"}</p></div>
          <div className="card"><p className="label">Pipeline version</p><p className="mono mt-2">{r.meta.pipeline_version ?? "—"} · seed {r.meta.seed ?? "—"}</p></div>
        </div>
      )}

      {/* Retrieval evaluation */}
      {r.retrieval_eval && (
        <section className="mt-8">
          <h2 className="text-lg font-semibold">Retrieval evaluation (gold evidence from FEVER)</h2>
          <div className="mt-3 grid gap-4 md:grid-cols-3">
            {Object.entries(r.retrieval_eval.methods ?? {}).map(([method, m]: any) => (
              <div key={method} className="card">
                <p className="mb-3 font-semibold uppercase tracking-wide">{method}</p>
                <div className="space-y-2.5">
                  <MetricBar label="Recall@5" value={m["recall@5"]} />
                  <MetricBar label="Recall@10" value={m["recall@10"]} />
                  <MetricBar label="MRR@10" value={m["mrr@10"]} />
                  <MetricBar label="nDCG@10" value={m["ndcg@10"]} />
                </div>
                <p className="mono mt-3 text-slate-400">{(m.mean_latency_ms ?? 0).toFixed(1)} ms/query</p>
              </div>
            ))}
          </div>
          <p className="mt-2 text-xs text-slate-500">{r.retrieval_eval.notes}</p>
        </section>
      )}

      {/* NLI evaluation */}
      {r.nli_eval && (
        <section className="mt-8">
          <h2 className="text-lg font-semibold">End-to-end verification (NLI pipeline)</h2>
          <div className="mt-3 grid gap-4 md:grid-cols-2">
            <div className="card">
              <p className="label mb-3">Overall ({r.nli_eval.n_claims} claims)</p>
              <div className="space-y-2.5">
                <MetricBar label="Accuracy" value={r.nli_eval.accuracy} />
                <MetricBar label="Macro-F1" value={r.nli_eval.macro_f1} />
                <MetricBar label="Mean confidence" value={r.nli_eval.mean_confidence} />
              </div>
              <p className="mono mt-3 text-slate-400">
                retrieval {(r.nli_eval.latency_ms?.retrieval_mean ?? 0).toFixed(0)} ms · nli {(r.nli_eval.latency_ms?.nli_mean ?? 0).toFixed(0)} ms · total {(r.nli_eval.latency_ms?.total_mean ?? 0).toFixed(0)} ms
              </p>
            </div>
            <div className="card">
              <p className="label mb-3">Per class</p>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="text-slate-500">
                    <tr>
                      <th className="p-1">class</th><th className="p-1">precision</th>
                      <th className="p-1">recall</th><th className="p-1">F1</th><th className="p-1">n</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(r.nli_eval.per_class ?? {}).map(([cls, m]: any) => (
                      <tr key={cls} className="border-t border-slate-100">
                        <td className="p-1 font-medium">{cls}</td>
                        <td className="p-1">{pct(m.precision)}</td>
                        <td className="p-1">{pct(m.recall)}</td>
                        <td className="p-1">{pct(m.f1)}</td>
                        <td className="p-1 font-mono">{m.support}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* Ablations */}
      {r.ablations && (
        <section className="mt-8">
          <h2 className="text-lg font-semibold">Ablations</h2>
          <div className="mt-3 grid gap-4 md:grid-cols-2">
            <div className="card">
              <p className="label mb-3">Retrieval method → verdict quality</p>
              <table className="w-full text-left text-xs">
                <thead className="text-slate-500">
                  <tr><th className="p-1">method</th><th className="p-1">accuracy</th><th className="p-1">macro-F1</th></tr>
                </thead>
                <tbody>
                  {Object.entries(r.ablations.retrieval_method ?? {}).map(([m, v]: any) => (
                    <tr key={m} className="border-t border-slate-100">
                      <td className="p-1 font-medium">{m}</td>
                      <td className="p-1">{pct(v.accuracy)}</td>
                      <td className="p-1">{pct(v.macro_f1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="card">
              <p className="label mb-3">Top-K → verdict quality</p>
              <table className="w-full text-left text-xs">
                <thead className="text-slate-500">
                  <tr><th className="p-1">top_k</th><th className="p-1">accuracy</th><th className="p-1">macro-F1</th></tr>
                </thead>
                <tbody>
                  {Object.entries(r.ablations.top_k ?? {}).map(([k, v]: any) => (
                    <tr key={k} className="border-t border-slate-100">
                      <td className="p-1 font-medium">{k}</td>
                      <td className="p-1">{pct(v.accuracy)}</td>
                      <td className="p-1">{pct(v.macro_f1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}

      {/* Calibration */}
      {r.calibration && (
        <section className="mt-8">
          <h2 className="text-lg font-semibold">Calibration</h2>
          <div className="mt-3 grid gap-4 md:grid-cols-2">
            <div className="card">
              <p className="label mb-3">Expected Calibration Error (ECE, 10 bins)</p>
              <div className="space-y-2.5">
                <MetricBar label="ECE before temperature scaling" value={r.calibration.ece_before} />
                <MetricBar label="ECE after temperature scaling" value={r.calibration.ece_after} />
              </div>
              <p className="mono mt-3 text-slate-400">T = {r.calibration.temperature}</p>
            </div>
            <div className="card">
              <p className="label mb-3">Reliability (confidence vs accuracy)</p>
              <table className="w-full text-left text-xs">
                <thead className="text-slate-500">
                  <tr><th className="p-1">confidence bin</th><th className="p-1">mean conf</th><th className="p-1">accuracy</th><th className="p-1">n</th></tr>
                </thead>
                <tbody>
                  {(r.calibration.reliability_bins ?? []).map((b: any) => (
                    <tr key={b.bin} className="border-t border-slate-100">
                      <td className="p-1 font-mono">{b.bin}</td>
                      <td className="p-1">{pct(b.mean_confidence)}</td>
                      <td className="p-1">{pct(b.accuracy)}</td>
                      <td className="p-1 font-mono">{b.count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
