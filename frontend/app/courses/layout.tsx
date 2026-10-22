import { AccountGate } from "@/components/AccountProvider";

export default function CourseLayout({ children }: { children: React.ReactNode }) {
  return <AccountGate destination="/courses">{children}</AccountGate>;
}
