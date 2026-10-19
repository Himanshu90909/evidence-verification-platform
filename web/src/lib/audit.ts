import type { NextRequest } from "next/server";
import { Prisma } from "@prisma/client";
import { prisma } from "@/lib/prisma";

/** Persist a request-level audit row in PostgreSQL. */
export async function writeAudit(params: {
  action: string;
  resourceType: string;
  userId?: string | null;
  resourceId?: string | null;
  request: NextRequest;
  statusCode: number;
  latencyMs?: number;
  metadata?: Record<string, unknown>;
}): Promise<void> {
  try {
    await prisma.auditLog.create({
      data: {
        action: params.action,
        resourceType: params.resourceType,
        userId: params.userId ?? null,
        resourceId: params.resourceId ?? null,
        ipAddress:
          params.request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ?? null,
        userAgent: params.request.headers.get("user-agent") ?? null,
        statusCode: params.statusCode,
        latencyMs: params.latencyMs ?? null,
        metadata: (params.metadata ?? Prisma.JsonNull) === Prisma.JsonNull ? undefined : (JSON.parse(JSON.stringify(params.metadata)) as Prisma.InputJsonValue),
      },
    });
  } catch (err) {
    // Never fail the request because of audit logging; surface in server logs.
    console.error("audit log write failed:", err);
  }
}
