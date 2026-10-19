import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { getSessionUser } from "@/lib/auth";

export const dynamic = "force-dynamic";

export async function GET(_req: NextRequest, { params }: { params: { id: string } }) {
  const user = await getSessionUser();
  if (!user) return NextResponse.json({ error: "Authentication required" }, { status: 401 });

  const claim = await prisma.claim.findFirst({
    where: { id: params.id, userId: user.id },
    include: {
      verificationResults: {
        orderBy: { createdAt: "desc" },
        include: {
          modelVersion: true,
          nliPredictions: { include: { evidence: { include: { source: true } } }, orderBy: { rank: "asc" } },
          retrievalResults: { include: { evidence: true }, orderBy: { rank: "asc" } },
        },
      },
    },
  });
  if (!claim) return NextResponse.json({ error: "Not found" }, { status: 404 });

  return NextResponse.json({ claim });
}
