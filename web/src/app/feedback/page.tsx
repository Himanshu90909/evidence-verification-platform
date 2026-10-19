"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

interface FeedbackRow {
  id: string;
  rating: number;
  comment: string | null;
  createdAt: string;
  verificationResult: { claim: { text: string } } | null;
}

export default function FeedbackPage() {
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState("");
  const [resultId, setResultId] = useState("");
  const [items, setItems] = useState<FeedbackRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState(false);
  const [loading, setLoading] = useState(false);

  async function load() {
    try {
      const res = await fetch("/api/feedback");
      if (res.status === 401) {
        setError("Authentication required");
        return;
      }
      const d = await res.json();
      setItems(d.feedback ?? []);
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setOk(false);
    setError(null);
    setLoading(true);
    try {
      const body: Record<string, unknown> = { rating, comment: comment || undefined };
      if (resultId.trim()) body.verificationResultId = resultId.trim();
      const res = await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const d = await res.json();
      if (!res.ok) setError(d.error ?? "Failed to submit feedback");
      else {
        setOk(true);
        setComment("");
        setResultId("");
        load();
      }
    } catch {
      setError("Network error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight">Feedback</h1>
      <p className="mt-1 text-sm text-slate-500">
        Rate verification results (1–5). Feedback is stored in PostgreSQL and used for
        error analysis and future model improvements.
      </p>

      <form onSubmit={submit} className="card mt-6 space-y-4">
        <div>
          <label className="label">Rating</label>
          <div className="mt-2 flex gap-1">
            {[1, 2, 3, 4, 5].map((n) => (
              <button
                key={n}
                type="button"
                onClick={() => setRating(n)}
                className={`h-9 w-9 rounded-md border text-sm font-semibold transition ${
                  n <= rating
                    ? "border-slate-700 bg-slate-900 text-white"
                    : "border-slate-300 bg-white text-slate-600 hover:bg-slate-100"
                }`}
              >
                {n}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label htmlFor="comment" className="label">Comment (optional)</label>
          <textarea id="comment" className="input mt-1 min-h-20" value={comment} onChange={(e) => setComment(e.target.value)} />
        </div>
        <div>
          <label htmlFor="resultId" className="label">Verification result ID (optional)</label>
          <input id="resultId" className="input mono mt-1" placeholder="cresult id from history page" value={resultId} onChange={(e) => setResultId(e.target.value)} />
        </div>
        {error && (
          <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
            {error === "Authentication required" && <> <Link href="/login" className="font-semibold underline">Sign in</Link></>}
          </p>
        )}
        {ok && <p className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">Feedback recorded. Thank you.</p>}
        <button type="submit" className="btn-primary" disabled={loading}>
          {loading ? "Submitting…" : "Submit feedback"}
        </button>
      </form>

      {items.length > 0 && (
        <>
          <h2 className="mb-3 mt-8 text-lg font-semibold">Your feedback</h2>
          <div className="space-y-3">
            {items.map((f) => (
              <div key={f.id} className="card">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold">{"★".repeat(f.rating)}{"☆".repeat(5 - f.rating)}</span>
                  <span className="text-xs text-slate-400">{new Date(f.createdAt).toLocaleString()}</span>
                </div>
                {f.comment && <p className="mt-2 text-sm text-slate-700">{f.comment}</p>}
                {f.verificationResult && (
                  <p className="mono mt-2 truncate text-slate-400">on: {f.verificationResult.claim.text}</p>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
