import { describe, expect, it } from "vitest";
import { rateLimit } from "@/lib/rate-limit";

describe("rateLimit", () => {
  it("allows up to the limit then blocks", () => {
    for (let i = 0; i < 3; i++) {
      expect(rateLimit("key-fill", 3, 1000).allowed).toBe(true);
    }
    const blocked = rateLimit("key-fill", 3, 1000);
    expect(blocked.allowed).toBe(false);
    expect(blocked.remaining).toBe(0);
  });

  it("tracks keys independently", () => {
    for (let i = 0; i < 3; i++) rateLimit("key-a", 3, 1000);
    expect(rateLimit("key-b", 3, 1000).allowed).toBe(true);
    expect(rateLimit("key-a", 3, 1000).allowed).toBe(false);
  });

  it("reports reset time when blocked", () => {
    expect(rateLimit("key-c", 1, 1000).allowed).toBe(true);
    const r2 = rateLimit("key-c", 1, 1000);
    expect(r2.allowed).toBe(false);
    expect(r2.resetInSeconds).toBeGreaterThan(0);
    expect(r2.resetInSeconds).toBeLessThanOrEqual(1);
  });

  it("expires the window over time", async () => {
    expect(rateLimit("key-d", 1, 30).allowed).toBe(true);
    expect(rateLimit("key-d", 1, 30).allowed).toBe(false);
    await new Promise((r) => setTimeout(r, 60));
    expect(rateLimit("key-d", 1, 30).allowed).toBe(true);
  });
});
