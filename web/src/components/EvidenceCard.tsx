"use client";

import { MlEvidence, MlNliResult } from "@/lib/ml-client";

const NLI_STYLES: Record<string, string> = {
  ENTAILMENT: "bg-emerald-50 text-emerald-700 border-emerald-200",
  CONTRADICTION: "bg-red-50 text-red-700 border-red-200",
  NEUTRAL: "bg-slate-50 text-slate-600 border-slate-200",
};

export default function EvidenceCard({
  evidence,
  nli,
}: {
  evidence: MlEvidence;
  nli?: MlNliResult;
}) {
  return (
    <div className="card">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium text-slate-900">{evidence.page ?? evidence.document_id}</p>
          <p className="mono mt-1 text-slate-400">{evidence.document_id}</p>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <span className={`rounded border px-2 py-0.5 text-xs font-semibold ${NLI_STYLES[nli?.label ?? "NEUTRAL"]}`}>
            NLI: {nli?.label ?? "—"}
          </span>
          <span className="mono text-slate-500">rank #{evidence.rank}</span>
        </div>
      </div>

      <p className="mt-3 text-sm leading-relaxed text-slate-700">{evidence.text}</p>

      <div className="mt-4">
        <div className="flex items-center justify-between">
          <span className="label">Retrieval score</span>
          <span className="mono text-slate-600">{(evidence.score * 100).toFixed(1)}%</span>
        </div>
        <div className="mt-1 h-1.5 w-full rounded-full bg-slate-200">
          <div className="h-1.5 rounded-full bg-slate-700" style={{ width: `${Math.min(evidence.score * 100, 100)}%` }} />
        </div>
      </div>

      {nli && (
        <div className="mt-3 grid grid-cols-3 gap-2 text-center">
          {(["ENTAILMENT", "CONTRADICTION", "NEUTRAL"] as const).map((l) => (
            <div key={l} className="rounded bg-slate-50 px-1 py-1.5">
              <div className="mono text-slate-500">{l.slice(0, 3)}</div>
              <div className="text-xs font-semibold text-slate-800">
                {((nli.probabilities?.[l] ?? 0) * 100).toFixed(1)}%
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="mt-3 flex items-center justify-between border-t border-slate-100 pt-2">
        <span className="text-xs text-slate-500">{evidence.source ?? "FEVER / Wikipedia (research corpus)"}</span>
        {evidence.source_url && (
          <a
            href={evidence.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs font-medium text-slate-600 underline decoration-slate-300 hover:text-slate-900"
          >
            source ↗
          </a>
        )}
      </div>
    </div>
  );
}
