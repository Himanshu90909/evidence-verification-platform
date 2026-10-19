import Link from "next/link";
import { prisma } from "@/lib/prisma";
import VerdictBadge from "@/components/VerdictBadge";

export const dynamic = "force-dynamic";

async function getStats() {
  const [totalUsers, totalClaims, totalVerifications, byVerdict, avgConf] = await Promise.all([
    prisma.user.count(),
    prisma.claim.count(),
    prisma.verificationResult.findMany({ select: { verdict: true, confidence: true, createdAt: true, status: true } }),
    prisma.verificationResult.groupBy({ by: ["verdict"], _count: { _all: true }, where: { status: "COMPLETED" } }),
    prisma.verificationResult.aggregate({
      _avg: { confidence: true, uncertainty: true, totalLatencyMs: true },
      where: { status: "COMPLETED" },
    }),
  ]);

  const completed = byVerdict.map((g) => ({ verdict: g.verdict, count: g._count._all }));
  const total = completed.reduce((s, g) => s + g.count, 0);
  return {
    totalUsers,
    totalClaims,
    totalVerifications: total,
    completed,
    avgConfidence: avgConf._avg.confidence,
    avgUncertainty: avgConf._avg.uncertainty,
    avgLatencyMs: avgConf._avg.totalLatencyMs,
    totalVerified: totalVerifications.length,
  };
}

export default async function DashboardPage() {
  let stats: Awaited<ReturnType<typeof getStats>> | null = null;
  try {
    stats = await getStats();
  } catch {
    stats = null;
  }

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <p className="mt-1 text-sm text-slate-500">
          Hybrid retrieval (BM25 + dense) with NLI-based verification over a controlled
          FEVER/Wikipedia research corpus.
        </p>
      </div>

      {!stats ? (
        <div className="card border-amber-200 bg-amber-50">
          <p className="text-sm font-medium text-amber-800">Database not reachable.</p>
          <p className="mt-1 text-sm text-amber-700">
            Configure <code className="mono">DATABASE_URL</code> and run{" "}
            <code className="mono">npm run db:migrate</code>. See the README for setup.
          </p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <div className="card">
              <p className="label">Claims verified</p>
              <p className="mt-2 text-3xl font-semibold">{stats.totalVerified}</p>
            </div>
            <div className="card">
              <p className="label">Mean confidence</p>
              <p className="mt-2 text-3xl font-semibold">
                {stats.avgConfidence != null ? `${(stats.avgConfidence * 100).toFixed(1)}%` : "—"}
              </p>
            </div>
            <div className="card">
              <p className="label">Mean uncertainty</p>
              <p className="mt-2 text-3xl font-semibold">
                {stats.avgUncertainty != null ? `${(stats.avgUncertainty * 100).toFixed(1)}%` : "—"}
              </p>
            </div>
            <div className="card">
              <p className="label">Mean latency</p>
              <p className="mt-2 text-3xl font-semibold">
                {stats.avgLatencyMs != null ? `${Math.round(stats.avgLatencyMs)} ms` : "—"}
              </p>
            </div>
          </div>

          <div className="mt-6 grid gap-6 md:grid-cols-2">
            <div className="card">
              <p className="label mb-3">Verdict distribution</p>
              {stats.totalVerifications === 0 ? (
                <p className="text-sm text-slate-500">
                  No verifications yet. <Link href="/verify" className="underline">Verify your first claim</Link>.
                </p>
              ) : (
                <div className="space-y-3">
                  {stats.completed.map((g) => (
                    <div key={g.verdict}>
                      <div className="mb-1 flex items-center justify-between">
                        <VerdictBadge verdict={g.verdict} />
                        <span className="text-xs text-slate-500">
                          {g.count} ({((g.count / stats!.totalVerifications) * 100).toFixed(1)}%)
                        </span>
                      </div>
                      <div className="h-2 rounded-full bg-slate-200">
                        <div
                          className="h-2 rounded-full bg-slate-700"
                          style={{ width: `${(g.count / Math.max(stats!.totalVerifications, 1)) * 100}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="card">
              <p className="label mb-3">Pipeline</p>
              <ol className="space-y-1.5 text-sm text-slate-600">
                {[
                  "BM25 sparse retrieval",
                  "Dense retrieval (sentence embeddings + FAISS)",
                  "Hybrid fusion (reciprocal rank fusion)",
                  "NLI evidence reranking",
                  "Multi-evidence weighted aggregation",
                  "Uncertainty estimation (entropy + calibration)",
                ].map((s, i) => (
                  <li key={s} className="flex gap-2">
                    <span className="mono text-slate-400">{i + 1}.</span> {s}
                  </li>
                ))}
              </ol>
              <Link href="/verify" className="btn-primary mt-4">
                Verify a claim
              </Link>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
