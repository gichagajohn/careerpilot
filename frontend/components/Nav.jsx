"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { logout } from "@/lib/api";

const LINKS = [
  { href: "/", label: "Dashboard", icon: "M3 12l9-9 9 9M5 10v10h5v-6h4v6h5V10" },
  { href: "/jobs", label: "Jobs", icon: "M21 13.255A23.93 23.93 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" },
  { href: "/scholarships", label: "Scholarships", icon: "M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.246 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" },
  { href: "/applications", label: "Applications", icon: "M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" },
  { href: "/documents", label: "Documents", icon: "M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" },
  { href: "/cv-builder", label: "CV Builder", icon: "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" },
  { href: "/cover-letters", label: "Cover Letters", icon: "M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" },
  { href: "/interviews", label: "Interviews", icon: "M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" },
  { href: "/profile", label: "Profile", icon: "M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" },
  { href: "/settings", label: "Settings", icon: "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" },
];

export default function Nav({ userEmail }) {
  const pathname = usePathname();
  return (
    <aside className="hidden md:flex md:flex-col md:w-60 md:shrink-0 bg-slate-900 text-slate-300 min-h-screen sticky top-0">
      <div className="px-5 py-5 border-b border-slate-800">
        <div className="text-white font-bold text-lg tracking-tight">CareerPilot<span className="text-brand-400"> AI</span></div>
        <div className="text-xs text-slate-400 mt-0.5">Career &amp; Scholarship Agent</div>
      </div>
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {LINKS.map((l) => {
          const active = pathname === l.href;
          return (
            <Link key={l.href} href={l.href}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${
                active ? "bg-slate-800 text-white" : "hover:bg-slate-800/60 hover:text-white"
              }`}>
              <svg className="h-4.5 w-4.5 h-5 w-5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d={l.icon} />
              </svg>
              {l.label}
            </Link>
          );
        })}
      </nav>
      <div className="px-4 py-4 border-t border-slate-800 text-xs">
        <div className="text-slate-400 truncate">{userEmail || "…"}</div>
        <button onClick={logout} className="mt-1 text-brand-400 hover:text-brand-300 cursor-pointer">
          Sign out
        </button>
      </div>
    </aside>
  );
}

export function MobileNav({ userEmail }) {
  return (
    <div className="md:hidden sticky top-0 z-20 bg-slate-900 text-white px-4 py-3 flex items-center justify-between">
      <div className="font-bold">CareerPilot<span className="text-brand-400"> AI</span></div>
      <div className="flex items-center gap-3 text-xs">
        <span className="text-slate-400 truncate max-w-[120px]">{userEmail || ""}</span>
        <button onClick={logout} className="text-brand-400 cursor-pointer">Sign out</button>
      </div>
    </div>
  );
}

export function MobileLinks() {
  const pathname = usePathname();
  return (
    <div className="md:hidden flex gap-2 px-4 py-2 overflow-x-auto border-b border-slate-200 bg-white">
      {LINKS.map((l) => {
        const active = pathname === l.href;
        return (
          <Link key={l.href} href={l.href}
            className={`whitespace-nowrap rounded-full px-3 py-1 text-xs font-medium ${
              active ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-600"}`}>
            {l.label}
          </Link>
        );
      })}
    </div>
  );
}
