"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

const LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/verify", label: "Verify Claim" },
  { href: "/evidence", label: "Evidence" },
  { href: "/history", label: "History" },
  { href: "/model", label: "Model" },
  { href: "/research", label: "Research" },
  { href: "/feedback", label: "Feedback" },
];

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<{ email: string } | null>(null);

  useEffect(() => {
    let active = true;
    fetch("/api/auth/me")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (active) setUser(d?.user ?? null);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [pathname]);

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
    setUser(null);
    router.push("/login");
    router.refresh();
  }

  return (
    <header className="border-b border-slate-200 bg-white">
      <nav className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
        <div className="flex items-center gap-6">
          <Link href="/" className="text-sm font-bold tracking-tight text-slate-900">
            Evidence Verification Platform
          </Link>
          <div className="hidden items-center gap-4 md:flex">
            {LINKS.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                className={`text-sm transition hover:text-slate-900 ${
                  pathname === l.href ? "font-semibold text-slate-900" : "text-slate-500"
                }`}
              >
                {l.label}
              </Link>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-3">
          {user ? (
            <>
              <span className="hidden text-xs text-slate-500 sm:block">{user.email}</span>
              <button onClick={logout} className="btn-secondary h-8 px-3 text-xs">
                Sign out
              </button>
            </>
          ) : (
            <>
              <Link href="/login" className="btn-secondary h-8 px-3 text-xs">
                Sign in
              </Link>
              <Link href="/register" className="btn-primary h-8 px-3 text-xs">
                Register
              </Link>
            </>
          )}
        </div>
      </nav>
      <div className="flex gap-4 overflow-x-auto border-t border-slate-100 px-4 py-2 md:hidden">
        {LINKS.map((l) => (
          <Link
            key={l.href}
            href={l.href}
            className={`whitespace-nowrap text-xs ${
              pathname === l.href ? "font-semibold text-slate-900" : "text-slate-500"
            }`}
          >
            {l.label}
          </Link>
        ))}
      </div>
    </header>
  );
}
