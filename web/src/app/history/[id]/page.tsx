"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import VerdictBadge from "@/components/VerdictBadge";

interface ClaimDetail {
  id: string;
  text: string;
  createdAt: string;
  verificationResults: Array<{
    id: string;
    verdict: string;
    confidence: number;
    uncertainty: number;
    status: string;
    errorMessage: string | null;
    topK: number;
    totalLatencyMs: number;
    createdAt: string;
    modelVersion: { name: string; version: string; embeddingModel: string; nliModel: string; retriever: string; configHash: string };
    nliPredictions: Array<{
      id: string;
      label: string;
      entailmentProb: number;
      contradictionProb: number;
      neutralProb: number;
      rank: number;
      evidence: { documentId: string; text: string; page: string | null; source: { name: string; url: string | null } };
    }>;
  }>;
}

export default function ClaimDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [claim, setClaim] = useState<ClaimDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`/api/claims/${id}`)
      .then(async (r) => {
        if (r.status === 401) throw new Error("Authentication required");
        if (r.status === 404) throw new Error("Claim not found");
        if (!r.ok) throw new Error("Failed to load claim");
        return r.json();
      })
      .then((d) => setClaim(d.claim))
      .catch((e) => setError(e.message));
  }, [id]);

  if (error) {
    return (
      <div>
        <Link href="/history" className="text-sm text-slate-500 underline">← back to history</Link>
        <p className="mt-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
      </div>
    );
  }

  if (!claim) return <p className="mt-6 text-sm text-slate-500">Loading…</p>;

  const result = claim.verificationResults[0];

  return (
    <div>
      <Link href="/history" className="text-sm text-slate-500 underline">← back to history</Link>
      <h1 className="mt-4 text-xl font-bold tracking-tight">{claim.text}</h1>
      <p className="mt-1 text-xs text-slate-400">
        first submitted {new Date(claim.createdAt).toLocaleString()} · {claim.verificationResults.length} verification(s)
      </p>

      {!result && <p className="card mt-6 text-sm text-slate-500">No verification result recorded.</p>}

      {result && (
        <>
          <div className="card mt-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <VerdictBadge verdict={result.verdict} large />
              <div className="text-right text-xs text-slate-500">
                <p>confidence <span className="font-semibold text-slate-700">{(result.confidence * 100).toFixed(1)}%</span></p>
                <p>uncertainty <span className="font-semibold text-slate-700">{(result.uncertainty * 100).toFixed(1)}%</span></p>
                {result.status === "FAILED" && <p className="text-red-600">FAILED: {result.errorMessage}</p>}
              </div>
            </div>
            <div className="mt-4 grid gap-2 border-t border-slate-100 pt-4 text-xs text-slate-600 sm:grid-cols-2">
              <p>model: <span className="font-mono">{result.modelVersion.name} v{result.modelVersion.version}</span></p>
              <p>config hash: <span className="font-mono">{result.modelVersion.configHash}</span></p>
              <p>embedding: <span className="font-mono">{result.modelVersion.embeddingModel}</span></p>
              <p>NLI: <span className="font-mono">{result.modelVersion.nliModel}</span></p>
              <p>retriever: <span className="font-mono">{result.modelVersion.retriever}</span></p>
              <p>top_k: <span className="font-mono">{result.topK}</span></p>
            </div>
          </div>

          <h2 className="mb-3 mt-8 text-lg font-semibold">Evidence & NLI</h2>
          <div className="space-y-4">
            {result.nliPredictions.map((n) => (
              <div key={n.id} className="card">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium">{n.evidence.page ?? n.evidence.documentId}</p>
                  <span className="mono text-slate-400">#{n.rank} · {n.label}</span>
                </div>
                <p className="mt-2 text-sm leading-relaxed text-slate-700">{n.evidence.text}</p>
                <div className="mt-3 grid grid-cols-3 gap-2 text-center text-xs">
                  <div className="rounded bg-slate-50 py-1.5">ENT {(n.entailmentProb * 100).toFixed(1)}%</div>
                  <div className="rounded bg-slate-50 py-1.5">CON {(n.contradictionProb * 100).toFixed(1)}%</div>
                  <div className="rounded bg-slate-50 py-1.5">NEU {(n.neutralProb * 100).toFixed(1)}%</div>
                </div>
                <div className="mt-2 flex justify-between text-xs text-slate-500">
                  <span>{n.evidence.source.name}</span>
                  {n.evidence.source.url && (
                    <a href={n.evidence.source.url} target="_blank" rel="noopener noreferrer" className="underline">
                      source ↗
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
