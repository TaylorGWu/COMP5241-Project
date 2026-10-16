import Link from "next/link";

import { cx } from "@/components/ui";

/** A small, persistent information scent for the teacher-only course area. */
export function TeacherNavigation({ active }: { active: "courses" | "create" }) {
  const item = (selected: boolean) => cx(
    "rounded-sm px-3 py-2 text-sm font-semibold transition-colors",
    selected ? "bg-blue-soft text-blue" : "text-body hover:bg-soft hover:text-ink",
  );

  return <header className="mb-9 flex flex-wrap items-center justify-between gap-4 border-b border-line pb-4">
    <Link href="/courses" className="text-[20px] font-bold tracking-[-0.04em] text-ink">PathPilot <span className="font-medium text-muted">/ Teacher</span></Link>
    <nav aria-label="Teacher course navigation" className="flex items-center gap-1">
      <Link href="/courses" className={item(active === "courses")}>Your courses</Link>
      <Link href="/courses/new" className={item(active === "create")}>Create course</Link>
    </nav>
  </header>;
}
