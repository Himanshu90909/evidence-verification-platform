-- CreateEnum
CREATE TYPE "Role" AS ENUM ('USER', 'ADMIN');

-- CreateEnum
CREATE TYPE "Verdict" AS ENUM ('SUPPORTED', 'REFUTED', 'NOT_ENOUGH_INFORMATION');

-- CreateEnum
CREATE TYPE "NliLabel" AS ENUM ('ENTAILMENT', 'CONTRADICTION', 'NEUTRAL');

-- CreateEnum
CREATE TYPE "RetrievalMethod" AS ENUM ('BM25', 'DENSE', 'HYBRID');

-- CreateEnum
CREATE TYPE "RequestStatus" AS ENUM ('COMPLETED', 'FAILED');

-- CreateTable
CREATE TABLE "User" (
    "id" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "password_hash" TEXT NOT NULL,
    "name" TEXT,
    "role" "Role" NOT NULL DEFAULT 'USER',
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "User_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Claim" (
    "id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "text" TEXT NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Claim_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ModelVersion" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "version" TEXT NOT NULL,
    "embedding_model" TEXT NOT NULL,
    "nli_model" TEXT NOT NULL,
    "retriever" TEXT NOT NULL,
    "nli_backend" TEXT NOT NULL DEFAULT 'transformers',
    "config_hash" TEXT NOT NULL,
    "temperature" DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    "config" JSONB NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ModelVersion_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "VerificationResult" (
    "id" TEXT NOT NULL,
    "claim_id" TEXT NOT NULL,
    "model_version_id" TEXT NOT NULL,
    "verdict" "Verdict" NOT NULL,
    "confidence" DOUBLE PRECISION NOT NULL,
    "uncertainty" DOUBLE PRECISION NOT NULL,
    "status" "RequestStatus" NOT NULL DEFAULT 'COMPLETED',
    "error_message" TEXT,
    "retrieval_method" "RetrievalMethod" NOT NULL DEFAULT 'HYBRID',
    "top_k" INTEGER NOT NULL DEFAULT 5,
    "evidence_used" INTEGER NOT NULL,
    "retrieval_latency_ms" DOUBLE PRECISION NOT NULL,
    "nli_latency_ms" DOUBLE PRECISION NOT NULL,
    "total_latency_ms" DOUBLE PRECISION NOT NULL,
    "requestId" TEXT NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "VerificationResult_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "EvidenceSource" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "url" TEXT,
    "description" TEXT,
    "license" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "EvidenceSource_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Evidence" (
    "id" TEXT NOT NULL,
    "document_id" TEXT NOT NULL,
    "text" TEXT NOT NULL,
    "page" TEXT,
    "line_id" INTEGER,
    "source_id" TEXT NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Evidence_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "RetrievalResult" (
    "id" TEXT NOT NULL,
    "verification_result_id" TEXT NOT NULL,
    "evidence_id" TEXT NOT NULL,
    "method" "RetrievalMethod" NOT NULL,
    "score" DOUBLE PRECISION NOT NULL,
    "rank" INTEGER NOT NULL,
    "bm25_score" DOUBLE PRECISION,
    "dense_score" DOUBLE PRECISION,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "RetrievalResult_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "NliPrediction" (
    "id" TEXT NOT NULL,
    "verification_result_id" TEXT NOT NULL,
    "evidence_id" TEXT NOT NULL,
    "label" "NliLabel" NOT NULL,
    "entailment_prob" DOUBLE PRECISION NOT NULL,
    "contradiction_prob" DOUBLE PRECISION NOT NULL,
    "neutral_prob" DOUBLE PRECISION NOT NULL,
    "rank" INTEGER NOT NULL,
    "is_top_evidence" BOOLEAN NOT NULL DEFAULT false,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "NliPrediction_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Experiment" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "description" TEXT NOT NULL,
    "mode" TEXT NOT NULL DEFAULT 'research',
    "dataset" TEXT NOT NULL,
    "metrics" JSONB NOT NULL,
    "results_path" TEXT NOT NULL,
    "model_version_id" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Experiment_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Feedback" (
    "id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "verification_result_id" TEXT,
    "rating" INTEGER NOT NULL,
    "comment" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Feedback_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "AuditLog" (
    "id" TEXT NOT NULL,
    "user_id" TEXT,
    "action" TEXT NOT NULL,
    "resource_type" TEXT NOT NULL,
    "resource_id" TEXT,
    "ip_address" TEXT,
    "user_agent" TEXT,
    "status_code" INTEGER NOT NULL,
    "latency_ms" DOUBLE PRECISION,
    "metadata" JSONB,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "AuditLog_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "User_email_key" ON "User"("email");

-- CreateIndex
CREATE INDEX "User_created_at_idx" ON "User"("created_at");

-- CreateIndex
CREATE INDEX "Claim_user_id_created_at_idx" ON "Claim"("user_id", "created_at");

-- CreateIndex
CREATE INDEX "Claim_text_idx" ON "Claim"("text");

-- CreateIndex
CREATE UNIQUE INDEX "Claim_user_id_text_key" ON "Claim"("user_id", "text");

-- CreateIndex
CREATE INDEX "ModelVersion_created_at_idx" ON "ModelVersion"("created_at");

-- CreateIndex
CREATE UNIQUE INDEX "ModelVersion_name_version_config_hash_key" ON "ModelVersion"("name", "version", "config_hash");

-- CreateIndex
CREATE UNIQUE INDEX "VerificationResult_requestId_key" ON "VerificationResult"("requestId");

-- CreateIndex
CREATE INDEX "VerificationResult_claim_id_created_at_idx" ON "VerificationResult"("claim_id", "created_at");

-- CreateIndex
CREATE INDEX "VerificationResult_verdict_idx" ON "VerificationResult"("verdict");

-- CreateIndex
CREATE INDEX "VerificationResult_model_version_id_idx" ON "VerificationResult"("model_version_id");

-- CreateIndex
CREATE INDEX "VerificationResult_created_at_idx" ON "VerificationResult"("created_at");

-- CreateIndex
CREATE UNIQUE INDEX "EvidenceSource_name_key" ON "EvidenceSource"("name");

-- CreateIndex
CREATE UNIQUE INDEX "Evidence_document_id_key" ON "Evidence"("document_id");

-- CreateIndex
CREATE INDEX "Evidence_page_idx" ON "Evidence"("page");

-- CreateIndex
CREATE INDEX "RetrievalResult_evidence_id_idx" ON "RetrievalResult"("evidence_id");

-- CreateIndex
CREATE UNIQUE INDEX "RetrievalResult_verification_result_id_evidence_id_key" ON "RetrievalResult"("verification_result_id", "evidence_id");

-- CreateIndex
CREATE INDEX "NliPrediction_evidence_id_idx" ON "NliPrediction"("evidence_id");

-- CreateIndex
CREATE INDEX "NliPrediction_label_idx" ON "NliPrediction"("label");

-- CreateIndex
CREATE UNIQUE INDEX "NliPrediction_verification_result_id_evidence_id_key" ON "NliPrediction"("verification_result_id", "evidence_id");

-- CreateIndex
CREATE UNIQUE INDEX "Experiment_name_key" ON "Experiment"("name");

-- CreateIndex
CREATE INDEX "Experiment_created_at_idx" ON "Experiment"("created_at");

-- CreateIndex
CREATE INDEX "Feedback_user_id_created_at_idx" ON "Feedback"("user_id", "created_at");

-- CreateIndex
CREATE INDEX "Feedback_verification_result_id_idx" ON "Feedback"("verification_result_id");

-- CreateIndex
CREATE INDEX "AuditLog_user_id_created_at_idx" ON "AuditLog"("user_id", "created_at");

-- CreateIndex
CREATE INDEX "AuditLog_action_created_at_idx" ON "AuditLog"("action", "created_at");

-- AddForeignKey
ALTER TABLE "Claim" ADD CONSTRAINT "Claim_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "VerificationResult" ADD CONSTRAINT "VerificationResult_claim_id_fkey" FOREIGN KEY ("claim_id") REFERENCES "Claim"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "VerificationResult" ADD CONSTRAINT "VerificationResult_model_version_id_fkey" FOREIGN KEY ("model_version_id") REFERENCES "ModelVersion"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Evidence" ADD CONSTRAINT "Evidence_source_id_fkey" FOREIGN KEY ("source_id") REFERENCES "EvidenceSource"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "RetrievalResult" ADD CONSTRAINT "RetrievalResult_verification_result_id_fkey" FOREIGN KEY ("verification_result_id") REFERENCES "VerificationResult"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "RetrievalResult" ADD CONSTRAINT "RetrievalResult_evidence_id_fkey" FOREIGN KEY ("evidence_id") REFERENCES "Evidence"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "NliPrediction" ADD CONSTRAINT "NliPrediction_verification_result_id_fkey" FOREIGN KEY ("verification_result_id") REFERENCES "VerificationResult"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "NliPrediction" ADD CONSTRAINT "NliPrediction_evidence_id_fkey" FOREIGN KEY ("evidence_id") REFERENCES "Evidence"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Experiment" ADD CONSTRAINT "Experiment_model_version_id_fkey" FOREIGN KEY ("model_version_id") REFERENCES "ModelVersion"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Feedback" ADD CONSTRAINT "Feedback_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Feedback" ADD CONSTRAINT "Feedback_verification_result_id_fkey" FOREIGN KEY ("verification_result_id") REFERENCES "VerificationResult"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "AuditLog" ADD CONSTRAINT "AuditLog_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "User"("id") ON DELETE SET NULL ON UPDATE CASCADE;

