import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { getSessionUser } from "@/lib/auth";

export const dynamic = "force-dynamic";

export async function GET() {
  const user = await getSessionUser();
  if (!user) return NextResponse.json({ error: "Authentication required" }, { status: 401 });

  const claims = await prisma.claim.findMany({
    where: { userId: user.id },
    orderBy: { createdAt: "desc" },
    take: 50,
    include: {
      verificationResults: {
        orderBy: { createdAt: "desc" },
        take: 1,
        include: { modelVersion: true },
      },
    },
  });

  return NextResponse.json({
    claims: claims.map((c) => ({
      id: c.id,
      text: c.text,
      createdAt: c.createdAt,
      latestResult: c.verificationResults[0]
        ? {
            id: c.verificationResults[0].id,
            verdict: c.verificationResults[0].verdict,
            confidence: c.verificationResults[0].confidence,
            uncertainty: c.verificationResults[0].uncertainty,
            status: c.verificationResults[0].status,
            createdAt: c.verificationResults[0].createdAt,
            modelName: c.verificationResults[0].modelVersion.name,
            modelVersion: c.verificationResults[0].modelVersion.version,
          }
        : null,
    })),
  });
}
