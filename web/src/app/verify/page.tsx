"use client";

import Link from "next/link";
import { useState } from "react";
import VerdictBadge from "@/components/VerdictBadge";
import EvidenceCard from "@/components/EvidenceCard";
import type { MlVerifyResponse } from "@/lib/ml-client";

export default function VerifyPage() {
  const [claim, setClaim] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<MlVerifyResponse | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    setLoading(true);
    try {
      const res = await fetch("/api/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ claim }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "Verification failed");
      } else {
        setResult(data);
      }
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight">Claim Verification</h1>
      <p className="mt-1 text-sm text-slate-500">
        Submit a claim. Evidence is retrieved from the indexed research corpus and judged with NLI.
        Nothing is fabricated: every passage shown comes from the corpus with its source metadata.
      </p>

      <form onSubmit={submit} className="card mt-6">
        <label htmlFor="claim" className="label">
          Claim
        </label>
        <textarea
          id="claim"
          className="input mt-2 min-h-24"
          placeholder="e.g. The Eiffel Tower is located in Paris."
          value={claim}
          maxLength={2000}
          onChange={(e) => setClaim(e.target.value)}
          required
          minLength={3}
        />
        <div className="mt-3 flex items-center justify-between">
          <span className="text-xs text-slate-400">{claim.length}/2000</span>
          <button type="submit" className="btn-primary" disabled={loading || claim.trim().length < 3}>
            {loading ? "Verifying…" : "Verify claim"}
          </button>
        </div>
        {error && (
          <p className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
            {error === "Authentication required" && (
              <>
                {" "}
                <Link href="/login" className="font-semibold underline">
                  Sign in
                </Link>
              </>
            )}
          </p>
        )}
      </form>

      {result && (
        <div className="mt-8">
          <div className="card">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-4">
                <VerdictBadge verdict={result.verdict} large />
                <div>
                  <div className="flex items-baseline gap-2">
                    <span className="text-2xl font-semibold">{(result.confidence * 100).toFixed(1)}%</span>
                    <span className="label">confidence</span>
                  </div>
                  <div className="mt-1 flex items-baseline gap-2">
                    <span className="text-lg font-semibold text-slate-500">
                      {(result.uncertainty * 100).toFixed(1)}%
                    </span>
                    <span className="label">uncertainty (normalized entropy)</span>
                  </div>
                </div>
              </div>
              <div className="text-right text-xs text-slate-500">
                <p>
                  model <span className="font-semibold text-slate-700">{result.model.model} v{result.model.version}</span>
                </p>
                <p className="mono mt-0.5">config {result.model.config_hash}</p>
                <p className="mono mt-0.5">
                  {result.retrieval.method} · top_k {result.retrieval.top_k} · {result.latency_ms.toFixed(0)} ms
                </p>
              </div>
            </div>
            {result.explanation?.steps ? (
              <details className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3">
                <summary className="cursor-pointer text-sm font-medium text-slate-700">
                  Decision path
                </summary>
                <ol className="mt-2 space-y-1 text-xs text-slate-600">
                  {(result.explanation.steps as string[]).map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ol>
              </details>
            ) : null}
          </div>

          <h2 className="mb-3 mt-8 text-lg font-semibold">Evidence ({result.evidence.length})</h2>
          <div className="grid gap-4 lg:grid-cols-2">
            {result.evidence.map((ev) => (
              <EvidenceCard
                key={ev.document_id}
                evidence={ev}
                nli={result.nli.find((n) => n.document_id === ev.document_id)}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
