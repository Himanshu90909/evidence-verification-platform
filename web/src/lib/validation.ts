import { z } from "zod";

export const registerSchema = z.object({
  name: z.string().min(1).max(80).optional(),
  email: z.string().email().max(254),
  password: z
    .string()
    .min(8, "Password must be at least 8 characters")
    .max(128, "Password too long"),
});

export const loginSchema = z.object({
  email: z.string().email().max(254),
  password: z.string().min(1).max(128),
});

export const verifySchema = z.object({
  claim: z
    .string()
    .trim()
    .min(3, "Claim must be at least 3 characters")
    .max(2000, "Claim must be at most 2000 characters"),
  topK: z.number().int().min(1).max(20).optional(),
});

export const evidenceSearchSchema = z.object({
  query: z.string().trim().min(2).max(2000),
  topK: z.number().int().min(1).max(50).default(10),
  method: z.enum(["bm25", "dense", "hybrid"]).default("hybrid"),
});

export const feedbackSchema = z.object({
  rating: z.number().int().min(1).max(5),
  comment: z.string().max(4000).optional(),
  verificationResultId: z.string().cuid().optional(),
});

export type RegisterInput = z.infer<typeof registerSchema>;
export type LoginInput = z.infer<typeof loginSchema>;
export type VerifyInput = z.infer<typeof verifySchema>;
export type FeedbackInput = z.infer<typeof feedbackSchema>;
