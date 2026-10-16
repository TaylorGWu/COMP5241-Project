import Link from "next/link";

import { cx } from "@/components/ui";

/** Navigation shared by the course library, creation flow and course workspace. */
export function TeacherNavigation({ active }: { active: "courses" | "create" }) {
  const item = (selected: boolean) => cx(
    "inline-flex min-h-11 items-center border-b-2 px-1 text-sm font-semibold transition-colors",
    selected ? "border-blue text-ink" : "border-transparent text-body hover:text-ink",
  );

  return (
    <header className="mb-8 flex flex-wrap items-center justify-between gap-x-8 gap-y-3 border-b border-line">
      <Link href="/courses" className="flex min-h-14 items-center gap-3 text-ink" aria-label="PathPilot teacher home">
        <span className="flex size-8 items-center justify-center rounded-[9px] bg-ink text-[17px] font-black tracking-[-0.12em] text-white">P<span className="text-[#9bb9ff]">.</span></span>
        <span className="text-[17px] font-bold tracking-[-0.045em]">PathPilot</span>
        <span className="hidden h-5 w-px bg-line sm:block" aria-hidden />
        <span className="hidden text-[13px] font-medium text-body sm:block">Teacher workspace</span>
      </Link>
      <nav aria-label="Teacher navigation" className="flex items-center gap-6">
        <Link href="/courses" className={item(active === "courses")} aria-current={active === "courses" ? "page" : undefined}>Your courses</Link>
        <Link href="/courses/new" className={item(active === "create")} aria-current={active === "create" ? "page" : undefined}>Create course</Link>
      </nav>
    </header>
  );
}
