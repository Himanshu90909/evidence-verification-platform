import type { Metadata } from "next";
import Navbar from "@/components/Navbar";
import "./globals.css";

export const metadata: Metadata = {
  title: "Evidence Verification Platform",
  description:
    "Hybrid retrieval + NLI claim verification over a FEVER-derived evidence corpus.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Navbar />
        <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
        <footer className="border-t border-slate-200 py-6 text-center text-xs text-slate-400">
          Evidence Verification Platform — research-grade claim verification. Evidence comes from a
          controlled FEVER/Wikipedia research corpus; uncertainty is always reported.
        </footer>
      </body>
    </html>
  );
}
