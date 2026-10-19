import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { getSessionUser } from "@/lib/auth";
import { feedbackSchema } from "@/lib/validation";
import { writeAudit } from "@/lib/audit";

export const dynamic = "force-dynamic";

export async function GET() {
  const user = await getSessionUser();
  if (!user) return NextResponse.json({ error: "Authentication required" }, { status: 401 });

  const feedback = await prisma.feedback.findMany({
    where: { userId: user.id },
    orderBy: { createdAt: "desc" },
    take: 50,
    include: { verificationResult: { include: { claim: true, modelVersion: true } } },
  });
  return NextResponse.json({ feedback });
}

export async function POST(req: NextRequest) {
  const user = await getSessionUser();
  if (!user) return NextResponse.json({ error: "Authentication required" }, { status: 401 });

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const parsed = feedbackSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: "Validation failed", issues: parsed.error.flatten().fieldErrors },
      { status: 400 }
    );
  }

  const { rating, comment, verificationResultId } = parsed.data;

  if (verificationResultId) {
    const result = await prisma.verificationResult.findFirst({
      where: { id: verificationResultId, claim: { userId: user.id } },
    });
    if (!result) {
      return NextResponse.json({ error: "Verification result not found" }, { status: 404 });
    }
  }

  const fb = await prisma.feedback.create({
    data: { userId: user.id, rating, comment, verificationResultId },
  });
  await writeAudit({
    action: "feedback.created", resourceType: "feedback", userId: user.id,
    resourceId: fb.id, request: req, statusCode: 201,
  });
  return NextResponse.json({ feedback: fb }, { status: 201 });
}
