import { StudentPortal } from "@/components/portals/StudentPortal";
import { AccountGate } from "@/components/AccountProvider";
export default function Page() { return <AccountGate destination="/student"><StudentPortal /></AccountGate>; }
