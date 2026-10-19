"use client";

import { useEffect, useState } from "react";

interface ModelInfo {
  service: {
    service_version: string;
    pipeline: {
      model: string; version: string; embedding_model: string; retriever: string;
      nli_model: string; nli_backend: string; temperature: number; config_hash: string;
    };
    corpus_documents: number;
    metrics: {
      request_count: number; error_count: number; error_rate: number;
      mean_confidence: number | null;
      verdict_distribution: Record<string, number>;
      stage_latencies_ms: Record<string, { mean_ms: number; max_ms: number; count: number }>;
    };
  };
  dbVersions: Array<{
    id: string; name: string; version: string; embeddingModel: string; nliModel: string;
    nliBackend: string; retriever: string; temperature: number; configHash: string;
    createdAt: string; predictionsCount: number;
  }>;
}

export default function ModelPage() {
  const [info, setInfo] = useState<ModelInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/model-info")
      .then(async (r) => {
        if (r.status === 401) throw new Error("Authentication required");
        if (!r.ok) throw new Error((await r.json()).error ?? "Failed to load model info");
        return r.json();
      })
      .then(setInfo)
      .catch((e) => setError(e.message));
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight">Model Information</h1>
      <p className="mt-1 text-sm text-slate-500">
        Live model card of the ML inference service plus all model versions that have produced
        stored predictions.
      </p>

      {error && (
        <p className="mt-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
      )}

      {info && (
        <>
          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <div className="card">
              <p className="label mb-2">Active pipeline (service v{info.service.service_version})</p>
              <dl className="space-y-1.5 text-sm">
                {[
                  ["pipeline", info.service.pipeline.model],
                  ["version", info.service.pipeline.version],
                  ["embedding model", info.service.pipeline.embedding_model],
                  ["retriever", info.service.pipeline.retriever],
                  ["NLI model", info.service.pipeline.nli_model],
                  ["NLI backend", info.service.pipeline.nli_backend],
                  ["temperature", String(info.service.pipeline.temperature)],
                  ["config hash", info.service.pipeline.config_hash],
                  ["corpus documents", info.service.corpus_documents.toLocaleString()],
                ].map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-4">
                    <dt className="text-slate-500">{k}</dt>
                    <dd className="mono text-right text-slate-800">{v}</dd>
                  </div>
                ))}
              </dl>
            </div>

            <div className="card">
              <p className="label mb-2">Live service metrics</p>
              <dl className="space-y-1.5 text-sm">
                <div className="flex justify-between"><dt className="text-slate-500">requests</dt><dd className="font-mono">{info.service.metrics.request_count}</dd></div>
                <div className="flex justify-between"><dt className="text-slate-500">errors</dt><dd className="font-mono">{info.service.metrics.error_count} ({(info.service.metrics.error_rate * 100).toFixed(2)}%)</dd></div>
                <div className="flex justify-between"><dt className="text-slate-500">mean confidence</dt><dd className="font-mono">{info.service.metrics.mean_confidence != null ? (info.service.metrics.mean_confidence * 100).toFixed(1) + "%" : "—"}</dd></div>
                {Object.entries(info.service.metrics.stage_latencies_ms).map(([stage, s]) => (
                  <div key={stage} className="flex justify-between">
                    <dt className="text-slate-500">{stage} latency (mean/max)</dt>
                    <dd className="font-mono">{s.mean_ms} / {s.max_ms} ms</dd>
                  </div>
                ))}
              </dl>
              {Object.keys(info.service.metrics.verdict_distribution).length > 0 && (
                <>
                  <p className="label mb-1 mt-3">Prediction distribution</p>
                  <div className="space-y-1 text-xs">
                    {Object.entries(info.service.metrics.verdict_distribution).map(([v, c]) => (
                      <div key={v} className="flex justify-between"><span className="text-slate-500">{v}</span><span className="font-mono">{c}</span></div>
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>

          <h2 className="mb-3 mt-8 text-lg font-semibold">Recorded model versions (PostgreSQL)</h2>
          {info.dbVersions.length === 0 ? (
            <p className="text-sm text-slate-500">No versions recorded yet.</p>
          ) : (
            <div className="card overflow-x-auto p-0">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-slate-200 text-slate-500">
                  <tr>
                    <th className="p-3">model</th><th className="p-3">version</th><th className="p-3">embedding</th>
                    <th className="p-3">NLI</th><th className="p-3">backend</th><th className="p-3">predictions</th><th className="p-3">since</th>
                  </tr>
                </thead>
                <tbody>
                  {info.dbVersions.map((v) => (
                    <tr key={v.id} className="border-b border-slate-100">
                      <td className="p-3 font-medium">{v.name}</td>
                      <td className="p-3 font-mono">{v.version}</td>
                      <td className="p-3">{v.embeddingModel}</td>
                      <td className="p-3">{v.nliModel}</td>
                      <td className="p-3">{v.nliBackend}</td>
                      <td className="p-3 font-mono">{v.predictionsCount}</td>
                      <td className="p-3">{new Date(v.createdAt).toLocaleDateString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
