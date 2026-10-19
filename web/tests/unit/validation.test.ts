import { describe, expect, it } from "vitest";
import { feedbackSchema, loginSchema, registerSchema, verifySchema } from "@/lib/validation";

describe("verifySchema", () => {
  it("accepts a valid claim", () => {
    expect(verifySchema.safeParse({ claim: "Paris is the capital of France." }).success).toBe(true);
  });
  it("rejects too-short claims", () => {
    expect(verifySchema.safeParse({ claim: "hi" }).success).toBe(false);
  });
  it("rejects over-long claims", () => {
    expect(verifySchema.safeParse({ claim: "x".repeat(2001) }).success).toBe(false);
  });
  it("rejects non-string claims", () => {
    expect(verifySchema.safeParse({ claim: 123456 }).success).toBe(false);
  });
  it("rejects out-of-range topK", () => {
    expect(verifySchema.safeParse({ claim: "A valid claim here.", topK: 21 }).success).toBe(false);
    expect(verifySchema.safeParse({ claim: "A valid claim here.", topK: 0 }).success).toBe(false);
  });
  it("accepts topK 1..20", () => {
    expect(verifySchema.safeParse({ claim: "A valid claim here.", topK: 5 }).success).toBe(true);
  });
});

describe("registerSchema", () => {
  it("requires a valid email and 8+ char password", () => {
    expect(registerSchema.safeParse({ email: "a@b.co", password: "longenough" }).success).toBe(true);
    expect(registerSchema.safeParse({ email: "not-an-email", password: "longenough" }).success).toBe(false);
    expect(registerSchema.safeParse({ email: "a@b.co", password: "short" }).success).toBe(false);
  });
});

describe("loginSchema", () => {
  it("requires non-empty email/password", () => {
    expect(loginSchema.safeParse({ email: "a@b.co", password: "x" }).success).toBe(true);
    expect(loginSchema.safeParse({ email: "", password: "x" }).success).toBe(false);
  });
});

describe("feedbackSchema", () => {
  it("accepts rating 1-5 with optional comment", () => {
    expect(feedbackSchema.safeParse({ rating: 4 }).success).toBe(true);
    expect(feedbackSchema.safeParse({ rating: 4, comment: "Great" }).success).toBe(true);
  });
  it("rejects out-of-range ratings", () => {
    expect(feedbackSchema.safeParse({ rating: 0 }).success).toBe(false);
    expect(feedbackSchema.safeParse({ rating: 6 }).success).toBe(false);
  });
});
