import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { mlHealth } from "@/lib/ml-client";

export const dynamic = "force-dynamic";

export async function GET() {
  const status = {
    web: "ok",
    database: "unknown",
    mlService: "unknown",
  };

  try {
    await prisma.$queryRaw`SELECT 1`;
    status.database = "ok";
  } catch {
    status.database = "error";
  }

  try {
    const ml = await mlHealth(4000);
    status.mlService = ml.status;
  } catch {
    status.mlService = "unreachable";
  }

  const ok = status.database === "ok" && ["ok", "degraded", "loading"].includes(status.mlService);
  return NextResponse.json({ status: ok ? "ok" : "degraded", ...status }, { status: 200 });
}
