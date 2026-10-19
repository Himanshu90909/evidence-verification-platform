import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { createSession, verifyPassword } from "@/lib/auth";
import { loginSchema } from "@/lib/validation";
import { rateLimit } from "@/lib/rate-limit";
import { writeAudit } from "@/lib/audit";

export async function POST(req: NextRequest) {
  const t0 = Date.now();
  const ip = req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ?? "local";
  const rl = rateLimit(`login:${ip}`, 10, 60_000);
  if (!rl.allowed) {
    return NextResponse.json(
      { error: "Too many login attempts. Try again later." },
      { status: 429, headers: { "Retry-After": String(rl.resetInSeconds) } }
    );
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const parsed = loginSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ error: "Invalid email or password" }, { status: 400 });
  }
  const { email, password } = parsed.data;

  const user = await prisma.user.findUnique({ where: { email } });
  // Constant-ish response regardless of which factor failed.
  if (!user || !(await verifyPassword(password, user.passwordHash))) {
    await writeAudit({
      action: "auth.login", resourceType: "user", request: req,
      statusCode: 401, latencyMs: Date.now() - t0, metadata: { email },
    });
    return NextResponse.json({ error: "Invalid email or password" }, { status: 401 });
  }

  const session = { id: user.id, email: user.email, name: user.name, role: user.role };
  await createSession(session);
  await writeAudit({
    action: "auth.login", resourceType: "user", userId: user.id, resourceId: user.id,
    request: req, statusCode: 200, latencyMs: Date.now() - t0,
  });

  return NextResponse.json({ user: session });
}
