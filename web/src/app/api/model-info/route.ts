import { NextResponse } from "next/server";
import { getSessionUser } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { MlServiceError, mlModelInfo } from "@/lib/ml-client";

export const dynamic = "force-dynamic";

export async function GET() {
  const user = await getSessionUser();
  if (!user) return NextResponse.json({ error: "Authentication required" }, { status: 401 });

  try {
    const ml = await mlModelInfo();
    const dbVersions = await prisma.modelVersion.findMany({
      orderBy: { createdAt: "desc" },
      take: 10,
      include: { _count: { select: { verificationResults: true } } },
    });
    return NextResponse.json({
      service: ml,
      dbVersions: dbVersions.map((v) => ({
        id: v.id,
        name: v.name,
        version: v.version,
        embeddingModel: v.embeddingModel,
        nliModel: v.nliModel,
        nliBackend: v.nliBackend,
        retriever: v.retriever,
        temperature: v.temperature,
        configHash: v.configHash,
        createdAt: v.createdAt,
        predictionsCount: v._count.verificationResults,
      })),
    });
  } catch (err) {
    const status = err instanceof MlServiceError ? err.status : 500;
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "ML service unavailable" },
      { status }
    );
  }
}
