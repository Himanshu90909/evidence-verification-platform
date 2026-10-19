"use client";

import Link from "next/link";
import { useState } from "react";
import EvidenceCard from "@/components/EvidenceCard";
import type { MlRetrieveResponse } from "@/lib/ml-client";

export default function EvidencePage() {
  const [query, setQuery] = useState("");
  const [method, setMethod] = useState<"bm25" | "dense" | "hybrid">("hybrid");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<MlRetrieveResponse | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    setLoading(true);
    try {
      const res = await fetch("/api/evidence/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, topK: 10, method }),
      });
      const data = await res.json();
      if (!res.ok) setError(data.error ?? "Search failed");
      else setResult(data);
    } catch {
      setError("Network error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight">Evidence Analysis</h1>
      <p className="mt-1 text-sm text-slate-500">
        Search the controlled FEVER/Wikipedia research corpus. Compare retrieval methods (BM25,
        dense, hybrid) on the same query.
      </p>

      <form onSubmit={submit} className="card mt-6">
        <label htmlFor="query" className="label">Query</label>
        <div className="mt-2 flex gap-2">
          <input
            id="query"
            className="input"
            placeholder="e.g. Nikola Tesla patents"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            required
            minLength={2}
          />
          <select
            className="input w-32"
            value={method}
            onChange={(e) => setMethod(e.target.value as typeof method)}
          >
            <option value="hybrid">hybrid</option>
            <option value="bm25">bm25</option>
            <option value="dense">dense</option>
          </select>
          <button type="submit" className="btn-primary whitespace-nowrap" disabled={loading || query.trim().length < 2}>
            {loading ? "Searching…" : "Search"}
          </button>
        </div>
        {error && (
          <p className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
            {error === "Authentication required" && (
              <> <Link href="/login" className="font-semibold underline">Sign in</Link></>
            )}
          </p>
        )}
      </form>

      {result && (
        <>
          <p className="mt-6 text-xs text-slate-500">
            {result.retrieval.n_documents_searched.toLocaleString()} documents searched ·{" "}
            {result.retrieval.method} · {result.retrieval.latency_ms.toFixed(0)} ms
          </p>
          <div className="mt-3 grid gap-4 lg:grid-cols-2">
            {result.evidence.map((ev) => (
              <EvidenceCard key={ev.document_id} evidence={ev} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
