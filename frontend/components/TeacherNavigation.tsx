import Link from "next/link";

import { cx } from "@/components/ui";
import { PRODUCT_NAME } from "@/lib/brand";

/** Navigation shared by the course library, creation flow and course workspace. */
export function TeacherNavigation({ active }: { active: "courses" | "create" | null }) {
  const item = (selected: boolean, create = false) => cx(
    "teacher-nav__link",
    selected && "is-active",
    create && "teacher-nav__link--create",
  );

  return (
    <header className="teacher-nav mb-7 flex flex-wrap items-center justify-between gap-x-8 gap-y-3 border-b border-line">
      <Link href="/courses" className="flex min-h-14 items-center gap-3 text-ink" aria-label={`${PRODUCT_NAME} teacher home`}>
        <span className="flex size-8 items-center justify-center rounded-[9px] bg-ink text-[13px] font-bold tracking-[-0.08em] text-white">CW</span>
        <span className="text-[17px] font-bold tracking-[-0.045em]">{PRODUCT_NAME}</span>
      </Link>
      <nav aria-label="Teacher navigation" className="flex items-center gap-6">
        <Link href="/courses" className={item(active === "courses")} aria-current={active === "courses" ? "page" : undefined}>Your courses</Link>
        <Link href="/courses/new" className={item(active === "create", true)} aria-current={active === "create" ? "page" : undefined}>Create course</Link>
      </nav>
    </header>
  );
}
