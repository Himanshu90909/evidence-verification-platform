import { describe, expect, it } from "vitest";
import bcrypt from "bcryptjs";
import { SignJWT, jwtVerify } from "jose";

const secret = new TextEncoder().encode("test-secret-at-least-16-chars");

describe("password hashing", () => {
  it("hashes and verifies passwords", async () => {
    const hash = await bcrypt.hash("s3curePassword", 4);
    expect(hash).not.toContain("s3curePassword");
    expect(await bcrypt.compare("s3curePassword", hash)).toBe(true);
    expect(await bcrypt.compare("wrongPassword", hash)).toBe(false);
  });
});

describe("JWT session tokens", () => {
  it("round-trips a session payload", async () => {
    const token = await new SignJWT({ id: "u1", email: "a@b.co", role: "USER" })
      .setProtectedHeader({ alg: "HS256" })
      .setSubject("u1")
      .setIssuedAt()
      .setExpirationTime("1h")
      .sign(secret);
    const { payload } = await jwtVerify(token, secret);
    expect(payload.id).toBe("u1");
    expect(payload.email).toBe("a@b.co");
  });
  it("rejects tampered tokens", async () => {
    const token = await new SignJWT({ id: "u1" }).setProtectedHeader({ alg: "HS256" }).sign(secret);
    const other = new TextEncoder().encode("different-secret-value");
    await expect(jwtVerify(token, other)).rejects.toThrow();
  });
  it("rejects expired tokens", async () => {
    const token = await new SignJWT({ id: "u1" })
      .setProtectedHeader({ alg: "HS256" })
      .setIssuedAt(Math.floor(Date.now() / 1000) - 7200)
      .setExpirationTime(Math.floor(Date.now() / 1000) - 3600)
      .sign(secret);
    await expect(jwtVerify(token, secret)).rejects.toThrow();
  });
});
