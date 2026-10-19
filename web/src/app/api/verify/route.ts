import { NextRequest, NextResponse } from "next/server";
import { randomUUID } from "crypto";
import { prisma } from "@/lib/prisma";
import { getSessionUser } from "@/lib/auth";
import { verifySchema } from "@/lib/validation";
import { rateLimit } from "@/lib/rate-limit";
import { writeAudit } from "@/lib/audit";
import { MlServiceError, mlVerify } from "@/lib/ml-client";
import type { MlVerifyResponse } from "@/lib/ml-client";

export const dynamic = "force-dynamic";

// Up to 20 verifications per minute per user (best-effort; see lib/rate-limit).
const VERIFY_LIMIT = 20;
const VERIFY_WINDOW_MS = 60_000;

async function persistVerification(
  userId: string,
  ml: MlVerifyResponse,
  requestId: string
): Promise<string> {
  const claim = await prisma.claim.upsert({
    where: { userId_text: { userId, text: ml.claim } },
    create: { userId, text: ml.claim },
    update: {},
  });

  const modelVersion = await prisma.modelVersion.upsert({
    where: {
      name_version_configHash: {
        name: ml.model.model,
        version: ml.model.version,
        configHash: ml.model.config_hash,
      },
    },
    create: {
      name: ml.model.model,
      version: ml.model.version,
      embeddingModel: ml.model.embedding_model,
      nliModel: ml.model.nli_model,
      retriever: ml.model.retriever,
      nliBackend: ml.model.nli_backend,
      configHash: ml.model.config_hash,
      temperature: ml.model.temperature,
      config: { top_k: ml.retrieval.top_k, min_evidence_prob: null, pipeline: "hybrid-nli" },
    },
    update: {},
  });

  const evidenceSourceName = ml.evidence[0]?.source ?? "FEVER / Wikipedia (research corpus)";
  const source = await prisma.evidenceSource.upsert({
    where: { name: evidenceSourceName },
    create: {
      name: evidenceSourceName,
      url: ml.evidence[0]?.source_url ?? null,
      description:
        "Gold evidence sentences from the FEVER shared task, derived from Wikipedia. Used as the controlled research corpus.",
      license: "CC BY-SA 3.0 (Wikipedia text); FEVER dataset terms apply.",
    },
    update: {},
  });

  const evidenceRecords = await Promise.all(
    ml.evidence.map((ev) =>
      prisma.evidence.upsert({
        where: { documentId: ev.document_id },
        create: {
          documentId: ev.document_id,
          text: ev.text,
          page: ev.page ?? null,
          lineId: ev.line_id ?? null,
          sourceId: source.id,
        },
        update: {},
      })
    )
  );
  const evidenceByDocId = new Map(evidenceRecords.map((e) => [e.documentId, e]));

  const result = await prisma.verificationResult.create({
    data: {
      claimId: claim.id,
      modelVersionId: modelVersion.id,
      verdict: ml.verdict,
      confidence: ml.confidence,
      uncertainty: ml.uncertainty,
      status: "COMPLETED",
      retrievalMethod: "HYBRID",
      topK: ml.retrieval.top_k,
      evidenceUsed: ml.evidence.length,
      retrievalLatencyMs: ml.retrieval.latency_ms,
      nliLatencyMs: (ml.explanation as { stage_latencies?: { nli?: number } } | null)?.stage_latencies?.nli
        ?? ml.latency_ms - ml.retrieval.latency_ms,
      totalLatencyMs: ml.latency_ms,
      requestId,
      retrievalResults: {
        create: ml.evidence.map((ev) => ({
          evidenceId: evidenceByDocId.get(ev.document_id)!.id,
          method: "HYBRID",
          score: ev.score,
          rank: ev.rank,
        })),
      },
      nliPredictions: {
        create: ml.nli.map((n) => ({
          evidenceId: evidenceByDocId.get(n.document_id)!.id,
          label: n.label,
          entailmentProb: n.probabilities.ENTAILMENT ?? 0,
          contradictionProb: n.probabilities.CONTRADICTION ?? 0,
          neutralProb: n.probabilities.NEUTRAL ?? 0,
          rank: evidenceByDocId.get(n.document_id) ? ml.evidence.findIndex((e) => e.document_id === n.document_id) + 1 : 0,
          isTopEvidence: n.is_top_evidence,
        })),
      },
    },
  });

  return result.id;
}

export async function POST(req: NextRequest) {
  const t0 = Date.now();
  const user = await getSessionUser();
  if (!user) {
    return NextResponse.json({ error: "Authentication required" }, { status: 401 });
  }

  const rl = rateLimit(`verify:${user.id}`, VERIFY_LIMIT, VERIFY_WINDOW_MS);
  if (!rl.allowed) {
    await writeAudit({
      action: "verify.rate_limited", resourceType: "verification", userId: user.id,
      request: req, statusCode: 429,
    });
    return NextResponse.json(
      { error: "Rate limit reached. Please wait before submitting another claim." },
      { status: 429, headers: { "Retry-After": String(rl.resetInSeconds) } }
    );
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const parsed = verifySchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: "Validation failed", issues: parsed.error.flatten().fieldErrors },
      { status: 400 }
    );
  }

  const requestId = randomUUID();
  try {
    const ml = await mlVerify(parsed.data.claim, parsed.data.topK);
    const resultId = await persistVerification(user.id, ml, requestId);
    await writeAudit({
      action: "verify.completed", resourceType: "verification", userId: user.id,
      resourceId: resultId, request: req, statusCode: 200,
      latencyMs: Date.now() - t0,
      metadata: { verdict: ml.verdict, model: ml.model.model, version: ml.model.version },
    });
    return NextResponse.json({ requestId, resultId, ...ml });
  } catch (err) {
    const status = err instanceof MlServiceError ? err.status : 500;
    const message = err instanceof Error ? err.message : "Verification failed";
    // Record the failed request too (production monitoring).
    try {
      const claim = await prisma.claim.upsert({
        where: { userId_text: { userId: user.id, text: parsed.data.claim } },
        create: { userId: user.id, text: parsed.data.claim },
        update: {},
      });
      await prisma.verificationResult.create({
        data: {
          claimId: claim.id,
          modelVersionId: (
            await prisma.modelVersion.findFirst({ orderBy: { createdAt: "desc" } })
          )?.id ?? (await prisma.modelVersion.create({
            data: {
              name: "unavailable", version: "0.0.0", embeddingModel: "unknown",
              nliModel: "unknown", retriever: "unknown", configHash: requestId.slice(0, 12),
              config: {},
            },
          })).id,
          verdict: "NOT_ENOUGH_INFORMATION",
          confidence: 0, uncertainty: 1, status: "FAILED",
          errorMessage: message.slice(0, 500),
          topK: 0, evidenceUsed: 0,
          retrievalLatencyMs: 0, nliLatencyMs: 0, totalLatencyMs: Date.now() - t0,
          requestId,
        },
      });
    } catch (persistErr) {
      console.error("Failed to record failed verification:", persistErr);
    }
    await writeAudit({
      action: "verify.failed", resourceType: "verification", userId: user.id,
      request: req, statusCode: status, latencyMs: Date.now() - t0,
      metadata: { error: message },
    });
    return NextResponse.json({ error: message, requestId }, { status });
  }
}
