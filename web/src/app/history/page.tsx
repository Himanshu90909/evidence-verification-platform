"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import VerdictBadge from "@/components/VerdictBadge";

interface ClaimRow {
  id: string;
  text: string;
  createdAt: string;
  latestResult: {
    id: string;
    verdict: string;
    confidence: number;
    uncertainty: number;
    status: string;
    createdAt: string;
    modelName: string;
    modelVersion: string;
  } | null;
}

export default function HistoryPage() {
  const [claims, setClaims] = useState<ClaimRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/claims")
      .then(async (r) => {
        if (r.status === 401) throw new Error("Authentication required");
        if (!r.ok) throw new Error("Failed to load history");
        return r.json();
      })
      .then((d) => setClaims(d.claims))
      .catch((e) => setError(e.message));
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight">History</h1>
      <p className="mt-1 text-sm text-slate-500">
        Your claim verification history, with model versions for reproducibility.
      </p>

      {error && (
        <p className="mt-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}{" "}
          <Link href="/login" className="font-semibold underline">
            Sign in
          </Link>
        </p>
      )}

      {claims && claims.length === 0 && (
        <div className="card mt-6 text-sm text-slate-500">
          No claims yet. <Link href="/verify" className="font-semibold underline">Verify a claim</Link>.
        </div>
      )}

      <div className="mt-6 space-y-3">
        {claims?.map((c) => (
          <Link
            key={c.id}
            href={`/history/${c.id}`}
            className="card block transition hover:border-slate-400"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="max-w-2xl truncate text-sm font-medium text-slate-900">{c.text}</p>
              {c.latestResult && <VerdictBadge verdict={c.latestResult.verdict} />}
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
              {c.latestResult ? (
                <>
                  <span>confidence {(c.latestResult.confidence * 100).toFixed(1)}%</span>
                  <span>uncertainty {(c.latestResult.uncertainty * 100).toFixed(1)}%</span>
                  <span className="mono">{c.latestResult.modelName} v{c.latestResult.modelVersion}</span>
                </>
              ) : (
                <span>no result recorded</span>
              )}
              <span>{new Date(c.createdAt).toLocaleString()}</span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
