/**
 * Server-side client for the Python ML inference service.
 * The service key never reaches the browser: these helpers run only in
 * API routes (Node runtime).
 */

export interface MlEvidence {
  document_id: string;
  text: string;
  score: number;
  source?: string | null;
  source_url?: string | null;
  page?: string | null;
  line_id?: number | null;
  rank: number;
  bm25_score?: number | null;
  dense_score?: number | null;
  nli_label?: string | null;
}

export interface MlNliResult {
  document_id: string;
  label: "ENTAILMENT" | "CONTRADICTION" | "NEUTRAL";
  probabilities: Record<string, number>;
  is_top_evidence: boolean;
}

export interface MlModelMeta {
  model: string;
  version: string;
  embedding_model: string;
  retriever: string;
  nli_model: string;
  nli_backend: string;
  temperature: number;
  config_hash: string;
  timestamp?: string | null;
}

export interface MlVerifyResponse {
  claim: string;
  verdict: "SUPPORTED" | "REFUTED" | "NOT_ENOUGH_INFORMATION";
  confidence: number;
  uncertainty: number;
  retrieval: { method: string; top_k: number; latency_ms: number; n_documents_searched: number };
  evidence: MlEvidence[];
  nli: MlNliResult[];
  model: MlModelMeta;
  latency_ms: number;
  explanation?: Record<string, unknown> | null;
}

export interface MlRetrieveResponse {
  query: string;
  retrieval: { method: string; top_k: number; latency_ms: number; n_documents_searched: number };
  evidence: MlEvidence[];
  model: MlModelMeta;
}

export interface MlModelInfoResponse {
  service_version: string;
  pipeline: MlModelMeta;
  corpus_documents: number;
  metrics: Record<string, unknown>;
}

export interface MlHealthResponse {
  status: "ok" | "degraded" | "loading" | "error";
  nli_backend: string;
  retrieval_backend: string;
  corpus_loaded: boolean;
  corpus_documents: number;
  uptime_seconds: number;
  detail?: string | null;
}

export class MlServiceError extends Error {
  constructor(message: string, public status: number, public detail?: string) {
    super(message);
    this.name = "MlServiceError";
  }
}

function serviceKey(): string {
  const key = process.env.MODEL_SERVICE_KEY;
  if (!key) throw new MlServiceError("MODEL_SERVICE_KEY is not configured", 500);
  return key;
}

function baseUrl(): string {
  const url = process.env.ML_API_URL;
  if (!url) throw new MlServiceError("ML_API_URL is not configured", 500);
  return url.replace(/\/+$/, "");
}

async function mlFetch<T>(path: string, init: RequestInit, timeoutMs = 30_000): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${baseUrl()}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": serviceKey(),
        ...(init.headers ?? {}),
      },
      cache: "no-store",
    });
    if (!res.ok) {
      let detail = "";
      try {
        detail = (await res.json())?.detail ?? "";
      } catch {
        /* ignore */
      }
      throw new MlServiceError(
        `ML service error (${res.status})`,
        res.status >= 500 ? 502 : res.status,
        detail
      );
    }
    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof MlServiceError) throw err;
    if (err instanceof Error && err.name === "AbortError") {
      throw new MlServiceError("ML service request timed out", 504);
    }
    throw new MlServiceError("ML service unreachable", 502, err instanceof Error ? err.message : undefined);
  } finally {
    clearTimeout(timer);
  }
}

export function mlVerify(claim: string, topK?: number): Promise<MlVerifyResponse> {
  // 90s: the ML service scales to zero when idle; the first request may pay a
  // ~20-30s cold start before inference (~2-5s) runs.
  return mlFetch<MlVerifyResponse>(
    "/verify",
    {
      method: "POST",
      body: JSON.stringify({ claim, top_k: topK, return_evidence: true }),
    },
    90_000
  );
}

export function mlRetrieve(
  query: string,
  topK: number,
  method: "bm25" | "dense" | "hybrid"
): Promise<MlRetrieveResponse> {
  return mlFetch<MlRetrieveResponse>("/retrieve", {
    method: "POST",
    body: JSON.stringify({ query, top_k: topK, method }),
  });
}

export function mlModelInfo(): Promise<MlModelInfoResponse> {
  return mlFetch<MlModelInfoResponse>("/model-info", { method: "GET" });
}

export function mlHealth(timeoutMs = 5_000): Promise<MlHealthResponse> {
  return mlFetch<MlHealthResponse>("/health", { method: "GET" }, timeoutMs);
}
