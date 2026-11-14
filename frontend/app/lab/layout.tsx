import { AccountGate } from "@/components/AccountProvider";
export default function LabLayout({ children }: { children: React.ReactNode }) { return <AccountGate destination="/courses">{children}</AccountGate>; }
