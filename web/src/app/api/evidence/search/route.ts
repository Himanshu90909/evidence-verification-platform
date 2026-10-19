import { NextRequest, NextResponse } from "next/server";
import { getSessionUser } from "@/lib/auth";
import { evidenceSearchSchema } from "@/lib/validation";
import { rateLimit } from "@/lib/rate-limit";
import { writeAudit } from "@/lib/audit";
import { MlServiceError, mlRetrieve } from "@/lib/ml-client";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const user = await getSessionUser();
  if (!user) return NextResponse.json({ error: "Authentication required" }, { status: 401 });

  const rl = rateLimit(`evidence:${user.id}`, 30, 60_000);
  if (!rl.allowed) {
    return NextResponse.json({ error: "Rate limit reached" }, { status: 429 });
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const parsed = evidenceSearchSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: "Validation failed", issues: parsed.error.flatten().fieldErrors },
      { status: 400 }
    );
  }

  try {
    const ml = await mlRetrieve(parsed.data.query, parsed.data.topK, parsed.data.method);
    await writeAudit({
      action: "evidence.search", resourceType: "evidence", userId: user.id,
      request: req, statusCode: 200,
    });
    return NextResponse.json(ml);
  } catch (err) {
    const status = err instanceof MlServiceError ? err.status : 500;
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Evidence search failed" },
      { status }
    );
  }
}
