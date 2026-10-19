import { NextRequest, NextResponse } from "next/server";
import { destroySession, getSessionUser } from "@/lib/auth";
import { writeAudit } from "@/lib/audit";

export async function POST(req: NextRequest) {
  const user = await getSessionUser();
  await destroySession();
  if (user) {
    await writeAudit({
      action: "auth.logout", resourceType: "user", userId: user.id,
      resourceId: user.id, request: req, statusCode: 200,
    });
  }
  return NextResponse.json({ ok: true });
}
