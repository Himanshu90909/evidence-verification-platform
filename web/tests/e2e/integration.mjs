#!/usr/bin/env node
/**
 * End-to-end integration test: Claim -> Web API -> ML service -> PostgreSQL.
 *
 * Prerequisites:
 *   - PostgreSQL running (DATABASE_URL set in web/.env)
 *   - ML service running (ML_API_URL, MODEL_SERVICE_KEY set)
 *   - web dev/prod server running on WEB_URL (default http://localhost:3000)
 *
 * Usage: node tests/e2e/integration.mjs
 */
import { randomUUID } from "crypto";

const WEB_URL = process.env.WEB_URL ?? "http://localhost:3000";
const EMAIL = `e2e_${randomUUID().slice(0, 8)}@example.com`;
const PASSWORD = "e2e-test-password-123";

let failures = 0;
function check(name, cond, extra = "") {
  const ok = Boolean(cond);
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${ok ? "" : "  " + extra}`);
  if (!ok) failures += 1;
}

async function api(path, opts = {}) {
  const res = await fetch(`${WEB_URL}${path}`, opts);
  let body = null;
  try {
    body = await res.json();
  } catch {
    /* no body */
  }
  return { res, body };
}

function cookieOf(res) {
  const set = res.headers.get("set-cookie");
  return set ? set.split(";")[0] : null;
}

async function main() {
  console.log(`E2E against ${WEB_URL}\n`);

  // --- service health
  const health = await api("/api/health");
  check("web /api/health responds", health.res.status === 200);
  check("database reachable", health.body?.database === "ok", JSON.stringify(health.body));
  check(
    "ML service reachable",
    ["ok", "degraded", "loading"].includes(health.body?.mlService ?? "unreachable"),
    JSON.stringify(health.body)
  );

  // --- auth
  const reg = await api("/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: EMAIL, password: PASSWORD }),
  });
  check("registration succeeds", reg.res.status === 201, JSON.stringify(reg.body));
  const cookie = cookieOf(reg.res) ?? cookieOf((await api("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: EMAIL, password: PASSWORD }),
  })).res);
  check("session cookie set", Boolean(cookie));
  const auth = { "Content-Type": "application/json", Cookie: cookie ?? "" };

  // --- input validation
  const badClaim = await api("/api/verify", {
    method: "POST", headers: auth, body: JSON.stringify({ claim: "no" }),
  });
  check("claim validation rejects short input", badClaim.res.status === 400);

  const unauth = await fetch(`${WEB_URL}/api/verify`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ claim: "The Eiffel Tower is in Paris." }),
  });
  check("verify requires authentication", unauth.status === 401);

  // --- claim verification (web -> ml -> postgres)
  const verify = await api("/api/verify", {
    method: "POST",
    headers: auth,
    body: JSON.stringify({ claim: "The Eiffel Tower is a lattice tower located in Paris, France." }),
  });
  check("verification returns 200", verify.res.status === 200, JSON.stringify(verify.body));
  const v = verify.body;
  if (v?.verdict) {
    check("verdict is valid", ["SUPPORTED", "REFUTED", "NOT_ENOUGH_INFORMATION"].includes(v.verdict));
    check("confidence in [0,1]", v.confidence >= 0 && v.confidence <= 1);
    check("uncertainty in [0,1]", v.uncertainty >= 0 && v.uncertainty <= 1);
    check("evidence returned with metadata", Array.isArray(v.evidence) && v.evidence.length > 0
      && v.evidence.every((e) => e.document_id && e.text && e.source_url));
    check("model version recorded", Boolean(v.model?.version && v.model?.config_hash));
  }

  // --- persistence
  const history = await api("/api/claims", { headers: auth });
  check("history endpoint works", history.res.status === 200);
  const entry = history.body?.claims?.find((c) =>
    c.text.includes("Eiffel Tower")
  );
  check("claim persisted in PostgreSQL", Boolean(entry), JSON.stringify(history.body?.claims?.slice(0, 3)));
  check(
    "verification result persisted",
    entry?.latestResult && ["SUPPORTED", "REFUTED", "NOT_ENOUGH_INFORMATION"].includes(entry.latestResult.verdict),
    JSON.stringify(entry?.latestResult)
  );

  // --- detail page data
  const detail = await api(`/api/claims/${entry?.id}`, { headers: auth });
  check("claim detail includes NLI predictions", (detail.body?.claim?.verificationResults?.[0]?.nliPredictions?.length ?? 0) > 0);

  // --- model info
  const model = await api("/api/model-info", { headers: auth });
  check("model-info works", model.res.status === 200 && Boolean(model.body?.service?.pipeline?.version));

  // --- feedback
  const fb = await api("/api/feedback", {
    method: "POST",
    headers: auth,
    body: JSON.stringify({ rating: 5, comment: "e2e smoke test", verificationResultId: v?.resultId }),
  });
  check("feedback stored", fb.res.status === 201, JSON.stringify(fb.body));

  console.log(`\n${failures === 0 ? "ALL CHECKS PASSED" : failures + " CHECK(S) FAILED"}`);
  process.exit(failures === 0 ? 0 : 1);
}

main().catch((e) => {
  console.error("E2E crashed:", e);
  process.exit(1);
});
