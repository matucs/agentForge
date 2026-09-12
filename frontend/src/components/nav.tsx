"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Overview" },
  { href: "/runs", label: "Runs" },
  { href: "/tasks", label: "Tasks" },
  { href: "/agents", label: "Agents" },
  { href: "/evaluations", label: "Evaluations" },
  { href: "/operations", label: "Operations" },
  { href: "/approvals", label: "Approvals" },
];

export function Nav() {
  const pathname = usePathname();

  return (
    <nav className="border-b border-slate-800 bg-slate-950/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center gap-1 overflow-x-auto px-4 py-3">
        <span className="mr-4 shrink-0 text-sm font-semibold tracking-tight text-slate-100">
          AgentForge
        </span>
        {LINKS.map((link) => {
          const active =
            link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`shrink-0 rounded-md px-3 py-1.5 text-sm transition-colors ${
                active
                  ? "bg-slate-800 text-slate-100"
                  : "text-slate-400 hover:bg-slate-900 hover:text-slate-200"
              }`}
            >
              {link.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
