/**
 * Seeds:
 *  - the evidence source registry (FEVER/Wikipedia research corpus)
 *  - Experiment rows from research/results/*.json (REAL experiment outputs;
 *    skipped if no results exist - never fabricates metrics)
 *  - an admin account if ADMIN_EMAIL / ADMIN_PASSWORD are set
 */
import { PrismaClient } from "@prisma/client";
import { readdirSync, readFileSync, existsSync } from "fs";
import { join } from "path";
import bcrypt from "bcryptjs";

const prisma = new PrismaClient();

async function seedEvidenceSources() {
  await prisma.evidenceSource.upsert({
    where: { name: "FEVER / Wikipedia (research corpus)" },
    create: {
      name: "FEVER / Wikipedia (research corpus)",
      url: "https://fever.ai/",
      description:
        "Gold evidence sentences from the FEVER shared task (claim verification " +
        "over Wikipedia). Used as the controlled research corpus for retrieval " +
        "and NLI experiments; not a live web crawl.",
      license: "Wikipedia text: CC BY-SA 3.0; FEVER dataset terms apply.",
    },
    update: {},
  });
  console.log("evidence source seeded");
}

async function seedExperiments() {
  const resultsDir = join(__dirname, "..", "..", "research", "results");
  if (!existsSync(resultsDir)) {
    console.log("no research/results directory - skipping experiment seeding");
    return;
  }
  const files = readdirSync(resultsDir).filter((f) => f.endsWith(".json"));
  if (files.length === 0) {
    console.log("no experiment result files - skipping");
    return;
  }
  let meta: any = null;
  for (const f of files) {
    if (f === "meta.json") {
      meta = JSON.parse(readFileSync(join(resultsDir, f), "utf-8"));
    }
  }
  const modelVersion = await prisma.modelVersion.findFirst({
    where: { name: "hybrid-bm25-dense-nli" },
  });
  for (const f of files) {
    if (f === "meta.json") continue;
    const metrics = JSON.parse(readFileSync(join(resultsDir, f), "utf-8"));
    const name = f.replace(/\.json$/, "").replace(/_/g, "-");
    await prisma.experiment.upsert({
      where: { name },
      create: {
        name,
        description: `Research evaluation: ${name} (loaded from research/results/${f})`,
        mode: "research",
        dataset: meta?.dataset ?? "FEVER validation split",
        metrics,
        resultsPath: `research/results/${f}`,
        modelVersionId: modelVersion?.id ?? null,
      },
      update: { metrics, modelVersionId: modelVersion?.id ?? null },
    });
    console.log(`experiment seeded: ${name}`);
  }
}

async function seedAdmin() {
  const email = process.env.ADMIN_EMAIL;
  const password = process.env.ADMIN_PASSWORD;
  if (!email || !password) return;
  const existing = await prisma.user.findUnique({ where: { email } });
  if (existing) {
    console.log(`admin ${email} already exists`);
    return;
  }
  await prisma.user.create({
    data: {
      email,
      name: "Administrator",
      role: "ADMIN",
      passwordHash: await bcrypt.hash(password, 12),
    },
  });
  console.log(`admin ${email} created`);
}

async function main() {
  await seedEvidenceSources();
  await seedExperiments();
  await seedAdmin();
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
